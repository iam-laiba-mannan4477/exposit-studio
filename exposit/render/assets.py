"""Vendored assets for the renderer: SVG icons (Lucide, Kubernetes), fonts and the world map.

Everything is read from exposit/assets/ (licences in exposit/assets/LICENSES.md). Nothing is fetched at render time.
Parsed icons are cached per (name, colour, stroke width); the map is parsed once and cached as Skia paths per
projection and size.
"""
from __future__ import annotations
import functools, json, math
from pathlib import Path
import skia
from .. import config

ASSETS = config.ASSETS
ICON_DIRS = {"lucide": ASSETS / "icons" / "lucide", "k8s": ASSETS / "icons" / "k8s"}
K8S_BLUE = "#326ce5"


@functools.lru_cache(maxsize=1)
def icon_names() -> dict[str, str]:
    """Every icon name the renderer accepts, mapped to its family. Lucide names are plain ('server');
    Kubernetes names carry a prefix ('k8s:pod')."""
    out = {}
    for fam, d in ICON_DIRS.items():
        for p in sorted(d.glob("*.svg")):
            out[p.stem if fam == "lucide" else f"k8s:{p.stem}"] = fam
    return out


# Friendly aliases the AI roles may use; each resolves to a vendored file.
ALIASES = {
    "phone": "smartphone", "mobile": "smartphone", "server-stack": "server", "storage": "hard-drive", "disk": "hard-drive",
    "memory": "memory-stick", "ram": "memory-stick", "queue": "list", "list-queue": "list", "alert": "triangle-alert",
    "warning": "triangle-alert", "refresh": "refresh-cw", "retry": "rotate-ccw", "location": "map-pin", "pin": "map-pin",
    "world": "globe", "internet": "globe", "dns": "globe", "browser": "monitor", "client": "laptop", "desktop": "monitor",
    "cdn": "cloud", "edge": "server", "origin": "server-cog", "cache": "database-zap", "db": "database", "load-balancer": "split",
    "lb": "split", "gateway": "router", "firewall": "shield", "tls": "lock", "https": "lock", "secret": "key", "auth": "fingerprint",
    "latency": "timer", "speed": "gauge", "fast": "zap", "ok": "check", "hit": "circle-check", "miss": "circle-x", "fail": "circle-x",
    "error": "circle-x", "success": "circle-check", "code-file": "file-code", "config": "file-code", "logs": "file-text",
    "message": "message-square", "event": "send", "branch": "git-branch", "deploy": "rocket", "metrics": "activity",
    "pod": "k8s:pod", "service": "k8s:svc", "ingress": "k8s:ing", "deployment": "k8s:deploy", "replicaset": "k8s:rs",
    "statefulset": "k8s:sts", "daemonset": "k8s:ds", "job": "k8s:job", "configmap": "k8s:cm", "pvc": "k8s:pvc",
    "hpa": "k8s:hpa", "namespace": "k8s:ns", "node": "k8s:node", "k8s-node": "k8s:node", "control-plane": "k8s:control-plane",
}

# The icon an element of a given kind gets when its spec names none. Old specs gain icons this way.
KIND_ICON = {
    "browser": "monitor", "client": "laptop", "user": "user", "users": "users", "phone": "smartphone", "dns": "globe",
    "lb": "split", "nginx": "server-cog", "ingress": "k8s:ing", "service": "k8s:svc", "pod": "k8s:pod", "node": "server",
    "zone": "layers", "region": "map-pin", "group": "layers", "datacenter": "building-2", "db": "database", "queue": "list",
    "hub": "network", "gateway": "router", "cdn": "cloud", "edge": "server", "cache": "database-zap", "router": "router",
    "server": "server", "origin": "server-cog", "worker": "cpu", "replica": "database", "item": "file", "panel": "file-code",
    "component": "box", "storage": "hard-drive", "instance": "server", "switch": "network", "balancer": "split",
    "firewall": "shield", "secret": "key", "file": "file", "code": "code", "api": "braces", "function": "zap",
}


def resolve(name: str | None) -> str | None:
    """A known icon name, or None. Accepts aliases and the 'lucide:' prefix."""
    if not name:
        return None
    n = str(name).strip().lower().removeprefix("lucide:")
    n = ALIASES.get(n, n)
    return n if n in icon_names() else None


