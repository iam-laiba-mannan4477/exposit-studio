"""Exposit scene renderer.

A scene is rendered from a declarative specification plus the word timings of its narration.
No model-written code is executed: the specification only selects components and cues.
Drawing uses Skia on the CPU; frames are piped to ffmpeg. One scene in, one silent clip out.

Treatments: kinetic (typography + UI bar), flow2d (network-flow map), isometric (zones and nodes),
cutaway (inside a Kubernetes node), chart (bars).
"""
from __future__ import annotations
import math, re, subprocess
from typing import Callable
import skia
from .. import config

THEMES = {
    "premium-technical": dict(bg0="#0B0B0F", bg1="#14141C", grid="#1E1E2A", panel="#171720", line="#34343F",
                              text="#EDEDF2", text2="#A3A3B2", accent="#7C6CF6", blue="#52A7F5", teal="#2FC7B5",
                              green="#3DCB8C", amber="#F2B34A", red="#F0575C", pink="#E46AA6"),
    "midnight-blue": dict(bg0="#070B16", bg1="#0E1730", grid="#182444", panel="#111B36", line="#2B3A63",
                          text="#EAF0FF", text2="#9FB0D6", accent="#5B8CFF", blue="#6FC3FF", teal="#39D0C3",
                          green="#44D39A", amber="#FFC25C", red="#FF6B6B", pink="#E88BD0"),
    "minimal-mono": dict(bg0="#0E0E0E", bg1="#151515", grid="#1F1F1F", panel="#181818", line="#3A3A3A",
                         text="#F2F2F2", text2="#A8A8A8", accent="#FFFFFF", blue="#D0D0D0", teal="#BDBDBD",
                         green="#E6E6E6", amber="#CFCFCF", red="#8A8A8A", pink="#BDBDBD"),
}
KIND_COLOR = {"browser": "blue", "client": "blue", "dns": "teal", "lb": "accent", "nginx": "green", "ingress": "green",
              "service": "amber", "pod": "blue", "node": "text2", "zone": "line", "db": "pink", "queue": "amber",
              "hub": "accent", "gateway": "accent", "cdn": "teal", "edge": "teal", "cache": "amber", "router": "amber",
              "server": "text2", "origin": "pink", "worker": "blue", "replica": "blue", "item": "blue", "panel": "green",
              "component": "green", "storage": "pink", "user": "blue"}

# Generic roles inside the isometric and cutaway treatments. The original Kubernetes/AWS kinds still work.
ISO_HUB = ("lb", "hub", "gateway", "cdn", "router", "origin", "cache")
ISO_GROUP = ("zone", "region", "group", "datacenter")
ISO_MEMBER = ("node", "server", "edge", "replica", "instance", "worker")
CUT_PANEL = ("nginx", "ingress", "panel", "component", "gateway", "cdn", "edge", "server")
CUT_ROUTER = ("service", "router", "cache", "switch", "queue", "balancer")
CUT_WORKER = ("pod", "worker", "item", "replica", "storage", "db", "instance")

_fonts: dict = {}


def typeface(name: str) -> skia.Typeface:
    if name not in _fonts:
        _fonts[name] = skia.Typeface.MakeFromFile(str(config.ASSETS / "fonts" / name))
    return _fonts[name]


def font(size: float, weight: str = "Regular", mono: bool = False) -> skia.Font:
    f = skia.Font(typeface("JetBrainsMono-Regular.ttf" if mono else f"Inter-{weight}.otf"), size)
    f.setSubpixel(True)
    return f


def col(hex_: str, a: float = 1.0) -> int:
    h = hex_.lstrip("#")
    return skia.Color(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(max(0.0, min(1.0, a)) * 255))


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def ease(x: float) -> float:
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_io(x: float) -> float:
    x = clamp(x)
    return 4 * x * x * x if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def norm_word(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower())


def caption_chunks(timing: dict, max_chars: int = 44) -> list[dict]:
    """Split narration into caption cues that follow word timings."""
    out, cur = [], []
    for w in timing.get("words", []):
        if cur and (len(" ".join(x["w"] for x in cur)) + len(w["w"]) + 1 > max_chars or cur[-1]["si"] != w["si"]):
            out.append(cur)
            cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return [{"s": c[0]["s"], "e": c[-1]["e"], "text": " ".join(x["w"] for x in c)} for c in out]


class Scene:
    """Resolves cues to times and answers 'what is on screen at t'."""

    def __init__(self, spec: dict, timing: dict, theme: str = "premium-technical"):
        self.spec, self.timing = spec, timing
        self.T = THEMES.get(spec.get("theme") or theme, THEMES["premium-technical"])
        self.pad0 = float(spec.get("pad_start", 0.4))
        self.pad1 = float(spec.get("pad_end", 0.5))
        self.dur = self.pad0 + float(timing.get("duration", 3.0)) + self.pad1
        self.motion = float(spec.get("motion_scale", 1.0))
        self.els = {e["id"]: e for e in spec.get("elements", [])}
        self.order = [e["id"] for e in spec.get("elements", [])]
        self.events = []
        for c in spec.get("cues", []):
            t = self.cue_time(c.get("at"))
            if t is not None:
                self.events.append(dict(c, t=t))
        self.events.sort(key=lambda e: e["t"])
        self.show_at = {}
        for e in self.events:
            if e["action"] == "show":
                for tid in ([e["target"]] if isinstance(e.get("target"), str) else e.get("targets", [])):
                    self.show_at.setdefault(tid, e["t"])
        hidden = [i for i in self.order if self.els[i].get("hidden")]
        k = 0
        for i in self.order:
            if i not in self.show_at:
                self.show_at[i] = 1e9 if i in hidden else 0.15 + 0.12 * k
                k += 1
        self.captions = [dict(c, s=c["s"] + self.pad0, e=c["e"] + self.pad0) for c in caption_chunks(timing)]

    def cue_time(self, at) -> float | None:
        if at is None:
            return 0.0
        if isinstance(at, (int, float)):
            return float(at)
        if "t" in at:
            return float(at["t"])
        words = self.timing.get("words", [])
        if "word" in at:
            target, occ, n = norm_word(at["word"]), int(at.get("occurrence", 1)), 0
            for w in words:
                if norm_word(w["w"]) == target:
                    n += 1
                    if n == occ:
                        return self.pad0 + w["s"] + float(at.get("offset", 0))
            return None
        if "sentence" in at:
            s = self.timing.get("sentences", [])
            i = int(at["sentence"])
            if 0 <= i < len(s):
                return self.pad0 + s[i]["s"] + float(at.get("offset", 0))
        return None

    def vis(self, eid: str, t: float, d: float = 0.45) -> float:
        return ease((t - self.show_at.get(eid, 0.0)) / d)

    def events_of(self, action: str) -> list[dict]:
        return [e for e in self.events if e["action"] == action]

    def highlight(self, eid: str, t: float) -> float:
        hs = self.events_of("highlight")
        best = 0.0
        for i, e in enumerate(hs):
            if e.get("target") != eid:
                continue
            end = e["t"] + float(e.get("hold", 0)) if e.get("hold") else (hs[i + 1]["t"] if i + 1 < len(hs) else self.dur)
            best = max(best, min(ease((t - e["t"]) / 0.35), 1 - ease((t - end) / 0.35)))
        return best

    def any_highlight(self, t: float) -> float:
        return max([self.highlight(i, t) for i in self.order] or [0.0])

    def packets(self, t: float) -> list[tuple[dict, float]]:
        out = []
        for e in self.events_of("packet"):
            d = float(e.get("dur", 0.9)) * self.motion
            if e["t"] <= t <= e["t"] + d + 0.6:
                out.append((e, (t - e["t"]) / d))
        return out

    def note(self, eid: str, t: float):
        res = None
        for e in self.events_of("note"):
            if e.get("target") == eid and t >= e["t"]:
                res = (e.get("text", ""), ease((t - e["t"]) / 0.4))
        return res

    def latest(self, action: str, t: float):
        res = None
        for e in self.events_of(action):
            if t >= e["t"]:
                res = e
        return res


