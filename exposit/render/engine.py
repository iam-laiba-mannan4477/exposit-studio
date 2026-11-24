"""Exposit scene renderer.

A scene is rendered from a declarative specification plus the word timings of its narration.
No model-written code is executed: the specification only selects components and cues.
Drawing uses Skia on the CPU; frames are piped to ffmpeg. One scene in, one silent clip out.

Treatments: kinetic (typography + UI bar), flow2d (network-flow map), isometric (zones and nodes),
cutaway (inside a component), chart (bars), and the professional set in pro.py: iconflow, map, sequence, cards,
compare, stat. Look and feel come from the template (design.py); icons and the map from assets.py.
"""
from __future__ import annotations
import functools, math, re, subprocess
from pathlib import Path
from typing import Callable
import numpy as np
import skia
from .. import config
from . import assets, design, styles

THEMES = {name: tpl.T for name, tpl in design.TEMPLATES.items()}   # colour keys, for old callers
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

def font(size: float, weight: str = "Regular", mono: bool = False) -> skia.Font:
    """Font for the active template (Inter by default; Caveat in sketch; mono labels in blueprint)."""
    return design.make_font(size, weight, mono)


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


CAPTION_STYLES = ("phrase", "word")


def word_groups(timing: dict, max_words: int = 4, max_chars: int = 22) -> list[dict]:
    """Groups of 2 to 4 words for word-highlight captions. A group never spans two sentences. A lone word left
    at a sentence end takes the last word of the group before it (or joins it, if that group has only two), so
    only a one-word sentence gives a one-word group. Each group keeps its words with their own timings."""
    sentences: list[list[dict]] = []
    for w in timing.get("words", []):
        if not sentences or sentences[-1][-1]["si"] != w["si"]:
            sentences.append([])
        sentences[-1].append(w)
    out = []
    for ws in sentences:
        groups: list[list[dict]] = []
        cur: list[dict] = []
        for w in ws:
            if cur and (len(cur) >= max_words or (len(cur) >= 2 and len(" ".join(x["w"] for x in cur)) + len(w["w"]) + 1 > max_chars)):
                groups.append(cur)
                cur = []
            cur.append(w)
        if cur:
            if len(cur) == 1 and groups and len(groups[-1]) >= 3:
                groups.append([groups[-1].pop()] + cur)
            elif len(cur) == 1 and groups:
                groups[-1].extend(cur)
            else:
                groups.append(cur)
        out += [{"s": g[0]["s"], "e": g[-1]["e"], "words": [dict(w) for w in g]} for g in groups]
    return out


class Scene:
    """Resolves cues to times and answers 'what is on screen at t'."""

    def __init__(self, spec: dict, timing: dict, theme: str = "premium-technical"):
        self.spec, self.timing = spec, timing
        self.tpl = design.template(spec.get("theme") or theme)
        self.T = self.tpl.T
        self.pad0 = float(spec.get("pad_start", 0.4))
        st = styles.style_of(self.tpl)
        self.intertitle = None                                 # silent film: the heading on a card before the scene
        if st and st.intertitles and spec.get("heading") and spec.get("treatment") != "kinetic":
            self.intertitle = spec["heading"]
            self.pad0 = max(self.pad0, styles.INTERTITLE_SECONDS + 0.3)
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
        self.caption_style = "phrase"
        self.word_groups = [dict(g, s=g["s"] + self.pad0, e=g["e"] + self.pad0,
                                 words=[dict(w, s=w["s"] + self.pad0, e=w["e"] + self.pad0) for w in g["words"]])
                            for g in word_groups(timing)]

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
    design.put_text(c, s, x, y, f, color)
    return w


def fit_font(s: str, maxw: float, size: float, smallest: float, weight: str = "Regular", mono: bool = False) -> skia.Font:
    """The largest size from `size` down to `smallest` at which `s` fits in `maxw` (cached per template font family)."""
    return _fit_font(s, maxw, size, smallest, weight, mono, design.family_key())


@functools.lru_cache(maxsize=4096)
def _fit_font(s, maxw, size, smallest, weight, mono, fam) -> skia.Font:
    sz = size
    while sz > smallest and font(sz, weight, mono=mono).measureText(s) > maxw:
        sz -= 1
    return font(sz, weight, mono=mono)


def fit(s: str, maxw: float, size: float, smallest: float, weight: str = "Regular", mono: bool = False) -> str:
    return _fit(s, maxw, size, smallest, weight, mono, design.family_key())


@functools.lru_cache(maxsize=4096)
def _fit(s: str, maxw: float, size: float, smallest: float, weight: str, mono: bool, fam: str) -> str:
    """`s` itself if it fits at some size down to `smallest`; otherwise cut with an ellipsis so it never leaves its box."""
    f = fit_font(s, maxw, size, smallest, weight, mono)
    if f.measureText(s) <= maxw:
        return s
    while s and f.measureText(s + "…") > maxw:
        s = s[:-1]
    return s.rstrip() + "…"


def wrap(s: str, f: skia.Font, maxw: float) -> list[str]:
    """Balanced word wrap to a pixel width (see design.wrap_font)."""
    return design.wrap_font(s, f, maxw)


def _wrap_greedy(s: str, f: skia.Font, maxw: float) -> list[str]:
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


def box(c, sc: Scene, x, y, w, h, label, kind="node", a=1.0, hl=0.0, dim=0.0, sub=None, mono_sub=False, radius=18, icon=None,
        R=None, vertical=None):
    """A component card in the template's style with an icon badge on every node: badge on the left and the label
    beside it, or (`vertical`, the default for tall cards) badge on top and the label centred under it."""
    tpl, T = sc.tpl, sc.T
    alpha = a * (1 - design.DIM * dim * (1 - hl))
    if alpha <= 0.01:
        return
    ta = a                                                 # text keeps full contrast under focus dimming
    ic = assets.resolve(icon) or assets.icon_for({"kind": kind}) or "box"
    seed = sum(map(ord, label)) % 97
    design.card(c, tpl, x, y, w, h, alpha, hl, 0.0, radius=radius if tpl.legacy else None, seed=seed)
    tone = KIND_COLOR.get(kind, "accent") if tpl.icon["style"] in ("pastel", "tint") else None
    vertical = (h >= 1.15 * w or h > 250) if vertical is None else vertical
    if vertical:
        R = R or min(60.0, w * 0.2, h * 0.22)
        by = y + 26 + R
        design.badge(c, tpl, ic, x + w / 2, by, R, alpha, hl, tone=tone, seed=seed)
        design.label_under(c, tpl, label, x + w / 2, by + R + 12, w - 40, 44, ta, sub, hl=hl)
        return
    R = R or min(60.0, (h - 36) / 2)
    bx, by = x + 26 + R, y + h / 2
    design.badge(c, tpl, ic, bx, by, R, alpha, hl, tone=tone, seed=seed)
    lx = bx + R + 26
    lw = x + w - 24 - lx
    rows, sz = design.fit_block(label, lw, 2, 44, 36, "SemiBold")
    srows, ss = design.fit_block(sub, lw, 2, 32, 30) if sub else ([], 0)
    total = len(rows) * sz * 1.1 + (len(srows) * ss * 1.18 + 6 if sub else 0)
    ty = by - total / 2 + sz * 0.86
    for j, r in enumerate(rows):
        design.draw_text(c, r, lx, ty + j * sz * 1.1, sz, col(T["text"], ta), "SemiBold")
    for j, r in enumerate(srows):
        design.draw_text(c, r, lx, ty + len(rows) * sz * 1.1 - sz * 0.1 + 6 + (j + 0.75) * ss * 1.18, ss,
                         col(T["text2"], ta), mono=mono_sub)


def packet_dot(c, sc: Scene, x, y, a=1.0):
    design.node_dot(c, sc.tpl, x, y, 13, a)