def icon_for(el: dict) -> str | None:
    """The icon for an element: its own 'icon' if valid, else the one for its kind."""
    return resolve(el.get("icon")) or resolve(KIND_ICON.get(el.get("kind", ""), ""))


def icon_file(name: str) -> Path:
    fam = icon_names()[name]
    return ICON_DIRS[fam] / (name.split(":", 1)[1] + ".svg" if fam == "k8s" else name + ".svg")


@functools.lru_cache(maxsize=1024)
def _dom(name: str, color: str, stroke: float, glyph: str):
    data = icon_file(name).read_text(encoding="utf-8")
    if icon_names()[name] == "k8s":
        data = data.replace(K8S_BLUE, color).replace("#ffffff", glyph).replace("#FFFFFF", glyph)
    else:
        data = data.replace("currentColor", color).replace('stroke-width="2"', f'stroke-width="{stroke:g}"')
    dom = skia.SVGDOM.MakeFromStream(skia.MemoryStream(data.encode("utf-8"), True))
    sz = dom.containerSize()
    native = max(sz.width(), sz.height())
    rec = skia.PictureRecorder()
    pc = rec.beginRecording(skia.Rect.MakeWH(native, native))
    dom.render(pc)
    return rec.finishRecordingAsPicture(), native


def draw_icon(c: skia.Canvas, name: str | None, cx: float, cy: float, size: float, color: str,
              alpha: float = 1.0, stroke: float = 2.0, glyph: str = "#FFFFFF") -> bool:
    """Draws an icon centred on (cx, cy), `size` pixels wide. Colours are hex strings. Returns False if unknown."""
    name = resolve(name)
    if not name or alpha <= 0.01 or size <= 1:
        return False
    pic, native = _dom(name, color.upper(), round(stroke, 2), glyph.upper())
    k = size / native
    m = skia.Matrix.Translate(cx - size / 2, cy - size / 2)
    m.preScale(k, k)
    c.drawPicture(pic, m, skia.Paint(Alphaf=alpha) if alpha < 0.999 else None)
    return True


# ------------------------------------------------------------------ fonts
FONT_FILES = {"Inter-Regular": "Inter-Regular.otf", "Inter-Medium": "Inter-Medium.otf", "Inter-SemiBold": "Inter-SemiBold.otf",
              "Inter-Bold": "Inter-Bold.otf", "Mono": "JetBrainsMono-Regular.ttf", "Caveat": "Caveat-Variable.ttf",
              "IMFell": "IMFellEnglish-Regular.ttf", "Pixel": "PressStart2P-Regular.ttf"}


@functools.lru_cache(maxsize=16)
def typeface(key: str) -> skia.Typeface:
    tf = skia.Typeface.MakeFromFile(str(ASSETS / "fonts" / FONT_FILES[key]))
    if tf is None:
        raise RuntimeError(f"Font file missing or unreadable: {FONT_FILES[key]}")
    return tf


# ------------------------------------------------------------------ world map
@functools.lru_cache(maxsize=1)
def world() -> dict:
    return json.loads((ASSETS / "map" / "land-110m.json").read_text(encoding="utf-8"))


LAT_MIN, LAT_MAX = -58.0, 84.0


def robinson(lon: float, lat: float) -> tuple[float, float]:
    """Robinson projection, normalised so x is in [-1, 1] and y in roughly [-0.51, 0.51] (north up)."""
    tbl = ((0.8487, 0.0), (0.84751182, 0.0620), (0.84479598, 0.1240), (0.83359314, 0.1860), (0.81257725, 0.2480),
           (0.78659072, 0.3100), (0.75163697, 0.3720), (0.71248026, 0.4340), (0.66817401, 0.4958), (0.61793476, 0.5571),
           (0.56123047, 0.6176), (0.50028622, 0.6769), (0.43575686, 0.7346), (0.37091454, 0.7903), (0.30726126, 0.8435),
           (0.24624014, 0.8936), (0.18836617, 0.9394), (0.13492567, 0.9761), (0.0848, 1.0))
    a = min(abs(lat), 89.999) / 5.0
    i = int(a)
    f = a - i
    x0, y0 = tbl[i]
    x1, y1 = tbl[min(i + 1, len(tbl) - 1)]
    px, py = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
    return px * lon / 180.0 / 0.8487, math.copysign(py * 0.5072, lat)


