"""HTTP API and the single background worker. One job runs at a time, by design, for an 8 GB laptop."""
from __future__ import annotations
import json, mimetypes, shutil, threading, time, traceback
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from . import config, store, director, knowledge, providers, tts, scout, refs, gates, schemas, cli

app = FastAPI(title="Exposit Studio", version="0.1.0")
DIST = config.WEB / "dist"


# ------------------------------------------------------------------ worker
def run_job(job: dict) -> None:
    jid, pid = job["id"], job["production_id"]
    params = json.loads(job["params"] or "{}")
    ctx = director.Ctx(jid)
    kind = job["kind"]
    if kind == "pipeline":
        director.run_pipeline(pid, ctx, params.get("start", "research"), params.get("only", False))
    elif kind == "rebuild":
        director.run_pipeline(pid, ctx, "produce")
    elif kind == "propose_edit":
        director.propose_edit(pid, params["scene"], params["instruction"], ctx)
        ctx.say("Proposal ready", 1.0)
    elif kind == "scout":
        res = scout.run(ctx)
        ctx.say(f"Scout finished: {res['note']}", 1.0)
    elif kind == "reference":
        refs.analyse(params["ref"], ctx)
        ctx.say("Reference analysed", 1.0)
    else:
        raise RuntimeError(f"Unknown job kind {kind}")


def worker() -> None:
    while True:
        try:
            rows = store.q("SELECT * FROM jobs WHERE state='queued' ORDER BY created LIMIT 1")
            if not rows:
                time.sleep(0.7)
                continue
            job = rows[0]
            store.update_job(job["id"], state="running", started=time.time(), message="Starting")
            if providers.is_paid(store.get_settings()) and job["kind"] in ("pipeline", "propose_edit"):
                store.update_job(job["id"], paid=1)
            try:
                run_job(job)
                store.update_job(job["id"], state="done", finished=time.time(), progress=1.0)
            except Exception as e:
                store.job_log(job["id"], traceback.format_exc()[-1500:])
                store.update_job(job["id"], state="failed", finished=time.time(), message=str(e)[:300])
        except Exception:
            time.sleep(2)


@app.on_event("startup")
def startup() -> None:
    knowledge.seed()
    store.q("UPDATE jobs SET state='failed', message='Interrupted: the studio was closed while this job ran' WHERE state='running'")
    threading.Thread(target=worker, daemon=True, name="worker").start()
    scout.start_scheduler(lambda: store.add_job("scout"))


def need(pid: str) -> dict:
    p = store.get_production(pid)
    if not p:
        raise HTTPException(404, "Production not found")
    return p


def guard(fn):
    try:
        return fn()
    except (ValueError, KeyError, StopIteration) as e:
        raise HTTPException(400, str(e) or "Invalid request")
    except Exception as e:  # pydantic validation and similar
        raise HTTPException(400, str(e)[:400])


# ------------------------------------------------------------------ system
def memory() -> dict:
    try:
        import psutil
        vm = psutil.virtual_memory()
        return {"total_mb": int(vm.total / 1e6), "available_mb": int(vm.available / 1e6), "used_percent": vm.percent,
                "studio_mb": int(psutil.Process().memory_info().rss / 1e6), "cpu_percent": psutil.cpu_percent(interval=None), "cpus": psutil.cpu_count()}
    except Exception:
        return {}


@app.get("/api/health")
def health():
    ff = config.ffmpeg_exe()
    return {"ok": True, "version": app.version, "provider": providers.status(), "voice_engines": tts.engines(),
            "ffmpeg": bool(shutil.which(ff) or Path(ff).exists()), "memory": memory(),
            "render": {"width": config.WIDTH, "height": config.HEIGHT, "fps": config.FPS}, "treatments": schemas.TREATMENTS,
            "themes": list(director.engine.THEMES), "disk_free_gb": round(shutil.disk_usage(config.DATA).free / 1e9, 1)}


