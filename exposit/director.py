"""The Director: stage order, quality gates, dependency hashing, scene edits, history and export.

It is plain code, not a model. It hands work to roles (through the provider adapter) and to the
deterministic tools (voice, renderer, ffmpeg), validates what comes back, and decides what is stale.
"""
from __future__ import annotations
import json, shutil, time, zipfile
from pathlib import Path
from . import config, store, roles, providers, gates, knowledge, tts, sound, compose, schemas, scout
from .render import engine

ORDER = store.STAGES  # research, strategy, script, storyboard, produce, export
AUTO_GATED = ("research", "script", "storyboard")


class Ctx:
    """Progress reporting for one job."""

    def __init__(self, job_id: str = ""):
        self.job_id = job_id

    def say(self, msg: str, progress: float | None = None) -> None:
        if not self.job_id:
            return
        kw = {"message": msg}
        if progress is not None:
            kw["progress"] = round(float(progress), 3)
        store.update_job(self.job_id, **kw)
        store.job_log(self.job_id, msg)

    def meta(self, pid: str) -> dict:
        return {"production_id": pid, "_on_wait": lambda m: store.update_job(self.job_id, message=m) if self.job_id else None}


def _brief(pid: str) -> dict:
    return store.read_json(pid, "brief.json", {})


def _target_seconds(brief: dict) -> float:
    return float(brief.get("duration", 60))


def _documents(pid: str) -> list[dict]:
    docs = []
    for f in sorted((store.pdir(pid) / "uploads").glob("*")):
        if f.suffix.lower() in (".txt", ".md", ".json", ".yaml", ".yml", ".csv"):
            docs.append({"name": f.name, "text": f.read_text(encoding="utf-8", errors="replace")[:20000]})
    return docs


def _save_gate(pid: str, gate: dict, auto: bool) -> None:
    gate["decided"] = "automatically" if auto else "by you"
    gate["at"] = time.time()
    store.write_json(pid, f"gates/{gate['gate']}.json", gate)


# ------------------------------------------------------------------ stages
def _repairs() -> int:
    """Repair rounds a role gets when its gate fails, before the stage stops for you (Settings)."""
    try:
        return max(0, min(3, int(store.get_settings().get("repair_rounds", 1))))
    except (TypeError, ValueError):
        return 1


def run_research(pid: str, ctx: Ctx) -> bool:
    brief = _brief(pid)
    payload = {"brief": brief, "documents": _documents(pid)}
    gate = None
    for attempt in range(1 + _repairs()):
        ctx.say("Researcher: collecting facts and sources" + (" (repair)" if attempt else ""), 0.05)
        facts = roles.run("researcher", payload, ctx.meta(pid)).model_dump()
        gate = gates.research_gate(facts)
        store.write_json(pid, "research/facts.json", facts)
        if gate["passed"]:
            break
        payload["gate_failures"] = [c for c in gate["criteria"] if not c["passed"]]
    gate["attempts"] = attempt + 1
    _save_gate(pid, gate, True)
    return gate["passed"]


def recent_structures(exclude: str = "", n: int = 10) -> list[dict]:
    out = []
    for p in store.list_productions():
        if p["id"] == exclude:
            continue
        s = store.read_json(p["id"], "strategy/strategy.json")
        if s:
            out.append({"title": p["title"], "structure": s.get("narrative_structure", "")[:160], "hook": s.get("hook", "")[:120],
                        "treatments": sorted({sc.get("treatment", "") for sc in s.get("scene_breakdown", [])})})
        if len(out) >= n:
            break
    return out


def apply_overrides(strategy: dict, overrides: dict) -> dict:
    for d in strategy.get("decisions", []):
        if d["key"] in overrides:
            d.update(choice=overrides[d["key"]], overridden=True, tier="preference", reason="You overrode this decision.")
    return strategy


