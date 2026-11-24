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
    S = 0.5 if R <= 520 else max(0.1, min(0.5, 4096 / (2 * math.pi * R) * 1.3))   # about one sample per texel when zoomed in: the linear upscale stays smooth, never blocky
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


# ------------------------------------------------------------------ camera view on the flat (equirectangular) map
@functools.lru_cache(maxsize=2)
def world_image(tex: str, gain: float) -> skia.Image:
    """The whole texture as one BGRA image with the brightness gain applied (built once)."""
    t = texture(tex).astype(np.float32) * gain
    rgba = np.empty(t.shape[:2] + (4,), np.uint8)
    rgba[:, :, :3] = np.clip(t, 0, 255).astype(np.uint8)[:, :, [2, 1, 0]]
    rgba[:, :, 3] = 255
    return skia.Image.fromarray(np.ascontiguousarray(rgba), skia.kBGRA_8888_ColorType, skia.kPremul_AlphaType)


@functools.lru_cache(maxsize=1)
def _line_boxes():
    v = vectors()
    out = []
    for key in ("coast", "borders"):
        for line in v[key]:
            a = np.asarray(line, np.float32)
            out.append((key, a, float(a[:, 0].min()), float(a[:, 0].max()), float(a[:, 1].min()), float(a[:, 1].max())))
    return out


@functools.lru_cache(maxsize=8)
def border_paths(lon0: int, lon1: int, lat0: int, lat1: int) -> tuple:
    """Coastlines and borders inside a (10-degree rounded) window, as paths in texture-pixel coordinates."""
    paths = {"coast": skia.Path(), "borders": skia.Path()}
    for key, a, x0, x1, y0, y1 in _line_boxes():
        if x1 < lon0 or x0 > lon1 or y1 < lat0 or y0 > lat1:
            continue
        px = (a[:, 0] + 180.0) / 360.0 * 4096.0
        py = (90.0 - a[:, 1]) / 180.0 * 2048.0
        paths[key].addPoly([skia.Point(float(x), float(y)) for x, y in zip(px, py)], False)
    return paths["coast"], paths["borders"]


class View:
    """A camera on the flat map: centre (lat_c, lon_c) and `span` degrees of longitude across `rect`. Latitude keeps
    the right local proportion (equirectangular with a cos(latitude) correction)."""

    @classmethod
    def at(cls, rect, lat, lon, span):
        v = cls()
        x, y, w, h = rect
        v.rect, v.lat_c, v.lon_c, v.span = rect, lat, lon, span
        v.lat_span = span * math.cos(math.radians(lat)) * h / w
        return v

    @classmethod
    def region(cls, rect, region):
        lon0, lon1, lat0, lat1 = region
        x, y, w, h = rect
        lc = (lat0 + lat1) / 2
        span = max(lon1 - lon0, (lat1 - lat0) * w / h / max(0.2, math.cos(math.radians(lc))))
        return cls.at(rect, lc, (lon0 + lon1) / 2, span)

    def project(self, lat, lon, depth: float = 1.0):
        x, y, w, h = self.rect
        sx = (lon - self.lon_c) / self.span * depth
        sy = (self.lat_c - lat) / self.lat_span * depth
        return x + w / 2 + sx * w, y + h / 2 + sy * h

    def _src(self):
        lon0 = self.lon_c - self.span / 2
        lat1 = self.lat_c + self.lat_span / 2
        return ((lon0 + 180.0) / 360.0 * 4096.0, (90.0 - lat1) / 180.0 * 2048.0,
                self.span / 360.0 * 4096.0, self.lat_span / 180.0 * 2048.0)

    def draw(self, c, tex: str = "night", gain: float = 1.7, alpha: float = 1.0) -> None:
        sx, sy, sw, sh = self._src()
        c.drawImageRect(world_image(tex, round(gain, 2)), skia.Rect.MakeXYWH(sx, sy, sw, sh), skia.Rect.MakeXYWH(*self.rect),
                        skia.SamplingOptions(skia.FilterMode.kLinear), skia.Paint(Alphaf=alpha))

    def borders(self, c) -> None:
        sx, sy, sw, sh = self._src()
        x, y, w, h = self.rect
        lon0, lat1 = self.lon_c - self.span / 2, self.lat_c + self.lat_span / 2
        win = (int(math.floor((lon0 - 5) / 10) * 10), int(math.ceil((lon0 + self.span + 5) / 10) * 10),
               int(math.floor((lat1 - self.lat_span - 5) / 10) * 10), int(math.ceil((lat1 + 5) / 10) * 10))
        coast, bord = border_paths(*win)
        kx, ky = w / sw, h / sh
        c.save()
        c.translate(x, y)
        c.scale(kx, ky)
        c.translate(-sx, -sy)
        wd = 1.0 / math.sqrt(kx * ky)
        c.drawPath(coast, D.paint(col("#7FB4E6", 0.55), 1.7 * wd))
        c.drawPath(bord, D.paint(col("#9CC8F0", 0.45), 1.3 * wd))
        c.restore()


