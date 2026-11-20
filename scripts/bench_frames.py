"""Short 1080p frame benchmark: 16 frames per treatment through the same path as render_clip (native Skia surface,
then one readPixels to RGBA). Prints ms per frame for each treatment, the cProfile top 5 for the slowest one, and
this process's peak memory.

    python scripts/bench_frames.py [--frames 16] [--template noir-network] [--portrait]
"""
from __future__ import annotations
import argparse, cProfile, io, pstats, statistics, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import numpy as np            # noqa: E402
import skia                   # noqa: E402
import render_gallery as G    # noqa: E402
from exposit.render import engine  # noqa: E402


def peak_mb() -> float:
    try:
        import psutil
        mi = psutil.Process().memory_info()
        return getattr(mi, "peak_wset", mi.rss) / 1e6
    except Exception:
        return float("nan")


def frames_for(scene: dict, template: str, portrait: bool, n: int):
    """Yields a callable that renders frame i like render_clip does, after the first frame has warmed the caches."""
    tm = G.timing_for(scene["narration"])
    spec = dict(scene["spec"], theme=template)
    w, h = (1080, 1920) if portrait else (1920, 1080)
    tr = engine.build(spec, tm, template, portrait=portrait)
    surf = skia.Surface(w, h)
    c = surf.getCanvas()
    out = np.zeros((h, w, 4), np.uint8)
    info = skia.ImageInfo.Make(w, h, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)

    def one(i):
        engine.draw_frame(c, tr, tr.sc.dur * i / n, w, h, True)
        surf.readPixels(info, out)
    one(0)
    return one


def measure(scene, template, portrait, n):
    one = frames_for(scene, template, portrait, n)
    ms = []
    for i in range(n):
        t0 = time.perf_counter()
        one(i)
        ms.append((time.perf_counter() - t0) * 1000)
    return statistics.median(ms), max(ms)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=16)
    ap.add_argument("--template", default="noir-network")
    ap.add_argument("--portrait", action="store_true")
    a = ap.parse_args()
    rows = []
    for s in G.scenes():
        med, worst = measure(s, a.template, a.portrait, a.frames)
        rows.append((s["id"], med, worst))
        print(f"{s['id']:15s} median {med:6.1f} ms   worst {worst:6.1f} ms", flush=True)
    slow = max(rows, key=lambda r: r[2])
    scene = next(s for s in G.scenes() if s["id"] == slow[0])
    one = frames_for(scene, a.template, a.portrait, a.frames)
    pr = cProfile.Profile()
    pr.enable()
    for i in range(a.frames):
        one(i)
    pr.disable()
    buf = io.StringIO()
    pstats.Stats(pr, stream=buf).sort_stats("tottime").print_stats(5)
    print(f"\nslowest: {slow[0]} ({slow[2]:.1f} ms worst). cProfile top 5 by own time:")
    print("\n".join(l for l in buf.getvalue().splitlines() if l.strip())[-900:])
    print(f"peak memory {peak_mb():.0f} MB")


if __name__ == "__main__":
    main()