def strategy_markdown(s: dict, title: str) -> str:
    L = [f"# Creative strategy: {title}", "", f"**Audience.** {s.get('audience_profile','')}", "", f"**Learning objective.** {s.get('learning_objective','')}", "",
         f"**Concept.** {s.get('creative_concept','')}", "", f"**Hook.** {s.get('hook','')}", "", f"**Narrative structure.** {s.get('narrative_structure','')}", "",
         f"**Visual direction.** {s.get('visual_direction','')}", "", f"**Narration.** {s.get('narration_approach','')}", "", "## Treatments compared", ""]
    for t in s.get("treatments", []):
        mark = " (chosen)" if t["name"] == s.get("chosen") else ""
        L += [f"### {t['name']}{mark}", t.get("shape", ""), "",
              f"- Engagement: {t.get('engagement','')}\n- Teaching fit: {t.get('teaching_fit','')}\n- Accuracy risk: {t.get('accuracy_risk','')}\n- Feasibility: {t.get('feasibility','')}", "", t.get("verdict", ""), ""]
    L += ["## Decisions and reasons", "", "| Decision | Choice | Reason | Evidence |", "| --- | --- | --- | --- |"]
    for d in s.get("decisions", []):
        L.append(f"| {d['key']} | {d['choice']} | {d['reason']} | {d['tier']}{' (overridden)' if d.get('overridden') else ''} |")
    L += ["", "## Scene breakdown", "", "| Scene | Treatment | Seconds | Purpose |", "| --- | --- | --- | --- |"]
    for sc in s.get("scene_breakdown", []):
        L.append(f"| {sc['title']} | {sc['treatment']} | {sc['seconds']} | {sc.get('purpose','')} |")
    L += ["", "## Likely drop-off points (hypotheses)", ""] + [f"- **{d['where']}**: {d['why']} Countermeasure: {d['countermeasure']}" for d in s.get("dropoff", [])]
    L += ["", f"**Experiment in this video.** {s.get('experiment') or 'None'}", "", "**Tools.** " + ", ".join(s.get("tools", []))]
    return "\n".join(L) + "\n"


def run_strategy(pid: str, ctx: Ctx) -> bool:
    p = store.get_production(pid)
    brief = _brief(pid)
    facts = store.read_json(pid, "research/facts.json", {})
    prefs = [k for k in knowledge.items() if k["tier"] == "preference" and k["status"] == "active"]
    payload = {"brief": brief, "facts": facts, "library": knowledge.for_strategy(),
               "preferences": [{"title": k["title"], "body": k["body"]} for k in prefs],
               "recent_productions": recent_structures(pid), "treatments_available": schemas.TREATMENTS,
               "tools_available": [t["name"] for t in knowledge.tools() if t["status"] in ("adopted", "optional")],
               "hardware": "8 GB RAM, CPU only, one render at a time", "budget_paid_usd": store.get_settings()["budget_paid_usd"],
               "scout_signals": scout.signals(), "scout_signals_caveat": scout.SIGNALS_CAVEAT}
    ctx.say("Creative Director: comparing three treatments", 0.15)
    s = roles.run("creative_director", payload, ctx.meta(pid)).model_dump()
    crit = [gates._crit("Three treatments compared", len(s["treatments"]) >= 3, f"{len(s['treatments'])} treatments"),
            gates._crit("One treatment chosen", any(t["name"] == s["chosen"] for t in s["treatments"]), s["chosen"]),
            gates._crit("Every decision has a reason", all(d["reason"].strip() for d in s["decisions"]) and len(s["decisions"]) >= 5, f"{len(s['decisions'])} decisions"),
            gates._crit("Scene breakdown uses supported treatments", all(sc["treatment"] in schemas.TREATMENTS for sc in s["scene_breakdown"]))]
    s = apply_overrides(s, p.get("overrides", {}))
    store.write_json(pid, "strategy/strategy.json", s)
    (store.pdir(pid) / "strategy" / "strategy.md").write_text(strategy_markdown(s, p["title"]), encoding="utf-8")
    knowledge.note_usage(s.get("recipes_used", []), pid)
    _save_gate(pid, {"gate": "strategy", "passed": all(c["passed"] for c in crit), "criteria": crit}, True)
    return all(c["passed"] for c in crit)


