"""Style-pack gallery: the same CDN scene in every ready animation style, 9:16 and 16:9, plus a contact sheet.
Output: docs/style-packs/<style>__<9x16|16x9>.png and contact.png.

    python scripts/render_style_gallery.py [--scene iconflow] [--only a,b] [--bench]
"""
from __future__ import annotations
import argparse, io, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import numpy as np                                     # noqa: E402
import skia                                            # noqa: E402
from PIL import Image, ImageDraw, ImageFont            # noqa: E402
from exposit.render import engine, styles              # noqa: E402
import render_gallery as gallery                       # noqa: E402

OUT = ROOT / "docs" / "style-packs"


def scene(sid: str):
    s = next(x for x in gallery.scenes() if x["id"] == sid)
    return s


def bench(s: dict, style: str, portrait: bool, step: int = 3) -> float:
    """95th percentile ms per frame at 1080p, drawing plus the style's post-process, after the cache build."""
    tm = gallery.timing_for(s["narration"])
    spec = dict(s["spec"], theme=style)
    w, h = (1080, 1920) if portrait else (1920, 1080)
    tr = engine.build(spec, tm, style, portrait=portrait)
    surf = skia.Surface(w, h)
    c = surf.getCanvas()
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    info = skia.ImageInfo.Make(w, h, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)
    st = styles.STYLES[style]
    frames = [i / 30 for i in range(0, int(tr.sc.dur * 30), step)]

    def one(t):
        engine.draw_frame(c, tr, t, w, h, False)
        surf.readPixels(info, arr)
        if st.post:
            styles.post_process(arr, st.post, int(t * 30))
    for t in frames:
        one(t)
    ts = []
    for t in frames:
        t0 = time.perf_counter()
        one(t)
        ts.append((time.perf_counter() - t0) * 1000)
    ts.sort()
    return ts[int(0.95 * (len(ts) - 1))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="iconflow")
    ap.add_argument("--only", default="")
    ap.add_argument("--bench", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    s = scene(a.scene)
    names = [n for n in styles.READY if not a.only or n in a.only.split(",")]
    tiles = {}
    for n in names:
        for portrait in (True, False):
            png = gallery.render(s, n, portrait, 0.5)
            (OUT / f"{n}__{'9x16' if portrait else '16x9'}.png").write_bytes(png)
            tiles[(n, portrait)] = png
        if a.bench:
            print(f"{n:22s} 9:16 {bench(s, n, True):6.1f} ms   16:9 {bench(s, n, False):6.1f} ms")
    cw, ch, lw, lh, pad = 216, 384, 216, 122, 10
    sheet = Image.new("RGB", (len(names) * (cw + pad) + pad, 30 + ch + pad + lh + pad), "#202226")
    d = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.truetype(str(ROOT / "exposit" / "assets" / "fonts" / "Inter-SemiBold.otf"), 14)
    except Exception:
        f = None
    for i, n in enumerate(names):
        x = pad + i * (cw + pad)
        d.text((x, 8), n, fill="#E6E6E6", font=f)
        sheet.paste(Image.open(io.BytesIO(tiles[(n, True)])).convert("RGB").resize((cw, ch), Image.LANCZOS), (x, 30))
        sheet.paste(Image.open(io.BytesIO(tiles[(n, False)])).convert("RGB").resize((lw, lh), Image.LANCZOS), (x, 30 + ch + pad))
    sheet.save(OUT / "contact.png")


if __name__ == "__main__":
    main()