def background(c, sc: Scene, w, h):
    """The template's background (gradient, grid or dots, vignette), cached per size."""
    design.background(c, sc.tpl, w, h)


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
    """A chain of component cards (badge, label, sub-line) joined by connectors with arrowheads; packets run between
    them. Landscape: a row; portrait: a column filling the band below the heading."""
    W, H = 380, 300

    def layout(self):
        ids = self.sc.order
        n = max(1, len(ids))
        top = design.content_top(self.sc.spec, self.portrait)
        if self.portrait:
            self.W = 900.0
            bottom = design.band_bottom(self.sc) - 20
            gap = 96.0
            self.H = min(250.0, (bottom - top - (n - 1) * gap) / n)
            total = n * self.H + (n - 1) * gap
            y0 = top + (bottom - top - total) / 2
            for i, eid in enumerate(ids):
                self.pos[eid] = (90.0, y0 + i * (self.H + gap), self.W, self.H)
            return
        gap = 110.0
        self.W = min(520.0, (1920 - 200 - (n - 1) * gap) / n)
        self.H = 420.0
        total = n * self.W + (n - 1) * gap
        x0 = (1920 - total) / 2
        y = top + (1010 - top - self.H) / 2
        for i, eid in enumerate(ids):
            self.pos[eid] = (x0 + i * (self.W + gap), y, self.W, self.H)

    def frame_for(self, targets):
        """Frame the targets; then widen until no other box is cut by the frame edge."""
        targets = [i for i in targets if i in self.pos]
        for _ in range(len(self.pos) + 1):
            s, fx, fy = self._frame(targets)
            if self.portrait:
                lo, hi, a, b = fy - 620 / s, fy + 620 / s, 1, 3
            else:
                lo, hi, a, b = fx - 960 / s, fx + 960 / s, 0, 2
            cut = [i for i, p in self.pos.items() if i not in targets and p[a] < hi and p[a] + p[b] > lo
                   and not (p[a] >= lo and p[a] + p[b] <= hi)]
            if not cut:
                return s, fx, fy
            targets = targets + cut
        return s, fx, fy

    def _frame(self, targets):
        xs = [self.pos[i] for i in targets if i in self.pos]
        if not xs or set(targets) >= set(self.pos):
            return 1.0, self.CX, self.CY
        if self.portrait:
            y0, y1 = min(p[1] for p in xs), max(p[1] + p[3] for p in xs)
            return clamp(1180 / (y1 - y0 + 200), 1.0, 1.4), 540.0, (y0 + y1) / 2
        x0, x1 = min(p[0] for p in xs), max(p[0] + p[2] for p in xs)
        return clamp(1920 / (x1 - x0 + 400), 1.0, 1.5), (x0 + x1) / 2, 540.0

    def camera(self, t):
        frames = [(0.0, self.frame_for(self.sc.spec.get("camera", {}).get("start") or self.sc.order))]
        for e in self.sc.events_of("frame"):
            frames.append((e["t"], self.frame_for(e.get("targets", []))))
        cur = frames[0][1]
        for (ft, f) in frames[1:]:
            k = ease_io((t - ft) / 0.9)
            cur = tuple(lerp(a, b, k) for a, b in zip(cur, f))
        return cur

    def _link_path(self, a, b):
        ax, ay, aw, ah = self.pos[a]
        bx, by, bw, bh = self.pos[b]
        p = skia.Path()
        if self.portrait:
            p.moveTo(540, ay + ah + 12)
            p.lineTo(540, by - 12)
        else:
            p.moveTo(ax + aw + 12, ay + ah / 2)
            p.lineTo(bx - 12, by + bh / 2)
        return p

    def draw(self, c, t):
        sc, tpl = self.sc, self.sc.tpl
        dim = sc.any_highlight(t)
        ids = sc.order
        for i, (a, b) in enumerate(sc.spec.get("links") or list(zip(ids, ids[1:]))):
            if a in self.pos and b in self.pos:
                al = min(sc.vis(a, t), sc.vis(b, t))
                k = ease((t - max(sc.show_at[a], sc.show_at[b])) / 0.5)
                design.stroke(c, tpl, self._link_path(a, b), al, k, seed=i)
        for eid in ids:
            e = sc.els[eid]
            x, y, w, h = self.pos[eid]
            a = sc.vis(eid, t)
            nt = sc.note(eid, t)
            box(c, sc, x, y + (1 - a) * 24, w, h, e.get("label", eid), e.get("kind", "node"), a, sc.highlight(eid, t), dim,
                sub=e.get("sub"), icon=e.get("icon"), R=75.0)
            if nt:
                ny = y + h + (48 if self.portrait else 64)
                f = font(32, mono=True)
                tw = f.measureText(nt[0])
                cx = x + w / 2
                bgc = T_bg(sc)
                c.drawRoundRect(skia.Rect.MakeXYWH(cx - tw / 2 - 16, ny - 34, tw + 32, 48), 10, 10, paint(col(bgc, 0.95 * nt[1])))
                text(c, nt[0], cx, ny, f, col(design.text_on(tpl, tpl.T["teal"], bgc), nt[1]), "center")
            if e.get("badge"):
                bx, by = x + w - 26, y - 4
                c.drawCircle(bx, by, 28, paint(col(tpl.T["accent"], a)))
                text(c, str(e["badge"]), bx, by + 11, font(32, "Bold"), col("#FFFFFF", a), "center")
        self.draw_packets(c, t, self.center)

    def draw_packets(self, c, t, endpoint):
        for e, k in self.sc.packets(t):
            if e.get("from") in self.pos and e.get("to") in self.pos:
                a, b = e["from"], e["to"]
                order = list(self.sc.order)
                rev = a in order and b in order and order.index(a) > order.index(b)
                p = self._link_path(b, a) if rev else self._link_path(a, b)
                kk = ease_io(clamp(k))
                design.packet(c, self.sc.tpl, p, 1 - kk if rev else kk, 1 - clamp((k - 1) / 0.4) if k > 1 else 1.0)


class Kinetic(Treatment):
    """Big typography, line by line. Earlier lines step back to the secondary text colour (never to a faint alpha)."""

    def _line_color(self, l, older):
        T = self.sc.T
        if l.get("accent"):
            return design.text_on(self.sc.tpl, T["accent"], T["bg0"] if self.sc.tpl.dark else T["bg0"])
        return T["text2"] if older and not l.get("keep") else T["text"]

    def draw(self, c, t):
        if self.portrait:
            return self.draw_portrait(c, t)
        sc, T = self.sc, self.sc.T
        st = styles.style_of(sc.tpl)
        if st and st.intertitles:
            styles.draw_intertitle(c, sc.tpl, "", 1920, 1080, 1.0, False)
        ui = sc.spec.get("ui")
        y0 = 330
        if ui:
            a = ease(t / 0.5)
            r = skia.Rect.MakeXYWH(360, 190, 1200, 104)
            c.drawRoundRect(r, 52, 52, paint(col(T["panel"], a)))
            c.drawRoundRect(r, 52, 52, paint(col(T["line"], a), 3))
            c.drawCircle(424, 242, 14, paint(col(T["text2"], a), 4))
            ty = sc.latest("type", t)
            url = ui.get("url", "")
            n = int(len(url) * clamp((t - ty["t"]) / (1.1 * sc.motion))) if ty else 0
            f = font(40, mono=True)
            wdt = text(c, url[:n], 466, 256, f, col(T["text"], a))
            if int(t * 2.4) % 2 == 0 or (ty and n < len(url)):
                c.drawRect(skia.Rect.MakeXYWH(470 + wdt, 220, 4, 46), paint(col(T["accent"], a)))
            en = sc.latest("enter", t)
            if en:
                k = clamp((t - en["t"]) / 0.5)
                c.drawRoundRect(r, 52, 52, paint(col(T["accent"], (1 - k) * 0.9), 4 + 10 * k))
            y0 = 380
        lines = sc.spec.get("lines", [])
        times = [sc.cue_time(l.get("at")) or 0.0 for l in lines]
        sizes = [max(84, l.get("size", 104)) for l in lines]
        total = sum(s * 1.22 + 26 for s in sizes)
        if not ui:
            y0 = 540 - total / 2
        for i, l in enumerate(lines):
            if t < times[i]:
                continue
            k = ease((t - times[i]) / 0.45)
            older = any(t >= tt for tt in times[i + 1:])
            size = sizes[i]
            f = font(size, "Bold" if l.get("accent") or l.get("brand") else "SemiBold")
            y = y0 + sum(s * 1.22 + 26 for s in sizes[:i]) + size * 0.82 + (1 - k) * 36
            text(c, l["text"], 960, y, f, col(self._line_color(l, older), k), "center")

    def draw_portrait(self, c, t):
        sc, T = self.sc, self.sc.T
        st = styles.style_of(sc.tpl)
        if st and st.intertitles:                          # silent film: kinetic scenes are intertitle cards
            styles.draw_intertitle(c, sc.tpl, "", 1080, 1920, 1.0, False)
        ui = sc.spec.get("ui")
        lines = sc.spec.get("lines", [])
        times = [sc.cue_time(l.get("at")) or 0.0 for l in lines]
        blocks = []
        col_w = 780 if (st and st.intertitles) else 940      # inside the intertitle card's border
        for l in lines:                                     # each line wraps to the column
            wt = "Bold" if l.get("accent") or l.get("brand") else "SemiBold"
            size = design.fit_size(l["text"], col_w, max(96, min(l.get("size", 120), 132)), 84, wt)
            f = font(size, wt)
            blocks.append((f, size, wrap(l["text"], f, col_w)))
        total = sum(len(r) * size * 1.14 + 30 for _, size, r in blocks)
        top = 560.0 if ui else design.PORTRAIT_BAND[0]
        y = top + (design.band_bottom(self.sc) - top - total) / 2
        if ui:
            a = ease(t / 0.5)
            r = skia.Rect.MakeXYWH(60, 330, 960, 104)
            c.drawRoundRect(r, 52, 52, paint(col(T["panel"], a)))
            c.drawRoundRect(r, 52, 52, paint(col(T["line"], a), 3))
            c.drawCircle(116, 382, 14, paint(col(T["text2"], a), 4))
            ty = sc.latest("type", t)
            url = ui.get("url", "")
            n = int(len(url) * clamp((t - ty["t"]) / (1.1 * sc.motion))) if ty else 0
            f = font(38, mono=True)
            wdt = text(c, url[:n], 152, 396, f, col(T["text"], a))
            if int(t * 2.4) % 2 == 0 or (ty and n < len(url)):
                c.drawRect(skia.Rect.MakeXYWH(156 + wdt, 360, 4, 44), paint(col(T["accent"], a)))
            en = sc.latest("enter", t)
            if en:
                k = clamp((t - en["t"]) / 0.5)
                c.drawRoundRect(r, 52, 52, paint(col(T["accent"], (1 - k) * 0.9), 4 + 10 * k))
        for i, (l, (f, size, rows)) in enumerate(zip(lines, blocks)):
            if t >= times[i]:
                k = ease((t - times[i]) / 0.45)
                older = any(t >= tt for tt in times[i + 1:])
                for j, row in enumerate(rows):
                    text(c, row, 540, y + j * size * 1.14 + size * 0.82 + (1 - k) * 36, f, col(self._line_color(l, older), k), "center")
            y += len(rows) * size * 1.14 + 30