@app.get("/api/settings")
def get_settings():
    return {"settings": store.get_settings(), "provider": providers.status(), "voices": tts.voices(),
            "env": {k: bool(config.env(k)) for k in ("EXPOSIT_LLM_API_KEY", "EXPOSIT_GITHUB_TOKEN", "EXPOSIT_YOUTUBE_API_KEY")},
            "providers": [{"id": "bridge", "name": "Agent bridge (any coding agent, or you)", "paid": False},
                          {"id": "claude_cli", "name": "Claude Code command line (your plan)", "paid": False},
                          {"id": "openai", "name": "OpenAI-compatible endpoint (Ollama, LM Studio, hosted)", "paid": "depends on the address"},
                          {"id": "anthropic", "name": "Anthropic API", "paid": True}, {"id": "none", "name": "None", "paid": False}]}


@app.put("/api/settings")
async def put_settings(req: Request):
    patch = await req.json()
    cur = store.get_settings()
    merged = {**cur, **patch}
    if merged.get("caption_style", "phrase") not in ("phrase", "word"):
        raise HTTPException(400, "Caption style must be 'phrase' or 'word'.")
    if providers.is_paid(merged) and float(merged.get("budget_paid_usd") or 0) <= 0:
        raise HTTPException(400, "That provider is paid, and your budget for paid services is $0. Raise the budget first if you want to allow it.")
    return {"settings": store.set_settings(patch), "provider": providers.status()}


# ------------------------------------------------------------------ productions
def summary(p: dict) -> dict:
    pid = p["id"]
    man = store.read_json(pid, "export/manifest.json")
    return {**{k: p.get(k) for k in ("id", "title", "created", "updated", "stages", "final", "approved_at")}, "brief": p["brief"],
            "duration": man.get("duration") if man else None, "has_video": (store.pdir(pid) / "export" / "video.mp4").exists(),
            "jobs": [j for j in store.list_jobs(5, pid) if j["state"] in ("queued", "running")]}


@app.get("/api/productions")
def productions():
    return [summary(p) for p in store.list_productions()]


@app.post("/api/productions")
async def create_production(req: Request):
    b = await req.json()
    if not (b.get("topic") or "").strip():
        raise HTTPException(400, "Enter a topic.")
    s = store.get_settings()
    brief = {"title": (b.get("title") or b["topic"])[:90], "topic": b["topic"].strip(), "audience": b.get("audience", "decide"), "duration": int(b.get("duration", 60)),
             "format": b.get("format", "16:9"), "quality": b.get("quality", "1080p"), "fps": 30, "language": "en", "style": b.get("style", "decide"),
             "theme": b.get("theme", "premium-technical"), "voice": b.get("voice") or s["voice"], "voice_speed": float(b.get("voice_speed") or s["voice_speed"]),
             "review_mode": b.get("review_mode", s.get("default_review_mode", "final_only")), "budget_paid_usd": 0, "objective": b.get("objective", "")}
    if brief["theme"] != "auto" and brief["theme"] not in director.engine.design.TEMPLATES:
        raise HTTPException(400, f"Unknown template {brief['theme']}.")
    if brief["format"] not in ("16:9", "9:16"):
        raise HTTPException(400, "16:9 (landscape) and 9:16 (vertical, for Reels and Shorts) are implemented. 1:1 square is planned.")
    p = store.create_production(brief)
    job = store.add_job("pipeline", p["id"], {"start": "research"}) if b.get("start", True) else None
    return {"id": p["id"], "job": job}


@app.post("/api/productions/from-example")
async def from_example(req: Request):
    try:
        b = await req.json()
    except Exception:
        b = {}
    fmt = (b or {}).get("format", "16:9")
    if fmt not in ("16:9", "9:16"):
        raise HTTPException(400, "Format must be 16:9 or 9:16.")
    pid = guard(lambda: cli.create_from_example(fmt=fmt))
    job = store.add_job("pipeline", pid, {"start": "produce"})
    return {"id": pid, "job": job}


