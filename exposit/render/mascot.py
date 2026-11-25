"""The channel owner's pixel mascot (assets/brand/clawd-sunglasses.png, 48x48), animated without redrawing it.

Pixel-art rules: integer scale only (3x or 4x), nearest-neighbour sampling, no blur, original colours. The sprite is
split into two layers from its own pixels: GLASSES (the black pixels) and BODY (everything else, with the glasses'
area filled with the sampled body colour plus two small dark square eyes). Squash and stretch resample the 48x48
source on its own pixel grid (nearest), so every drawn pixel is still a whole, unblended sprite pixel.

Moves: idle bob, hop (squash, arc, stretch, landing squash, dust), walk (2-frame waddle with a tilt), drop-in,
glasses drop (lift, blink, slide down in 2 px steps, 1 px bounce, shine), peek, tap, shake, into/out of a folder.

A scene's "mascot" spec: {"scale": 3, "pos": [x, y], "acts": [{"type", "at": cue, "to": [x, y], ...}]}; (x, y) is
the point under the feet, centre bottom, in 1080x1920 screen space.
"""
from __future__ import annotations
import functools, math
from pathlib import Path
import numpy as np
import skia
from . import design as D
from .design import clamp, ease_out, ease_in_out, lerp

SRC = Path(__file__).resolve().parents[2] / "assets" / "brand" / "clawd-sunglasses.png"
FPS = 30.0
DUST = "#9A938B"


def available() -> bool:
    return SRC.exists()