class Isometric(Treatment):
    """Zones as plates, members as blocks, a hub block above them; an icon badge on every node and the hub. The
    whole drawing is scaled to fill the content area below the heading."""
    U = 66.0

    def iso(self, gx, gy, gz=0.0):
        return (self.ox + (gx - gy) * self.U * 0.866, self.oy + (gx + gy) * self.U * 0.5 - gz * self.U)

    def zone_origin(self, i: int) -> tuple[float, float]:
        if self.portrait:                                  # a zig-zag down the frame
            o = 1.1 if i % 2 else -1.1
            return i * 5.0 + o, i * 5.0 - o
        return i * 4.6, 0.0

    def _hub_box(self):
        n = max(1, len(self.zones))
        if self.portrait:
            return -4.8, -4.8, 2.4, 2.4
        return 0.4, -4.4, (n - 1) * 4.6 + 2.6, 1.8

    def layout(self):
        sc = self.sc
        self.zones = [e for e in sc.spec.get("elements", []) if e.get("kind") in ISO_GROUP]
        self.nodes = [e for e in sc.spec.get("elements", []) if e.get("kind") in ISO_MEMBER]
        self.lb = next((e for e in sc.spec.get("elements", []) if e.get("kind") in ISO_HUB), None)
        self.R = 75.0 if self.portrait else 60.0
        # the extent of the drawing at U = 1, origin 0 (plates, blocks, hub, badges above blocks)
        self.U, self.ox, self.oy = 1.0, 0.0, 0.0
        pts = []
        for i, _ in enumerate(self.zones or [None]):
            gx, gy = self.zone_origin(i)
            pts += [self.iso(gx + a, gy + b) for a in (0, 3.4) for b in (0, 3.4)]
            pts.append(self.iso(gx + 1.7, gy + 1.7, 3.4))
        if self.lb:
            hx, hy, hw, hd = self._hub_box()
            pts += [self.iso(hx + a, hy + b, z) for a in (0, hw) for b in (0, hd) for z in (0.3, 1.0)]
            pts.append(self.iso(hx + hw / 2, hy + hd / 2, 3.2))
        x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
        y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
        top = design.content_top(sc.spec, self.portrait)
        if self.portrait:
            area = (60.0, top + 10, 560.0, design.band_bottom(self.sc) - 80 - top - 10)     # labels go to the right
        else:
            area = (140.0, top + 10, 1300.0, 1000 - top - 70)
        self.U = min(area[2] / (x1 - x0), area[3] / (y1 - y0), 120.0)
        self.ox = area[0] + (area[2] - (x1 - x0) * self.U) / 2 - x0 * self.U
        self.oy = area[1] + (area[3] - (y1 - y0) * self.U) / 2 - y0 * self.U
        for i, z in enumerate(self.zones):
            gx, gy = self.zone_origin(i)
            cx, cy = self.iso(gx + 1.7, gy + 1.7)
            self.pos[z["id"]] = (cx - 10, cy - 10, 20, 20)
        for nd in self.nodes:
            zi = self._zone_index(nd)
            gx, gy = self.zone_origin(zi)
            cx, cy = self.iso(gx + 1.7, gy + 1.7, 1.3)
            self.pos[nd["id"]] = (cx - 10, cy - 10, 20, 20)
        if self.lb:
            hx, hy, hw, hd = self._hub_box()
            cx, cy = self.iso(hx + hw / 2, hy + hd / 2, 1.0)
            self.pos[self.lb["id"]] = (cx - 10, cy - 10, 20, 20)
        cx, cy = self.iso(-6.4, -6.4, 1.0)
        self.pos["_in"] = (cx - 10, cy - 10, 20, 20)

    def _zone_index(self, nd):
        return next((i for i, z in enumerate(self.zones) if z["id"] == nd.get("zone")), 0)

    def camera(self, t):
        k = ease_io(t / (self.sc.dur))
        return 1.0 + 0.03 * k, self.CX, self.CY

    def poly(self, c, pts, fill, stroke=None, sw=2):
        """A filled (and stroked) polygon; settled ones (opaque inputs, no animation) go through the sprite cache."""
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        x0, y0 = min(xs), min(ys)
        key = ("poly", tuple((round(q[0] - x0, 1), round(q[1] - y0, 1)) for q in pts), fill, stroke, sw)

        def fn(cc):
            p = skia.Path()
            p.moveTo(pts[0][0] - x0, pts[0][1] - y0)
            for q in pts[1:]:
                p.lineTo(q[0] - x0, q[1] - y0)
            p.close()
            cc.drawPath(p, paint(fill))
            if stroke is not None:
                cc.drawPath(p, paint(stroke, sw))
        if getattr(self, "_settled", False):
            design.sprite(c, key, x0, y0, max(xs) - x0, max(ys) - y0, fn, 1.0, pad=sw + 2)
            return
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
        dark = self.sc.tpl.dark
        self.poly(c, left, col(base, (0.42 if dark else 0.55) * a), e, 2.5)
        self.poly(c, right, col(base, (0.26 if dark else 0.35) * a), e, 2.5)
        self.poly(c, top, col(base, (0.62 if dark else 0.8) * a), e, 2.5)

    def _label(self, c, s, sub, x, y, align, a, size=44, sub_color=None):
        T = self.sc.T
        maxw = 420.0 if not self.portrait else 300.0
        rows, sz = design.fit_block(s, maxw, 2, size, 36, "SemiBold")
        srows, ss = design.fit_block(sub, maxw, 2, 32, 30) if sub else ([], 30)
        bw = max([design.text_width(r, sz, "SemiBold") for r in rows] + [design.text_width(r, ss) for r in srows])
        bh = len(rows) * sz * 1.08 + (len(srows) * ss * 1.15 + 14 if sub else 0) + 14
        bx = x - 12 if align == "left" else x - bw - 12
        c.drawRoundRect(skia.Rect.MakeXYWH(bx, y - sz * 0.95, bw + 24, bh), 12, 12,
                        paint(col(T_bg(self.sc), 0.9 * a)))
        for j, r in enumerate(rows):
            design.draw_text(c, r, x, y + j * sz * 1.08, sz, col(T["text"], a), "SemiBold", align)
        yy = y + (len(rows) - 1) * sz * 1.08
        if sub:
            for j, r in enumerate(srows):
                design.draw_text(c, r, x, yy + 44 + j * ss * 1.15, ss, col(sub_color or T["text2"], a), "Regular", align)

    def draw(self, c, t):
        sc, T, tpl = self.sc, self.sc.T, self.sc.tpl
        I = self.iso
        icon_tone = lambda k: KIND_COLOR.get(k, "accent") if tpl.icon["style"] in ("pastel", "tint") else None
        pulse = sc.latest("pulse", t)
        ids = [z["id"] for z in self.zones] + [n["id"] for n in self.nodes] + ([self.lb["id"]] if self.lb else [])
        self._settled = all(sc.vis(i, t) >= 0.999 for i in ids)
        for i, z in enumerate(self.zones):
            a = sc.vis(z["id"], t)
            if a <= 0.01:
                continue
            gx, gy = self.zone_origin(i)
            drop = (1 - a) * 1.0
            plate = [I(gx, gy, -drop), I(gx + 3.4, gy, -drop), I(gx + 3.4, gy + 3.4, -drop), I(gx, gy + 3.4, -drop)]
            self.poly(c, plate, col(T["panel"], 0.95 * a), col(T["line"] if not tpl.legacy else T["text2"], a), 3)
            lx, ly = I(gx + 3.4, gy + 3.4, -drop)
            fx, fy = I(gx, gy + 3.4, -drop)
            design.draw_text(c, z.get("label", ""), (lx + fx) / 2 - 20, ly + 56, 36, col(T["text2"], a), "SemiBold", "center")
        if self.lb:
            a = sc.vis(self.lb["id"], t)
            hl = sc.highlight(self.lb["id"], t)
            if a > 0.01:
                hx, hy, hw, hd = self._hub_box()
                self.cuboid(c, hx, hy, hw, hd, 0.7, T["accent"], a * (0.8 + 0.2 * hl), z0=0.3 - (1 - a) * 1.2)
                bx, by = I(hx + hw / 2, hy + hd / 2, 1.0)
                design.badge(c, tpl, assets.icon_for(self.lb), bx, by - self.R - 6, self.R, a, hl, tone=icon_tone(self.lb.get("kind")), seed=3)
                if self.portrait:
                    self._label(c, self.lb.get("label", "Hub"), self.lb.get("sub"), bx + self.R + 26, by - self.R + 10, "left", a)
                else:
                    self._label(c, self.lb.get("label", "Hub"), self.lb.get("sub"), bx + self.R + 30, by - self.R + 10, "left", a)
        for nd in self.nodes:
            zi = self._zone_index(nd)
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
            self.cuboid(c, gx, gy, 1.6, 1.6, 1.25, base if (healthy or hl) else T["text2"], a * (1.0 if healthy else 0.7),
                        edge=T["accent"] if hl > 0.3 else None, z0=(1 - a) * 1.5)
            cx, cy = I(gx + 0.8, gy + 0.8, 1.25)
            if hl > 0.05:
                design.halo(c, cx, cy, 90, T["accent"], 0.5 * hl)
            if pulse and self.lb:
                k = clamp((t - pulse["t"]) / (1.4 * sc.motion))
                if k > 0:
                    x0, y0 = self.center(self.lb["id"])
                    p = skia.Path()
                    p.moveTo(x0, y0)
                    p.lineTo(cx, cy - 2 * self.R - 24)
                    design.stroke(c, tpl, p, a, ease(clamp(k * 1.6)), dashed=True,
                                  color=design.role_color(tpl, "success" if healthy else "fail"), seed=zi, arrow=True)
            design.badge(c, tpl, assets.icon_for(nd), cx, cy - self.R - 14, self.R, a, hl, tone=icon_tone(nd.get("kind")), seed=zi + 5)
            sl = sc.spec.get("state_labels") or {}
            state = None
            if pulse and clamp((t - pulse["t"]) / (1.4 * sc.motion)) > 0.6:
                state = sl.get("healthy", "healthy") if healthy else sl.get("unhealthy", "failing health check")
            lx = cx + self.R + 24
            stc = design.text_on(tpl, design.role_color(tpl, "success" if healthy else "fail"), T["bg0"] if tpl.dark else "#FFFFFF")
            self._label(c, nd.get("label", ""), state, lx, cy - self.R - 14, "left", a, sub_color=stc)
        self.draw_packets(c, t, self.center)

    def draw_packets(self, c, t, endpoint):
        for e, k in self.sc.packets(t):
            ax, ay = endpoint(e["from"])
            bx, by = endpoint(e["to"])
            kk = ease_io(clamp(k))
            packet_dot(c, self.sc, lerp(ax, bx, kk), lerp(ay, by, kk), 1 - clamp((k - 1) / 0.4) if k > 1 else 1.0)


