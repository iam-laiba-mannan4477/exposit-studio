import json, sys, time
from pathlib import Path
R = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(R))
from exposit.render import engine
H = Path(__file__).parent; (H / "out").mkdir(exist_ok=True)
sid = sys.argv[1]
sp = {s["id"]: s for s in json.loads((H / "board.json").read_text(encoding="utf-8"))["scenes"]}[sid]
tm = json.loads((H / "audio" / f"{sid}.timing.json").read_text(encoding="utf-8"))
t0 = time.time()
print(sid, engine.render_clip(dict(sp), tm, str(H / "out" / f"{sid}_1080.mp4"), 1080, 1920, 30, "claude-orange-dark", False), f"{time.time()-t0:.0f}s", flush=True)