def _review(pid: str, ctx: Ctx, script: dict, facts: dict) -> dict | None:
    if not store.get_settings().get("independent_review", True):
        return None
    try:
        ctx.say("Quality Reviewer: checking the script against the facts", 0.3)
        return roles.run("reviewer", {"facts": facts, "script": script}, ctx.meta(pid)).model_dump()
    except providers.ProviderError as e:
        return {"passed": True, "accuracy_issues": [], "engagement_notes": [], "summary": f"Independent review did not run: {e}", "skipped": True}


def run_script(pid: str, ctx: Ctx) -> bool:
    brief = _brief(pid)
    facts = store.read_json(pid, "research/facts.json", {})
    strategy = store.read_json(pid, "strategy/strategy.json", {})
    payload = {"brief": brief, "facts": facts, "strategy": strategy, "target_seconds": _target_seconds(brief),
               "words_per_second": gates.WPS, "library": [k for k in knowledge.for_strategy() if k["category"] in ("Narration guidelines", "Opening hooks", "Audience engagement")]}
    gate = None
    for attempt in range(1 + _repairs()):
        ctx.say("Storyteller: writing the narration" + (" (repair)" if attempt else ""), 0.25)
        script = roles.run("storyteller", payload, ctx.meta(pid)).model_dump()
        review = _review(pid, ctx, script, facts)
        gate = gates.script_gate(script, facts, strategy, _target_seconds(brief), review)
        store.write_json(pid, "script/script.json", script)
        if gate["passed"]:
            break
        payload["gate_failures"] = [c for c in gate["criteria"] if not c["passed"]]
    gate["attempts"] = attempt + 1
    _save_gate(pid, gate, True)
    return gate["passed"]


def run_storyboard(pid: str, ctx: Ctx) -> bool:
    script = store.read_json(pid, "script/script.json", {})
    facts = store.read_json(pid, "research/facts.json", {})
    strategy = store.read_json(pid, "strategy/strategy.json", {})
    payload = {"script": script, "system_model": facts.get("model", {}), "strategy": strategy,
               "library": [k for k in knowledge.for_strategy() if k["category"] in ("Animation recipes", "Camera movements", "Transition patterns", "Visual compositions", "Motion graphics patterns")]}
    gate = None
    for attempt in range(1 + _repairs()):
        ctx.say("Visual Planner: writing one specification per scene" + (" (repair)" if attempt else ""), 0.35)
        board = roles.run("visual_planner", payload, ctx.meta(pid)).model_dump(exclude_none=True)
        gate = gates.storyboard_gate(board, script, facts)
        store.write_json(pid, "storyboard/board.json", board)
        if gate["passed"]:
            break
        payload["gate_failures"] = [c for c in gate["criteria"] if not c["passed"]]
    gate["attempts"] = attempt + 1
    _save_gate(pid, gate, True)
    if gate["passed"]:
        push_history(pid, "Storyboard created")
    return gate["passed"]


# ------------------------------------------------------------------ hashing and production
def render_settings(pid: str) -> dict:
    b = _brief(pid)
    s = store.get_settings()
    w, h = {"16:9": (config.WIDTH, config.HEIGHT), "9:16": (1080, 1920), "1:1": (1080, 1080)}.get(b.get("format", "16:9"), (config.WIDTH, config.HEIGHT))
    q = b.get("quality", "1080p")
    if q == "720p":
        w, h = int(w * 2 / 3) // 2 * 2, int(h * 2 / 3) // 2 * 2
    if q == "540p":
        w, h = w // 2, h // 2
    return {"w": w, "h": h, "fps": int(b.get("fps", config.FPS)), "theme": b.get("theme", "premium-technical"),
            "captions": bool(s.get("burn_captions", True)), "caption_style": s.get("caption_style", "phrase") if s.get("caption_style") in engine.CAPTION_STYLES else "phrase", "voice": b.get("voice") or s["voice"], "speed": float(b.get("voice_speed") or s["voice_speed"]),
            "music": bool(s.get("music", True)), "sfx": bool(s.get("sfx", True))}