# ------------------------------------------------------------------ drawing helpers
def paint(color: int, stroke: float = 0, **kw) -> skia.Paint:
    p = skia.Paint(AntiAlias=True, Color=color, **kw)
    if stroke:
        p.setStyle(skia.Paint.kStroke_Style)
        p.setStrokeWidth(stroke)
    return p


def text(c: skia.Canvas, s: str, x: float, y: float, f: skia.Font, color: int, align: str = "left") -> float:
    w = f.measureText(s)
    if align == "center":
        x -= w / 2
    elif align == "right":
        x -= w
    c.drawString(s, x, y, f, skia.Paint(AntiAlias=True, Color=color))
    return w


def wrap(s: str, f: skia.Font, maxw: float) -> list[str]:
    """Greedy word wrap to a pixel width."""
    rows, cur = [], ""
    for w in s.split():
        t2 = (cur + " " + w).strip()
        if cur and f.measureText(t2) > maxw:
            rows.append(cur)
            cur = w
        else:
            cur = t2
    if cur:
        rows.append(cur)
    return rows or [""]


def glow(c: skia.Canvas, rect: skia.Rect, radius: float, color: int, sigma: float = 18) -> None:
    p = skia.Paint(AntiAlias=True, Color=color)
    p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, sigma))
    c.drawRoundRect(rect, radius, radius, p)


def box(c, sc: Scene, x, y, w, h, label, kind="node", a=1.0, hl=0.0, dim=0.0, sub=None, mono_sub=False, radius=18):
    T = sc.T
    alpha = a * (1 - 0.5 * dim * (1 - hl))
    if alpha <= 0.01:
        return
    kc = T[KIND_COLOR.get(kind, "text2")]
    r = skia.Rect.MakeXYWH(x, y, w, h)
    if hl > 0:
        glow(c, r, radius, col(kc, 0.55 * hl * alpha), 22)
    c.drawRoundRect(r, radius, radius, paint(col(T["panel"], alpha)))
    c.drawRoundRect(r, radius, radius, paint(col(kc if hl > 0.05 else T["line"], alpha * (0.6 + 0.4 * hl)), 2 + 1.5 * hl))
    c.drawCircle(x + 30, y + 34, 9, paint(col(kc, alpha)))
    text(c, label, x + 50, y + 43, font(27, "SemiBold"), col(T["text"], alpha))
    if sub:
        text(c, sub, x + 28, y + h - 26, font(21, mono=mono_sub), col(T["text2"], alpha))


def packet_dot(c, sc: Scene, x, y, a=1.0):
    kc = sc.T["accent"]
    p = skia.Paint(AntiAlias=True, Color=col(kc, 0.7 * a))
    p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 14))
    c.drawCircle(x, y, 20, p)
    c.drawCircle(x, y, 11, paint(col("#FFFFFF", a)))
    c.drawCircle(x, y, 11, paint(col(kc, a), 3))


def background(c, sc: Scene, w, h):
    T = sc.T
    p = skia.Paint()
    p.setShader(skia.GradientShader.MakeLinear([skia.Point(0, 0), skia.Point(w, h)], [col(T["bg0"]), col(T["bg1"])]))
    c.drawRect(skia.Rect.MakeWH(w, h), p)
    gp = paint(col(T["grid"], 0.9))
    for gx in range(60, int(w), 60):
        for gy in range(60, int(h), 60):
            c.drawCircle(gx, gy, 1.6, gp)


# ------------------------------------------------------------------ treatments
# Landscape treatments draw in a 1920x1080 space; portrait (9:16) ones in 1080x1920, with the stage in the
# band y 370..1250 (below the heading and step badge) so that Instagram's and YouTube's own buttons and captions do not cover anything.
class Treatment:
    def __init__(self, sc: Scene):
        self.sc = sc
        self.portrait = bool(getattr(sc, "portrait", False))
        self.CX, self.CY = (540.0, 810.0) if self.portrait else (960.0, 540.0)
        self.pos: dict[str, tuple[float, float, float, float]] = {}
        self.layout()

    def layout(self): ...
    def draw(self, c: skia.Canvas, t: float): ...

    def center(self, eid: str) -> tuple[float, float]:
        x, y, w, h = self.pos.get(eid, (self.CX, self.CY, 0, 0))
        return x + w / 2, y + h / 2

    def camera(self, t: float) -> tuple[float, float, float]:
        """Returns (scale, focus_x, focus_y)."""
        return 1.0, self.CX, self.CY

    def draw_packets(self, c, t, endpoint: Callable[[str], tuple[float, float]]):
        for e, k in self.sc.packets(t):
            ax, ay = endpoint(e["from"])
            bx, by = endpoint(e["to"])
            kk = ease_io(k)
            fade = 1 - clamp((k - 1) / 0.5) if k > 1 else 1.0
            for j in range(6, 0, -1):
                kj = clamp(kk - j * 0.035)
                c.drawCircle(lerp(ax, bx, kj), lerp(ay, by, kj), 7, paint(col(self.sc.T["accent"], 0.10 * fade)))
            packet_dot(c, self.sc, lerp(ax, bx, kk), lerp(ay, by, kk), fade)


