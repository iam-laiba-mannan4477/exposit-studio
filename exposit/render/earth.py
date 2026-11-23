"""The real Earth: NASA Blue Marble (day) and Black Marble (night) textures on an orthographic sphere, computed in numpy,
and a flat (equirectangular) regional map from the same textures with Natural Earth 50m borders, coastlines and places.

Globe: per pixel inside the disc the inverse orthographic projection gives lat/lon; the day and night textures are
sampled there and blended across the terminator by the sun direction; the limb darkens and a thin atmosphere ring
glows outside it. Work is done at half resolution and drawn scaled up with linear filtering (the textures are 4096 px
wide, so this loses nothing visible) as one BGRA premultiplied image, the fast path in this skia build.
Assets: exposit/assets/earth (built by scripts/build_earth_assets.py; see exposit/assets/LICENSES.md).
"""
from __future__ import annotations
import functools, json, math
import numpy as np
import skia
from . import design as D
from .design import col, clamp, ease_out, ease_in_out

ASSETS = D.ASSETS / "earth" if hasattr(D, "ASSETS") else None
CREDIT = "Imagery: NASA Earth Observatory. Map data: Natural Earth."
ATMOS = np.array([90, 170, 255], np.float32)               # atmosphere glow colour (RGB)


def _dir():
    from pathlib import Path
    return Path(__file__).resolve().parent.parent / "assets" / "earth"


@functools.lru_cache(maxsize=2)
def texture(name: str) -> np.ndarray:
    """(2048, 4096, 3) uint8, equirectangular, row 0 at 90 N, column 0 at 180 W."""
    from PIL import Image
    return np.asarray(Image.open(_dir() / f"{name}-4096.jpg").convert("RGB"))


@functools.lru_cache(maxsize=2)
def packed(name: str) -> np.ndarray:
    """The texture as one uint32 per texel (RGBA bytes), so a lookup is a single gather."""
    t = texture(name)
    a = np.empty(t.shape[:2] + (4,), np.uint8)
    a[:, :, :3] = t
    a[:, :, 3] = 255
    return a.reshape(-1).view(np.uint32)


@functools.lru_cache(maxsize=1)
def vectors() -> dict:
    return json.loads((_dir() / "vectors-50m.json").read_text(encoding="utf-8"))


ALIASES = {"sao paulo": "São Paulo", "new york": "New York", "washington": "Washington, D.C."}


@functools.lru_cache(maxsize=256)
def place(name: str) -> tuple[float, float] | None:
    """(lat, lon) of a Natural Earth populated place; the most populous one when names repeat (Sydney, Australia)."""
    key = ALIASES.get(name.lower().strip(), name).lower()
    cands = [p for p in vectors()["places"] if (p["name"] or "").lower() == key or (p["ascii"] or "").lower() == key]
    if not cands:
        return None
    p = max(cands, key=lambda p: p["pop"])
    return p["lat"], p["lon"]


def resolve(pt: dict) -> tuple[float, float]:
    if "lat" in pt and "lon" in pt:
        return float(pt["lat"]), float(pt["lon"])
    ll = place(pt.get("place") or pt.get("name") or "")
    if ll is None:
        raise ValueError(f"Unknown place {pt.get('place') or pt.get('name')}")
    return ll


def _unit(lat: float, lon: float) -> np.ndarray:
    la, lo = math.radians(lat), math.radians(lon)
    return np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])