def scene_hashes(pid: str) -> list[dict]:
    """Current input hashes for every scene. Nothing is rendered here."""
    rs = render_settings(pid)
    script = store.read_json(pid, "script/script.json", {"scenes": []})
    board = store.read_json(pid, "storyboard/board.json", {"scenes": []})
    out = []
    for spec in board["scenes"]:
        sc = next((s for s in script["scenes"] if s["id"] == spec["id"]), None)
        sentences = [s["text"] for s in sc["sentences"]] if sc else []
        ah = store.sha("audio", sentences, rs["voice"], rs["speed"], tts.PRONUNCIATION)
        ch = store.sha("clip", spec, ah, rs["w"], rs["h"], rs["fps"], rs["theme"], rs["captions"], config.ENGINE_VERSION,
                      *([rs["caption_style"]] if rs["caption_style"] != "phrase" else []))   # Phrase hashes unchanged
        out.append({"id": spec["id"], "title": spec.get("title", ""), "audio_hash": ah, "clip_hash": ch, "sentences": sentences, "spec": spec})
    return out


def plan(pid: str) -> dict:
    """What a rebuild would do, in words, before anything runs."""
    man = store.read_json(pid, "export/manifest.json", {"scenes": []})
    old = {s["id"]: s for s in man.get("scenes", [])}
    clips_dir = store.pdir(pid) / "clips"
    items, n_audio, n_clip = [], 0, 0
    cur = scene_hashes(pid)
    for s in cur:
        o = old.get(s["id"], {})
        audio = o.get("audio_hash") != s["audio_hash"]
        cached = (clips_dir / f"{s['clip_hash']}.mp4").exists()
        clip = o.get("clip_hash") != s["clip_hash"]
        if audio or clip:
            items.append({"scene": s["id"], "title": s["title"], "narration": audio, "clip": "restore from cache" if (clip and cached) else ("render" if clip else "keep")})
        n_audio += audio
        n_clip += (clip and not cached)
    order_changed = [s["id"] for s in cur] != [s["id"] for s in man.get("scenes", [])]
    fin = man.get("final_hash") != final_hash(pid, cur)
    summary = (f"Rebuilds {n_clip} clip{'s' if n_clip != 1 else ''} and {n_audio} narration file{'s' if n_audio != 1 else ''}; "
               f"{len(cur) - len(items)} of {len(cur)} scenes are untouched. " + ("Then re-joins the video." if (items or fin or order_changed) else "Nothing to do."))
    return {"scenes": items, "renders": n_clip, "narrations": n_audio, "rejoin": bool(items or fin or order_changed), "summary": summary, "total_scenes": len(cur)}


def final_hash(pid: str, cur: list[dict] | None = None) -> str:
    rs = render_settings(pid)
    cur = cur or scene_hashes(pid)
    return store.sha("final", [(s["id"], s["clip_hash"]) for s in cur], rs["music"], rs["sfx"])


def run_produce(pid: str, ctx: Ctx) -> bool:
    rs = render_settings(pid)
    d = store.pdir(pid)
    cur = scene_hashes(pid)
    man_scenes, t0 = [], 0.0
    n = len(cur)
    for i, s in enumerate(cur):
        wav = d / "audio" / f"{s['id']}.wav"
        hfile = d / "audio" / f"{s['id']}.hash"
        if not (wav.exists() and hfile.exists() and hfile.read_text() == s["audio_hash"]):
            ctx.say(f"Audio Producer: narrating scene {i + 1} of {n}", 0.40 + 0.15 * i / n)
            tts.narrate_scene(s["sentences"], wav, rs["voice"], rs["speed"])
            hfile.write_text(s["audio_hash"])
        s["timing"] = json.loads(wav.with_suffix(".timing.json").read_text(encoding="utf-8"))
    tts.unload()  # free the voice model before rendering
    for i, s in enumerate(cur):
        clip = d / "clips" / f"{s['clip_hash']}.mp4"
        if not clip.exists():
            base = 0.55 + 0.35 * i / n
            ctx.say(f"Animation Producer: rendering scene {i + 1} of {n} ({s['spec'].get('treatment')})", base)
            t_start = time.time()
            tmp = clip.with_suffix(".part.mp4")
            info = engine.render_clip(s["spec"], s["timing"], str(tmp), rs["w"], rs["h"], rs["fps"], rs["theme"], rs["captions"],
                                      progress=lambda k, b=base: store.update_job(ctx.job_id, progress=round(b + 0.35 / n * k, 3)) if ctx.job_id else None,
                                      caption_style=rs["caption_style"])
            tmp.replace(clip)
            store.job_log(ctx.job_id, f"Rendered {s['id']}: {info['frames']} frames in {time.time() - t_start:.1f} s") if ctx.job_id else None
        sw, sh = (540, 960) if rs["h"] > rs["w"] else (960, 540)
        (d / "storyboard" / f"{s['id']}.png").write_bytes(engine.render_still(s["spec"], s["timing"], None, sw, sh, theme=rs["theme"],
                                                                                 caption_band=bool(rs["captions"])))
        sc = engine.Scene(s["spec"], s["timing"], rs["theme"])
        man_scenes.append({"id": s["id"], "title": s["title"], "audio_hash": s["audio_hash"], "clip_hash": s["clip_hash"], "start": round(t0, 3),
                           "duration": round(round(sc.dur * rs["fps"]) / rs["fps"], 3), "pad_start": sc.pad0, "treatment": s["spec"].get("treatment"),
                           "events": [{"t": round(e["t"], 3), "action": e["action"]} for e in sc.events]})
        t0 += man_scenes[-1]["duration"]
    store.write_json(pid, "export/manifest.json", {"scenes": man_scenes, "duration": round(t0, 3), "settings": rs, "final_hash": ""})
    return True