class Flow2D(Treatment):
    W, H = 250, 132

    def layout(self):
        ids = self.sc.order
        n = max(1, len(ids))
        if self.portrait:                                   # a vertical chain, top to bottom
            self.W, self.H = 600, min(132.0, (880 - (n - 1) * 56) / n)
            gap = min(110.0, (880 - n * self.H) / max(1, n - 1)) if n > 1 else 0
            total = n * self.H + (n - 1) * gap
            y0 = self.CY - total / 2
            for i, eid in enumerate(ids):
                self.pos[eid] = (540 - self.W / 2, y0 + i * (self.H + gap), self.W, self.H)
            return
        gap = min(140, (1920 - 220 - n * self.W) / max(1, n - 1)) if n > 1 else 0
        total = n * self.W + (n - 1) * gap
        x0 = (1920 - total) / 2
        for i, eid in enumerate(ids):
            self.pos[eid] = (x0 + i * (self.W + gap), 474, self.W, self.H)

    def frame_for(self, targets):
        xs = [self.pos[i] for i in targets if i in self.pos]
        if not xs:
            return 1.0, self.CX, self.CY
        if self.portrait:
            y0, y1 = min(p[1] for p in xs), max(p[1] + p[3] for p in xs)
            return clamp(980 / (y1 - y0 + 300), 1.0, 1.6), 540.0, (y0 + y1) / 2
        x0, x1 = min(p[0] for p in xs), max(p[0] + p[2] for p in xs)
        scale = clamp(1920 / (x1 - x0 + 520), 1.0, 1.7)
        return scale, (x0 + x1) / 2, 540.0

    def camera(self, t):
        frames = [(0.0, self.frame_for(self.sc.spec.get("camera", {}).get("start") or self.sc.order))]
        for e in self.sc.events_of("frame"):
            frames.append((e["t"], self.frame_for(e.get("targets", []))))
        cur = frames[0][1]
        for (ft, f) in frames[1:]:
            k = ease_io((t - ft) / 0.9)
            cur = tuple(lerp(a, b, k) for a, b in zip(cur, f))
        return cur

    def draw(self, c, t):
        sc, T = self.sc, self.sc.T
        dim = sc.any_highlight(t)
        ids = sc.order
        for a, b in sc.spec.get("links") or list(zip(ids, ids[1:])):
            if a in self.pos and b in self.pos and self.portrait:
                x = 540.0
                ay = self.pos[a][1] + self.H
                by = self.pos[b][1]
                al = min(sc.vis(a, t), sc.vis(b, t)) * (1 - 0.5 * dim)
                k = ease((t - max(sc.show_at[a], sc.show_at[b])) / 0.5)
                c.drawLine(x, ay + 8, x, lerp(ay + 8, by - 8, k), paint(col(T["line"], al), 3))
                if k > 0.95:
                    path = skia.Path()
                    path.moveTo(x, by - 8); path.lineTo(x - 9, by - 24); path.lineTo(x + 9, by - 24); path.close()
                    c.drawPath(path, paint(col(T["line"], al)))
            elif a in self.pos and b in self.pos:
                ax = self.pos[a][0] + self.W
                bx = self.pos[b][0]
                y = self.pos[a][1] + self.H / 2
                al = min(sc.vis(a, t), sc.vis(b, t)) * (1 - 0.5 * dim)
                k = ease((t - max(sc.show_at[a], sc.show_at[b])) / 0.5)
                c.drawLine(ax + 10, y, lerp(ax + 10, bx - 10, k), y, paint(col(T["line"], al), 3))
                if k > 0.95:
                    path = skia.Path()
                    path.moveTo(bx - 10, y); path.lineTo(bx - 26, y - 9); path.lineTo(bx - 26, y + 9); path.close()
                    c.drawPath(path, paint(col(T["line"], al)))
        for eid in ids:
            e = sc.els[eid]
            x, y, w, h = self.pos[eid]
            a = sc.vis(eid, t)
            nt = sc.note(eid, t)
            box(c, sc, x, y + (1 - a) * 24, w, h, e.get("label", eid), e.get("kind", "node"), a, sc.highlight(eid, t), dim,
                sub=e.get("sub"))
            if nt and self.portrait:                        # on a small plate, so the link line does not run through it
                f = font(24, mono=True)
                tw = f.measureText(nt[0])
                ny = y + h + 22
                c.drawRoundRect(skia.Rect.MakeXYWH(540 - tw / 2 - 14, ny, tw + 28, 40), 10, 10, paint(col(T["bg0"], 0.92 * nt[1])))
                text(c, nt[0], 540, ny + 29, f, col(T["teal"], nt[1]), "center")
            elif nt:
                text(c, nt[0], x + w / 2, y + h + 44, font(24, mono=True), col(T["teal"], nt[1]), "center")
            if e.get("badge"):
                bx, by = x + w - 26, y - 4
                c.drawCircle(bx, by, 22, paint(col(T["accent"], a)))
                text(c, str(e["badge"]), bx, by + 9, font(24, "Bold"), col("#FFFFFF", a), "center")
        self.draw_packets(c, t, self.center)