# ------------------------------------------------------------------ globe
class Globe:
    """An orthographic view centred on (lat0, lon0), disc radius R px, centre (cx, cy) on a W x H frame."""

    def __init__(self, W, H, cx, cy, R, lat0, lon0):
        self.W, self.H, self.cx, self.cy, self.R = W, H, cx, cy, R
        self.lat0, self.lon0 = lat0, lon0
        self.s0, self.c0 = math.sin(math.radians(lat0)), math.cos(math.radians(lat0))

    def project(self, lat: float, lon: float, alt: float = 0.0):
        """Screen (x, y) and whether the point faces the viewer. alt lifts a point above the surface (arcs)."""
        la, dl = math.radians(lat), math.radians(lon - self.lon0)
        x = math.cos(la) * math.sin(dl)
        y = self.c0 * math.sin(la) - self.s0 * math.cos(la) * math.cos(dl)
        cosc = self.s0 * math.sin(la) + self.c0 * math.cos(la) * math.cos(dl)
        r = self.R * (1.0 + alt)
        vis = cosc > 0 or (alt > 0 and (x * x + y * y) * (1 + alt) ** 2 > 1.0)
        return self.cx + r * x, self.cy - r * y, vis

    def render(self, c, sun: tuple[float, float] | None, night_gain: float = 1.6, alpha: float = 1.0) -> None:
        img = _globe_image(int(self.W), int(self.H), round(self.cx, 1), round(self.cy, 1), round(self.R, 1),
                           round(self.lat0, 3), round(self.lon0, 3), sun, night_gain)
        if img is None:
            return
        im, x0, y0, w, h = img
        p = skia.Paint(Alphaf=alpha)
        c.drawImageRect(im, skia.Rect.MakeXYWH(x0, y0, w, h), skia.SamplingOptions(skia.FilterMode.kLinear), p)


@functools.lru_cache(maxsize=6)
def _globe_image(W, H, cx, cy, R, lat0, lon0, sun, night_gain):
    S = 0.5 if R <= 520 else max(0.3, 0.5 * 520 / R)       # half resolution; less when zoomed in (the texture is coarser)
    A = 1.10                                                  # atmosphere reaches 10% beyond the limb
    x0, x1 = max(0.0, cx - R * A), min(float(W), cx + R * A)
    y0, y1 = max(0.0, cy - R * A), min(float(H), cy + R * A)
    if x1 <= x0 or y1 <= y0:
        return None
    nw, nh = max(2, int((x1 - x0) * S)), max(2, int((y1 - y0) * S))
    xs = (x0 + (np.arange(nw, dtype=np.float32) + 0.5) / S - cx) / R
    ys = (cy - (y0 + (np.arange(nh, dtype=np.float32) + 0.5) / S)) / R
    X, Y = np.meshgrid(xs, ys)
    rho2 = X * X + Y * Y
    inside = rho2 < 1.0
    out = np.zeros((nh, nw, 4), np.float32)
    s0, c0 = math.sin(math.radians(lat0)), math.cos(math.radians(lat0))
    xi, yi = X[inside], Y[inside]
    z = np.sqrt(1.0 - rho2[inside])
    lat = np.arcsin(np.clip(z * s0 + yi * c0, -1, 1))
    lon = math.radians(lon0) + np.arctan2(xi, z * c0 - yi * s0)
    th, tw = 2048, 4096
    u = ((lon / (2 * math.pi) + 0.5) % 1.0 * tw).astype(np.int32) % tw
    v = np.clip(((0.5 - lat / math.pi) * th).astype(np.int32), 0, th - 1)
    idx = v * tw + u
    nt = packed("night")[idx].view(np.uint8).reshape(-1, 4)[:, :3].astype(np.float32) * night_gain
    limb = (0.35 + 0.65 * z)[:, None]
    if sun is None:                                           # all night
        rgb = nt * limb
    else:
        dt = packed("day")[idx].view(np.uint8).reshape(-1, 4)[:, :3].astype(np.float32)
        sv = _unit(*sun)
        cl = np.cos(lat)
        d = cl * np.cos(lon) * sv[0] + cl * np.sin(lon) * sv[1] + np.sin(lat) * sv[2]
        w = np.clip((d + 0.08) / 0.24, 0, 1)[:, None]         # soft terminator
        w = w * w * (3 - 2 * w)
        rgb = (dt * (0.25 + 0.75 * np.clip(d, 0, 1))[:, None] * w + nt * (1 - w)) * limb
    out[inside, :3] = np.clip(rgb, 0, 255)
    out[inside, 3] = 255.0
    ring = (~inside) & (rho2 < A * A)                         # atmosphere: premultiplied glow fading outwards
    k = 1.0 - (np.sqrt(rho2[ring]) - 1.0) / (A - 1.0)
    a = (k ** 3.0) * 150.0
    out[ring, :3] = ATMOS[None, :] * (a / 255.0)[:, None]
    out[ring, 3] = a
    rim = inside & (rho2 > 0.93)                              # blue haze just inside the limb
    hz = ((np.sqrt(rho2[rim]) - 0.9645) / 0.0355).clip(0, 1)[:, None] * 0.55
    out[rim, :3] = out[rim, :3] * (1 - hz) + ATMOS[None, :] * hz
    bgra = np.ascontiguousarray(out[:, :, [2, 1, 0, 3]].astype(np.uint8))
    im = skia.Image.fromarray(bgra, skia.kBGRA_8888_ColorType, skia.kPremul_AlphaType)
    return im, x0, y0, nw / S, nh / S