@functools.lru_cache(maxsize=1)
def layers() -> dict:
    """BODY and GLASSES as RGBA uint8 arrays, plus the geometry found in the sprite."""
    img = skia.Image.open(str(SRC)).convert(alphaType=skia.kUnpremul_AlphaType, colorType=skia.kRGBA_8888_ColorType)
    a = np.array(img).copy()
    op = a[..., 3] > 0
    dark = op & (a[..., :3].astype(int).sum(-1) < 120)
    body_px = a[op & ~dark][:, :4]
    vals, counts = np.unique(body_px.reshape(-1, 4), axis=0, return_counts=True)
    body_col = vals[counts.argmax()]                       # the sampled body colour
    glasses = np.zeros_like(a)
    glasses[dark] = a[dark]
    body = a.copy()
    body[dark] = body_col
    ys, xs = np.nonzero(dark)
    g = dict(top=int(ys.min()), bottom=int(ys.max()), left=int(xs.min()), right=int(xs.max()))
    # the lenses: dark columns below the bridge rows; one eye centred in each lens
    bridge = [y for y in range(g["top"], g["bottom"] + 1) if dark[y].sum() > 0.6 * (g["right"] - g["left"])]
    lens_y0 = max(bridge) + 1
    cols = np.nonzero(dark[lens_y0])[0]
    runs, start = [], cols[0]
    for p, q in zip(cols, cols[1:]):
        if q != p + 1:
            runs.append((start, p)); start = q
    runs.append((start, cols[-1]))
    eye = max(2, (g["bottom"] - lens_y0 + 1) // 2)         # small square eyes, in the sprite's own block size
    eyes = [((x0 + x1 + 1) // 2 - eye // 2, (lens_y0 + g["bottom"] + 1) // 2 - eye // 2) for x0, x1 in runs[:2]]
    op_rows = np.nonzero(op.any(1))[0]
    return dict(body=body, glasses=glasses, body_col=tuple(int(v) for v in body_col), eyes=eyes, eye=eye,
                lens=(runs[0][0], lens_y0, runs[-1][1], g["bottom"]), top=int(op_rows.min()), h=a.shape[0], w=a.shape[1])


def _resample(arr: np.ndarray, sx: float, sy: float) -> np.ndarray:
    """Nearest-neighbour resample on the source grid, anchored at the bottom centre (squash and stretch)."""
    h, w = arr.shape[:2]
    nh, nw = max(1, round(h * sy)), max(1, round(w * sx))
    yi = np.clip((np.arange(nh) / sy).astype(int), 0, h - 1)
    xi = np.clip(((np.arange(nw) - nw / 2 + 0.5) / sx + w / 2).astype(int), 0, w - 1)
    return arr[yi][:, xi]


def frame(t_blink: bool = False, glasses_dy: int = 0, eye_dx: int = 0, shine: float = -1.0, glasses: bool = True,
          walk: int = -1, tilt: int = 0) -> np.ndarray:
    """One composed 48x48 frame (RGBA uint8)."""
    L = layers()
    out = L["body"].copy()
    k = L["eye"]
    for (ex, ey) in L["eyes"]:
        if t_blink:
            out[ey + k // 2, ex + eye_dx:ex + eye_dx + k] = (20, 20, 20, 255)
        else:
            out[ey:ey + k, ex + eye_dx:ex + eye_dx + k] = (20, 20, 20, 255)
    if glasses:
        g = np.roll(L["glasses"], glasses_dy, axis=0)
        if glasses_dy < 0:
            g[glasses_dy:] = 0
        m = g[..., 3] > 0
        out[m] = g[m]
        if shine >= 0:                                    # a 2-pixel white glint sweeping across the lenses
            x0, y0, x1, y1 = L["lens"]
            sx = int(lerp(x0 - 2, x1 + 2, shine))
            for d in range(2):
                for yy in range(y0 + glasses_dy, y1 + 1 + glasses_dy):
                    xx = sx + d - (yy - y0 - glasses_dy) // 2
                    if 0 <= yy < out.shape[0] and 0 <= xx < out.shape[1] and m[yy, xx]:
                        out[yy, xx] = (255, 255, 255, 255)
    if walk >= 0:                                         # 2-frame waddle: lift one pair of legs by a block
        legs_top = out.shape[0] - 6
        half = out.shape[1] // 2
        sl = slice(0, half) if walk == 0 else slice(half, out.shape[1])
        seg = out[legs_top:, sl].copy()
        out[legs_top:, sl] = 0
        out[legs_top - 3:out.shape[0] - 3, sl] = np.where(seg[..., 3:] > 0, seg, out[legs_top - 3:out.shape[0] - 3, sl])
    if tilt:                                              # lean: upper rows shift a pixel or two
        top = L["top"]
        for yy in range(top, top + 15):
            out[yy] = np.roll(out[yy], tilt * (2 if yy < top + 8 else 1), axis=0)
    return out


def blit(c, arr: np.ndarray, x: float, y: float, scale: int, clip_y: float | None = None, alpha: float = 1.0,
         rim: str | None = None, shadow: bool = False) -> None:
    """Draws a frame with its feet (bottom centre) at (x, y), integer scale, nearest sampling, snapped to the grid."""
    img = skia.Image.fromarray(np.ascontiguousarray(arr), skia.kRGBA_8888_ColorType)
    h, w = arr.shape[:2]
    x0 = round(x - w * scale / 2)
    y0 = round(y - h * scale)
    c.save()
    if clip_y is not None:
        c.clipRect(skia.Rect.MakeLTRB(-100, -100, 2000, clip_y))
    if shadow:                                            # a small warm ground shadow under the feet
        sp = D.blur(D.paint(D.col("#000000", 0.55 * alpha)), 6)
        c.drawOval(skia.Rect.MakeXYWH(x - w * scale * 0.36, y - 8, w * scale * 0.72, 16), sp)
    if rim:                                               # a 1-pixel cream rim: the silhouette, offset, at half opacity
        sil = np.zeros_like(arr)
        sil[..., :3] = [int(rim[i:i + 2], 16) for i in (1, 3, 5)]
        sil[..., 3] = (arr[..., 3] > 0) * 255
        simg = skia.Image.fromarray(np.ascontiguousarray(sil), skia.kRGBA_8888_ColorType)
        rp = skia.Paint(Alphaf=0.5 * alpha)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            c.drawImageRect(simg, skia.Rect.MakeXYWH(x0 + dx * scale, y0 + dy * scale, w * scale, h * scale),
                            skia.SamplingOptions(skia.FilterMode.kNearest), rp)
    p = skia.Paint(Alphaf=alpha) if alpha < 1 else None
    c.drawImageRect(img, skia.Rect.MakeXYWH(x0, y0, w * scale, h * scale),
                    skia.SamplingOptions(skia.FilterMode.kNearest), p)
    c.restore()


# ================================================================== timeline
HOP = 0.37          # 1 squash frame, 9 arc frames, 1 landing frame
GLASSES = 0.8


def _glasses(u: float) -> dict:
    """The 0.8 s glasses drop at u seconds: up on the head, a blink, a slide down in 2 px steps, a 1 px bounce,
    a shine across the lenses."""
    if u < 0.2:
        return dict(glasses_dy=-12)
    if u < 0.32:
        return dict(glasses_dy=-12, t_blink=u < 0.28)
    if u < 0.52:
        k = (u - 0.32) / 0.2
        return dict(glasses_dy=-12 + 2 * int(6 * k + 1e-6))
    if u < 0.58:
        return dict(glasses_dy=1)
    shine = (u - 0.58) / 0.22
    return dict(glasses_dy=0, shine=clamp(shine) if shine < 1 else -1.0)


class Mascot:
    def __init__(self, spec: dict, cue_t):
        self.scale = int(spec.get("scale", 3))
        self.pos = tuple(spec.get("pos", (900, 1880)))
        self.acts = []
        for a in spec.get("acts", []):
            t0 = cue_t(a.get("at"), 0.0) + float(a.get("delay", 0.0))
            self.acts.append(dict(a, t0=t0))
        self.acts.sort(key=lambda a: a["t0"])
        self.events: list[tuple[str, float, dict]] = []   # for the diagram: taps, folder in/out, block

    def _move_dur(self, a, frm):
        if a["type"] == "hop":
            return HOP + float(a.get("extra", 0.0))
        if a["type"] == "walk":
            return max(0.4, abs(a["to"][0] - frm[0]) / float(a.get("speed", 190)))
        if a["type"] == "drop_in":
            return 0.55
        if a["type"] in ("into_folder",):
            return HOP + 0.25
        return 0.0

    def state(self, t: float):
        """(x, y, frame kwargs, sx, sy, clip_y, dust list, visible)."""
        x, y = self.pos
        kw: dict = {}
        sx = sy = 1.0
        clip = None
        dust = []
        visible = True
        busy_until = -1.0
        if self.acts and self.acts[0]["type"] == "drop_in" and t < self.acts[0]["t0"]:
            visible = False                                   # not on screen before it drops in
        for a in self.acts:
            if t < a["t0"]:
                break
            typ, u = a["type"], t - a["t0"]
            to = tuple(a.get("to", (x, y)))
            d = self._move_dur(a, (x, y))
            if typ in ("hop", "drop_in", "into_folder", "out_of_folder"):
                if typ == "out_of_folder":
                    d = HOP
                    visible = True
                land = u - d
                if u < d:
                    if typ == "drop_in":
                        k = clamp(u / d)
                        x, y = to[0], lerp(-80.0, to[1], k * k)
                        sy, sx = (1.12, 0.92) if k > 0.3 else (1.0, 1.0)
                    else:
                        if u < 1 / FPS:                       # squash before take-off
                            sx, sy = 1.15, 0.84
                        else:
                            k = ease_out((u - 1 / FPS) / (d - 1 / FPS))
                            h = max(60.0, 0.32 * math.hypot(to[0] - x, to[1] - y))
                            x, y = lerp(x, to[0], k), lerp(y, to[1], k) - h * 4 * k * (1 - k)
                            sx, sy = (0.9, 1.12) if k < 0.4 else (1.0, 1.0)   # stretch on the way up
                        if typ == "into_folder":
                            clip = to[1] - 6 if (u / d) > 0.55 else None
                    busy_until = a["t0"] + d
                    continue
                x, y = to
                if typ == "into_folder":
                    visible = land > float(a.get("hold", 1e9))
                    if not visible:
                        continue
                if land < 2 / FPS:                            # landing squash
                    sx, sy = 1.18, 0.82
                if land < 0.45:
                    dust = [(to[0] + s * (20 + 90 * land / 0.45) * self.scale / 3, to[1] - 4 - 30 * land, 1 - land / 0.45)
                            for s in (-1.0, -0.55, 0.55, 1.0)]
                busy_until = max(busy_until, a["t0"] + d + 2 / FPS)
            elif typ == "walk":
                if u < d:
                    k = u / d
                    x = lerp(x, to[0], k)
                    y = lerp(y, to[1], k)
                    kw = dict(walk=int(u / 0.12) % 2, tilt=1 if to[0] > a.get("_from", x) else -1)
                    busy_until = a["t0"] + d
                    continue
                x, y = to
        # overlays on the current pose
        for a in self.acts:
            if t < a["t0"]:
                break
            u = t - a["t0"]
            typ = a["type"]
            if typ == "glasses" and u < GLASSES:
                kw.update(_glasses(u))
            elif typ == "peek" and u < float(a.get("dur", 2.0)):
                dur = float(a.get("dur", 2.0))
                if u < 0.25:
                    kw.update(glasses_dy=-int(12 * u / 0.25) // 2 * 2)
                elif u < dur - GLASSES:
                    kw.update(glasses_dy=-12, eye_dx=(-3 if ((u - 0.25) // 0.45) % 2 == 0 else 3))
                else:
                    kw.update(_glasses(u - (dur - GLASSES)))
            elif typ == "tap" and u < 0.5:
                kw.update(tilt=int(a.get("dir", -1)) * (1 if u < 0.25 else 0))
            elif typ == "shake" and u < 0.45:
                x += (6 if int(u / 0.075) % 2 == 0 else -6)
        if not kw and t > busy_until + 0.05 and visible:     # idle: a 1 px bob every 0.5 s (in screen pixels: one
            y -= self.scale * (int(t / 0.5) % 2)              # sprite pixel at the drawn scale)
        return x, y, kw, sx, sy, clip, dust, visible

    def draw(self, c, t: float, alpha: float = 1.0, to_screen=None, rim: str | None = None, shadow: bool = False) -> None:
        if not available():
            return
        x, y, kw, sx, sy, clip, dust, visible = self.state(t)
        if to_screen:
            x, y = to_screen(x, y)
            dust = [(*to_screen(dx, dy), a) for dx, dy, a in dust]
            clip = to_screen(0, clip)[1] if clip is not None else None
        for (dx, dy, a) in dust:
            sz = self.scale * 2
            c.drawRect(skia.Rect.MakeXYWH(round(dx - sz / 2), round(dy - sz), sz, sz), D.paint(D.col(DUST, max(0.0, a) * alpha)))
        if not visible:
            return
        arr = frame(**kw)
        if sx != 1.0 or sy != 1.0:
            arr = _resample(arr, sx, sy)
        blit(c, arr, x, y, self.scale, clip, alpha, rim, shadow and visible)