class Cutaway(Treatment):
    """Inside one component: a framed shell with its name, the front end (with code lines), a router or index in the
    middle and the workers or stores it reaches. Every part carries an icon badge."""

    def layout(self):
        sc = self.sc
        els = sc.spec.get("elements", [])
        self.ng = next((e for e in els if e.get("kind") in CUT_PANEL), None)
        self.svc = next((e for e in els if e.get("kind") in CUT_ROUTER), None)
        self.pods = [e for e in els if e.get("kind") in CUT_WORKER]
        top = design.content_top(sc.spec, self.portrait)
        if self.portrait:
            self.shell = (60.0, top, 960.0, design.band_bottom(self.sc) - 10 - top)
            y = top + 96
            avail = top + self.shell[3] - 30 - y               # front end, index and stores share what is left
            gap = 70.0 if avail > 1000 else 44.0
            ng_h = min(360.0, (avail - 150 - 2 * gap) * 0.55)
            if self.ng:
                self.pos[self.ng["id"]] = (100, y, 880, ng_h)
            y += ng_h + gap
            if self.svc:
                self.pos[self.svc["id"]] = (240, y, 600, 150)
            y += 150 + gap
            n = max(1, len(self.pods))
            pw = (880 - (n - 1) * 30) / n
            ph = min(300.0, top + self.shell[3] - 30 - y)
            for i, p in enumerate(self.pods):
                self.pos[p["id"]] = (100 + i * (pw + 30), y, pw, ph)
            self.pos["_in"] = (530, top - 40, 20, 20)
            return
        self.shell = (100.0, top, 1720.0, 1010 - top)
        if self.ng:
            self.pos[self.ng["id"]] = (150, top + 110, 760, 1010 - top - 160)
        if self.svc:
            self.pos[self.svc["id"]] = (970, top + 110, 420, 150)
        n = max(1, len(self.pods))
        avail = 1010 - top - 160
        ph = min(260.0, (avail - (n - 1) * 30) / n)
        for i, p in enumerate(self.pods):
            self.pos[p["id"]] = (1420, top + 110 + i * (ph + 30), 360, ph)
        self.pos["_in"] = (40, 540, 20, 20)

    def camera(self, t):
        sc = self.sc
        k = ease_io(t / 0.9)
        base = lerp(1.06, 1.0, k)
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
        sc, T, tpl = self.sc, self.sc.T, self.sc.tpl
        a0 = ease(t / 0.5)
        sx, sy, sw, sh = self.shell

        def shell_fn(cc, w=sw, h=sh):
            rr = skia.Rect.MakeWH(w, h)
            cc.drawRoundRect(rr, 28, 28, paint(col(T["panel"], 0.5)))
            dash = paint(col(T["text2"] if not tpl.dark else T["line"]), 4)
            dash.setPathEffect(skia.DashPathEffect.Make([22, 14], 0))
            cc.drawRoundRect(rr, 28, 28, dash)
        design.sprite(c, ("shell", tpl.name, sw, sh), sx, sy, sw, sh, shell_fn, a0, pad=4)
        design.draw_text(c, sc.spec.get("container_label", ""), sx + 40, sy + 66, 44, col(T["text"], a0), "Bold")
        dim = sc.any_highlight(t)
        lk = sc.latest("lookup", t)
        flash = math.sin(clamp((t - lk["t"]) / 1.2) * math.pi) if lk else 0.0
        if self.ng:
            eid = self.ng["id"]
            x, y, w, h = self.pos[eid]
            a, hl = sc.vis(eid, t), sc.highlight(eid, t)
            design.card(c, tpl, x, y, w, h, a, hl, dim, seed=4)
            R = 60.0
            design.badge(c, tpl, assets.icon_for(self.ng), x + 30 + R, y + 30 + R, R, a, hl,
                         tone=KIND_COLOR.get(self.ng.get("kind"), "accent") if tpl.icon["style"] in ("pastel", "tint") else None, seed=4)
            rows, sz = design.fit_block(self.ng.get("label", "Component"), w - 2 * R - 90, 2, 44, 36, "SemiBold")
            for j, r in enumerate(rows):
                design.draw_text(c, r, x + 2 * R + 56, y + 30 + R + 14 - (len(rows) - 1) * sz * 0.55 + j * sz * 1.1, sz, col(T["text"], a), "SemiBold")
            code = sc.spec.get("code", [])
            cl = sc.latest("code", t)
            cy0 = y + 2 * R + 100
            for i, line in enumerate(code):
                ly = cy0 + i * 58
                shown = ease((t - (sc.show_at.get(eid, 0) + 0.3 + 0.12 * i)) / 0.4) * a
                active = cl is not None and i in cl.get("lines", [])
                if active:
                    k = ease((t - cl["t"]) / 0.3)
                    c.drawRoundRect(skia.Rect.MakeXYWH(x + 22, ly - 40, w - 44, 54), 8, 8, paint(col(T["green"], 0.22 * k * a)))
                f = design.make_font(design.fit_size(line, w - 80, 34, 30, mono=True), mono=True)
                text(c, design.ellipsize(line, w - 80, f.getSize(), mono=True), x + 40, ly, f, col(T["text"] if active or not dim else T["text2"], shown))
        if self.svc:
            eid = self.svc["id"]
            x, y, w, h = self.pos[eid]
            a, hl = sc.vis(eid, t), sc.highlight(eid, t)
            if a > 0.01:
                r = skia.Rect.MakeXYWH(x, y, w, h)
                amb = T["amber"]
                if hl > 0 or flash > 0:
                    design.soft_shadow(c, x, y, w, h, h / 2, amb, 0.45 * max(hl, flash) * a, 20)
                dp = paint(col(amb, a), 4)
                dp.setPathEffect(skia.DashPathEffect.Make([16, 11], 0))
                c.drawRoundRect(r, h / 2, h / 2, paint(col(T["panel"], a)))
                c.drawRoundRect(r, h / 2, h / 2, dp)
                R = 48.0
                design.badge(c, tpl, assets.icon_for(self.svc), x + 30 + R, y + h / 2, R, a, hl,
                             tone="amber" if tpl.icon["style"] in ("pastel", "tint") else None, seed=6)
                lab = self.svc.get("label", "Service")
                sz = design.fit_size(lab, w - 2 * R - 90, 44, 30, "SemiBold")
                design.draw_text(c, design.ellipsize(lab, w - 2 * R - 90, sz, "SemiBold"), x + 2 * R + 56, y + h / 2 + sz * 0.36, sz, col(T["text"], a), "SemiBold")
                st = sc.latest("strike", t)
                if st:
                    k = ease((t - st["t"]) / 0.5)
                    bx, by = x + w + 30, y + 8
                    text(c, st.get("text", "a program?"), bx, by + 40, font(32, "Medium"), col(T["text2"], k * a))
                    wd = font(32, "Medium").measureText(st.get("text", "a program?"))
                    k2 = ease((t - st["t"] - 0.7) / 0.35)
                    c.drawLine(bx - 6, by + 30, bx - 6 + (wd + 12) * k2, by + 30, paint(col(T["red"], a), 5))
                for i, p in enumerate(self.pods):
                    px, py, pw, ph = self.pos[p["id"]]
                    la = a * sc.vis(p["id"], t)
                    path = skia.Path()
                    if self.portrait:
                        path.moveTo(x + w / 2, y + h + 8)
                        path.lineTo(px + pw / 2, py - 10)
                    else:
                        path.moveTo(x + w / 2, y + h + 8)
                        path.lineTo(x + w / 2, py + ph / 2)
                        path.lineTo(px - 10, py + ph / 2)
                        path = design.ortho_path([(x + w / 2, y + h + 8), (x + w / 2, py + ph / 2), (px - 10, py + ph / 2)], 22)
                    design.stroke(c, tpl, path, la * (0.75 + 0.25 * flash), 1.0, dashed=True, color=amb, seed=i, flow=t)
                if self.ng:
                    nx, ny, nw, nh = self.pos[self.ng["id"]]
                    path = skia.Path()
                    if self.portrait:
                        path.moveTo(nx + nw / 2, ny + nh + 8)
                        path.lineTo(x + w / 2, y - 10)
                    else:
                        path.moveTo(nx + nw + 8, y + h / 2)
                        path.lineTo(x - 10, y + h / 2)
                    design.stroke(c, tpl, path, a, 1.0, color=amb if flash > 0 else None, seed=9)
        for p in self.pods:
            eid = p["id"]
            x, y, w, h = self.pos[eid]
            box(c, sc, x, y, w, h, p.get("label", "Worker"), p.get("kind", "pod"), sc.vis(eid, t), sc.highlight(eid, t), dim,
                sub=p.get("sub"), icon=p.get("icon"), R=52.0 if not self.portrait else 56.0,
                vertical=self.portrait)
        self.draw_packets(c, t, self.edge_point)