def great_circle(a: tuple[float, float], b: tuple[float, float], n: int = 64) -> list[tuple[float, float, float]]:
    """(lat, lon, f) points from a to b along the great circle; f runs 0..1."""
    p0, p1 = _unit(*a), _unit(*b)
    om = math.acos(clamp(float(p0 @ p1), -1.0, 1.0)) or 1e-6
    out = []
    for i in range(n + 1):
        f = i / n
        v = (math.sin((1 - f) * om) * p0 + math.sin(f * om) * p1) / math.sin(om)
        out.append((math.degrees(math.asin(clamp(v[2], -1, 1))), math.degrees(math.atan2(v[1], v[0])), f))
    return out


def light_trail(c, pts: list[tuple[float, float]], head: float, color: str, a: float = 1.0, length: float = 0.22,
                width: float = 7.0) -> None:
    """A packet travelling along a polyline with a fading light trail behind it (head and length in 0..1)."""
    n = len(pts) - 1
    if n < 1 or head <= 0:
        return
    h = min(head, 1.0)
    i1 = h * n
    i0 = max(0.0, i1 - length * n)
    steps = 14
    prev = None
    for s in range(steps + 1):
        f = i0 + (i1 - i0) * s / steps
        k = int(min(f, n - 1))
        t = f - k
        x = pts[k][0] + (pts[k + 1][0] - pts[k][0]) * t
        y = pts[k][1] + (pts[k + 1][1] - pts[k][1]) * t
        if prev:
            q = s / steps
            c.drawLine(prev[0], prev[1], x, y, D.paint(col(color, a * q * 0.9), width * (0.4 + 0.6 * q)))
        prev = (x, y)
    if head < 1.0:
        D.halo(c, prev[0], prev[1], 34, color, a)
        c.drawCircle(prev[0], prev[1], 9, D.paint(col("#FFFFFF", a)))


# ------------------------------------------------------------------ flat regional map
class FlatMap:
    """Equirectangular view of [lon0, lon1] x [lat0, lat1] filling (x, y, w, h); the window widens to fit."""

    def __init__(self, rect, region):
        x, y, w, h = rect
        lon0, lon1, lat0, lat1 = region
        lc = (lat0 + lat1) / 2
        k = math.cos(math.radians(lc))                       # keep shapes right at mid-latitude
        dl, dp = (lon1 - lon0) * k, lat1 - lat0
        if dl / dp > w / h:
            dp = dl * h / w
        else:
            dl = dp * w / h
        cl, cp = (lon0 + lon1) / 2, lc
        self.lon0, self.lon1 = cl - dl / k / 2, cl + dl / k / 2
        self.lat0, self.lat1 = cp - dp / 2, cp + dp / 2
        self.rect = rect

    def project(self, lat, lon):
        x, y, w, h = self.rect
        return x + (lon - self.lon0) / (self.lon1 - self.lon0) * w, y + (self.lat1 - lat) / (self.lat1 - self.lat0) * h

    def render(self, c, tex: str = "night", gain: float = 1.6, borders: bool = True, alpha: float = 1.0) -> None:
        im = _flat_image(tuple(round(v, 1) for v in self.rect), round(self.lon0, 3), round(self.lon1, 3),
                         round(self.lat0, 3), round(self.lat1, 3), tex, gain, borders)
        c.drawImage(im, self.rect[0], self.rect[1], skia.SamplingOptions(), skia.Paint(Alphaf=alpha))


