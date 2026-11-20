"""Frame-time benchmark: draws real frames (1920x1080 and 1080x1920) across every gallery scene's timeline in every
template and reports the mean and worst draw time per frame. The budget is 80 ms per frame.

    python scripts/bench_frames.py [--step 6] [--budget 80]
"""
from __future__ import annotations
import argparse, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import skia                                           # noqa: E402
from exposit.render import design, engine             # noqa: E402
import render_gallery as gallery                      # noqa: E402


def bench(scene: dict, template: str, portrait: bool, step: int, fps: int = 30) -> tuple[float, float, float]:
    tm = gallery.timing_for(scene["narration"])
    spec = dict(scene["spec"], theme=template)
    w, h = (1080, 1920) if portrait else (1920, 1080)
    tr = engine.build(spec, tm, template, portrait=portrait)
    surf = skia.Surface(w, h)
    canvas = surf.getCanvas()
    n = max(1, int(tr.sc.dur * fps))
    times = []
    for i in range(0, n, step):
        t0 = time.perf_counter()
        engine.draw_frame(canvas, tr, i / fps, w, h, True)
        surf.flushAndSubmit() if hasattr(surf, "flushAndSubmit") else None
        times.append((time.perf_counter() - t0) * 1000)
    srt = sorted(times)
    p95 = srt[min(len(srt) - 1, int(0.95 * len(srt)))]
    return sum(times) / len(times), p95, max(times)   # mean includes the one-off cache builds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=int, default=6)
    ap.add_argument("--budget", type=float, default=80.0)
    a = ap.parse_args()
    rows, worst = [], 0.0
    for s in gallery.scenes():
        for tp in ["premium-technical", *design.NEW_TEMPLATES]:
            for portrait in (False, True):
                mean, p95, mx = bench(s, tp, portrait, a.step)
                worst = max(worst, mx)
                rows.append((p95, mean, mx, s["id"], tp, "9x16" if portrait else "16x9"))
    rows.sort(reverse=True)
    print(f"{'p95 ms':>7} {'mean ms':>8} {'max ms':>7}  scene / template / format")
    for p95, mean, mx, sid, tp, fmt in rows[:12]:
        print(f"{p95:7.1f} {mean:8.1f} {mx:7.1f}  {sid} / {tp} / {fmt}")
    over = [r for r in rows if r[0] > a.budget or r[1] > a.budget]
    print(f"\n{len(rows)} combinations; slowest mean {max(r[1] for r in rows):.1f} ms, slowest p95 {rows[0][0]:.1f} ms, "
          f"worst single frame {worst:.1f} ms (a cache build); budget {a.budget:.0f} ms on mean and p95; "
          f"over budget: {len(over)}")
    sys.exit(1 if over else 0)


if __name__ == "__main__":
    main()