class Chart(Treatment):
    """Bars with value labels on top and category labels under them; the spec's title is the scene heading."""

    def draw(self, c, t):
        sc, T, tpl = self.sc, self.sc.T, self.sc.tpl
        data = sc.spec.get("data", [])
        if not data:
            return
        mx = max(d["value"] for d in data) or 1
        n = len(data)
        title = sc.spec.get("heading") or sc.spec.get("title")
        top = design.content_top(dict(sc.spec, heading=title), self.portrait)
        if title and not sc.spec.get("heading"):
            design.draw_heading(c, tpl, title, self.portrait, ease(t / 0.5))
        acc = T["accent"]
        if self.portrait:
            x0, x1, base = 90.0, 990.0, design.band_bottom(self.sc) - 150
        else:
            x0, x1, base = 200.0, 1720.0, 900.0
        bw = min(220.0 if not self.portrait else 200.0, (x1 - x0) / n * 0.62)
        slot = (x1 - x0) / n
        hmax = base - top - 80
        c.drawLine(x0 - 20, base, x1 + 20, base, paint(col(T["text2"]), 3))
        for i, d in enumerate(data):
            k = ease((t - 0.4 - i * 0.18 * sc.motion) / 0.8)
            h = hmax * d["value"] / mx * k
            cx = x0 + slot * (i + 0.5)
            colr = acc if d.get("accent") else T["blue"]
            r = skia.Rect.MakeXYWH(cx - bw / 2, base - h, bw, h)
            if tpl.jitter:
                p = skia.Path()
                p.addRect(r)
                c.drawPath(p, paint(col(colr, 0.85)))
                c.drawPath(design.sketchify(p, i, tpl.jitter), paint(col("#2A2A2A"), 3))
            else:
                c.drawRoundRect(r, 10, 10, paint(col(colr, 0.95)))
            rows, sz = design.fit_block(d["label"], slot - 20, 2, 32, 30)
            for j, row in enumerate(rows):
                design.draw_text(c, row, cx, base + 48 + j * sz * 1.15, sz, col(T["text2"], k), "Regular", "center")
            design.draw_text(c, str(d["value"]), cx, base - h - 20, 44, col(T["text"], k), "Bold", "center")


FOOTAGE_DIR = Path(__file__).resolve().parent.parent / "assets" / "footage"


def footage_path(spec: dict) -> Path:
    return FOOTAGE_DIR / Path(str(spec.get("src", ""))).name      # only files vendored in assets/footage


class Footage:
    """{"treatment": "footage", "src": "<file in exposit/assets/footage>", "align": {"word", "beat"}}: a recorded clip
    played as-is (no re-styling, no overlays). Its own sound is mixed under the narration and music. The director sets
    pad_start so the aligned word lands on the beat, and pad_end so the scene lasts exactly as long as the clip."""

    def __init__(self, sc):
        self.sc, self.portrait, self.pos, self.fade_out, self.fade_in = sc, sc.portrait, {}, False, False
        self.path = footage_path(sc.spec)

    def center(self, _id):
        return 0.0, 0.0

    def draw(self, canvas, t: float, w: int, h: int) -> None:
        canvas.drawImage(footage_frame(str(self.path), round(t, 3), w, h), 0, 0)


@functools.lru_cache(maxsize=8)
def footage_frame(path: str, t: float, w: int, h: int) -> skia.Image:
    """One decoded frame of a footage clip, scaled to w x h (the last frame when t is past the end)."""
    dur = footage_duration(path)
    t = min(max(0.0, t), max(0.0, dur - 1 / 60))
    out = subprocess.run([config.ffmpeg_exe(), "-loglevel", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1",
                          "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgba", "-"], capture_output=True, check=True).stdout
    if len(out) < w * h * 4:                               # past the last decodable frame: step back a little
        return footage_frame(path, max(0.0, t - 0.05), w, h) if t > 0.05 else skia.Image.fromarray(np.zeros((h, w, 4), np.uint8))
    arr = np.frombuffer(out[: w * h * 4], np.uint8).reshape(h, w, 4).copy()
    return skia.Image.fromarray(arr, skia.kRGBA_8888_ColorType)