def region_marker(c, tpl, x, y, label, code, k, t, color=None, side="right", W=1080) -> None:
    """An AWS Region: a large ring with a slow pulse, the city label and the Region code."""
    if k <= 0:
        return
    colr = color or "#FFB84D"
    pulse = (t * 0.6) % 1.0
    D.halo(c, x, y, 44, colr, 0.8 * k)
    c.drawCircle(x, y, 22, D.paint(col(colr, k), 4))
    c.drawCircle(x, y, 22 + 26 * pulse, D.paint(col(colr, 0.5 * (1 - pulse) * k), 3))
    c.drawCircle(x, y, 7, D.paint(col("#FFFFFF", k)))
    size, cs = 44.0, 32.0
    w = max(D.text_width(label, size, "SemiBold"), D.text_width(code, cs, "Regular", mono=True))
    slide = (1 - k) * 30
    lx = (x + 40 + slide) if side == "right" else (x - 40 - w - slide)
    lx = clamp(lx, 50, W - 50 - w)
    top = y - size * 0.95
    c.drawRoundRect(skia.Rect.MakeXYWH(lx - 14, top - 8, w + 28, size * 1.3 + cs * 1.25 + 14), 12, 12, D.paint(col("#050B16", 0.85 * k)))
    D.draw_text(c, label, lx, y + size * 0.3, size, col("#F2F6FC", k), "SemiBold")
    if code:
        D.draw_text(c, code, lx, y + size * 0.3 + cs * 1.2, cs, col(colr, k), "Regular", mono=True)


def edge_point(c, tpl, x, y, k, t, color=None, label=None, W=1080) -> None:
    """A CloudFront edge location: a small bright point that flares as it lights up."""
    if k <= 0:
        return
    colr = color or tpl.conn["active"]
    flare = max(0.0, 1.0 - k) * 2 + 0.3 * (0.5 + 0.5 * math.sin(t * 3))
    D.halo(c, x, y, 18 + 14 * flare, colr, 0.9 * k)
    c.drawCircle(x, y, 5, D.paint(col("#FFFFFF", k)))
    if label:
        size = 32.0
        w = D.text_width(label, size, "Medium")
        lx = clamp(x + 18 + (1 - k) * 20, 50, W - 50 - w)
        c.drawRoundRect(skia.Rect.MakeXYWH(lx - 10, y - size * 0.8, w + 20, size * 1.2), 10, 10, D.paint(col("#050B16", 0.78 * k)))
        D.draw_text(c, label, lx, y + size * 0.3, size, col("#DCE7F5", k), "Medium")


def legend(c, tpl, items, x, y) -> None:
    """A small legend plate: AWS Region ring, edge location point (30 px labels)."""
    size = 30.0
    w = max(D.text_width(i["label"], size) for i in items) + 90
    h = len(items) * 50 + 24
    c.drawRoundRect(skia.Rect.MakeXYWH(x, y, w, h), 14, 14, D.paint(col("#050B16", 0.82)))
    for j, it in enumerate(items):
        cy = y + 37 + j * 50
        if it.get("mark") == "region":
            c.drawCircle(x + 34, cy, 13, D.paint(col("#FFB84D"), 3.5))
            c.drawCircle(x + 34, cy, 4, D.paint(col("#FFFFFF")))
        else:
            D.halo(c, x + 34, cy, 14, tpl.conn["active"], 0.9)
            c.drawCircle(x + 34, cy, 5, D.paint(col("#FFFFFF")))
        D.draw_text(c, it["label"], x + 64, cy + size * 0.35, size, col("#DCE7F5"))


