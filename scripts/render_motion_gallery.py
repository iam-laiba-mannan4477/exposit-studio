"""Motion-effects gallery: a still (9:16 and 16:9) and a 3-second test clip (9:16) of each of the ten effects.
Output: docs/motion-gallery/<effect>__<9x16|16x9>.png, <effect>.mp4 and contact.png.

    python scripts/render_motion_gallery.py [--template noir-network] [--only a,b] [--no-clips]
"""
from __future__ import annotations
import argparse, io, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from PIL import Image, ImageDraw, ImageFont          # noqa: E402
from exposit.render import engine                     # noqa: E402
import render_gallery as gallery                      # noqa: E402

OUT = ROOT / "docs" / "motion-gallery"
FLOW = [{"id": "user", "kind": "user", "label": "Browser"}, {"id": "edge", "kind": "edge", "label": "Edge location"},
        {"id": "regional", "kind": "cache", "icon": "database-zap", "label": "Regional cache"},
        {"id": "origin", "kind": "origin", "icon": "server-cog", "label": "Origin"}]
TOPICS = [{"icon": "server", "title": "Edge locations", "text": "Answer users nearby"},
          {"icon": "database-zap", "title": "Regional caches", "text": "A larger cache behind the edges"},
          {"icon": "server-cog", "title": "Origin", "text": "Reached only on a miss"},
          {"icon": "clock", "title": "Cache-Control", "text": "max-age sets the lifetime"},
          {"icon": "refresh-cw", "title": "304 Not Modified", "text": "Revalidated without a body"}]
N = "Edge locations answer users nearby. Regional caches sit behind them. The origin is reached only on a miss."

EFFECTS = {
    "parallax": {"narration": N, "spec": {"treatment": "iconflow", "heading": "Parallax depth", "elements": FLOW,
                 "effects": [{"type": "parallax", "layers": 4}]}},
    "pinned_heading": {"narration": N, "spec": {"treatment": "cards", "variant": "benefits", "heading": "What the cache changes",
                       "items": TOPICS[:4], "effects": [{"type": "pinned_heading", "distance": 380}]}},
    "card_zoom_3d": {"narration": N, "spec": {"treatment": "motion", "effect": "card_zoom_3d",
                     "card": {"icon": "database-zap", "title": "Regional edge cache", "text": "A larger cache between the edges and the origin"}}},
    "line_reveal": {"narration": N, "spec": {"treatment": "motion", "effect": "line_reveal", "code": True, "lines": [
                    {"text": "HTTP/2 200", "at": 0.2}, {"text": "cache-control: max-age=86400", "at": 0.8},
                    {"text": "age: 512", "at": 1.4}, {"text": "x-cache: Hit from cloudfront", "at": 2.0, "accent": True}]}},
    "marquee": {"narration": N, "spec": {"treatment": "motion", "effect": "marquee",
                "rows": [{"text": "Edge"}, {"text": "Cache hit", "accent": True}, {"text": "Origin"}]}},
    "card_carousel": {"narration": N, "spec": {"treatment": "motion", "effect": "card_carousel", "items": TOPICS,
                      "counter": "CDN parts"}},
    "model_3d": {"narration": N, "spec": {"treatment": "motion", "effect": "model_3d", "model": "server_rack",
                 "label": "Edge server", "sub": "one of many in a point of presence"}},
    "stacking_cards": {"narration": N, "spec": {"treatment": "motion", "effect": "stacking_cards", "items": TOPICS[:4]}},
    "focus_frame": {"narration": N, "spec": {"treatment": "iconflow", "heading": "Focus frame", "elements": FLOW,
                    "effects": [{"type": "focus_frame", "targets": [{"id": "user", "at": 0.4}, {"id": "edge", "at": 1.2},
                                                                    {"id": "regional", "at": 2.0}, {"id": "origin", "at": 2.8}]}]}},
    "scroll_demo": {"narration": N, "spec": {"treatment": "motion", "effect": "scroll_demo", "title": "bash",
                    "lines": [{"text": "curl -sI https://example.com/app.js", "cmd": True, "at": 0.2},
                              {"text": "HTTP/2 200", "at": 0.9}, {"text": "cache-control: max-age=86400", "at": 1.1},
                              {"text": "age: 512", "at": 1.3}, {"text": "x-cache: Hit from cloudfront", "tone": "ok", "at": 1.5},
                              {"text": "curl -sI https://example.com/new.js", "cmd": True, "at": 1.9},
                              {"text": "HTTP/2 200", "at": 2.4}, {"text": "x-cache: Miss from cloudfront", "tone": "err", "at": 2.6},
                              {"text": "via: 1.1 ...cloudfront.net (CloudFront)", "tone": "dim", "at": 2.8}]}},
    "globe": {"narration": N, "spec": {"treatment": "motion", "effect": "globe",
              "fly": [{"lat": 30, "lon": -30, "zoom": 1.0}, {"place": "London", "zoom": 2.0, "at": 1.0}],
              "cities": [{"place": "London", "at": 0.6}, {"place": "New York", "at": 0.3}],
              "arcs": [{"from": "New York", "to": "London", "at": 0.4}]}},
    "flat_map": {"narration": N, "spec": {"treatment": "motion", "effect": "flat_map", "heading": "Europe",
                 "region": [-12, 30, 36, 62], "cities": [{"place": "London", "at": 0.3}, {"place": "Frankfurt", "at": 0.6}],
                 "arcs": [{"from": "London", "to": "Frankfurt", "at": 0.8}]}},
    "split_compare": {"narration": N, "spec": {"treatment": "motion", "effect": "split_compare", "rows": [
        {"title": "From the factory", "note": "far away", "far": True, "tone": "fail", "from": {"icon": "factory", "label": "Factory"},
         "to": {"icon": "house", "label": "You"}, "at": 0.3},
        {"title": "From the shop", "note": "down the road", "tone": "success", "via": "milk", "from": {"icon": "store", "label": "Shop"},
         "to": {"icon": "house", "label": "You"}, "at": 0.6}]}},
    "cache_split": {"narration": N, "spec": {"treatment": "motion", "effect": "cache_split", "hit_at": 0.3, "miss_at": 0.8,
                    "fetch_at": 1.2, "keep_at": 1.8, "proof": [{"text": "X-Cache: Miss from cloudfront", "tone": "err", "at": 1.0},
                                                               {"text": "X-Cache: Hit from cloudfront", "tone": "ok", "at": 2.0}]}},
    "project_tree": {"narration": N, "spec": {"treatment": "motion", "effect": "project_tree", "pad_start": 0.3,
                     "tree": [{"id": "root", "name": "my-project/", "depth": 0, "icon": "folder-open"},
                              {"id": "readme", "name": "CLAUDE.md", "depth": 1, "icon": "file-text", "card": "Project brief loaded at session start."},
                              {"id": "cfg", "name": ".claude/", "depth": 1, "icon": "folder-open"},
                              {"id": "set", "name": "settings.json", "depth": 2, "icon": "file-cog", "card": "Permissions, hooks, env vars. Enforced."}],
                     "build": [{"rows": ["root", "readme"], "at": 0.2}, {"rows": ["cfg", "set"], "at": 1.0}]}},
    "dev_scene": {"narration": N, "spec": {"treatment": "motion", "effect": "dev_scene", "kind": "agents", "file": ".claude/agents/"}},
}
# extra 3D models on the still sheet
MODELS = ["server_rack", "cube", "globe", "database"]