@functools.lru_cache(maxsize=16)
def footage_duration(path: str) -> float:
    from .. import compose
    return float(compose.probe(path).get("duration", 0.0))


def render_footage(spec: dict, dur: float, out_path: str, w: int, h: int, fps: int) -> dict:
    """The clip scaled to the frame, at the production frame rate, held on its last frame if the scene runs longer."""
    src = footage_path(spec)
    extra = max(0.0, dur - footage_duration(str(src)))
    vf = f"scale={w}:{h},fps={fps}" + (f",tpad=stop_mode=clone:stop_duration={extra:.3f}" if extra > 0 else "")
    subprocess.run([config.ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(src), "-vf", vf, "-an", "-t", f"{dur:.3f}",
                    "-c:v", "libx264", "-preset", config.X264_PRESET, "-crf", config.X264_CRF, "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", out_path], check=True)
    return {"duration": dur, "frames": int(round(dur * fps))}


TREATMENTS = {"flow2d": Flow2D, "kinetic": Kinetic, "isometric": Isometric, "cutaway": Cutaway, "chart": Chart}
LEGACY_TREATMENTS = tuple(TREATMENTS)
from .pro import PRO_TREATMENTS          # noqa: E402  (pro imports engine lazily)
from . import motion                      # noqa: E402
TREATMENTS.update(PRO_TREATMENTS)
TREATMENTS["motion"] = motion.MotionScene
TREATMENTS["footage"] = Footage


# ------------------------------------------------------------------ frame + clip
def active_word_group(sc, t: float) -> tuple[dict, int] | None:
    """The word group on screen at t and the index of the word being spoken (the last one that has started)."""
    for g in sc.word_groups:
        if g["s"] - 0.05 <= t <= g["e"] + 0.25:
            k = 0
            for i, w in enumerate(g["words"]):
                if w["s"] <= t:
                    k = i
            return g, k
    return None


def draw_word_captions(canvas: skia.Canvas, sc, t: float, cx: float, top: float, size: float, max_w: float) -> None:
    """Reels-style captions: 2 to 4 words, large and bold, the spoken word in the accent colour.
    Shrinks the type when a group of long words would not fit in max_w."""
    hit = active_word_group(sc, t)
    if not hit:
        return
    g, k = hit
    T = sc.T
    words = [w["w"] for w in g["words"]]
    f = font(size, "Bold")
    gap = f.measureText(" ")
    total = sum(f.measureText(w) for w in words) + gap * (len(words) - 1)
    if total > max_w:
        size = size * max_w / total
        f = font(size, "Bold")
        gap = f.measureText(" ")
        total = sum(f.measureText(w) for w in words) + gap * (len(words) - 1)
    pad_x, h = size * 0.5, size * 1.5
    r = skia.Rect.MakeXYWH(cx - total / 2 - pad_x, top, total + 2 * pad_x, h)
    canvas.drawRoundRect(r, size * 0.3, size * 0.3, paint(col("#000000", 0.62)))
    x, base = cx - total / 2, top + h / 2 + size * 0.36
    rest = T["text2"] if T["accent"].upper() == "#FFFFFF" else "#FFFFFF"    # Mono theme: white accent, so dim the other words
    for i, w in enumerate(words):
        text(canvas, w, x, base, f, col(T["accent"] if i == k else rest))
        x += f.measureText(w) + gap


def style_time(tr, t: float) -> float:
    """Style motion rules: a 12 or 18 fps feel holds each drawing for several output frames."""
    st = styles.style_of(tr.sc.tpl)
    if st and st.fps:
        return math.floor(t * st.fps + 1e-6) / st.fps
    return t


def draw_frame(canvas: skia.Canvas, tr: Treatment, t: float, w: int, h: int, captions: bool = True) -> None:
    if isinstance(tr, Footage):                             # recorded footage is shown as-is: no style, no overlays
        return tr.draw(canvas, t, w, h)
    design.set_active(tr.sc.tpl)
    t = style_time(tr, t)
    st = styles.style_of(tr.sc.tpl)
    if st and st.jitter:                                    # stop-motion: the whole set shifts a little per drawing
        k = int(t * (st.fps or 12))
        canvas.save()
        canvas.translate(math.sin(k * 12.9898) * st.jitter * w / 1080, math.cos(k * 78.233) * st.jitter * w / 1080)
        try:
            _draw_frame(canvas, tr, t, w, h, captions)
        finally:
            canvas.restore()
    else:
        _draw_frame(canvas, tr, t, w, h, captions)
    if st and st.post:                                      # textures (grain, paper, vignette...) as image blits
        styles.overlay(canvas, st.post, w, h, int(t * 30))


def _draw_frame(canvas: skia.Canvas, tr: Treatment, t: float, w: int, h: int, captions: bool = True) -> None:
    if isinstance(tr, Footage):
        return tr.draw(canvas, t, w, h)
    sc, T = tr.sc, tr.sc.T
    if tr.portrait:
        return draw_frame_portrait(canvas, tr, t, w, h, captions)
    canvas.save()
    canvas.scale(w / 1920.0, h / 1080.0)
    if not getattr(tr, "no_background", False):
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
    _effects_before(canvas, tr, t, 1920, 1080)
    canvas.save()
    canvas.translate(*getattr(tr, "shift", (0.0, 0.0)))   # match-cut carry (transitions)
    canvas.translate(960, 540)
    canvas.scale(s, s)
    canvas.translate(-fx, -fy)
    canvas.translate(0, -_scroll(tr, t))
    tr.draw(canvas, t)
    _effects_after_stage(canvas, tr, t, 1920, 1080)
    canvas.restore()
    _effects_after(canvas, tr, t, 1920, 1080)
    # overlays, not affected by the camera
    title = sc.spec.get("heading")
    if title:
        design.draw_heading(canvas, sc.tpl, title, False, ease((t - 0.2) / 0.5))
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
        canvas.drawRoundRect(r, 16, 16, paint(col(T["bg0"] if sc.tpl.dark else "#FFFFFF", 0.96 * k)))   # opaque: it overlays content
        canvas.drawRoundRect(r, 16, 16, paint(col(T["accent"], 0.20 * k)))
        canvas.drawRoundRect(r, 16, 16, paint(col(T["accent"], k), 2))
        text(canvas, co.get("text", ""), 960, r.top() + 53, f, col(T["text"], k), "center")
    if captions and sc.caption_style == "word":
        draw_word_captions(canvas, sc, t, 960, 900, 72, 1500)
    elif captions:
        for cp in sc.captions:
            if cp["s"] - 0.05 <= t <= cp["e"] + 0.25:
                f = font(36, "Medium")
                wd = f.measureText(cp["text"])
                r = skia.Rect.MakeXYWH(960 - wd / 2 - 26, 946, wd + 52, 62)
                canvas.drawRoundRect(r, 12, 12, paint(col("#000000", 0.62)))
                text(canvas, cp["text"], 960, 989, f, col("#FFFFFF"), "center")
                break
    _intertitle(canvas, tr, t, 1920, 1080)
    fade = min(clamp(t / 0.3) if getattr(tr, "fade_in", True) else 1.0,
               clamp((sc.dur - t) / 0.3) if getattr(tr, "fade_out", True) else 1.0)
    if fade < 1:
        design.sprite(canvas, ("fade", T["bg0"]), 0, 0, 1920, 1080, lambda cc: cc.drawColor(col(T["bg0"])), 1 - fade)   # cached, blitted
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
    if not getattr(tr, "no_background", False):
        background(canvas, sc, 1080, 1920)
    s, fx, fy = stage_camera(tr, t)
    _effects_before(canvas, tr, t, 1080, 1920)
    canvas.save()
    canvas.translate(*getattr(tr, "shift", (0.0, 0.0)))
    canvas.translate(tr.CX, tr.CY)
    canvas.scale(s, s)
    canvas.translate(-fx, -fy)
    canvas.translate(0, -_scroll(tr, t))
    tr.draw(canvas, t)
    _effects_after_stage(canvas, tr, t, 1080, 1920)
    canvas.restore()
    _effects_after(canvas, tr, t, 1080, 1920)
    title = sc.spec.get("heading")
    if title:
        design.draw_heading(canvas, sc.tpl, title, True, ease((t - 0.2) / 0.5))
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
        canvas.drawRoundRect(r, 16, 16, paint(col(T["bg0"] if sc.tpl.dark else "#FFFFFF", 0.96 * k)))
        canvas.drawRoundRect(r, 16, 16, paint(col(T["accent"], 0.20 * k)))
        canvas.drawRoundRect(r, 16, 16, paint(col(T["accent"], k), 2))
        for j, row in enumerate(rows):
            text(canvas, row, 540, r.top() + 58 + j * 54, f, col(T["text"], k), "center")
    if captions and sc.caption_style == "word":
        draw_word_captions(canvas, sc, t, 540, 1350, 88, 900)    # box ends by y 1482, inside the 1500 safe line
    elif captions:
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
    _intertitle(canvas, tr, t, 1080, 1920)
    fade = min(clamp(t / 0.3) if getattr(tr, "fade_in", True) else 1.0,
               clamp((sc.dur - t) / 0.3) if getattr(tr, "fade_out", True) else 1.0)
    if fade < 1:
        design.sprite(canvas, ("fade", T["bg0"]), 0, 0, 1080, 1920, lambda cc: cc.drawColor(col(T["bg0"])), 1 - fade)
    canvas.restore()


