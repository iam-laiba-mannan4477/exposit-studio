"""Renders this Reel's two Blender shots (S3 CDN network, S5 rolling-midnight globe) as 540x960 previews with their
narration, one Blender process at a time, and prints Blender time and peak RAM. Run it in your own terminal."""
import json, subprocess, sys, time
from pathlib import Path
R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R))
import imageio_ffmpeg
from exposit.render import engine, blender3d
H = Path(__file__).parent
O = H / "out"
O.mkdir(exist_ok=True)
board = {s["id"]: s for s in json.loads((H / "board.json").read_text(encoding="utf-8"))["scenes"]}
print("Blender:", blender3d.info().get("path") or "not found")
for sid in (sys.argv[1:] or ["s3", "s5"]):
    sp = dict(board[sid], _px=[540, 960])
    tm = json.loads((H / "audio" / f"{sid}.timing.json").read_text(encoding="utf-8"))
    sp["seconds"] = round(engine.Scene(sp, tm, "midnight-launch").dur, 2)
    t0 = time.time()
    silent = O / f"{sid}_3d_silent.mp4"
    engine.render_clip(sp, tm, str(silent), 540, 960, 30, "midnight-launch", False)
    done = [p for p in blender3d.cache_dir().glob("*/done.json") if p.stat().st_mtime >= t0]
    d = json.loads(done[0].read_text()) if done else {}
    sc = engine.Scene(sp, tm, "midnight-launch")
    out = O / f"{sid}_3d_preview.mp4"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(silent), "-i", str(H / "audio" / f"{sid}.wav"),
                    "-filter_complex", f"[1:a]adelay={int(sc.pad0 * 1000)}|{int(sc.pad0 * 1000)}[a]", "-map", "0:v", "-map", "[a]",
                    "-t", f"{sc.dur:.3f}", "-c:v", "copy", "-c:a", "aac", str(out)], check=True)
    print(f"{sid}: {'3D' if d else '2D fallback'}; blender {d.get('seconds', '-')} s, peak RAM {d.get('peak_rss_mb', '-')} MB -> {out}", flush=True)