@app.get("/api/productions/{pid}")
def production(pid: str):
    p = need(pid)
    rj = lambda rel, d=None: store.read_json(pid, rel, d)
    script = rj("script/script.json")
    target = float(p["brief"].get("duration", 60))
    return {**summary(p), "overrides": p.get("overrides", {}), "history": p.get("history", []), "hpos": p.get("hpos", -1), "versions": p.get("versions", []),
            "facts": rj("research/facts.json"), "strategy": rj("strategy/strategy.json"), "script": script, "board": rj("storyboard/board.json"),
            "manifest": rj("export/manifest.json"), "gates": {g: rj(f"gates/{g}.json") for g in ("research", "strategy", "script", "storyboard", "final")},
            "engagement": gates.engagement(script, None, target) if script else None,
            "plan": director.plan(pid) if rj("storyboard/board.json") else None,
            "uploads": [f.name for f in (store.pdir(pid) / "uploads").glob("*")],
            "exports": [{"name": f.name, "size": f.stat().st_size} for f in sorted((store.pdir(pid) / "export").glob("*")) if (f.suffix in (".mp4", ".srt", ".vtt", ".md", ".zip") and f.name != "silent.mp4") or f.name == "cover.png"]
            + ([{"name": "strategy.md", "size": (store.pdir(pid) / "strategy" / "strategy.md").stat().st_size}] if (store.pdir(pid) / "strategy" / "strategy.md").exists() else []),
            "all_jobs": store.list_jobs(20, pid)}


@app.put("/api/productions/{pid}/brief")
async def put_brief(pid: str, req: Request):
    need(pid)
    b = await req.json()
    brief = store.read_json(pid, "brief.json", {})
    for k in ("quality", "theme", "voice", "voice_speed", "review_mode", "title", "format", "engine_version", "cover_headline"):
        if k in b:
            brief[k] = b[k]
    if brief.get("format", "16:9") not in ("16:9", "9:16"):
        raise HTTPException(400, "Format must be 16:9 or 9:16. 1:1 square is planned.")
    if brief.get("theme", "auto") != "auto" and brief.get("theme") not in director.engine.design.TEMPLATES:
        raise HTTPException(400, f"Unknown template {brief.get('theme')}.")
    if brief.get("quality") not in ("1080p", "720p", "540p"):
        raise HTTPException(400, "Quality must be 1080p, 720p or 540p. 4K is not offered on this hardware.")
    store.write_json(pid, "brief.json", brief)
    p = store.get_production(pid)
    p["brief"] = brief
    p["title"] = brief.get("title", p["title"])
    store.save_production(p)
    return {"brief": brief, "plan": director.plan(pid) if store.read_json(pid, "storyboard/board.json") else None}


@app.delete("/api/productions/{pid}")
def delete_production(pid: str):
    need(pid)
    if store.q("SELECT id FROM jobs WHERE production_id=? AND state='running'", (pid,)):
        raise HTTPException(409, "A job is running for this production. Wait for it to finish.")
    director.delete_production(pid)
    return {"ok": True}


@app.post("/api/productions/{pid}/run")
async def run(pid: str, req: Request):
    need(pid)
    b = await req.json()
    start = b.get("start", "research")
    if start not in director.ORDER:
        raise HTTPException(400, "Unknown stage")
    if store.q("SELECT id FROM jobs WHERE production_id=? AND state IN ('queued','running')", (pid,)):
        raise HTTPException(409, "This production already has a job queued or running.")
    return {"job": store.add_job("pipeline", pid, {"start": start, "only": bool(b.get("only"))})}


@app.post("/api/productions/{pid}/gates/{stage}/approve")
def approve(pid: str, stage: str):
    p = need(pid)
    if stage not in ("script", "storyboard") or p["stages"].get(stage, {}).get("state") not in ("awaiting_approval", "needs_you"):
        raise HTTPException(400, "That gate is not waiting for approval.")
    return {"job": director.approve_gate(pid, stage)}


@app.post("/api/productions/{pid}/final/approve")
def approve_final(pid: str):
    p = need(pid)
    if p.get("final") not in ("awaiting_approval", "checks_failed"):
        raise HTTPException(400, "There is no finished video waiting for approval.")
    director.approve_final(pid)
    return {"ok": True}


@app.post("/api/productions/{pid}/strategy/override")
async def override(pid: str, req: Request):
    need(pid)
    b = await req.json()
    guard(lambda: director.set_override(pid, b["key"], b["choice"]))
    return {"ok": True, "note": "Recorded as your preference. Later stages are marked stale; run them again from Script to apply it."}


@app.put("/api/productions/{pid}/script/{sid}")
async def put_script(pid: str, sid: str, req: Request):
    need(pid)
    b = await req.json()
    return guard(lambda: director.update_script(pid, sid, b["sentences"]))


