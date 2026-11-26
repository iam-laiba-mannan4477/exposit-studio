"""Command line: python -m exposit.cli <command>

  serve            start the studio (API + web interface)
  sample           build the 60-second example production end to end and print where the MP4 is
  scout            run one Scout collection now
  bridge           list open agent tasks, or answer one:  bridge answer <task-id> <file.json>
  check <video>    run the automated checks on any video file
  models           download the narration model files (about 120 MB) and verify their checksums
  doctor           check that everything the studio needs is installed and working
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
from . import config, store, director, knowledge


def example_dir(name: str = "http-request-journey") -> Path:
    return config.ROOT / "examples" / name


def create_from_example(name: str = "http-request-journey", fmt: str = "16:9") -> str:
    d = example_dir(name)
    load = lambda f: json.loads((d / f).read_text(encoding="utf-8"))
    knowledge.seed()
    brief = load("brief.json")
    if fmt == "9:16":
        brief.update(format="9:16", title=brief["title"] + " (vertical)")
    p = store.create_production(brief)
    director.import_artifacts(p["id"], load("facts.json"), load("strategy.json"), load("script.json"), load("board.json"),
                              by="Claude, during development (examples/%s)" % name)
    return p["id"]


def peak_mb() -> float:
    try:
        import psutil
        m = psutil.Process().memory_info()
        return round(getattr(m, "peak_wset", m.rss) / 1e6, 0)
    except Exception:
        return 0.0


def cmd_sample() -> None:
    t0 = time.time()
    pid = create_from_example()
    jid = store.add_job("pipeline", pid, {"start": "produce"})
    store.update_job(jid, state="running", started=time.time())
    ctx = director.Ctx(jid)
    try:
        director.run_pipeline(pid, ctx, "produce")
        store.update_job(jid, state="done", finished=time.time(), progress=1.0)
    except Exception:
        store.update_job(jid, state="failed", finished=time.time())
        raise
    out = store.pdir(pid) / "export" / "video.mp4"
    gate = store.read_json(pid, "gates/final.json", {})
    print(f"Production {pid}")
    print(f"Video: {out}")
    print(f"Total time: {time.time() - t0:.0f} s; memory in use at the end: {peak_mb():.0f} MB")
    for c in gate.get("criteria", []):
        print(f"  [{'pass' if c['passed'] else 'FAIL'}] {c['name']}: {c['detail']}")
    print(store.get_job(jid)["log"])


MODEL_FILES = {  # Kokoro v1.0 (Apache-2.0 weights), as published by the kokoro-onnx project
    "kokoro-v1.0.int8.onnx": ("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx",
                              "6e742170d309016e5891a994e1ce1559c702a2ccd0075e67ef7157974f6406cb"),
    "voices-v1.0.bin": ("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
                        "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d"),
}


def _sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cmd_models() -> int:
    import httpx
    config.MODELS.mkdir(parents=True, exist_ok=True)
    for name, (url, digest) in MODEL_FILES.items():
        dest = config.MODELS / name
        if dest.exists() and _sha256(dest) == digest:
            print(f"ok       {name} (already present, checksum verified)")
            continue
        tmp = dest.with_suffix(dest.suffix + ".part")
        print(f"download {name} from {url}")
        with httpx.stream("GET", url, follow_redirects=True, timeout=120) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length") or 0)
            got, last = 0, -1
            with open(tmp, "wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
                    got += len(chunk)
                    pct = int(got * 100 / total) if total else -1
                    if pct // 10 != last // 10:
                        print(f"         {got / 1e6:.0f} MB" + (f" ({pct}%)" if total else ""), flush=True)
                        last = pct
        if _sha256(tmp) != digest:
            tmp.unlink(missing_ok=True)
            print(f"FAILED   {name}: checksum does not match. The file was deleted. Try again, or download it by hand (see docs/TROUBLESHOOTING.md).")
            return 1
        tmp.replace(dest)
        print(f"ok       {name} (checksum verified)")
    return 0


def cmd_doctor() -> int:
    import importlib, platform, shutil, socket
    bad = 0

    def line(ok, what, detail=""):
        nonlocal bad
        bad += 0 if ok else 1
        print(f"[{'ok' if ok else 'PROBLEM'}] {what}" + (f": {detail}" if detail else ""))

    line(sys.version_info >= (3, 11), "Python", platform.python_version() + ("" if sys.version_info >= (3, 11) else " (3.12 or 3.13 is required)"))
    for mod in ("fastapi", "uvicorn", "pydantic", "numpy", "scipy", "soundfile", "skia", "onnxruntime", "kokoro_onnx", "imageio_ffmpeg", "psutil", "PIL", "httpx", "multipart"):
        try:
            importlib.import_module(mod)
            line(True, f"package {mod}")
        except Exception as e:
            line(False, f"package {mod}", f"{type(e).__name__}: {e}. Run install again.")
    ff = config.ffmpeg_exe()
    line(bool(shutil.which(ff) or Path(ff).exists()), "FFmpeg", ff)
    for name, (_, digest) in MODEL_FILES.items():
        f = config.MODELS / name
        line(f.exists(), f"model {name}", "present" if f.exists() else "missing: run  python -m exposit.cli models")
    line((config.WEB / "dist" / "index.html").exists(), "web interface build", str(config.WEB / "dist"))
    try:
        from .render import engine
        png = engine.render_still({"id": "t", "title": "t", "treatment": "kinetic", "lines": [{"text": "Exposit", "at": 0}]},
                                  {"duration": 2, "sentences": [], "words": []}, 1.0, 320, 180, "premium-technical", False)
        line(len(png) > 1000, "scene renderer (Skia)", f"test frame {len(png)} bytes")
    except Exception as e:
        line(False, "scene renderer (Skia)", f"{type(e).__name__}: {e}")
    from .render import blender3d
    bi = blender3d.info(refresh=True)
    if bi.get("path"):
        line(True, "Blender (optional 3D)", f"{bi['path']} (version {bi.get('version') or 'unknown'})")
        ok, why = blender3d.test_render(log=lambda m: None)
        line(ok, "Blender test render (64x64, EEVEE, headless)", why)
    else:
        print("[info] Blender (optional 3D): not found. 3D shots fall back to 2D. Install it from blender.org and set "
              "BLENDER_PATH in .env if it is not in C:\\Program Files\\Blender Foundation.")
    try:
        import psutil
        vm = psutil.virtual_memory()
        line(vm.available > 1.5e9, "free memory", f"{vm.available / 1e9:.1f} GB available of {vm.total / 1e9:.1f} GB (rendering needs about 0.6 GB)")
    except Exception:
        pass
    free = shutil.disk_usage(config.DATA).free / 1e9
    line(free > 2, "free disk", f"{free:.1f} GB at {config.DATA}")
    s = socket.socket()
    try:
        s.bind((config.HOST, config.PORT))
        line(True, f"port {config.PORT}", "free")
    except OSError:
        line(False, f"port {config.PORT}", "in use: the studio may already be running, or set EXPOSIT_PORT in .env")
    finally:
        s.close()
    from . import providers
    st = providers.status()
    print(f"[info] AI provider: {st['provider']} ({'paid' if st['paid'] else 'no API cost'}). {st['note']}")
    print("All checks passed." if not bad else f"{bad} problem(s) found. See docs/TROUBLESHOOTING.md.")
    return 1 if bad else 0


def main() -> None:
    a = sys.argv[1:]
    cmd = a[0] if a else "serve"
    if cmd == "serve":
        import uvicorn
        uvicorn.run("exposit.app:app", host=config.HOST, port=config.PORT, log_level="warning")
    elif cmd == "sample":
        cmd_sample()
    elif cmd == "scout":
        from . import scout
        print(json.dumps(scout.run(director.Ctx()), indent=1))
    elif cmd == "bridge":
        from . import providers
        if len(a) >= 4 and a[1] == "answer":
            providers.bridge_submit(a[2], Path(a[3]).read_text(encoding="utf-8"))
            print("Answer submitted.")
        else:
            for t in providers.bridge_pending():
                print(t["id"], t["role"], t.get("production_id", ""))
    elif cmd == "models":
        sys.exit(cmd_models())
    elif cmd == "doctor":
        sys.exit(cmd_doctor())
    elif cmd == "check" and len(a) > 1:
        from . import compose
        p = compose.probe(a[1])
        for c in compose.checks(a[1], {"width": p["width"], "height": p["height"], "fps": p["fps"], "duration": p["duration"]}):
            print(f"[{'pass' if c['passed'] else 'FAIL'}] {c['name']}: {c['detail']}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