def scene(name: str, template: str) -> tuple[dict, dict]:
    e = EFFECTS[name]
    spec = dict(e["spec"], id=name, theme=template, cues=e["spec"].get("cues", []))
    return spec, gallery.timing_for(e["narration"])


def still(spec, tm, portrait: bool, t: float, scale: float = 0.5) -> bytes:
    w, h = (int(1080 * scale), int(1920 * scale)) if portrait else (int(1920 * scale), int(1080 * scale))
    return engine.render_still(spec, tm, t, w, h, spec["theme"], False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", default="noir-network")
    ap.add_argument("--only", default="")
    ap.add_argument("--no-clips", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    names = [n for n in EFFECTS if not a.only or n in a.only.split(",")]
    tiles = {}
    for n in names:
        spec, tm = scene(n, a.template)
        for portrait in (True, False):
            png = still(spec, tm, portrait, 2.6)
            (OUT / f"{n}__{'9x16' if portrait else '16x9'}.png").write_bytes(png)
            tiles[(n, portrait)] = png
        if not a.no_clips:
            tm3 = dict(tm, duration=2.1)                       # 0.4 s pad + 2.1 s + 0.5 s pad = 3 s
            engine.render_clip(spec, tm3, str(OUT / f"{n}.mp4"), 540, 960, 30, a.template, False)
    for m in MODELS:                                           # the four models, 9:16 stills
        spec = dict(EFFECTS["model_3d"]["spec"], id=m, theme=a.template, model=m, label=m.replace("_", " ").title(), sub=None, cues=[])
        tiles[("model:" + m, True)] = still(spec, gallery.timing_for(N), True, 1.8)
    cw, ch, pad = 216, 384, 10
    keys = [k for k in tiles if k[1]]
    sheet = Image.new("RGB", (len(keys) * (cw + pad) + pad, ch + 44 + 2 * pad + 122 + 10), "#202226")
    d = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.truetype(str(ROOT / "exposit" / "assets" / "fonts" / "Inter-SemiBold.otf"), 14)
    except Exception:
        f = None
    for i, k in enumerate(keys):
        x = pad + i * (cw + pad)
        d.text((x, 8), k[0], fill="#E6E6E6", font=f)
        sheet.paste(Image.open(io.BytesIO(tiles[k])).convert("RGB").resize((cw, ch), Image.LANCZOS), (x, 30))
        land = tiles.get((k[0], False))
        if land:
            sheet.paste(Image.open(io.BytesIO(land)).convert("RGB").resize((cw, 122), Image.LANCZOS), (x, 30 + ch + pad))
    sheet.save(OUT / "contact.png")


if __name__ == "__main__":
    main()