@functools.lru_cache(maxsize=4)
def _flat_image(rect, lon0, lon1, lat0, lat1, tex, gain, borders):
    x, y, w, h = rect
    W, H = int(w), int(h)
    t = texture(tex)
    th, tw = t.shape[:2]
    us = ((np.linspace(lon0, lon1, W) + 180) / 360 * tw).astype(np.int32) % tw
    vs = np.clip(((90 - np.linspace(lat1, lat0, H)) / 180 * th).astype(np.int32), 0, th - 1)
    img = t[vs[:, None], us[None, :]].astype(np.float32) * gain
    rgba = np.empty((H, W, 4), np.uint8)
    rgba[:, :, :3] = np.clip(img, 0, 255).astype(np.uint8)[:, :, [2, 1, 0]]
    rgba[:, :, 3] = 255
    surf = skia.Surface(W, H)
    cc = surf.getCanvas()
    cc.drawImage(skia.Image.fromarray(np.ascontiguousarray(rgba), skia.kBGRA_8888_ColorType, skia.kPremul_AlphaType), 0, 0)
    if borders:
        fm = FlatMap.__new__(FlatMap)
        fm.lon0, fm.lon1, fm.lat0, fm.lat1, fm.rect = lon0, lon1, lat0, lat1, (0, 0, W, H)
        v = vectors()
        for key, colr, wd in (("coast", "#7FB4E6", 1.6), ("borders", "#9CC8F0", 1.2)):
            p = skia.Path()
            for line in v[key]:
                if all(not (lon0 - 5 <= q[0] <= lon1 + 5 and lat0 - 5 <= q[1] <= lat1 + 5) for q in line[::4]):
                    continue
                for i, q in enumerate(line):
                    px, py = fm.project(q[1], q[0])
                    (p.moveTo if i == 0 else p.lineTo)(px, py)
            cc.drawPath(p, D.paint(col(colr, 0.55 if key == "coast" else 0.4), wd))
    snap = surf.makeImageSnapshot()
    arr = snap.toarray(colorType=skia.kBGRA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
    return skia.Image.fromarray(np.ascontiguousarray(arr), skia.kBGRA_8888_ColorType, skia.kPremul_AlphaType)


def city_marker(c, tpl, x, y, label: str | None, k: float, t: float, color: str | None = None, hub: bool = False,
                side: str = "right", size: float = 40, W: float = 1080) -> None:
    """A glowing city light with a pulse ring and a label on a dark plate."""
    if k <= 0:
        return
    colr = color or tpl.conn["active"]
    pulse = (t * 0.8) % 1.0
    D.halo(c, x, y, (40 if hub else 28), colr, 0.9 * k)
    c.drawCircle(x, y, 26 + 30 * pulse, D.paint(col(colr, 0.55 * (1 - pulse) * k), 3))
    c.drawCircle(x, y, 9 if hub else 7, D.paint(col("#FFFFFF", k)))
    if label:
        w = D.text_width(label, size, "SemiBold")
        lx = x + 30 if side == "right" else x - 30 - w
        lx = clamp(lx, 50, W - 50 - w)
        ly = y + size * 0.35
        c.drawRoundRect(skia.Rect.MakeXYWH(lx - 14, ly - size * 0.95, w + 28, size * 1.35), 12, 12,
                        D.paint(col("#050B16", 0.82 * k)))
        D.draw_text(c, label, lx, ly, size, col("#F2F6FC", k), "SemiBold")


def credit(c, W, y, a: float = 1.0) -> None:
    """The imagery credit: a small line in the bottom corner, inside the safe area."""
    D.draw_text(c, CREDIT, W - 60, y, 30, col("#AEBBD0", 0.9 * a), "Regular", "right")