class Kinetic(Treatment):
    def draw(self, c, t):
        if self.portrait:
            return self.draw_portrait(c, t)
        sc, T = self.sc, self.sc.T
        ui = sc.spec.get("ui")
        y0 = 330
        if ui:
            a = ease(t / 0.5)
            r = skia.Rect.MakeXYWH(360, 190, 1200, 96)
            c.drawRoundRect(r, 48, 48, paint(col(T["panel"], a)))
            c.drawRoundRect(r, 48, 48, paint(col(T["line"], a), 2))
            c.drawCircle(420, 238, 12, paint(col(T["text2"], a), 3))
            ty = sc.latest("type", t)
            url = ui.get("url", "")
            n = int(len(url) * clamp((t - ty["t"]) / (1.1 * sc.motion))) if ty else 0
            f = font(38, mono=True)
            wdt = text(c, url[:n], 460, 252, f, col(T["text"], a))
            if int(t * 2.4) % 2 == 0 or (ty and n < len(url)):
                c.drawRect(skia.Rect.MakeXYWH(464 + wdt, 218, 3, 42), paint(col(T["accent"], a)))
            en = sc.latest("enter", t)
            if en:
                k = clamp((t - en["t"]) / 0.5)
                c.drawRoundRect(r, 48, 48, paint(col(T["accent"], (1 - k) * 0.9), 4 + 10 * k))
            y0 = 380
        lines = sc.spec.get("lines", [])
        times = [sc.cue_time(l.get("at")) or 0.0 for l in lines]
        for i, l in enumerate(lines):
            if t < times[i]:
                continue
            k = ease((t - times[i]) / 0.45)
            later = [tt for tt in times[i + 1:] if t >= tt]
            a = k * (0.38 if later and not l.get("keep") else 1.0)
            size = l.get("size", 84)
            f = font(size, "Bold" if l.get("accent") else "SemiBold")
            y = y0 + sum(ll.get("size", 84) * 1.22 + 26 for ll in lines[:i]) + size * 0.82 + (1 - k) * 36
            text(c, l["text"], 960, y, f, col(T["accent"] if l.get("accent") else T["text"], a), "center")

    def draw_portrait(self, c, t):
        sc, T = self.sc, self.sc.T
        ui = sc.spec.get("ui")
        lines = sc.spec.get("lines", [])
        times = [sc.cue_time(l.get("at")) or 0.0 for l in lines]
        blocks = []
        for l in lines:                                     # each line wraps to the 940 px column
            size = min(l.get("size", 84), 92)
            f = font(size, "Bold" if l.get("accent") else "SemiBold")
            blocks.append((f, size, wrap(l["text"], f, 940)))
        total = sum(len(r) * size * 1.18 + 26 for _, size, r in blocks)
        y = 520.0 if ui else self.CY - total / 2
        if ui:
            a = ease(t / 0.5)
            r = skia.Rect.MakeXYWH(60, 330, 960, 92)
            c.drawRoundRect(r, 46, 46, paint(col(T["panel"], a)))
            c.drawRoundRect(r, 46, 46, paint(col(T["line"], a), 2))
            c.drawCircle(112, 376, 11, paint(col(T["text2"], a), 3))
            ty = sc.latest("type", t)
            url = ui.get("url", "")
            n = int(len(url) * clamp((t - ty["t"]) / (1.1 * sc.motion))) if ty else 0
            f = font(34, mono=True)
            wdt = text(c, url[:n], 146, 388, f, col(T["text"], a))
            if int(t * 2.4) % 2 == 0 or (ty and n < len(url)):
                c.drawRect(skia.Rect.MakeXYWH(150 + wdt, 356, 3, 40), paint(col(T["accent"], a)))
            en = sc.latest("enter", t)
            if en:
                k = clamp((t - en["t"]) / 0.5)
                c.drawRoundRect(r, 46, 46, paint(col(T["accent"], (1 - k) * 0.9), 4 + 10 * k))
        for i, (l, (f, size, rows)) in enumerate(zip(lines, blocks)):
            if t >= times[i]:
                k = ease((t - times[i]) / 0.45)
                later = [tt for tt in times[i + 1:] if t >= tt]
                a = k * (0.38 if later and not l.get("keep") else 1.0)
                for j, row in enumerate(rows):
                    text(c, row, 540, y + j * size * 1.18 + size * 0.82 + (1 - k) * 36, f,
                         col(T["accent"] if l.get("accent") else T["text"], a), "center")
            y += len(rows) * size * 1.18 + 26


