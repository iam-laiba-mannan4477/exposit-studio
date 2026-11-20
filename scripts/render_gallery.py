"""Render the style gallery: every treatment in every template, 16:9 and 9:16, as stills at the scene's most complete
moment, plus contact sheets. Output: docs/style-gallery/<scene>__<template>__<16x9|9x16>.png and contact-*.png.

    python scripts/render_gallery.py [--only scene1,scene2] [--templates a,b] [--scale 0.5]
"""
from __future__ import annotations
import argparse, io, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw, ImageFont          # noqa: E402
from exposit.render import engine, design            # noqa: E402

GALLERY = ROOT / "examples" / "style-gallery" / "scenes.json"
OUT = ROOT / "docs" / "style-gallery"


def timing_for(narration: str, wps: float = 2.6) -> dict:
    """Even word timings for a narration (the real pipeline uses synthesised timings)."""
    words, t, sents = [], 0.4, []
    for si, s in enumerate([x.strip() + "." for x in narration.replace("?", ".").split(".") if x.strip()]):
        s0 = t
        for w in s.split():
            words.append({"w": w, "s": round(t, 3), "e": round(t + 0.85 / wps * 2, 3), "si": si})
            t += 1 / wps
        sents.append({"text": s, "s": s0, "e": t})
        t += 0.25
    return {"duration": round(t + 0.4, 3), "sentences": sents, "words": words}


def scenes() -> list[dict]:
    return json.loads(GALLERY.read_text(encoding="utf-8"))["scenes"]


def most_complete_t(spec: dict, timing: dict) -> float:
    """After the last cue has played out, before the end fade."""
    sc = engine.Scene(spec, timing)
    last = max([e["t"] for e in sc.events] + [0.0])
    for m in spec.get("messages", []) + spec.get("items", []) + spec.get("lines", []):
        tt = sc.cue_time(m.get("at")) if m.get("at") is not None else None
        last = max(last, tt or 0.0)
    if spec.get("treatment") == "compare":
        last = max(last, 0.4 + 0.9 * 5 + 0.6)
    return min(sc.dur - 0.35, max(last + 1.6, sc.dur * 0.8))


def render(scene: dict, template: str, portrait: bool, scale: float = 0.5) -> bytes:
    tm = timing_for(scene["narration"])
    spec = dict(scene["spec"], theme=template)
    w, h = (int(1080 * scale), int(1920 * scale)) if portrait else (int(1920 * scale), int(1080 * scale))
    tr = engine.build(spec, tm, template, portrait=portrait)
    t = most_complete_t(spec, tm)
    tr.sc.dur = max(tr.sc.dur, t + 0.4)
    return engine.render_still(spec, tm, t, w, h, template, False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--templates", default="")
    ap.add_argument("--scale", type=float, default=0.5)
    ap.add_argument("--no-sheet", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    tpls = [x for x in a.templates.split(",") if x] or ["premium-technical", *design.NEW_TEMPLATES]
    scs = [s for s in scenes() if not a.only or s["id"] in a.only.split(",")]
    made = {}
    for s in scs:
        for tp in tpls:
            for portrait in (False, True):
                png = render(s, tp, portrait, a.scale)
                name = f"{s['id']}__{tp}__{'9x16' if portrait else '16x9'}.png"
                (OUT / name).write_bytes(png)
                made[(s["id"], tp, portrait)] = png
    if a.no_sheet:
        return
    for portrait in (False, True):
        cw, ch = (192, 341) if portrait else (384, 216)
        pad, head = 8, 26
        sheet = Image.new("RGB", (len(tpls) * (cw + pad) + pad + 150, len(scs) * (ch + pad) + pad + head), "#202226")
        d = ImageDraw.Draw(sheet)
        try:
            f = ImageFont.truetype(str(ROOT / "exposit" / "assets" / "fonts" / "Inter-SemiBold.otf"), 15)
        except Exception:
            f = None
        for j, tp in enumerate(tpls):
            d.text((150 + pad + j * (cw + pad), 6), tp, fill="#E6E6E6", font=f)
        for i, s in enumerate(scs):
            d.text((8, head + pad + i * (ch + pad) + ch // 2 - 8), s["id"], fill="#E6E6E6", font=f)
            for j, tp in enumerate(tpls):
                im = Image.open(io.BytesIO(made[(s["id"], tp, portrait)])).convert("RGB").resize((cw, ch), Image.LANCZOS)
                sheet.paste(im, (150 + pad + j * (cw + pad), head + pad + i * (ch + pad)))
        sheet.save(OUT / f"contact-{'9x16' if portrait else '16x9'}.png")


if __name__ == "__main__":
    main()