@app.put("/api/productions/{pid}/scenes/{sid}")
async def put_scene(pid: str, sid: str, req: Request):
    need(pid)
    b = await req.json()
    return guard(lambda: director.update_scene(pid, sid, b.get("patch", {}), b.get("label", "")))


@app.post("/api/productions/{pid}/scenes/{sid}/instruct")
async def instruct(pid: str, sid: str, req: Request):
    need(pid)
    b = await req.json()
    st = providers.status()
    if not st["ready"]:
        raise HTTPException(400, "Natural-language edits need an AI provider. " + st["note"])
    return {"job": store.add_job("propose_edit", pid, {"scene": sid, "instruction": b.get("instruction", "")})}


@app.get("/api/productions/{pid}/scenes/{sid}/proposal")
def proposal(pid: str, sid: str):
    return store.read_json(pid, f"storyboard/proposal-{sid}.json") or {}


@app.post("/api/productions/{pid}/scenes/{sid}/proposal/apply")
def apply_proposal(pid: str, sid: str):
    pr = store.read_json(pid, f"storyboard/proposal-{sid}.json")
    if not pr:
        raise HTTPException(404, "No proposal")
    res = guard(lambda: director.update_scene(pid, sid, {k: pr["spec"].get(k) for k in director.EDITABLE if k in pr["spec"]}, f"Instruction: {pr['instruction'][:60]}"))
    (store.pdir(pid) / "storyboard" / f"proposal-{sid}.json").unlink(missing_ok=True)
    return res


@app.post("/api/productions/{pid}/scenes")
async def add_scene(pid: str, req: Request):
    """Insert one scene: {"after": "<scene id>", "script": {id, title, sentences}, "spec": {...}}."""
    need(pid)
    b = await req.json()
    return guard(lambda: director.insert_scene(pid, b["after"], b["script"], b["spec"]))


@app.post("/api/productions/{pid}/cover")
def regenerate_cover(pid: str):
    """Re-renders only export/cover.png, in the video's template and style (headline: brief.cover_headline or title)."""
    need(pid)
    out = guard(lambda: director.write_cover(pid, director.render_settings(pid), {}))
    return {"ok": True, "name": out.name, "size": out.stat().st_size}


@app.post("/api/productions/{pid}/reorder")
async def reorder(pid: str, req: Request):
    need(pid)
    b = await req.json()
    return guard(lambda: director.reorder(pid, b["ids"]))


@app.get("/api/productions/{pid}/plan")
def get_plan(pid: str):
    need(pid)
    return director.plan(pid)


@app.post("/api/productions/{pid}/rebuild")
def rebuild(pid: str):
    need(pid)
    if store.q("SELECT id FROM jobs WHERE production_id=? AND state IN ('queued','running')", (pid,)):
        raise HTTPException(409, "This production already has a job queued or running.")
    return {"job": store.add_job("rebuild", pid, {}), "plan": director.plan(pid)}


@app.post("/api/productions/{pid}/undo")
def undo(pid: str):
    return guard(lambda: director.undo_redo(pid, -1))


@app.post("/api/productions/{pid}/redo")
def redo(pid: str):
    return guard(lambda: director.undo_redo(pid, +1))


@app.post("/api/productions/{pid}/versions")
async def save_version(pid: str, req: Request):
    need(pid)
    b = await req.json()
    return director.save_version(pid, (b.get("label") or "Saved version")[:80])


@app.post("/api/productions/{pid}/versions/{vid}/restore")
def restore_version(pid: str, vid: str):
    return guard(lambda: director.restore_version(pid, vid))


@app.post("/api/productions/{pid}/uploads")
async def upload(pid: str, file: UploadFile = File(...)):
    need(pid)
    name = Path(file.filename or "file").name
    if Path(name).suffix.lower() not in (".txt", ".md", ".json", ".yaml", ".yml", ".csv"):
        raise HTTPException(400, "Research reads text files: .txt, .md, .json, .yaml, .csv. PDF reading is planned.")
    data = await file.read()
    if len(data) > 2_000_000:
        raise HTTPException(400, "File is larger than 2 MB.")
    (store.pdir(pid) / "uploads" / name).write_bytes(data)
    return {"ok": True, "name": name}