class MapProjection:
    """Maps lon/lat into a rectangle (x, y, w, h) with the given projection, keeping the aspect ratio of the world
    between LAT_MIN and LAT_MAX and centring it. Optional lon/lat window crops to a region."""

    def __init__(self, rect: tuple[float, float, float, float], kind: str = "robinson",
                 window: tuple[float, float, float, float] | None = None):
        self.kind = kind
        lon0, lon1, lat0, lat1 = window or (-180.0, 180.0, LAT_MIN, LAT_MAX)
        ax0, ay0 = self._raw(lon0, lat1)
        ax1, ay1 = self._raw(lon1, lat0)
        bx0, bx1 = min(ax0, ax1), max(ax0, ax1)
        by0, by1 = min(ay0, ay1), max(ay0, ay1)
        x, y, w, h = rect
        self.rect = rect
        s = min(w / (bx1 - bx0), h / (by1 - by0))
        self.s = s
        self.ox = x + (w - (bx1 - bx0) * s) / 2 - bx0 * s
        self.oy = y + (h - (by1 - by0) * s) / 2 - by0 * s
        self.key = (round(x), round(y), round(w), round(h), kind, window)

    def _raw(self, lon, lat):
        if self.kind == "equirectangular":
            return lon / 180.0, -lat / 180.0
        rx, ry = robinson(lon, lat)
        return rx, -ry

    def __call__(self, lon: float, lat: float) -> tuple[float, float]:
        rx, ry = self._raw(lon, lat)
        return self.ox + rx * self.s, self.oy + ry * self.s


@functools.lru_cache(maxsize=16)
def _land_path_cached(key) -> skia.Path:
    x, y, w, h, kind, window = key
    proj = MapProjection((x, y, w, h), kind, window)
    path = skia.Path()
    for ring in world()["rings"]:
        lons, lats = ring[0::2], ring[1::2]
        un = [lons[0]]
        for lo in lons[1:]:                      # unwrap so a ring crossing +-180 stays one shape
            d = lo - un[-1]
            un.append(lo - 360 if d > 180 else lo + 360 if d < -180 else lo)
        shifts = [0.0] + ([-360.0] if max(un) > 180 else []) + ([360.0] if min(un) < -180 else [])
        for sh in shifts:
            pts = [proj(lo + sh, la) for lo, la in zip(un, lats)]
            path.moveTo(*pts[0])
            for q in pts[1:]:
                path.lineTo(*q)
            path.close()
    return path


def land_path(proj: MapProjection) -> skia.Path:
    return _land_path_cached(proj.key)


def land_dots(proj: MapProjection) -> list[tuple[float, float]]:
    d = world()["dots"]
    return [proj(d[i], d[i + 1]) for i in range(0, len(d), 2)]


def great_circle(lon1: float, lat1: float, lon2: float, lat2: float, n: int = 48) -> list[tuple[float, float]]:
    """Points along the great circle between two places, as lon/lat."""
    p1, l1, p2, l2 = map(math.radians, (lat1, lon1, lat2, lon2))
    v1 = (math.cos(p1) * math.cos(l1), math.cos(p1) * math.sin(l1), math.sin(p1))
    v2 = (math.cos(p2) * math.cos(l2), math.cos(p2) * math.sin(l2), math.sin(p2))
    dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(v1, v2))))
    om = math.acos(dot)
    if om < 1e-6:
        return [(lon1, lat1), (lon2, lat2)]
    out = []
    for i in range(n + 1):
        f = i / n
        a = math.sin((1 - f) * om) / math.sin(om)
        b = math.sin(f * om) / math.sin(om)
        x, y, z = (a * v1[k] + b * v2[k] for k in range(3))
        out.append((math.degrees(math.atan2(y, x)), math.degrees(math.atan2(z, math.hypot(x, y)))))
    return out