# ------------------------------------------------------------------ compact labels (32 px semibold, 30 px mono codes)
class Labels:
    """Places small dark pills so they never overlap each other or the arcs: each label tries right, left, above
    and below its point and takes the first free spot (else the least crowded)."""

    def __init__(self, W, H, band=(240, 1510)):
        self.placed, self.avoid, self.W, self.H, self.band = [], [], W, H, band

    def avoid_points(self, pts, r=10.0):
        self.avoid += [(x - r, y - r, x + r, y + r) for x, y in pts]

    @staticmethod
    def _hit(a, b):
        return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])

    def add(self, c, x, y, name, code="", k=1.0, color="#F2F6FC", code_color="#FFB84D", pref="right", gap=26.0):
        if k <= 0 or not name:
            return
        ns, cs = 32.0, 30.0
        w = max(D.text_width(name, ns, "SemiBold"), D.text_width(code, cs, "Regular", mono=True) if code else 0) + 28
        h = (ns * 1.35 + (cs * 1.2 if code else 0)) + 10
        cands = {"right": (x + gap, y - h / 2), "left": (x - gap - w, y - h / 2), "above": (x - w / 2, y - gap - h),
                 "below": (x - w / 2, y + gap)}
        order = [pref] + [o for o in ("right", "left", "above", "below") if o != pref]
        best, score = None, 1e9
        for o in order:
            lx, ly = cands[o]
            lx = clamp(lx, 40, self.W - 40 - w)
            ly = clamp(ly, self.band[0], self.band[1] - h)
            r = (lx, ly, lx + w, ly + h)
            n = sum(self._hit(r, q) for q in self.placed) * 10 + sum(self._hit(r, q) for q in self.avoid)
            if n < score:
                best, score = r, n
            if n == 0:
                break
        lx, ly, rx, ry = best
        self.placed.append(best)
        slide = (1 - k) * 24
        c.drawRoundRect(skia.Rect.MakeXYWH(lx + slide, ly, rx - lx, ry - ly), 14, 14, D.paint(col("#050B16", 0.78 * k)))
        D.draw_text(c, name, lx + 14 + slide, ly + 5 + ns * 0.95, ns, col(color, k), "SemiBold")
        if code:
            D.draw_text(c, code, lx + 14 + slide, ly + 5 + ns * 1.35 + cs * 0.85, cs, col(code_color, k), "Regular", mono=True)


def small_ring(c, x, y, a=1.0, color="#FFB84D") -> None:
    """An AWS Region in the background layer."""
    c.drawCircle(x, y, 9, D.paint(col(color, 0.85 * a), 2.5))


def small_point(c, x, y, a=1.0, color="#38D6F5") -> None:
    """A CloudFront edge location in the background layer."""
    D.halo(c, x, y, 11, color, 0.7 * a)
    c.drawCircle(x, y, 3.2, D.paint(col("#FFFFFF", 0.95 * a)))


def focus_pulse(c, x, y, k, t, color="#38D6F5") -> None:
    """A bright pulse on a place the camera has just arrived at."""
    if k <= 0:
        return
    for j in range(2):
        q = ((t * 0.9) + j * 0.5) % 1.0
        c.drawCircle(x, y, 14 + 46 * q, D.paint(col(color, 0.7 * (1 - q) * k), 4))
    D.halo(c, x, y, 34, color, k)
    c.drawCircle(x, y, 8, D.paint(col("#FFFFFF", k)))


def alert_pulse(c, x, y, k, t) -> None:
    """A red pulse for a place under heavy load."""
    if k <= 0:
        return
    red = "#FF5A5A"
    for j in range(3):
        q = ((t * 1.4) + j / 3) % 1.0
        c.drawCircle(x, y, 18 + 70 * q, D.paint(col(red, 0.8 * (1 - q) * k), 5))
    D.halo(c, x, y, 56, red, k)
    c.drawCircle(x, y, 11, D.paint(col("#FFFFFF", k)))