class Isometric(Treatment):
    U = 66.0

    def iso(self, gx, gy, gz=0.0):
        return (self.ox + (gx - gy) * self.U * 0.866, self.oy + (gx + gy) * self.U * 0.5 - gz * self.U)

    def zone_origin(self, i: int) -> tuple[float, float]:
        if self.portrait:
            o = 0.9 if i % 2 else -0.9                     # zig-zag: odd zones to the right, even to the left
            return i * 4.2 + o, i * 4.2 - o
        return i * 4.3, 0.0

    def layout(self):
        sc = self.sc
        self.zones = [e for e in sc.spec.get("elements", []) if e.get("kind") in ISO_GROUP]
        self.nodes = [e for e in sc.spec.get("elements", []) if e.get("kind") in ISO_MEMBER]
        self.lb = next((e for e in sc.spec.get("elements", []) if e.get("kind") in ISO_HUB), None)
        n = max(1, len(self.zones))
        if self.portrait:
            self.span = 0.0
            top, bottom = -4.9, (n - 1) * 4.2 + 3.4 + 0.8   # in units of U, from the load balancer to the last plate
            self.U = min(60.0, 880 / (bottom - top))
            self.ox, self.oy = 540.0, self.CY - (top + bottom) / 2 * self.U
            for i, z in enumerate(self.zones):
                gx, gy = self.zone_origin(i)
                cx, cy = self.iso(gx + 1.7, gy + 1.7)
                self.pos[z["id"]] = (cx - 10, cy - 10, 20, 20)
            for nd in self.nodes:
                zi = next((i for i, z in enumerate(self.zones) if z["id"] == nd.get("zone")), 0)
                gx, gy = self.zone_origin(zi)
                cx, cy = self.iso(gx + 1.7, gy + 1.7, 1.3)
                self.pos[nd["id"]] = (cx - 10, cy - 10, 20, 20)
            if self.lb:
                cx, cy = self.iso(-2.6, -2.6, 1.0)
                self.pos[self.lb["id"]] = (cx - 10, cy - 10, 20, 20)
            cx, cy = self.iso(-6.4, -6.4, 1.0)
            self.pos["_in"] = (cx - 10, cy - 10, 20, 20)
            return
        self.span = n * 4.3 - 0.9
        self.ox, self.oy = 960 - (self.span / 2 - 1.2) * self.U * 0.866 - 150, 440 - (self.span / 2) * self.U * 0.5
        for i, z in enumerate(self.zones):
            cx, cy = self.iso(i * 4.3 + 1.7, 1.7)
            self.pos[z["id"]] = (cx - 10, cy - 10, 20, 20)
        for nd in self.nodes:
            zi = next((i for i, z in enumerate(self.zones) if z["id"] == nd.get("zone")), 0)
            cx, cy = self.iso(zi * 4.3 + 1.7, 1.7, 1.3)
            self.pos[nd["id"]] = (cx - 10, cy - 10, 20, 20)
        if self.lb:
            cx, cy = self.iso(self.span / 2, -3.0, 1.0)
            self.pos[self.lb["id"]] = (cx - 10, cy - 10, 20, 20)
        cx, cy = self.iso(self.span / 2, -7.4, 1.0)
        self.pos["_in"] = (cx - 10, cy - 10, 20, 20)

    def camera(self, t):
        k = ease_io(t / (self.sc.dur))
        return 1.0 + 0.06 * k, self.CX, self.CY

    def poly(self, c, pts, fill, stroke=None, sw=2):
        p = skia.Path()
        p.moveTo(*pts[0])
        for q in pts[1:]:
            p.lineTo(*q)
        p.close()
        c.drawPath(p, paint(fill))
        if stroke is not None:
            c.drawPath(p, paint(stroke, sw))

    def cuboid(self, c, gx, gy, sx, sy, sz, base, a, edge=None, z0=0.0):
        I = self.iso
        top = [I(gx, gy, z0 + sz), I(gx + sx, gy, z0 + sz), I(gx + sx, gy + sy, z0 + sz), I(gx, gy + sy, z0 + sz)]
        left = [I(gx, gy + sy, z0 + sz), I(gx + sx, gy + sy, z0 + sz), I(gx + sx, gy + sy, z0), I(gx, gy + sy, z0)]
        right = [I(gx + sx, gy, z0 + sz), I(gx + sx, gy + sy, z0 + sz), I(gx + sx, gy + sy, z0), I(gx + sx, gy, z0)]
        e = col(edge or base, a)
        self.poly(c, left, col(base, 0.30 * a), e)
        self.poly(c, right, col(base, 0.18 * a), e)
        self.poly(c, top, col(base, 0.48 * a), e)

    def draw(self, c, t):
        sc, T = self.sc, self.sc.T
        I = self.iso
        if self.lb:
            a = sc.vis(self.lb["id"], t)
            hl = sc.highlight(self.lb["id"], t)
            if a > 0.01 and self.portrait:
                self.cuboid(c, -3.9, -3.9, 2.6, 2.6, 0.7, T["accent"], a * (0.75 + 0.25 * hl), z0=0.3 - (1 - a) * 1.2)
                lx, ly = I(-1.3, -3.9, 1.0)
                text(c, self.lb.get("label", "Load balancer"), lx + 34, ly + 6, font(30, "SemiBold"), col(T["text"], a))
                if self.lb.get("sub"):
                    text(c, self.lb["sub"], lx + 34, ly + 40, font(22), col(T["text2"], a))
            elif a > 0.01:
                self.cuboid(c, 0, -3.8, self.span, 1.6, 0.7, T["accent"], a * (0.75 + 0.25 * hl), z0=0.3 - (1 - a) * 1.2)
                lx, ly = I(self.span / 2, -3.8, 1.0)
                text(c, self.lb.get("label", "Load balancer"), lx + 40, ly - 96, font(30, "SemiBold"), col(T["text"], a), "center")
                if self.lb.get("sub"):
                    text(c, self.lb["sub"], lx + 40, ly - 62, font(22), col(T["text2"], a), "center")
        pulse = sc.latest("pulse", t)
        for i, z in enumerate(self.zones):
            a = sc.vis(z["id"], t)
            if a <= 0.01:
                continue
            gx, gy = self.zone_origin(i)
            drop = (1 - a) * 1.0
            plate = [I(gx, gy, -drop), I(gx + 3.4, gy, -drop), I(gx + 3.4, gy + 3.4, -drop), I(gx, gy + 3.4, -drop)]
            self.poly(c, plate, col(T["panel"], 0.95 * a), col(T["line"], a), 2)
            if self.portrait:                              # label on the outer side of the zig-zag
                if i % 2:
                    lx, ly = I(gx + 3.4, gy, -drop)
                    text(c, z.get("label", ""), lx + 24, ly + 50, font(24, "Medium"), col(T["text2"], a))
                else:
                    lx, ly = I(gx, gy + 3.4, -drop)
                    text(c, z.get("label", ""), lx - 24, ly + 50, font(24, "Medium"), col(T["text2"], a), "right")
            else:
                lx, ly = I(gx + 1.7, 3.4, -drop)
                text(c, z.get("label", ""), lx, ly + 44, font(24, "Medium"), col(T["text2"], a), "center")
        for nd in self.nodes:
            zi = next((i for i, z in enumerate(self.zones) if z["id"] == nd.get("zone")), 0)
            a = sc.vis(nd["id"], t)
            if a <= 0.01:
                continue
            healthy = nd.get("state", "healthy") == "healthy"
            st = sc.latest("state", t)
            if st and st.get("target") == nd["id"]:
                healthy = st.get("value", "healthy") == "healthy"
            hl = sc.highlight(nd["id"], t)
            base = T["green"] if healthy else T["red"]
            zgx, zgy = self.zone_origin(zi)
            gx, gy = zgx + 0.9, zgy + 0.9
            self.cuboid(c, gx, gy, 1.6, 1.6, 1.25, base if (healthy or hl) else T["text2"], a * (1.0 if healthy else 0.5),
                        edge=T["accent"] if hl > 0.3 else None, z0=(1 - a) * 1.5)
            cx, cy = I(gx + 0.8, gy + 0.8, 1.25)
            if hl > 0.05:
                p = skia.Paint(AntiAlias=True, Color=col(T["accent"], 0.5 * hl))
                p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 26))
                c.drawCircle(cx, cy, 70, p)
            if self.portrait:                              # name and state on the outer side, level with the node
                right = bool(zi % 2)
                lx, ly = I(zgx + 3.4, zgy, 0.0) if right else I(zgx, zgy + 3.4, 0.0)
                lx, ly, al = lx + (24 if right else -24), cy + 10, ("left" if right else "right")
                text(c, nd.get("label", ""), lx, ly, font(26, "SemiBold"), col(T["text"], a), al)
                hy = ly - 36
            else:
                lx, ly = I(gx + 0.8, 1.7, 1.25)
                text(c, nd.get("label", ""), lx, ly - 64, font(24, "SemiBold"), col(T["text"], a), "center")
                al, hy = "center", ly - 96
            if pulse:
                k = clamp((t - pulse["t"]) / (1.4 * sc.motion))
                if self.lb and 0 < k:
                    x0, y0 = self.center(self.lb["id"])
                    x1, y1 = self.center(nd["id"])
                    kk = ease(clamp(k * 1.6))
                    c.drawLine(x0, y0, lerp(x0, x1, kk), lerp(y0, y1, kk),
                               paint(col(T["green"] if healthy else T["red"], 0.55 * a), 2.5))
                    if k > 0.6:
                        ma = ease((k - 0.6) / 0.3)
                        sl = sc.spec.get("state_labels") or {}
                        text(c, sl.get("healthy", "healthy") if healthy else sl.get("unhealthy", "failing health check"), lx, hy, font(21, "Medium"),
                             col(T["green"] if healthy else T["red"], ma * a), al)
        self.draw_packets(c, t, self.center)


