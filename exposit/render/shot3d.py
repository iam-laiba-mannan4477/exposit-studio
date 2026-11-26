"""The "blender3d" treatment: composites a Blender shot (transparent RGBA PNG frames, see blender3d.py) over the
template background, then draws every label in skia at the projected anchors, so text is always sharp, >= 30 px and
inside the platform safe band. A scene only reaches this class when its frames exist; otherwise engine.build swaps in
the 2D fallback."""
from __future__ import annotations
import json
from pathlib import Path
import skia
from . import design as D
from .design import col, clamp, ease_out
from .pro import ProTreatment


class Blender3DScene(ProTreatment):
    drift = 0.0

    def layout(self):
        sp = self.sc.spec
        self.dir = Path(sp["_shot_dir"])
        a = json.loads((self.dir / "anchors.json").read_text(encoding="utf-8"))
        self.n = int(a["frames"])
        self.anchors = a["anchors"]
        self.progress = a.get("progress") or []
        self.fps = 30
        self._img = (None, None)

    def frame_at(self, t):
        return int(clamp(t * self.fps, 0, self.n - 1)) + 1

    def _image(self, f):
        if self._img[0] != f:
            self._img = (f, skia.Image.open(str(self.dir / f"f_{f:04d}.png")))
        return self._img[1]

    def draw(self, c, t):
        f = self.frame_at(t)
        c.drawImageRect(self._image(f), skia.Rect.MakeWH(self.W, self.H), skia.SamplingOptions(skia.FilterMode.kLinear))
        tpl, T = self.tpl, self.tpl.T
        placed = []                                           # (x, y, w, h) of labels drawn so far: no overlaps
        prog = [l for l in self.sc.spec.get("labels", []) if l.get("progress") is not None]
        passed = [l for l in prog if self.progress and self.progress[f - 1] >= float(l["progress"])]
        latest = max(passed, key=lambda l: float(l["progress"])) if passed and self.sc.spec.get("latest_only") else None
        for l in self.sc.spec.get("labels", []):
            if l.get("progress") is not None:              # path3d badges appear as the mover passes their point
                if l not in passed or (latest is not None and l is not latest):
                    continue
                t0 = None
            else:
                t0 = self.cue_t(l.get("at"), 0.3)
                if t < t0:
                    continue
            k = 1.0 if t0 is None else ease_out((t - t0) / 0.35)
            pts = self.anchors.get(l.get("anchor", ""), [])
            if pts:
                x, y = pts[f - 1][0] * self.W, pts[f - 1][1] * self.H
            else:
                x, y = float(l.get("x", 0.5)) * self.W, float(l.get("y", 0.5)) * self.H
            x += float(l.get("dx", 0))
            y += float(l.get("dy", 0))
            size = max(30.0, float(l.get("size", 38)))
            w = D.text_width(l["text"], size, "SemiBold") + 48
            h = size * 1.6
            x = clamp(x - (w if l.get("side") == "left" else 0), 60, 1020 - w)       # inside the safe band
            y = clamp(y - h / 2, 262, 1500 - h)
            for (px, py, pw, ph) in sorted(placed, key=lambda r: r[1]):
                if x < px + pw and px < x + w and y < py + ph + 10 and py < y + h + 10:
                    y = py + ph + 12 if y >= py else py - h - 12
            y = clamp(y, 262, 1500 - h)
            placed.append((x, y, w, h))
            accent = l.get("color") or tpl.conn.get("active", T["accent"])
            rr = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y + (1 - k) * 14, w, h), h / 2, h / 2)
            c.drawRRect(rr, D.paint(col(T["bg0"], 0.92 * k)))
            c.drawRRect(rr, D.paint(col(accent, k), 2.5))
            D.draw_text(c, l["text"], x + 24, y + (1 - k) * 14 + h * 0.66, size, col(T["text"], k), "SemiBold")