def _file(path: Path, download: str = ""):
    if not path.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(str(path), media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream", filename=download or None)


@app.get("/api/productions/{pid}/media/video")
def media_video(pid: str):
    return _file(store.pdir(pid) / "export" / "video.mp4")


@app.get("/api/productions/{pid}/media/clip/{sid}")
def media_clip(pid: str, sid: str):
    man = store.read_json(pid, "export/manifest.json", {"scenes": []})
    s = next((x for x in man["scenes"] if x["id"] == sid), None)
    if not s:
        raise HTTPException(404, "Scene not rendered yet")
    return _file(store.pdir(pid) / "clips" / f"{s['clip_hash']}.mp4")


@app.get("/api/productions/{pid}/media/still/{sid}")
def media_still(pid: str, sid: str):
    return _file(store.pdir(pid) / "storyboard" / f"{sid}.png")


@app.get("/api/productions/{pid}/media/audio/{sid}")
def media_audio(pid: str, sid: str):
    return _file(store.pdir(pid) / "audio" / f"{sid}.wav")


@app.get("/api/productions/{pid}/file/{name}")
def export_file(pid: str, name: str):
    name = Path(name).name
    d = store.pdir(pid)
    return _file(d / "strategy" / name if name == "strategy.md" else d / "export" / name, download=name)


# ------------------------------------------------------------------ jobs, bridge, voices
@app.get("/api/jobs")
def jobs(limit: int = 60):
    titles = {p["id"]: p["title"] for p in store.list_productions()}
    return {"jobs": [dict(j, title=titles.get(j["production_id"], "")) for j in store.list_jobs(limit)], "memory": memory()}


@app.get("/api/jobs/{jid}")
def job(jid: str):
    j = store.get_job(jid)
    if not j:
        raise HTTPException(404, "Job not found")
    return j


@app.post("/api/jobs/{jid}/cancel")
def cancel(jid: str):
    j = store.get_job(jid)
    if not j:
        raise HTTPException(404, "Job not found")
    if j["state"] != "queued":
        raise HTTPException(400, "Only queued jobs can be cancelled. A running job finishes its current step.")
    store.update_job(jid, state="cancelled", finished=time.time(), message="Cancelled")
    return {"ok": True}


@app.get("/api/bridge")
def bridge():
    out = []
    for f in sorted((providers.bridge_dir() / "tasks").glob("*.json")):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return out


@app.post("/api/bridge/{tid}")
async def bridge_answer(tid: str, req: Request):
    b = await req.json()
    text = b.get("text", "")
    guard(lambda: json.loads(text) if text.strip().startswith(("{", "[")) else None)
    providers.bridge_submit(tid, text)
    return {"ok": True}


@app.get("/api/voices")
def voices():
    return {"engines": tts.engines(), "voices": tts.voices()}


@app.post("/api/voices/preview")
async def voice_preview(req: Request):
    b = await req.json()
    if store.q("SELECT id FROM jobs WHERE state='running'"):
        raise HTTPException(409, "A job is running. Preview the voice when it has finished, to keep memory low.")
    out = config.DATA / "cache" / "preview.wav"
    guard(lambda: tts.narrate_scene([b.get("text") or "This is how your narration will sound."], out, b.get("voice", "am_michael"), float(b.get("speed", 1.0))))
    tts.unload()
    return _file(out)


# ------------------------------------------------------------------ library, registry
@app.get("/api/knowledge")
def get_knowledge():
    its = knowledge.items()
    return {"items": its, "categories": sorted({i["category"] for i in its}), "tiers": knowledge.TIERS}


@app.post("/api/knowledge")
async def add_knowledge(req: Request):
    b = await req.json()
    if not b.get("title") or not b.get("body"):
        raise HTTPException(400, "A title and a body are required.")
    if b.get("tier") == "verified" and not b.get("source"):
        raise HTTPException(400, "A verified item needs a source: the measurement it rests on.")
    b.setdefault("date", time.strftime("%Y-%m-%d"))
    b.pop("id", None)
    return knowledge.add_item(b)


@app.put("/api/knowledge/{kid}")
async def put_knowledge(kid: str, req: Request):
    rows = [i for i in knowledge.items() if i["id"] == kid]
    if not rows:
        raise HTTPException(404, "Item not found")
    b = await req.json()
    return knowledge.add_item({**rows[0], **b, "id": kid})


@app.delete("/api/knowledge/{kid}")
def del_knowledge(kid: str):
    store.q("DELETE FROM knowledge WHERE id=?", (kid,))
    return {"ok": True}


TOOL_STATUSES = ["discovered", "evaluated", "approved for trial", "adopted", "optional", "watching", "rejected"]


@app.get("/api/registry")
def registry():
    return {"tools": knowledge.tools(), "statuses": TOOL_STATUSES}


@app.post("/api/registry/{tid}/status")
async def registry_status(tid: str, req: Request):
    b = await req.json()
    if b.get("status") not in TOOL_STATUSES:
        raise HTTPException(400, "Unknown status. A tool can be recorded as: " + ", ".join(TOOL_STATUSES) + ".")
    knowledge.set_tool_status(tid, b["status"])
    return {"ok": True, "note": "Status recorded. Exposit never installs or runs a tool for you."}


# ------------------------------------------------------------------ scout
@app.get("/api/scout")
def get_scout():
    return {"items": scout.items(300), "runs": scout.runs(), "summary": scout.weekly_summary(), "access": scout.ACCESS,
            "settings": {k: v for k, v in store.get_settings().items() if k.startswith("scout_")}}


@app.post("/api/scout/run")
def scout_run():
    if store.q("SELECT id FROM jobs WHERE kind='scout' AND state IN ('queued','running')"):
        raise HTTPException(409, "A Scout run is already queued or running.")
    return {"job": store.add_job("scout")}


# ------------------------------------------------------------------ references
@app.get("/api/references")
def references():
    return {"references": refs.all_refs(), "unsupported": refs.UNSUPPORTED}


@app.post("/api/references")
async def add_reference(title: str = Form(""), transcript: str = Form(""), url: str = Form(""), file: UploadFile | None = File(None)):
    content, name = b"", ""
    if file is not None and file.filename:
        name = Path(file.filename).name
        ext = Path(name).suffix.lower()
        if ext not in refs.VIDEO + refs.IMAGE + (".txt", ".md"):
            raise HTTPException(400, "Upload a video (mp4, mov, mkv, webm), an image, or a text transcript.")
        content = await file.read()
        if len(content) > 600_000_000:
            raise HTTPException(400, "File is larger than 600 MB.")
    if not (name or transcript.strip() or url.strip()):
        raise HTTPException(400, "Add a file, a transcript or a web address.")
    r = refs.create(title, name, content, transcript, url)
    return {"id": r["id"], "job": store.add_job("reference", "", {"ref": r["id"]})}


@app.get("/api/references/{rid}")
def reference(rid: str):
    r = refs.get(rid)
    if not r:
        raise HTTPException(404, "Reference not found")
    return r


@app.get("/api/references/{rid}/frames/{name}")
def reference_frame(rid: str, name: str):
    return _file(refs.rdir(rid) / "frames" / Path(name).name)


@app.post("/api/references/{rid}/to-library")
def reference_to_library(rid: str):
    r = refs.get(rid)
    if not r or not r.get("analysis"):
        raise HTTPException(400, "Analyse the reference first.")
    return {"created": refs.to_library(rid)}


@app.delete("/api/references/{rid}")
def reference_delete(rid: str):
    refs.delete(rid)
    return {"ok": True}


# ------------------------------------------------------------------ web interface
@app.exception_handler(404)
async def spa(request: Request, exc):
    if request.url.path.startswith("/api") or not (DIST / "index.html").exists():
        return JSONResponse({"detail": getattr(exc, "detail", "Not found")}, status_code=404)
    f = (DIST / request.url.path.lstrip("/")).resolve()
    if f.is_file() and DIST.resolve() in f.parents:      # built assets and fonts
        return FileResponse(str(f))
    if "." in request.url.path.rsplit("/", 1)[-1]:        # a missing file is a 404, not the app shell
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return FileResponse(str(DIST / "index.html"))


@app.get("/")
def index():
    if (DIST / "index.html").exists():
        return FileResponse(str(DIST / "index.html"))
    return JSONResponse({"detail": "The web interface has not been built. Run: cd web; npm install; npm run build"}, status_code=503)