class Cutaway(Treatment):
    def layout(self):
        sc = self.sc
        els = sc.spec.get("elements", [])
        self.ng = next((e for e in els if e.get("kind") in CUT_PANEL), None)
        self.svc = next((e for e in els if e.get("kind") in CUT_ROUTER), None)
        self.pods = [e for e in els if e.get("kind") in CUT_WORKER]
        if self.portrait:                                  # ingress on top, Service in the middle, pods in a row below
            if self.ng:
                self.pos[self.ng["id"]] = (100, 450, 880, 290)
            if self.svc:
                self.pos[self.svc["id"]] = (390, 810, 300, 92)
            n = max(1, len(self.pods))
            pw = (880 - (n - 1) * 24) / n
            for i, p in enumerate(self.pods):
                self.pos[p["id"]] = (100 + i * (pw + 24), 990, pw, 124)
            self.pos["_in"] = (530, 330, 20, 20)
            return
        if self.ng:
            self.pos[self.ng["id"]] = (250, 330, 640, 330)
        if self.svc:
            self.pos[self.svc["id"]] = (1010, 236, 300, 92)
        n = max(1, len(self.pods))
        ph = min(130, (470 - (n - 1) * 26) / n)
        for i, p in enumerate(self.pods):
            self.pos[p["id"]] = (1400, 372 + i * (ph + 26), 300, ph)
        self.pos["_in"] = (40, 500, 20, 20)

    def camera(self, t):
        sc = self.sc
        k = ease_io(t / 0.9)
        base = lerp(1.14, 1.0, k)
        zf = sc.latest("zoom", t)
        if zf and zf.get("target") in self.pos:
            kk = ease_io((t - zf["t"]) / 0.9)
            cx, cy = self.center(zf["target"])
            s = float(zf.get("scale", 1.25))
            return lerp(base, s, kk), lerp(self.CX, cx, kk), lerp(self.CY, cy, kk)
        return base, self.CX, self.CY

    def edge_point(self, eid):
        x, y, w, h = self.pos.get(eid, (self.CX, self.CY, 0, 0))
        return x + w / 2, y + h / 2

    def draw(self, c, t):
        sc, T = self.sc, self.sc.T
        a0 = ease(t / 0.5)
        shell = skia.Rect.MakeXYWH(50, 360, 980, 890) if self.portrait else skia.Rect.MakeXYWH(170, 150, 1600, 740)
        c.drawRoundRect(shell, 28, 28, paint(col(T["panel"], 0.55 * a0)))
        dash = paint(col(T["line"], a0), 3)
        dash.setPathEffect(skia.DashPathEffect.Make([18, 12], 0))
        c.drawRoundRect(shell, 28, 28, dash)
        lx, ly = (86, 412) if self.portrait else (206, 204)
        text(c, sc.spec.get("container_label", ""), lx, ly, font(28, "SemiBold"), col(T["text2"], a0))
        dim = sc.any_highlight(t)
        if self.ng:
            eid = self.ng["id"]
            x, y, w, h = self.pos[eid]
            a, hl = sc.vis(eid, t), sc.highlight(eid, t)
            box(c, sc, x, y, w, h, self.ng.get("label", "Component"), self.ng.get("kind", "nginx"), a, hl, dim, radius=22)
            code = sc.spec.get("code", [])
            cl = sc.latest("code", t)
            for i, line in enumerate(code):
                ly = y + 120 + i * 50
                shown = ease((t - (sc.show_at.get(eid, 0) + 0.3 + 0.12 * i)) / 0.4) * a
                active = cl is not None and i in cl.get("lines", [])
                if active:
                    k = ease((t - cl["t"]) / 0.3)
                    c.drawRoundRect(skia.Rect.MakeXYWH(x + 22, ly - 34, w - 44, 46), 8, 8, paint(col(T["green"], 0.22 * k * a)))
                text(c, line, x + 40, ly, font(27, mono=True),
                     col(T["text"] if active else T["text2"], shown * (1 - 0.45 * dim * (0 if active else 1))))
        if self.svc:
            eid = self.svc["id"]
            x, y, w, h = self.pos[eid]
            a, hl = sc.vis(eid, t), sc.highlight(eid, t)
            if a > 0.01:
                r = skia.Rect.MakeXYWH(x, y, w, h)
                if hl > 0:
                    glow(c, r, 46, col(T["amber"], 0.45 * hl * a), 20)
                dp = paint(col(T["amber"], a), 3)
                dp.setPathEffect(skia.DashPathEffect.Make([12, 9], 0))
                c.drawRoundRect(r, 46, 46, paint(col(T["panel"], a)))
                c.drawRoundRect(r, 46, 46, dp)
                text(c, self.svc.get("label", "Service"), x + w / 2, y + 56, font(27, "SemiBold"), col(T["text"], a), "center")
                st = sc.latest("strike", t)
                if st:
                    k = ease((t - st["t"]) / 0.5)
                    bx, by = x + w + 30, y + 8
                    text(c, st.get("text", "a program?"), bx, by + 34, font(26, "Medium"), col(T["text2"], k * a))
                    wd = font(26, "Medium").measureText(st.get("text", "a program?"))
                    k2 = ease((t - st["t"] - 0.7) / 0.35)
                    c.drawLine(bx - 6, by + 25, bx - 6 + (wd + 12) * k2, by + 25, paint(col(T["red"], a), 4))
                lk = sc.latest("lookup", t)
                for p in self.pods:
                    px, py, pw, ph = self.pos[p["id"]]
                    la = a * sc.vis(p["id"], t) * 0.8
                    flash = 0.0
                    if lk:
                        flash = math.sin(clamp((t - lk["t"]) / 1.2) * math.pi)
                    lp = paint(col(T["amber"], la * (0.45 + 0.55 * flash)), 2 + 2 * flash)
                    lp.setPathEffect(skia.DashPathEffect.Make([6, 8], -t * 30))
                    if self.portrait:
                        c.drawLine(x + w / 2, y + h, px + pw / 2, py, lp)
                    else:
                        c.drawLine(x + w / 2 + 60, y + h, px, py + ph / 2, lp)
                if lk and self.ng:
                    flash = math.sin(clamp((t - lk["t"]) / 1.2) * math.pi)
                    nx, ny, nw, nh = self.pos[self.ng["id"]]
                    lp = paint(col(T["amber"], a * flash), 3)
                    lp.setPathEffect(skia.DashPathEffect.Make([6, 8], -t * 30))
                    if self.portrait:
                        c.drawLine(nx + nw / 2, ny + nh, x + w / 2, y, lp)
                    else:
                        c.drawLine(nx + nw, ny + 60, x, y + h / 2, lp)
        for p in self.pods:
            eid = p["id"]
            x, y, w, h = self.pos[eid]
            box(c, sc, x, y, w, h, p.get("label", "Worker"), p.get("kind", "pod"), sc.vis(eid, t), sc.highlight(eid, t), dim, sub=p.get("sub"), mono_sub=True)
        self.draw_packets(c, t, self.edge_point)


