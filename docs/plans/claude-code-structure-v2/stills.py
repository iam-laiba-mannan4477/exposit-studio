"""Stills at chosen moments of each scene (1080x1920) and a contact sheet. Usage: stills.py [sid:t ...]"""
import json, sys
from pathlib import Path
R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R))
from exposit.render import engine
import skia
H = Path(__file__).parent
O = H / "out"; O.mkdir(exist_ok=True)
board = {s["id"]: s for s in json.loads((H / "board.json").read_text(encoding="utf-8"))["scenes"]}
TH = "claude-orange-dark"
def tm(sid): return json.loads((H / "audio" / f"{sid}.timing.json").read_text(encoding="utf-8"))
picks = sys.argv[1:] or [f"{s}:end" for s in board]
files = []
for p in picks:
    sid, at = p.split(":")
    sp = dict(board[sid], theme=TH)
    dur = engine.Scene(sp, tm(sid), TH).dur
    t = dur - 0.4 if at == "end" else float(at)
    f = O / f"{sid}_{at}.png"
    f.write_bytes(engine.render_still(sp, tm(sid), t, 1080, 1920, TH, False))
    files.append(f); print(sid, f"t={t:.2f}/{dur:.2f}")
n = len(files); cols = min(n, 6); rows = (n + cols - 1) // cols
surf = skia.Surface(cols * 360, rows * 640); c = surf.getCanvas(); c.clear(0xFF000000)
for i, f in enumerate(files):
    img = skia.Image.open(str(f))
    c.drawImageRect(img, skia.Rect.MakeXYWH((i % cols) * 360, (i // cols) * 640, 360, 640), skia.SamplingOptions(skia.FilterMode.kLinear))
surf.makeImageSnapshot().save(str(O / "sheet.png"))
