"""Local previews: real narration (Kokoro, am_michael, speed 1.1), stills of every scene at 1080x1920, and 540x960
clips with sound for the scenes named on the command line. Usage: preview.py [narrate] [stills] [clip s1 s5+s6 ...]"""
import json, subprocess, sys, time
from pathlib import Path
R = Path(r"C:\Users\PMLS\Desktop\studio\exposit-studio\exposit-studio")
sys.path.insert(0, str(R)); sys.path.insert(0, str(R / "scripts"))
import imageio_ffmpeg
import render_gallery as G
from exposit import tts
from exposit.render import engine

H = Path(__file__).parent
A = H / "audio"; A.mkdir(exist_ok=True)
O = H / "out"; O.mkdir(exist_ok=True)
board = {s["id"]: s for s in json.loads((H / "board.json").read_text(encoding="utf-8"))["scenes"]}
script = {s["id"]: [x["text"] for x in s["sentences"]] for s in json.loads((H / "script.json").read_text(encoding="utf-8"))["scenes"]}
FF = imageio_ffmpeg.get_ffmpeg_exe()
args = sys.argv[1:]


def timing(sid):
    return json.loads((A / f"{sid}.timing.json").read_text(encoding="utf-8"))


if "narrate" in args:
    for sid, sents in script.items():
        info = tts.narrate_scene(sents, A / f"{sid}.wav", "am_michael", 1.1)
        print(sid, round(info.get("duration", 0), 2), "s")
    tts.unload()

if "stills" in args:
    for sid, spec in board.items():
        tm = timing(sid)
        sp = dict(spec, theme="claude-orange")
        t = G.most_complete_t(sp, tm) if not sp.get("still_t") else engine.Scene(sp, tm, "claude-orange").dur - 0.4
        t0 = time.time()
        (O / f"{sid}.png").write_bytes(engine.render_still(sp, tm, t, 1080, 1920, "claude-orange", False))
        print(sid, f"t={t:.2f}", f"{(time.time() - t0) * 1000:.0f} ms")

if "clip" in args:
    for group in args[args.index("clip") + 1:]:
        parts = []
        for sid in group.split("+"):
            sp = dict(board[sid], theme="claude-orange")
            tm = timing(sid)
            silent = O / f"{sid}_silent.mp4"
            t0 = time.time()
            info = engine.render_clip(sp, tm, str(silent), 540, 960, 30, "claude-orange", False)
            sc = engine.Scene(sp, tm, "claude-orange")
            out = O / f"{sid}_preview.mp4"
            subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(silent), "-i", str(A / f"{sid}.wav"), "-filter_complex",
                            f"[1:a]adelay={int(sc.pad0 * 1000)}|{int(sc.pad0 * 1000)}[a]", "-map", "0:v", "-map", "[a]", "-t", f"{sc.dur:.3f}",
                            "-c:v", "copy", "-c:a", "aac", str(out)], check=True)
            parts.append(out)
            print(sid, info, f"{time.time() - t0:.1f} s wall")
        if len(parts) > 1:
            lst = O / "concat.txt"
            lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts))
            subprocess.run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                            str(O / f"{group.replace('+', '_')}_preview.mp4")], check=True)