class Chart(Treatment):
    def draw(self, c, t):
        sc, T = self.sc, self.sc.T
        data = sc.spec.get("data", [])
        if not data:
            return
        mx = max(d["value"] for d in data) or 1
        n = len(data)
        if self.portrait:
            bw = min(150, 820 / n * 0.6)
            gap = (900 - n * bw) / max(1, n)
            a0 = ease(t / 0.5)
            for j, row in enumerate(wrap(sc.spec.get("title", ""), font(44, "SemiBold"), 900)):
                text(c, row, 90, 420 + j * 54, font(44, "SemiBold"), col(T["text"], a0))
            c.drawLine(80, 1150, 1000, 1150, paint(col(T["line"]), 2))
            for i, d in enumerate(data):
                k = ease((t - 0.4 - i * 0.18 * sc.motion) / 0.8)
                h = 600 * d["value"] / mx * k
                x = 90 + gap / 2 + i * (bw + gap)
                c.drawRoundRect(skia.Rect.MakeXYWH(x, 1150 - h, bw, h), 8, 8, paint(col(T["accent"] if d.get("accent") else T["blue"], 0.9)))
                for j, row in enumerate(wrap(d["label"], font(24), bw + gap - 12)):
                    text(c, row, x + bw / 2, 1192 + j * 28, font(24), col(T["text2"], k), "center")
                text(c, str(d["value"]), x + bw / 2, 1150 - h - 16, font(26, "SemiBold"), col(T["text"], k), "center")
            return
        bw = min(180, 1300 / n * 0.6)
        gap = (1400 - n * bw) / max(1, n)
        text(c, sc.spec.get("title", ""), 260, 220, font(44, "SemiBold"), col(T["text"], ease(t / 0.5)))
        c.drawLine(250, 860, 1670, 860, paint(col(T["line"]), 2))
        for i, d in enumerate(data):
            k = ease((t - 0.4 - i * 0.18 * sc.motion) / 0.8)
            h = 560 * d["value"] / mx * k
            x = 260 + gap / 2 + i * (bw + gap)
            c.drawRoundRect(skia.Rect.MakeXYWH(x, 860 - h, bw, h), 8, 8, paint(col(T["accent"] if d.get("accent") else T["blue"], 0.9)))
            text(c, d["label"], x + bw / 2, 904, font(24), col(T["text2"], k), "center")
            text(c, str(d["value"]), x + bw / 2, 860 - h - 16, font(26, "SemiBold"), col(T["text"], k), "center")


TREATMENTS = {"flow2d": Flow2D, "kinetic": Kinetic, "isometric": Isometric, "cutaway": Cutaway, "chart": Chart}


# ------------------------------------------------------------------ frame + clip
def draw_frame(canvas: skia.Canvas, tr: Treatment, t: float, w: int, h: int, captions: bool = True) -> None:
    sc, T = tr.sc, tr.sc.T
    if tr.portrait:
        return draw_frame_portrait(canvas, tr, t, w, h, captions)
    canvas.save()
    canvas.scale(w / 1920.0, h / 1080.0)
    background(canvas, sc, 1920, 1080)
    cam = sc.spec.get("camera", {})
    s, fx, fy = tr.camera(t)
    if cam.get("enter") == "zoom_out":
        s *= lerp(1.22, 1.0, ease_io(t / 0.8))
    if cam.get("exit") == "push_in":
        k = ease_io((t - (sc.dur - 0.8)) / 0.8)
        if k > 0:
            px, py = tr.center(cam.get("exit_focus", "")) if cam.get("exit_focus") else (fx, fy)
            s, fx, fy = s * lerp(1.0, 1.9, k), lerp(fx, px, k), lerp(fy, py, k)
    canvas.save()
    canvas.translate(960, 540)
    canvas.scale(s, s)
    canvas.translate(-fx, -fy)
    tr.draw(canvas, t)
    canvas.restore()
    # overlays, not affected by the camera
    title = sc.spec.get("heading")
    if title:
        a = ease((t - 0.2) / 0.5)
        text(canvas, title, 96, 112, font(30, "Medium"), col(T["text2"], a))
    cnt = sc.latest("count", t)
    if cnt:
        k = ease((t - cnt["t"]) / 0.4)
        label = f'{cnt.get("n", 1)} / {cnt.get("total", 4)}'
        f = font(28, "SemiBold")
        f2 = font(26, "Medium")
        wl = f.measureText(label)
        wt = f2.measureText(cnt.get("label", ""))
        r = skia.Rect.MakeXYWH(1920 - 96 - (wl + wt + 76), 76, wl + wt + 76, 58)
        canvas.drawRoundRect(r, 29, 29, paint(col(T["panel"], 0.92 * k)))
        canvas.drawRoundRect(r, 29, 29, paint(col(T["accent"], k), 2))
        text(canvas, label, r.left() + 26, r.top() + 39, f, col(T["accent"], k))
        text(canvas, cnt.get("label", ""), r.left() + 46 + wl, r.top() + 39, f2, col(T["text"], k))
    co = sc.latest("callout", t)
    if co and t < co["t"] + float(co.get("hold", 3.2)):
        k = min(ease((t - co["t"]) / 0.4), 1 - ease((t - (co["t"] + float(co.get("hold", 3.2)) - 0.35)) / 0.35))
        f = font(40, "SemiBold")
        wd = f.measureText(co.get("text", ""))
        r = skia.Rect.MakeXYWH(960 - wd / 2 - 34, 836 + (1 - k) * 16, wd + 68, 80)
        canvas.drawRoundRect(r, 16, 16, paint(col(T["accent"], 0.20 * k)))
        canvas.drawRoundRect(r, 16, 16, paint(col(T["accent"], k), 2))
        text(canvas, co.get("text", ""), 960, r.top() + 53, f, col(T["text"], k), "center")
    if captions:
        for cp in sc.captions:
            if cp["s"] - 0.05 <= t <= cp["e"] + 0.25:
                f = font(36, "Medium")
                wd = f.measureText(cp["text"])
                r = skia.Rect.MakeXYWH(960 - wd / 2 - 26, 946, wd + 52, 62)
                canvas.drawRoundRect(r, 12, 12, paint(col("#000000", 0.62)))
                text(canvas, cp["text"], 960, 989, f, col("#FFFFFF"), "center")
                break
    fade = min(clamp(t / 0.3), clamp((sc.dur - t) / 0.3))
    if fade < 1:
        canvas.drawRect(skia.Rect.MakeWH(1920, 1080), paint(col(T["bg0"], 1 - fade)))
    canvas.restore()