def build(spec: dict, timing: dict, theme: str = "premium-technical", portrait: bool = False, caption_style: str = "phrase",
          captions: bool = False) -> Treatment:
    """`captions`: burned-in captions will be drawn, so 9:16 content keeps clear of them (stops at y 1340)."""
    st = styles.style_of(design.template(spec.get("theme") or theme))
    if st and st.effects and "effects" not in spec:          # a style's default motion effects ([] means none)
        spec = dict(spec, effects=[{"type": e} for e in st.effects])
    sc = Scene(spec, timing, theme)
    sc.portrait = portrait
    sc.caption_band = bool(captions) and portrait
    design.set_active(sc.tpl)                              # layouts measure text in the template's fonts
    sc.caption_style = caption_style if caption_style in CAPTION_STYLES else "phrase"
    if portrait:                                           # shorter caption cues for a narrow frame
        sc.captions = [dict(c, s=c["s"] + sc.pad0, e=c["e"] + sc.pad0) for c in caption_chunks(timing, 30)]
    return TREATMENTS.get(spec.get("treatment", "flow2d"), Flow2D)(sc)


def render_still(spec: dict, timing: dict, t: float | None = None, w: int = 960, h: int = 540,
                 theme: str = "premium-technical", captions: bool = False, caption_style: str = "phrase",
                 caption_band: bool | None = None) -> bytes:
    """`caption_band` lays out for burned-in captions without drawing them (storyboards); defaults to `captions`."""
    tr = build(spec, timing, theme, portrait=h > w, caption_style=caption_style,
               captions=captions if caption_band is None else caption_band)
    surf = skia.Surface(w, h)
    tt = tr.sc.dur * 0.62 if t is None else t
    draw_frame(surf.getCanvas(), tr, tt, w, h, captions)
    st = styles.style_of(tr.sc.tpl)
    if st and st.post and styles.needs_pixels(st.post):    # style post-process, on the pixels
        arr = np.zeros((h, w, 4), dtype=np.uint8)
        surf.readPixels(skia.ImageInfo.Make(w, h, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType), arr)
        styles.post_process(arr, st.post, int(style_time(tr, tt) * 30))
        return bytes(skia.Image.fromarray(arr, skia.kRGBA_8888_ColorType).encodeToData(skia.kPNG, 90))
    return bytes(surf.makeImageSnapshot().encodeToData(skia.kPNG, 90))


# ------------------------------------------------------------------ transitions between scenes
# A scene's spec may name how it enters: {"transition": "fade" | "crossfade" | "slide" | "push" | "match"}.
# "fade" (the default) fades in from the background. The others need the previous scene's last frame and run inside
# the incoming scene's opening padding, so narration timing is unchanged; the previous scene then does not fade out.
# "match" carries the scene so that an element present in both (same id) starts where it was and eases into place.
TRANSITIONS = ("fade", "crossfade", "slide", "push", "match", "cut")
BLENDS = ("crossfade", "slide", "push", "match")          # transitions that need the previous scene's last frame
# "cut": no fade at all; for a scene that continues exactly from the previous one's final frame.
TRANSITION_SECONDS = 0.45


def needs_prev(spec: dict) -> bool:
    return spec.get("transition", "fade") in BLENDS


def last_frame(tr: Treatment, w: int, h: int, captions: bool) -> skia.Image:
    """The previous scene's final frame (it does not fade out when the next scene transitions from it)."""
    tr.fade_out = False
    surf = skia.Surface(w, h)
    draw_frame(surf.getCanvas(), tr, max(0.0, tr.sc.dur - 1 / 30), w, h, captions)
    return surf.makeImageSnapshot()


def _match_shift(tr: Treatment, prev: Treatment, w: int, h: int) -> tuple[float, float]:
    """Logical-space offset that puts the first shared element where it was in the previous scene."""
    shared = [i for i in tr.pos if not i.startswith("_") and i in getattr(prev, "pos", {})]
    if not shared:
        return 0.0, 0.0
    (x1, y1), (x0, y0) = tr.center(shared[0]), prev.center(shared[0])
    return x0 - x1, y0 - y1


def transition_frame(canvas: skia.Canvas, tr: Treatment, t: float, w: int, h: int, captions: bool,
                     prev_img: skia.Image | None, kind: str, shift: tuple[float, float] = (0.0, 0.0),
                     scratch: skia.Surface | None = None) -> None:
    """Draws frame t of `tr`, composited with the previous scene's last frame while the transition runs."""
    k = ease_io(clamp(t / TRANSITION_SECONDS))
    if prev_img is None or kind not in BLENDS or k >= 1:
        tr.shift = (0.0, 0.0)
        draw_frame(canvas, tr, t, w, h, captions)
        return
    tr.fade_in = False
    if kind == "match":
        tr.shift = (shift[0] * (1 - k), shift[1] * (1 - k))
        draw_frame(canvas, tr, t, w, h, captions)
        canvas.drawImage(prev_img, 0, 0, skia.SamplingOptions(), skia.Paint(Alphaf=clamp(1 - k * 1.8)))
        return
    tr.shift = (0.0, 0.0)
    if kind == "crossfade":
        draw_frame(canvas, tr, t, w, h, captions)
        canvas.drawImage(prev_img, 0, 0, skia.SamplingOptions(), skia.Paint(Alphaf=1 - k))
        return
    scratch = scratch or skia.Surface(w, h)
    draw_frame(scratch.getCanvas(), tr, t, w, h, captions)
    cur = scratch.makeImageSnapshot()
    canvas.clear(skia.ColorBLACK)
    if kind == "slide":                                   # the new scene slides in over the old one
        canvas.drawImage(prev_img, 0, 0)
        canvas.drawImage(cur, w * (1 - k), 0)
    else:                                                 # push: the new scene pushes the old one out
        canvas.drawImage(prev_img, -w * k, 0)
        canvas.drawImage(cur, w * (1 - k), 0)


def render_clip(spec: dict, timing: dict, out_path: str, w: int = config.WIDTH, h: int = config.HEIGHT,
                fps: int = config.FPS, theme: str = "premium-technical", captions: bool = True,
                progress: Callable[[float], None] | None = None, caption_style: str = "phrase",
                prev: dict | None = None, fade_out: bool = True) -> dict:
    """Render one scene to a silent H.264 clip. Returns duration and frame count.
    `prev` ({"spec", "timing"}) is the previous scene, used when this scene's transition needs its last frame;
    `fade_out=False` when the next scene transitions from this one."""
    if spec.get("treatment") == "footage":
        return render_footage(spec, Scene(spec, timing, theme).dur, out_path, w, h, fps)
    tr = build(spec, timing, theme, portrait=h > w, caption_style=caption_style, captions=captions)
    tr.fade_out = fade_out
    kind = spec.get("transition", "fade")
    if kind == "cut":
        tr.fade_in = False
    prev_img, shift = None, (0.0, 0.0)
    if prev and needs_prev(spec):
        ptr = build(prev["spec"], prev["timing"], theme, portrait=h > w, caption_style=caption_style, captions=captions)
        prev_img = last_frame(ptr, w, h, captions)
        shift = _match_shift(tr, ptr, w, h)
        design.set_active(tr.sc.tpl)
    n = max(1, int(round(tr.sc.dur * fps)))
    st = styles.style_of(tr.sc.tpl)
    surf = skia.Surface(w, h)                             # native pixel order: cached layers blit without conversion
    scratch = skia.Surface(w, h) if prev_img is not None else None
    canvas = surf.getCanvas()
    frame = np.zeros((h, w, 4), dtype=np.uint8)
    rgba = skia.ImageInfo.Make(w, h, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)
    cmd = [config.ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}",
           "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264", "-preset", config.X264_PRESET, "-crf", config.X264_CRF,
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for i in range(n):
            transition_frame(canvas, tr, i / fps, w, h, captions, prev_img, kind, shift, scratch)
            surf.readPixels(rgba, frame)                  # one conversion to RGBA per frame (about 3 ms at 1080p)
            if st and st.post and styles.needs_pixels(st.post):   # pixel-level steps (sepia, pixelation...)
                styles.post_process(frame, st.post, int(style_time(tr, i / fps) * 30))
            proc.stdin.write(memoryview(frame))
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