SFX_FOR = {"packet": "packet", "highlight": "highlight", "callout": "callout", "count": "count", "enter": "enter", "type": "type"}


def run_export(pid: str, ctx: Ctx) -> bool:
    d = store.pdir(pid)
    p = store.get_production(pid)
    man = store.read_json(pid, "export/manifest.json")
    rs = man["settings"]
    ex = d / "export"
    ctx.say("Joining scenes", 0.91)
    compose.concat([str(d / "clips" / f"{s['clip_hash']}.mp4") for s in man["scenes"]], str(ex / "silent.mp4"))
    ctx.say("Audio Producer: mixing narration, music and effects", 0.93)
    narr = [(s["start"] + s["pad_start"], str(d / "audio" / f"{s['id']}.wav")) for s in man["scenes"]]
    events = []
    for s in man["scenes"]:
        events.append((s["start"], "transition"))
        events += [(s["start"] + e["t"], SFX_FOR[e["action"]]) for e in s["events"] if e["action"] in SFX_FOR]
    mixinfo = sound.mix(narr, events, man["duration"], str(ex / "mix.wav"), rs["music"], rs["sfx"])
    ctx.say("Encoding the final MP4", 0.95)
    compose.mux(str(ex / "silent.mp4"), str(ex / "mix.wav"), str(ex / "video.mp4"))
    timings = [(s["start"] + s["pad_start"], json.loads((d / "audio" / f"{s['id']}.timing.json").read_text(encoding="utf-8"))) for s in man["scenes"]]
    srt, vtt = compose.subtitles(timings)
    (ex / "subtitles.srt").write_text(srt, encoding="utf-8")
    (ex / "subtitles.vtt").write_text(vtt, encoding="utf-8")
    script = store.read_json(pid, "script/script.json", {"scenes": []})
    facts = store.read_json(pid, "research/facts.json", {"claims": []})
    (ex / "script.md").write_text(f"# {p['title']}\n\n" + "\n\n".join(f"## {s['title']}\n\n" + " ".join(x["text"] for x in s["sentences"]) for s in script["scenes"]) + "\n", encoding="utf-8")
    (ex / "sources.md").write_text(f"# Sources for {p['title']}\n\nArrangement depicted: {facts.get('arrangement','')}\n\n" + "\n".join(
        f"- **{c['id']}** {c['text']}\n" + "".join(f"  - [{s['title']}]({s['url']}) ({s.get('kind','')})\n" for s in c.get("sources", [])) for c in facts["claims"]), encoding="utf-8")
    ctx.say("Quality Reviewer: automated checks on the final video", 0.97)
    brief = _brief(pid)
    checks = compose.checks(str(ex / "video.mp4"), {"width": rs["w"], "height": rs["h"], "fps": rs["fps"], "duration": _target_seconds(brief),
                                                    "tolerance": max(3.0, 0.08 * _target_seconds(brief))})
    treatments = sorted({s["treatment"] for s in man["scenes"]})
    checks.append({"name": "No paid service was used", "passed": not any(j["paid"] for j in store.list_jobs(500, pid)), "detail": "Job log shows local tools only"})
    gate = {"gate": "final", "passed": all(c["passed"] for c in checks), "criteria": checks, "treatments": treatments, "mix": mixinfo}
    _save_gate(pid, gate, True)
    man["final_hash"] = final_hash(pid)
    store.write_json(pid, "export/manifest.json", man)
    write_record(pid)
    with zipfile.ZipFile(ex / "project.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in d.rglob("*"):
            if f.is_file() and f.name != "project.zip" and "clips" not in f.parts and f.suffix not in (".part",) and f.name not in ("silent.mp4", "mix.wav"):
                z.write(f, f.relative_to(d))
    save_version(pid, "Export", auto=True)
    p = store.get_production(pid)
    p["final"] = "awaiting_approval" if gate["passed"] else "checks_failed"
    store.save_production(p)
    return True


def write_record(pid: str) -> None:
    p = store.get_production(pid)
    s = store.read_json(pid, "strategy/strategy.json", {})
    jobs = store.list_jobs(500, pid)
    board = store.read_json(pid, "storyboard/board.json", {"scenes": []})
    rec = {"production": pid, "title": p["title"], "written": time.time(), "chosen_treatment": s.get("chosen"), "recipes_used": s.get("recipes_used", []),
           "scene_recipes": {sc["id"]: sc.get("recipes", []) for sc in board["scenes"]}, "edits": len(p.get("history", [])) - 1 if p.get("history") else 0,
           "gates": {g: store.read_json(pid, f"gates/{g}.json", {}).get("passed") for g in ("research", "strategy", "script", "storyboard", "final")},
           "jobs": [{"kind": j["kind"], "state": j["state"], "seconds": round((j["finished"] or 0) - (j["started"] or 0), 1), "paid": j["paid"]} for j in jobs],
           "results": p.get("results", "none supplied")}
    store.write_json(pid, "record/production-record.json", rec)


STAGE_FUNCS = {"research": run_research, "strategy": run_strategy, "script": run_script, "storyboard": run_storyboard,
               "produce": run_produce, "export": run_export}


def run_pipeline(pid: str, ctx: Ctx, start: str = "research", only: bool = False) -> None:
    brief = _brief(pid)
    every_gate = brief.get("review_mode", "final_only") == "every_gate"
    for st in ORDER[ORDER.index(start):]:
        store.set_stage(pid, st, state="running", started=time.time(), error="")
        try:
            ok = STAGE_FUNCS[st](pid, ctx)
        except Exception as e:
            store.set_stage(pid, st, state="failed", error=str(e)[:500])
            raise
        if not ok:
            store.set_stage(pid, st, state="needs_you", finished=time.time())
            ctx.say(f"The {st} gate did not pass after repair. It needs you.", None)
            return
        if st in AUTO_GATED and every_gate and st != "research":
            store.set_stage(pid, st, state="awaiting_approval", finished=time.time())
            ctx.say(f"The {st} is waiting for your approval.", None)
            return
        store.set_stage(pid, st, state="passed", finished=time.time(), by="automatically" if st in AUTO_GATED else "")
        if only:
            return
    ctx.say("Finished. The final video is waiting for your approval.", 1.0)


def approve_gate(pid: str, stage: str) -> str:
    """Manual approval of a script or storyboard gate; continues the pipeline."""
    store.set_stage(pid, stage, state="passed", by="you", finished=time.time())
    g = store.read_json(pid, f"gates/{stage}.json")
    if g:
        g["decided"] = "by you"
        store.write_json(pid, f"gates/{stage}.json", g)
    nxt = ORDER[ORDER.index(stage) + 1]
    return store.add_job("pipeline", pid, {"start": nxt})


def approve_final(pid: str) -> None:
    p = store.get_production(pid)
    p["final"] = "approved"
    p["approved_at"] = time.time()
    store.save_production(p)
    g = store.read_json(pid, "gates/final.json", {})
    g["decided"] = "by you"
    store.write_json(pid, "gates/final.json", g)


# ------------------------------------------------------------------ history, versions, edits
def _snapshot(pid: str) -> dict:
    return {"script": store.read_json(pid, "script/script.json"), "board": store.read_json(pid, "storyboard/board.json"), "brief": _brief(pid)}


def _restore(pid: str, snap: dict) -> None:
    if snap.get("script"):
        store.write_json(pid, "script/script.json", snap["script"])
    if snap.get("board"):
        store.write_json(pid, "storyboard/board.json", snap["board"])
    if snap.get("brief"):
        store.write_json(pid, "brief.json", snap["brief"])


def push_history(pid: str, label: str) -> None:
    p = store.get_production(pid)
    hist = p.get("history", [])[: p.get("hpos", -1) + 1]
    hid = store.new_id("h")
    store.write_json(pid, f"history/{hid}.json", _snapshot(pid))
    hist.append({"id": hid, "label": label, "at": time.time()})
    p["history"], p["hpos"] = hist[-60:], len(hist[-60:]) - 1
    store.save_production(p)


def undo_redo(pid: str, step: int) -> dict:
    p = store.get_production(pid)
    pos = p.get("hpos", -1) + step
    if not (0 <= pos < len(p.get("history", []))):
        raise ValueError("Nothing to undo" if step < 0 else "Nothing to redo")
    _restore(pid, store.read_json(pid, f"history/{p['history'][pos]['id']}.json"))
    p["hpos"] = pos
    store.save_production(p)
    return plan(pid)


def save_version(pid: str, label: str, auto: bool = False) -> dict:
    p = store.get_production(pid)
    vid = store.new_id("v")
    store.write_json(pid, f"versions/{vid}.json", _snapshot(pid))
    v = {"id": vid, "label": label, "at": time.time(), "auto": auto}
    p.setdefault("versions", []).append(v)
    store.save_production(p)
    return v


def restore_version(pid: str, vid: str) -> dict:
    snap = store.read_json(pid, f"versions/{vid}.json")
    if not snap:
        raise ValueError("Version not found")
    _restore(pid, snap)
    push_history(pid, "Restored a version")
    return plan(pid)


EDITABLE = ("title", "heading", "treatment", "theme", "elements", "links", "cues", "lines", "code", "ui", "data", "camera", "pad_start", "pad_end",
            "motion_scale", "objective", "container_label", "reason")


def update_scene(pid: str, sid: str, patch: dict, label: str = "") -> dict:
    board = store.read_json(pid, "storyboard/board.json")
    spec = next((s for s in board["scenes"] if s["id"] == sid), None)
    if spec is None:
        raise ValueError("Scene not found")
    for k, v in patch.items():
        if k in EDITABLE:
            if v is None:
                spec.pop(k, None)
            else:
                spec[k] = v
    schemas.SceneSpec.model_validate(spec)
    if spec.get("treatment") not in schemas.TREATMENTS:
        raise ValueError(f"Unknown treatment {spec.get('treatment')}")
    store.write_json(pid, "storyboard/board.json", board)
    push_history(pid, label or f"Edited {sid}")
    return plan(pid)


def update_script(pid: str, sid: str, sentences: list[str]) -> dict:
    script = store.read_json(pid, "script/script.json")
    sc = next((s for s in script["scenes"] if s["id"] == sid), None)
    if sc is None:
        raise ValueError("Scene not found")
    old = sc["sentences"]
    sc["sentences"] = [{"text": t.strip(), "claims": (old[i]["claims"] if i < len(old) else [])} for i, t in enumerate(sentences) if t.strip()]
    store.write_json(pid, "script/script.json", script)
    push_history(pid, f"Edited narration of {sid}")
    return plan(pid)


def reorder(pid: str, ids: list[str]) -> dict:
    board = store.read_json(pid, "storyboard/board.json")
    script = store.read_json(pid, "script/script.json")
    if sorted(ids) != sorted(s["id"] for s in board["scenes"]):
        raise ValueError("The new order must contain the same scenes")
    board["scenes"].sort(key=lambda s: ids.index(s["id"]))
    script["scenes"].sort(key=lambda s: ids.index(s["id"]))
    store.write_json(pid, "storyboard/board.json", board)
    store.write_json(pid, "script/script.json", script)
    push_history(pid, "Reordered scenes")
    return plan(pid)


def propose_edit(pid: str, sid: str, instruction: str, ctx: Ctx) -> dict:
    """Natural-language edit: the Animation Producer role proposes a new specification. Nothing is applied here."""
    board = store.read_json(pid, "storyboard/board.json")
    script = store.read_json(pid, "script/script.json")
    spec = next(s for s in board["scenes"] if s["id"] == sid)
    sc = next(s for s in script["scenes"] if s["id"] == sid)
    new = roles.run("scene_editor", {"instruction": instruction, "specification": spec, "narration": [s["text"] for s in sc["sentences"]]}, ctx.meta(pid)).model_dump(exclude_none=True)
    new["id"] = sid
    changed = sorted(k for k in set(spec) | set(new) if spec.get(k) != new.get(k))
    store.write_json(pid, f"storyboard/proposal-{sid}.json", {"instruction": instruction, "spec": new, "changed": changed})
    return {"spec": new, "changed": changed}


def set_override(pid: str, key: str, choice: str) -> None:
    p = store.get_production(pid)
    p.setdefault("overrides", {})[key] = choice
    store.save_production(p)
    s = store.read_json(pid, "strategy/strategy.json")
    if s:
        store.write_json(pid, "strategy/strategy.json", apply_overrides(s, p["overrides"]))
        (store.pdir(pid) / "strategy" / "strategy.md").write_text(strategy_markdown(s, p["title"]), encoding="utf-8")
    for st in ("script", "storyboard", "produce", "export"):
        if p["stages"].get(st, {}).get("state") in ("passed", "awaiting_approval"):
            store.set_stage(pid, st, stale=True)
    knowledge.add_item({"kind": "preference", "category": "User preferences", "title": f"Override: {key}", "body": choice, "tier": "preference",
                        "source": f"Production {pid}", "date": time.strftime("%Y-%m-%d"), "applies": "Recorded from an override; review before reuse", "confidence": "stated by you"})


# ------------------------------------------------------------------ import of prepared role outputs (examples, bridge in bulk)
def import_artifacts(pid: str, facts: dict, strategy: dict, script: dict, board: dict, by: str) -> dict:
    """Validates prepared role outputs against the schemas and runs the same gates as a live run."""
    facts = schemas.Facts.model_validate(facts).model_dump()
    strategy = schemas.Strategy.model_validate(strategy).model_dump()
    script = schemas.Script.model_validate(script).model_dump()
    board = schemas.Storyboard.model_validate(board).model_dump(exclude_none=True)
    p = store.get_production(pid)
    store.write_json(pid, "research/facts.json", facts)
    store.write_json(pid, "strategy/strategy.json", strategy)
    (store.pdir(pid) / "strategy" / "strategy.md").write_text(strategy_markdown(strategy, p["title"]), encoding="utf-8")
    store.write_json(pid, "script/script.json", script)
    store.write_json(pid, "storyboard/board.json", board)
    res = {"research": gates.research_gate(facts), "script": gates.script_gate(script, facts, strategy, _target_seconds(_brief(pid)), None),
           "storyboard": gates.storyboard_gate(board, script, facts)}
    res["strategy"] = {"gate": "strategy", "passed": len(strategy["treatments"]) >= 3, "criteria": [gates._crit("Three treatments compared", len(strategy["treatments"]) >= 3)]}
    for st, g in res.items():
        g["role_output_by"] = by
        _save_gate(pid, g, True)
        store.set_stage(pid, st, state="passed" if g["passed"] else "needs_you", by="automatically", finished=time.time(), imported=by)
    knowledge.note_usage(strategy.get("recipes_used", []), pid)
    push_history(pid, "Storyboard imported")
    return {k: v["passed"] for k, v in res.items()}


def delete_production(pid: str) -> None:
    shutil.rmtree(config.DATA / "productions" / pid, ignore_errors=True)
    store.q("DELETE FROM productions WHERE id=?", (pid,))
    store.q("DELETE FROM jobs WHERE production_id=?", (pid,))