def stage_camera(tr: Treatment, t: float) -> tuple[float, float, float]:
    sc = tr.sc
    cam = sc.spec.get("camera", {})
    s, fx, fy = tr.camera(t)
    if cam.get("enter") == "zoom_out":
        s *= lerp(1.22, 1.0, ease_io(t / 0.8))
    if cam.get("exit") == "push_in":
        k = ease_io((t - (sc.dur - 0.8)) / 0.8)
        if k > 0:
            px, py = tr.center(cam.get("exit_focus", "")) if cam.get("exit_focus") else (fx, fy)
            s, fx, fy = s * lerp(1.0, 1.9, k), lerp(fx, px, k), lerp(fy, py, k)
    return s, fx, fy


def draw_frame_portrait(canvas: skia.Canvas, tr: Treatment, t: float, w: int, h: int, captions: bool = True) -> None:
    """9:16 frame (1080x1920 space). Text sits between y 220 and 1500: Reels and Shorts cover the top bar,
    the bottom fifth (caption, audio, profile) and the right-hand buttons with their own interface."""
    sc, T = tr.sc, tr.sc.T
    canvas.save()
    canvas.scale(w / 1080.0, h / 1920.0)
    background(canvas, sc, 1080, 1920)
    s, fx, fy = stage_camera(tr, t)
    canvas.save()
    canvas.translate(tr.CX, tr.CY)
    canvas.scale(s, s)
    canvas.translate(-fx, -fy)
    tr.draw(canvas, t)
    canvas.restore()
    title = sc.spec.get("heading")
    if title:
        a = ease((t - 0.2) / 0.5)
        text(canvas, title, 64, 262, font(32, "Medium"), col(T["text2"], a))
    cnt = sc.latest("count", t)
    if cnt:
        k = ease((t - cnt["t"]) / 0.4)
        label = f'{cnt.get("n", 1)} / {cnt.get("total", 4)}'
        f, f2 = font(28, "SemiBold"), font(26, "Medium")
        wl, wt = f.measureText(label), f2.measureText(cnt.get("label", ""))
        r = skia.Rect.MakeXYWH(1080 - 64 - (wl + wt + 76), 284, wl + wt + 76, 58)
        canvas.drawRoundRect(r, 29, 29, paint(col(T["panel"], 0.92 * k)))
        canvas.drawRoundRect(r, 29, 29, paint(col(T["accent"], k), 2))
        text(canvas, label, r.left() + 26, r.top() + 39, f, col(T["accent"], k))
        text(canvas, cnt.get("label", ""), r.left() + 46 + wl, r.top() + 39, f2, col(T["text"], k))
    co = sc.latest("callout", t)
    if co and t < co["t"] + float(co.get("hold", 3.2)):
        k = min(ease((t - co["t"]) / 0.4), 1 - ease((t - (co["t"] + float(co.get("hold", 3.2)) - 0.35)) / 0.35))
        f = font(42, "SemiBold")
        rows = wrap(co.get("text", ""), f, 900)
        wd = max(f.measureText(r) for r in rows)
        r = skia.Rect.MakeXYWH(540 - wd / 2 - 34, 1278 + (1 - k) * 16, wd + 68, 34 + 54 * len(rows))
        canvas.drawRoundRect(r, 16, 16, paint(col(T["accent"], 0.20 * k)))
        canvas.drawRoundRect(r, 16, 16, paint(col(T["accent"], k), 2))
        for j, row in enumerate(rows):
            text(canvas, row, 540, r.top() + 58 + j * 54, f, col(T["text"], k), "center")
    if captions:
        for cp in sc.captions:
            if cp["s"] - 0.05 <= t <= cp["e"] + 0.25:
                f = font(46, "SemiBold")
                rows = wrap(cp["text"], f, 920)[:2]
                wd = max(f.measureText(r) for r in rows)
                r = skia.Rect.MakeXYWH(540 - wd / 2 - 28, 1430, wd + 56, 30 + 58 * len(rows))
                canvas.drawRoundRect(r, 14, 14, paint(col("#000000", 0.66)))
                for j, row in enumerate(rows):
                    text(canvas, row, 540, r.top() + 60 + j * 58, f, col("#FFFFFF"), "center")
                break
    fade = min(clamp(t / 0.3), clamp((sc.dur - t) / 0.3))
    if fade < 1:
        canvas.drawRect(skia.Rect.MakeWH(1080, 1920), paint(col(T["bg0"], 1 - fade)))
    canvas.restore()


def build(spec: dict, timing: dict, theme: str = "premium-technical", portrait: bool = False) -> Treatment:
    sc = Scene(spec, timing, theme)
    sc.portrait = portrait
    if portrait:                                           # shorter caption cues for a narrow frame
        sc.captions = [dict(c, s=c["s"] + sc.pad0, e=c["e"] + sc.pad0) for c in caption_chunks(timing, 30)]
    return TREATMENTS.get(spec.get("treatment", "flow2d"), Flow2D)(sc)


def render_still(spec: dict, timing: dict, t: float | None = None, w: int = 960, h: int = 540,
                 theme: str = "premium-technical", captions: bool = False) -> bytes:
    tr = build(spec, timing, theme, portrait=h > w)
    surf = skia.Surface(w, h)
    draw_frame(surf.getCanvas(), tr, tr.sc.dur * 0.62 if t is None else t, w, h, captions)
    return bytes(surf.makeImageSnapshot().encodeToData(skia.kPNG, 90))


def render_clip(spec: dict, timing: dict, out_path: str, w: int = config.WIDTH, h: int = config.HEIGHT,
                fps: int = config.FPS, theme: str = "premium-technical", captions: bool = True,
                progress: Callable[[float], None] | None = None) -> dict:
    """Render one scene to a silent H.264 clip. Returns duration and frame count."""
    tr = build(spec, timing, theme, portrait=h > w)
    n = max(1, int(round(tr.sc.dur * fps)))
    surf = skia.Surface(w, h)
    canvas = surf.getCanvas()
    cmd = [config.ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}",
           "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264", "-preset", config.X264_PRESET, "-crf", config.X264_CRF,
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for i in range(n):
            draw_frame(canvas, tr, i / fps, w, h, captions)
            proc.stdin.write(surf.toarray(colorType=skia.kRGBA_8888_ColorType).tobytes())
            if progress and i % 15 == 0:
                progress(i / n)
        proc.stdin.close()
        err = proc.stderr.read().decode("utf-8", "replace")
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg failed: " + err[-400:])
    finally:
        if proc.poll() is None:
            proc.kill()
    return {"duration": n / fps, "frames": n}