def T_bg(sc) -> str:
    return sc.T["bg0"] if sc.tpl.dark else "#FFFFFF"


# ------------------------------------------------------------------ cover image
def _visual_still(spec: dict, timing: dict, theme: str, w: int, h: int) -> skia.Image:
    """The scene at its most complete moment, without its heading, titles, step markers or captions."""
    v = {k: x for k, x in spec.items() if k not in ("heading",)}
    if v.get("treatment") == "cards":
        v.pop("title", None)
    v["cues"] = [c for c in v.get("cues", []) if c.get("action") not in ("count", "callout", "highlight")]
    v["camera"] = {}
    v["effects"] = []                                     # no focus dimming, scrolling or parallax on a cover
    tr = build(v, timing, theme, portrait=h > w)
    tr.fade_out = False
    tr.no_background = True                               # drawn straight onto the cover's own background
    t = max(0.0, tr.sc.dur - 0.45)
    surf = skia.Surface(w, h)
    surf.getCanvas().clear(skia.ColorTRANSPARENT)
    draw_frame(surf.getCanvas(), tr, t, w, h, False)
    return surf.makeImageSnapshot()


def render_cover(theme: str, headline: str, kicker: str = "", visual: tuple[dict, dict] | None = None,
                 portrait: bool = True, brand: str = "") -> bytes:
    """A cover in the production's template: a kicker, the headline, the first iconflow or cards scene as the visual,
    and a small brand badge. 9:16 covers are 1080x1920 with everything between y 240 and 1680 (the area feeds and
    profile grids keep); 16:9 covers are 1920x1080. Returns PNG bytes."""
    tpl = design.template(theme)
    design.set_active(tpl)
    T = tpl.T
    W, H = (1080, 1920) if portrait else (1920, 1080)
    surf = skia.Surface(W, H)
    c = surf.getCanvas()
    design.background(c, tpl, W, H)
    acc = design.text_on(tpl, tpl.conn["active"] if tpl.dark else T["accent"])
    if portrait:
        x0, maxw, y = 80.0, 920.0, 300.0
    else:
        x0, maxw, y = 110.0, 760.0, 260.0
    if kicker:
        f = design.make_font(40, "Bold")
        xx = x0
        for ch in kicker.upper():                          # letter-spaced kicker
            design.put_text(c, ch, xx, y, f, col(acc))
            xx += f.measureText(ch) + 9
        y += 40
    rows, sz = design.fit_block(headline, maxw, 3, 132 if portrait else 120, 80, "Bold")
    for j, r in enumerate(rows):
        design.draw_text(c, r, x0, y + sz * 0.95 + j * sz * 1.04, sz, col(T["text"]), "Bold")
    y += sz * 0.95 + (len(rows) - 1) * sz * 1.04 + 60
    if portrait:
        box = (60.0, y, 960.0, 1580.0 - y)
    else:
        box = (960.0, 140.0, 860.0, 800.0)
    if visual:
        spec, timing = visual
        vw, vh = (1080, 1920) if portrait else (1920, 1080)
        img = _visual_still(spec, timing, theme, vw, vh)
        sy0, sy1 = (design.PORTRAIT_BAND[0] - 14, design.PORTRAIT_BAND[1] + 14) if portrait else (60, 1040)
        src = skia.Rect.MakeLTRB(0, sy0, vw, sy1)
        bx, by, bw, bh = box
        k = min(bw / src.width(), bh / src.height())
        dw, dh = src.width() * k, src.height() * k
        dst = skia.Rect.MakeXYWH(bx + (bw - dw) / 2, by + (bh - dh) / 2, dw, dh)
        c.drawImageRect(img, src, dst, skia.SamplingOptions(skia.FilterMode.kLinear))
    if brand:                                              # small badge, bottom left of the safe area
        f = design.make_font(36, "Bold")
        tw = f.measureText(brand)
        bx, by = (80.0, 1600.0) if portrait else (110.0, 940.0)
        r = skia.Rect.MakeXYWH(bx, by, tw + 104, 64)
        c.drawRoundRect(r, 32, 32, design.paint(col(T["bg0"], 0.9)))
        c.drawRoundRect(r, 32, 32, design.paint(col(tpl.conn["active"]), 3))
        assets.draw_icon(c, "network", bx + 38, by + 32, 34, acc, 1.0, 2.75)
        design.put_text(c, brand, bx + 66, by + 44, f, col(T["text"]))
    st = styles.style_of(tpl)                              # the cover carries the video's style: textures, pixels
    if st and st.post:
        styles.overlay(c, st.post, W, H, 0)
        if styles.needs_pixels(st.post):
            arr = np.zeros((H, W, 4), dtype=np.uint8)
            surf.readPixels(skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType), arr)
            styles.post_process(arr, st.post, 0)
            return bytes(skia.Image.fromarray(arr, skia.kRGBA_8888_ColorType).encodeToData(skia.kPNG, 100))
    return bytes(surf.makeImageSnapshot().encodeToData(skia.kPNG, 100))


# ------------------------------------------------------------------ wrapper motion effects (motion.WRAPPERS)
def _scroll(tr, t: float) -> float:
    e = motion.wrapper_spec(tr.sc.spec, "pinned_heading")
    return motion.pinned_scroll(t, tr.sc.dur, float(e.get("distance", 500))) if e else 0.0


def _effects_before(canvas, tr, t: float, W: float, H: float) -> None:
    e = motion.wrapper_spec(tr.sc.spec, "parallax")
    if e:
        motion.parallax_layers(canvas, tr.sc.tpl, W, H, t, tr.sc.dur, int(e.get("layers", 4)), float(e.get("opacity", 1.0)))


def _effects_after_stage(canvas, tr, t: float, W: float, H: float) -> None:
    """Effects drawn in the treatment's own coordinates (they follow its layout)."""
    e = motion.wrapper_spec(tr.sc.spec, "focus_frame")
    if not e:
        return
    rects, times = [], []
    prev = 0.6
    for tg in e.get("targets", []):
        tid = tg.get("id") if isinstance(tg, dict) else tg
        if tid not in tr.pos:
            continue
        x, y, w, h = tr.pos[tid]
        pad = float(e.get("pad", 34))
        below = float(e.get("below", 130 if tr.sc.spec.get("treatment") in ("iconflow", "sequence") else 0))
        side = float(e.get("side", 60 if w < 260 else 0))
        if getattr(tr, "side", False):                    # labels beside the badges (9:16 single column)
            right = design.PORTRAIT_X[1] - (x + w) - 10
            rects.append((x - pad, y - pad, w + pad + right, h + 2 * pad))
        else:
            rects.append((x - pad - side, y - pad, w + 2 * (pad + side), h + 2 * pad + below))
        tt = tr.sc.cue_time(tg.get("at")) if isinstance(tg, dict) and tg.get("at") is not None else None
        prev = tt if tt is not None else prev + 1.2
        times.append(prev)
    W2, H2 = (1080, 1920) if tr.portrait else (1920, 1080)
    motion.focus_frame(canvas, tr.sc.tpl, rects, times, t, W2, H2 + 2000)
    if rects and t >= times[0] and hasattr(tr, "draw_labels"):    # labels stay readable above the dimming
        tr.draw_labels(canvas, t)


def _effects_after(canvas, tr, t: float, W: float, H: float) -> None:
    if motion.wrapper_spec(tr.sc.spec, "pinned_heading") and tr.sc.spec.get("heading"):
        motion.heading_mask(canvas, tr.sc.tpl, W, design.content_top(tr.sc.spec, tr.portrait) - 10)


def _intertitle(canvas, tr, t: float, W: float, H: float) -> None:
    """Silent film: the scene's heading as a 1.5 s intertitle in its opening pause, dissolving into the scene."""
    text = getattr(tr.sc, "intertitle", None)
    if not text:
        return
    end = styles.INTERTITLE_SECONDS
    if t >= end + 0.3:
        return
    a = 1.0 if t < end else 1 - (t - end) / 0.3
    styles.draw_intertitle(canvas, tr.sc.tpl, text, W, H, a)
