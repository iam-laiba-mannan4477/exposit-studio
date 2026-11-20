"""Design system for the renderer: templates, typography, drawing primitives and motion.

A template is a full design system, not a palette: background (gradient, vignette, grid or dots), card style (fill,
border, radius, shadow, glass), icon style (filled badge or outline), connector style, semantic colours (success,
fail, info), a type scale, glow on or off, and for "sketch" a deterministic hand-drawn jitter.

Every template also defines the colour keys the original treatments read from `sc.T` (bg0, bg1, grid, panel, line,
text, text2, accent, blue, teal, green, amber, red, pink), so old specs render in any template.

The renderer is single-threaded per process; the active template (for fonts) is set by draw_frame.
"""
from __future__ import annotations
import functools, math
import skia
from . import assets

# ------------------------------------------------------------------ colour helpers


def col(hex_: str, a: float = 1.0) -> int:
    h = hex_.lstrip("#")
    return skia.Color(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(max(0.0, min(1.0, a)) * 255))


def mix(h1: str, h2: str, k: float) -> str:
    a, b = h1.lstrip("#"), h2.lstrip("#")
    c = [round(int(a[i:i + 2], 16) * (1 - k) + int(b[i:i + 2], 16) * k) for i in (0, 2, 4)]
    return "#" + "".join(f"{v:02X}" for v in c)


def luminance(h: str) -> float:
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(h1: str, h2: str) -> float:
    l1, l2 = sorted((luminance(h1), luminance(h2)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


# ------------------------------------------------------------------ templates
LEGACY = {
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


class Template:
    """One design system. `T` holds the colour keys; the other attributes are design rules."""

    def __init__(self, name: str, T: dict, *, dark: bool, bg: str, card: dict, icon: dict, conn: dict, sem: dict,
                 glow: bool, family: str = "Inter", label_mono: bool = False, jitter: float = 0.0, vignette: float = 0.0,
                 title_weight: str = "Bold", legacy: bool = False, map_style: str = "dots"):
        self.name, self.T, self.dark, self.bg = name, T, dark, bg
        self.card, self.icon, self.conn, self.sem = card, icon, conn, sem
        self.glow, self.family, self.label_mono, self.jitter = glow, family, label_mono, jitter
        self.vignette, self.title_weight, self.legacy, self.map_style = vignette, title_weight, legacy, map_style

    def __repr__(self):
        return f"Template({self.name})"


def _legacy(name: str) -> Template:
    T = LEGACY[name]
    return Template(name, T, dark=True, bg="legacy", legacy=True, glow=True,
                    card=dict(fill=T["panel"], border=T["line"], width=2.0, radius=18, shadow=0.0, glass=False),
                    icon=dict(style="tint", color=None, badge=T["panel"], ring=None, stroke=2.0),
                    conn=dict(color=T["line"], width=3.0, active=T["accent"], glow=False, dash=(14, 10)),
                    sem=dict(success=T["green"], fail=T["red"], info=T["blue"], neutral=T["text2"]))


TEMPLATES: dict[str, Template] = {n: _legacy(n) for n in LEGACY}

TEMPLATES["paper"] = Template(
    "paper", dict(bg0="#F6F8FA", bg1="#EEF2F6", grid="#DDE3EA", panel="#FFFFFF", line="#C9D2DD", text="#0F2540",
                  text2="#4E6079", accent="#1F5FA8", blue="#1F5FA8", teal="#0F7F86", green="#1E7B3C", amber="#A86400",
                  red="#C0392B", pink="#8E3A73"),
    dark=False, bg="paper", glow=False, vignette=0.0,
    card=dict(fill="#FFFFFF", border="#D5DDE7", width=1.6, radius=20, shadow=0.10, shadow_color="#0B1F3A", glass=False),
    icon=dict(style="badge", color="#FFFFFF", badge="#173A63", ring="#173A63", stroke=1.9),
    conn=dict(color="#24364F", width=3.0, active="#1F5FA8", glow=False, dash=(12, 9)),
    sem=dict(success="#1E7B3C", fail="#2B2F36", info="#1F5FA8", neutral="#4E6079"))

TEMPLATES["noir-network"] = Template(
    "noir-network", dict(bg0="#050C1B", bg1="#0B1D3A", grid="#14305A", panel="#0C1D38", line="#2C5A8C", text="#EAF4FF",
                         text2="#8FB3D9", accent="#38D6F5", blue="#4FA3FF", teal="#38D6F5", green="#3EE3A0", amber="#FFC04D",
                         red="#FF5C7A", pink="#C98BFF"),
    dark=True, bg="noir", glow=True, vignette=0.55,
    card=dict(fill="#0E2445", border="#3C6FA8", width=1.6, radius=18, shadow=0.35, shadow_color="#000000", glass=True),
    icon=dict(style="badge", color="#FFFFFF", badge="#1D4E86", ring="#38D6F5", stroke=1.9),
    conn=dict(color="#3D7DBF", width=2.6, active="#38D6F5", glow=True, dash=(10, 9)),
    sem=dict(success="#3EE3A0", fail="#FF5C7A", info="#4FA3FF", neutral="#8FB3D9"))

TEMPLATES["blueprint"] = Template(
    "blueprint", dict(bg0="#0B2A5B", bg1="#0E3470", grid="#2D5A9A", panel="#0F3270", line="#CFE0FF", text="#F4F8FF",
                      text2="#B9CDF0", accent="#FFD166", blue="#9CC3FF", teal="#7FE7E0", green="#8FF0B0", amber="#FFD166",
                      red="#FF8A8A", pink="#F3A6FF"),
    dark=True, bg="blueprint", glow=False, label_mono=True, vignette=0.25, title_weight="SemiBold",
    card=dict(fill="#0E3170", border="#DCE8FF", width=1.5, radius=4, shadow=0.0, glass=False, ticks=True),
    icon=dict(style="outline", color="#F4F8FF", badge=None, ring="#DCE8FF", stroke=1.6),
    conn=dict(color="#DCE8FF", width=2.0, active="#FFD166", glow=False, dash=(8, 7)),
    sem=dict(success="#8FF0B0", fail="#FF8A8A", info="#9CC3FF", neutral="#B9CDF0"))

TEMPLATES["sketch"] = Template(
    "sketch", dict(bg0="#FFFFFF", bg1="#FBFAF7", grid="#ECE9E2", panel="#FFFFFF", line="#3A3A3A", text="#1F1F1F",
                   text2="#555555", accent="#2F7FD8", blue="#2F7FD8", teal="#1A9A8A", green="#2E9E4F", amber="#D98A00",
                   red="#D2453C", pink="#C2588F"),
    dark=False, bg="sketch", glow=False, family="Caveat", jitter=1.6, title_weight="Bold",
    card=dict(fill="#FFFFFF", border="#2A2A2A", width=2.2, radius=10, shadow=0.0, glass=False),
    icon=dict(style="pastel", color="#2A2A2A", badge=None, ring="#2A2A2A", stroke=2.0),
    conn=dict(color="#2F7FD8", width=2.6, active="#2F7FD8", glow=False, dash=(10, 9)),
    sem=dict(success="#2E9E4F", fail="#D2453C", info="#2F7FD8", neutral="#555555"))

PASTELS = {"blue": "#CFE3FA", "teal": "#C8EEE8", "green": "#D4F1D8", "amber": "#FDEBC4", "red": "#F9D2CF",
           "pink": "#F4D3E6", "accent": "#CFE3FA", "text2": "#E9E9E9", "line": "#E9E9E9"}

NEW_TEMPLATES = ("paper", "noir-network", "blueprint", "sketch")
ALL_TEMPLATES = tuple(TEMPLATES)


def template(name: str | None) -> Template:
    return TEMPLATES.get(name or "", TEMPLATES["premium-technical"])


# ------------------------------------------------------------------ typography (template-aware)
_active: list[Template] = [TEMPLATES["premium-technical"]]


def set_active(tpl: Template) -> None:
    _active[0] = tpl


def active() -> Template:
    return _active[0]


@functools.lru_cache(maxsize=4)
def _caveat(bold: bool) -> skia.Typeface:
    tf = assets.typeface("Caveat")
    if not bold:
        return tf
    C = skia.FontArguments.VariationPosition.Coordinate
    fa = skia.FontArguments()
    fa.setVariationDesignPosition(skia.FontArguments.VariationPosition(skia.FontArguments.VariationPosition.Coordinates([C(0x77676874, 700.0)])))
    return tf.makeClone(fa)


def family_key() -> str:
    t = active()
    return t.family + ("+mono" if t.label_mono else "")


def make_font(size: float, weight: str = "Regular", mono: bool = False) -> skia.Font:
    """Font for the active template. Sketch uses Caveat (scaled up, it runs small); blueprint sets labels
    (Regular and Medium) in JetBrains Mono; everything else is Inter."""
    t = active()
    if mono:
        tf = assets.typeface("Mono")
    elif t.family == "Caveat":
        tf, size = _caveat(weight in ("SemiBold", "Bold")), size * 1.28
    elif t.label_mono and weight in ("Regular", "Medium"):
        tf, size = assets.typeface("Mono"), size * 0.92
    else:
        tf = assets.typeface(f"Inter-{weight}")
    f = skia.Font(tf, size)
    f.setSubpixel(True)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    return f


# ------------------------------------------------------------------ motion
def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def ease_out(x: float) -> float:                    # ease-out-cubic
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x: float) -> float:
    x = clamp(x)
    return 4 * x * x * x if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def spring(x: float, overshoot: float = 1.70158) -> float:
    """Ease-out-back: overshoots a little and settles at 1."""
    x = clamp(x)
    c3 = overshoot + 1
    return 1 + c3 * (x - 1) ** 3 + overshoot * (x - 1) ** 2


def stagger(t: float, start: float, i: int, step: float = 0.08, dur: float = 0.5, fn=ease_out) -> float:
    """Progress of item i in a staggered entrance that begins at `start`."""
    return fn((t - start - i * step) / dur)


def pulse(t: float, period: float = 1.6) -> float:
    """0..1..0 breathing value for idle hubs."""
    return 0.5 - 0.5 * math.cos(2 * math.pi * (t % period) / period)


def lerp(a: float, b: float, k: float) -> float:
    return a + (b - a) * k


# ------------------------------------------------------------------ paints and text
def paint(color: int, stroke: float = 0, **kw) -> skia.Paint:
    p = skia.Paint(AntiAlias=True, Color=color, **kw)
    if stroke:
        p.setStyle(skia.Paint.kStroke_Style)
        p.setStrokeWidth(stroke)
        p.setStrokeCap(skia.Paint.kRound_Cap)
        p.setStrokeJoin(skia.Paint.kRound_Join)
    return p


def blur(p: skia.Paint, sigma: float) -> skia.Paint:
    p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, sigma))
    return p


def halo(c, x: float, y: float, r: float, color: str, a: float) -> None:
    """A soft glow disc drawn with a radial gradient: looks like a blur, costs a fraction of one."""
    if a <= 0.01 or r <= 0.5:
        return
    r = max(2.0, round(r / 2) * 2)

    def draw(cc):
        p = skia.Paint(AntiAlias=True)
        p.setShader(skia.GradientShader.MakeRadial(skia.Point(r, r), r, [col(color, 1.0), col(color, 0.35), col(color, 0.0)], [0.0, 0.45, 1.0]))
        cc.drawCircle(r, r, r, p)
    sprite(c, ("halo", color), x - r, y - r, 2 * r, 2 * r, draw, a)


def glow_stroke(c, path: skia.Path, color: str, a: float, w: float) -> None:
    """A glow along a path from three widening translucent strokes (no blur filter)."""
    for mult, al in ((5.0, 0.07), (3.2, 0.12), (2.0, 0.20)):
        c.drawPath(path, paint(col(color, al * a), w * mult))


_sprite_cache: dict = {}


def sprite(c, key, x: float, y: float, w: float, h: float, draw_fn, alpha: float = 1.0, pad: float = 0.0) -> None:
    """Draws a static shape through an image cache. `draw_fn(cc)` paints it in local coordinates (0..w, 0..h);
    the result is rendered once per key and canvas resolution and then blitted, with `alpha`, in one drawImage.
    Large translucent anti-aliased shapes are far cheaper to blit than to rasterise every frame."""
    if alpha <= 0.01:
        return
    s = cache_scale(c)
    k = (key, round(w), round(h), round(pad), s, int(c.imageInfo().colorType()))
    img = _sprite_cache.get(k)
    if img is None:
        surf = layer_surface(c, int((w + 2 * pad) * s) + 2, int((h + 2 * pad) * s) + 2)
        cc = surf.getCanvas()
        cc.clear(skia.ColorTRANSPARENT)
        cc.scale(s, s)
        cc.translate(pad, pad)
        draw_fn(cc)
        img = surf.makeImageSnapshot()
        if len(_sprite_cache) > 512:
            _sprite_cache.clear()
        _sprite_cache[k] = img
    c.save()
    c.translate(x - pad, y - pad)
    c.scale(1 / s, 1 / s)
    c.drawImage(img, 0, 0, skia.SamplingOptions(skia.FilterMode.kLinear), skia.Paint(Alphaf=min(1.0, alpha)) if alpha < 0.999 else None)
    c.restore()


_shadow_cache: dict = {}


def soft_shadow(c, x: float, y: float, w: float, h: float, r: float, color: str, a: float, sigma: float) -> None:
    """A blurred rounded-rectangle shadow, rendered once per size and colour and reused as an image."""
    if a <= 0.01:
        return
    s = cache_scale(c)
    w, h, r = (max(4.0, round(v / 4) * 4) for v in (w, h, r))
    key = (w, h, r, color, round(sigma), s, int(c.imageInfo().colorType()))
    img = _shadow_cache.get(key)
    pad = sigma * 3
    if img is None:
        pw, ph = int((w + 2 * pad) * s) + 2, int((h + 2 * pad) * s) + 2
        surf = layer_surface(c, pw, ph)
        cc = surf.getCanvas()
        cc.scale(s, s)
        cc.drawRoundRect(skia.Rect.MakeXYWH(pad, pad, w, h), r, r, blur(paint(col(color, 1.0)), sigma))
        img = surf.makeImageSnapshot()
        if len(_shadow_cache) > 256:
            _shadow_cache.clear()
        _shadow_cache[key] = img
    c.save()
    c.translate(x - pad, y - pad)
    c.scale(1 / s, 1 / s)
    c.drawImage(img, 0, 0, skia.SamplingOptions(skia.FilterMode.kLinear), skia.Paint(Alphaf=a))
    c.restore()


def draw_text(c, s: str, x: float, y: float, size: float, color: int, weight: str = "Regular", align: str = "left",
              mono: bool = False) -> float:
    f = make_font(size, weight, mono)
    w = f.measureText(s)
    if align == "center":
        x -= w / 2
    elif align == "right":
        x -= w
    c.drawString(s, x, y, f, skia.Paint(AntiAlias=True, Color=color))
    return w


def text_width(s: str, size: float, weight: str = "Regular", mono: bool = False) -> float:
    return make_font(size, weight, mono).measureText(s)


def fit_size(s: str, maxw: float, size: float, smallest: float, weight: str = "Regular", mono: bool = False) -> float:
    return _fit_size(s, maxw, size, smallest, weight, mono, family_key())


@functools.lru_cache(maxsize=8192)
def _fit_size(s, maxw, size, smallest, weight, mono, fam):
    sz = size
    while sz > smallest and make_font(sz, weight, mono).measureText(s) > maxw:
        sz -= 1
    return sz


def ellipsize(s: str, maxw: float, size: float, weight: str = "Regular", mono: bool = False) -> str:
    f = make_font(size, weight, mono)
    if f.measureText(s) <= maxw:
        return s
    while s and f.measureText(s + "…") > maxw:
        s = s[:-1]
    return s.rstrip() + "…"


def wrap(s: str, maxw: float, size: float, weight: str = "Regular", mono: bool = False) -> list[str]:
    f = make_font(size, weight, mono)
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


def fit_block(s: str, maxw: float, max_rows: int, size: float, smallest: float, weight: str = "Regular") -> tuple[list[str], float]:
    """Wraps `s` into at most `max_rows` rows of width `maxw`, shrinking the type down to `smallest`;
    the last row is ellipsized if it still does not fit. Text never leaves its box."""
    sz = size
    while True:
        rows = wrap(s, maxw, sz, weight)
        if (len(rows) <= max_rows and all(text_width(r, sz, weight) <= maxw for r in rows)) or sz <= smallest:
            break
        sz -= 1
    if len(rows) > max_rows:
        rows = rows[:max_rows - 1] + [" ".join(rows[max_rows - 1:])]
    rows = [ellipsize(r, maxw, sz, weight) for r in rows]
    return rows, sz


# ------------------------------------------------------------------ sketch jitter
def _noise(i: float, seed: int) -> float:
    return (math.sin(i * 12.9898 + seed * 78.233) * 43758.5453) % 1.0 * 2 - 1


def sketchify(path: skia.Path, seed: int, amp: float, step: float = 14.0) -> skia.Path:
    """Resamples a path and offsets each point a little, deterministically, so strokes look hand-drawn."""
    if amp <= 0:
        return path
    out = skia.Path()
    it = skia.PathMeasure(path, False)
    contour = 0
    while True:
        L = it.getLength()
        if L > 0:
            n = max(2, int(L / step))
            for i in range(n + 1):
                d = L * i / n
                pos, tan = it.getPosTan(d)
                k = math.sin(math.pi * i / n) if not it.isClosed() else 1.0
                off = _noise(i + contour * 101, seed) * amp * (0.35 + 0.65 * k)
                x, y = pos.x() - tan.y() * off, pos.y() + tan.x() * off
                if i == 0:
                    out.moveTo(x, y)
                else:
                    out.lineTo(x, y)
            if it.isClosed():
                out.close()
        contour += 1
        if not it.nextContour():
            break
    return out


# ------------------------------------------------------------------ cached layers
def cache_scale(c: skia.Canvas, extra: float = 1.0) -> float:
    """The resolution to cache a layer at: the canvas's current scale rounded UP to a quarter step, so a camera
    drift or an animated scale reuses the same cached image instead of re-rendering it every frame."""
    s = abs(c.getTotalMatrix().getScaleX()) * extra
    return max(0.25, math.ceil(s * 4 - 1e-6) / 4)


def layer_surface(c: skia.Canvas, pw: int, ph: int) -> skia.Surface:
    """An offscreen surface in the same pixel format as `c`, so drawing its image back is a plain copy."""
    s = None
    try:
        s = c.makeSurface(c.imageInfo().makeWH(max(1, pw), max(1, ph)))
    except Exception:
        s = None
    return s or skia.Surface(max(1, pw), max(1, ph))


# ------------------------------------------------------------------ backgrounds (cached per template and size)
_bg_cache: dict = {}


def background(c: skia.Canvas, tpl: Template, W: float, H: float) -> None:
    """Draws the template's background into the logical W x H space; cached as an image at device resolution."""
    m = c.getTotalMatrix()
    s = m.getScaleX()
    key = (tpl.name, int(W), int(H), round(s, 4), int(c.imageInfo().colorType()))
    img = _bg_cache.get(key)
    if img is None:
        pw, ph = max(1, int(round(W * s))), max(1, int(round(H * s)))
        surf = layer_surface(c, pw, ph)
        cc = surf.getCanvas()
        cc.scale(s, s)
        _paint_background(cc, tpl, W, H)
        img = surf.makeImageSnapshot()
        if len(_bg_cache) > 24:
            _bg_cache.clear()
        _bg_cache[key] = img
    c.save()
    c.scale(1 / s, 1 / s)
    c.drawImage(img, 0, 0)
    c.restore()


def _paint_background(c, tpl: Template, W, H):
    T = tpl.T
    full = skia.Rect.MakeWH(W, H)
    if tpl.bg == "legacy":
        p = skia.Paint()
        p.setShader(skia.GradientShader.MakeLinear([skia.Point(0, 0), skia.Point(W, H)], [col(T["bg0"]), col(T["bg1"])]))
        c.drawRect(full, p)
        gp = paint(col(T["grid"], 0.9))
        for gx in range(60, int(W), 60):
            for gy in range(60, int(H), 60):
                c.drawCircle(gx, gy, 1.6, gp)
        return
    if tpl.bg == "paper":
        c.drawRect(full, paint(col(T["bg0"])))
        p = skia.Paint()
        p.setShader(skia.GradientShader.MakeRadial(skia.Point(W * 0.5, H * 0.38), max(W, H) * 0.75,
                                                   [col("#FFFFFF", 0.85), col("#FFFFFF", 0.0)]))
        c.drawRect(full, p)
        gp = paint(col(T["grid"], 0.55))
        for gx in range(40, int(W), 40):
            for gy in range(40, int(H), 40):
                c.drawCircle(gx, gy, 1.1, gp)
        return
    if tpl.bg == "noir":
        p = skia.Paint()
        p.setShader(skia.GradientShader.MakeRadial(skia.Point(W * 0.5, H * 0.42), max(W, H) * 0.78,
                                                   [col(T["bg1"]), col(T["bg0"])]))
        c.drawRect(full, p)
        gp = paint(col(T["grid"], 0.45))
        for gx in range(48, int(W), 48):
            for gy in range(48, int(H), 48):
                c.drawCircle(gx, gy, 1.0, gp)
        haze = blur(paint(col("#1C6FD1", 0.10)), 160)
        c.drawCircle(W * 0.72, H * 0.30, max(W, H) * 0.22, haze)
        c.drawCircle(W * 0.22, H * 0.78, max(W, H) * 0.18, blur(paint(col("#0FB5D6", 0.06)), 160))
    elif tpl.bg == "blueprint":
        p = skia.Paint()
        p.setShader(skia.GradientShader.MakeLinear([skia.Point(0, 0), skia.Point(W, H)], [col(T["bg1"]), col(T["bg0"])]))
        c.drawRect(full, p)
        minor, major = paint(col("#FFFFFF", 0.055), 1), paint(col("#FFFFFF", 0.12), 1.2)
        for gx in range(0, int(W) + 1, 30):
            c.drawLine(gx, 0, gx, H, major if gx % 150 == 0 else minor)
        for gy in range(0, int(H) + 1, 30):
            c.drawLine(0, gy, W, gy, major if gy % 150 == 0 else minor)
    elif tpl.bg == "sketch":
        c.drawRect(full, paint(col(T["bg0"])))
        return
    if tpl.vignette > 0:
        p = skia.Paint()
        p.setShader(skia.GradientShader.MakeRadial(skia.Point(W / 2, H / 2), math.hypot(W, H) * 0.62,
                                                   [col("#000000", 0.0), col("#000000", tpl.vignette)], [0.55, 1.0]))
        c.drawRect(full, p)


# ------------------------------------------------------------------ cards, badges, chips, legends
def card(c, tpl: Template, x: float, y: float, w: float, h: float, a: float = 1.0, hl: float = 0.0, dim: float = 0.0,
         radius: float | None = None, seed: int = 0, accent: str | None = None, fill: str | None = None) -> None:
    """A card in the template's style. `hl` (0..1) glows or tints it as the focus; `dim` fades everything else."""
    if a <= 0.01:
        return
    cs, T = tpl.card, tpl.T
    alpha = a * (1 - 0.65 * dim * (1 - hl))
    r = cs["radius"] if radius is None else radius
    rect = skia.Rect.MakeXYWH(x, y, w, h)
    acc = accent or tpl.conn["active"]
    if cs.get("shadow", 0) > 0:
        soft_shadow(c, x, y + 10, w, h, r, cs.get("shadow_color", "#000000"), cs["shadow"] * alpha, 16)
    if hl > 0.02 and tpl.glow:
        soft_shadow(c, x, y, w, h, r, acc, 0.45 * hl * alpha, 22)
    if tpl.jitter:
        p = skia.Path()
        p.addRRect(skia.RRect.MakeRectXY(rect, r, r))
        c.drawPath(p, paint(col(fill or cs["fill"], alpha)))
        c.drawPath(sketchify(p, seed + 7, tpl.jitter), paint(col(mix(cs["border"], acc, hl), alpha), cs["width"] + 0.6 * hl))
        return
    hq = round(hl * 10) / 10
    fill_c = fill or cs["fill"]

    def body(cc):
        rr = skia.Rect.MakeXYWH(0, 0, w, h)
        cc.drawRoundRect(rr, r, r, paint(col(fill_c, 0.78 if cs.get("glass") else 1.0)))
        if cs.get("glass"):
            p = skia.Paint(AntiAlias=True)
            p.setShader(skia.GradientShader.MakeLinear([skia.Point(0, 0), skia.Point(0, h)], [col("#FFFFFF", 0.10), col("#FFFFFF", 0.0)]))
            cc.drawRoundRect(rr, r, r, p)
        border = mix(cs["border"], acc, hq) if hq > 0.02 else cs["border"]
        cc.drawRoundRect(rr, r, r, paint(col(border, 0.85 if tpl.dark else 1.0), cs["width"] + 1.2 * hq))
        if cs.get("ticks"):
            tp = paint(col(cs["border"], 1.0), 2)
            for (px, py, dx, dy) in ((0, 0, 1, 1), (w, 0, -1, 1), (0, h, 1, -1), (w, h, -1, -1)):
                cc.drawLine(px - dx * 6, py, px + dx * 14, py, tp)
                cc.drawLine(px, py - dy * 6, px, py + dy * 14, tp)
    sprite(c, ("card", tpl.name, r, fill_c, acc, hq), x, y, w, h, body, alpha, pad=8)


def role_color(tpl: Template, role: str) -> str:
    """A colour by role: semantic (success, fail, info, neutral) or a palette key."""
    return tpl.sem.get(role) or tpl.T.get(role) or tpl.T["accent"]


def badge(c, tpl: Template, icon: str | None, cx: float, cy: float, r: float, a: float = 1.0, hl: float = 0.0,
          dim: float = 0.0, scale: float = 1.0, tone: str | None = None, seed: int = 0) -> None:
    """An icon badge in the template's style: a filled circle with a white icon (paper, noir), a thin outlined
    circle (blueprint), a pastel disc with a dark hand-drawn ring (sketch), or a tinted icon (legacy)."""
    alpha = a * (1 - 0.65 * dim * (1 - hl))
    if alpha <= 0.01 or scale <= 0.01:
        return
    r = r * scale
    st, T = tpl.icon, tpl.T
    tone_col = role_color(tpl, tone) if tone else None
    if hl > 0.02 and tpl.glow:
        halo(c, cx, cy, r * 1.9, tpl.conn["active"], 0.55 * hl * alpha)
    if st["style"] == "badge":
        fill = tone_col or st["badge"]
        if tpl.glow:
            c.drawCircle(cx, cy, r + 5, paint(col(st["ring"], 0.35 * alpha + 0.5 * hl * alpha), 2.0))
        elif tpl.card.get("shadow"):
            soft_shadow(c, cx - r, cy - r + 6, 2 * r, 2 * r, r, "#0B1F3A", 0.16 * alpha, 10)
        c.drawCircle(cx, cy, r, paint(col(fill, alpha)))
        if tpl.glow:
            p = skia.Paint(AntiAlias=True)
            p.setShader(skia.GradientShader.MakeLinear([skia.Point(cx, cy - r), skia.Point(cx, cy + r)],
                                                       [col("#FFFFFF", 0.16 * alpha), col("#FFFFFF", 0.0)]))
            c.drawCircle(cx, cy, r, p)
        assets.draw_icon(c, icon, cx, cy, r * 1.05, st["color"], alpha, st["stroke"], glyph=fill)
    elif st["style"] == "outline":
        ring = tone_col or st["ring"]
        c.drawCircle(cx, cy, r, paint(col(T["bg0"], 0.85 * alpha)))
        c.drawCircle(cx, cy, r, paint(col(mix(ring, tpl.conn["active"], hl), alpha), 1.8 + hl))
        c.drawCircle(cx, cy, r - 6, paint(col(ring, 0.35 * alpha), 1))
        assets.draw_icon(c, icon, cx, cy, r * 1.0, mix(st["color"], tpl.conn["active"], hl), alpha, st["stroke"], glyph=T["bg0"])
    elif st["style"] == "pastel":
        fill = PASTELS.get(tone or "", None) or "#FDF3C8"
        p = skia.Path()
        p.addCircle(cx, cy, r)
        c.drawPath(p, paint(col(fill, alpha)))
        c.drawPath(sketchify(p, seed + 3, tpl.jitter * 0.8), paint(col(mix(st["ring"], tpl.conn["active"], hl), alpha), 2.0))
        assets.draw_icon(c, icon, cx, cy, r * 1.0, st["color"], alpha, st["stroke"], glyph=fill)
    else:                                                         # legacy: tinted icon on the panel
        colr = tone_col or st.get("color") or T["accent"]
        assets.draw_icon(c, icon, cx, cy, r * 1.3, colr, alpha, st["stroke"], glyph=T["panel"])


def chip(c, tpl: Template, cx: float, cy: float, label: str, icon: str | None = None, tone: str = "neutral",
         a: float = 1.0, scale: float = 1.0, size: float = 26, max_w: float = 520) -> tuple[float, float]:
    """A label chip centred on (cx, cy), like 'Cache hit' with a check. Returns its (width, height)."""
    if a <= 0.01 or scale <= 0.01:
        return 0.0, 0.0
    colr = role_color(tpl, tone)
    icon = assets.resolve(icon)
    ic = size * 1.25 if icon else 0
    tw_max = max_w - ic - size * 1.4
    sz = fit_size(label, tw_max, size, size * 0.7, "SemiBold")
    lab = ellipsize(label, tw_max, sz, "SemiBold")
    tw = text_width(lab, sz, "SemiBold")
    h = size * 1.75
    w = tw + size * 1.2 + (ic + size * 0.45 if icon else 0)
    c.save()
    c.translate(cx, cy)
    c.scale(scale, scale)
    rect = skia.Rect.MakeXYWH(-w / 2, -h / 2, w, h)
    bg = tpl.T["bg0"] if tpl.dark else "#FFFFFF"
    if tpl.glow:
        soft_shadow(c, -w / 2, -h / 2, w, h, h / 2, colr, 0.35 * a, 12)
    elif not tpl.dark and not tpl.jitter:
        soft_shadow(c, -w / 2, -h / 2 + 4, w, h, h / 2, "#0B1F3A", 0.10 * a, 8)
    if tpl.jitter:
        p = skia.Path()
        p.addRRect(skia.RRect.MakeRectXY(rect, h / 2, h / 2))
        c.drawPath(p, paint(col(bg, a)))
        c.drawPath(sketchify(p, 11, tpl.jitter), paint(col(colr, a), 2))
    else:
        c.drawRoundRect(rect, h / 2, h / 2, paint(col(bg, 0.94 * a)))
        c.drawRoundRect(rect, h / 2, h / 2, paint(col(colr, a), 2))
    x = -w / 2 + size * 0.6
    if icon:
        assets.draw_icon(c, icon, x + ic / 2, 0, ic, colr, a, 2.2, glyph=bg)
        x += ic + size * 0.45
    draw_text(c, lab, x, sz * 0.36, sz, col(colr if tpl.dark else tpl.T["text"], a), "SemiBold")
    c.restore()
    return w * scale, h * scale


def label_under(c, tpl: Template, s: str, cx: float, y: float, max_w: float, size: float = 28, a: float = 1.0,
                sub: str | None = None, weight: str = "SemiBold", hl: float = 0.0) -> float:
    """A centred label (and optional sub-line) that never exceeds max_w. Returns the bottom y."""
    rows, sz = fit_block(s, max_w, 2, size, size * 0.72, weight)
    colr = mix(tpl.T["text"], tpl.conn["active"], 0.35 * hl) if tpl.dark else tpl.T["text"]
    for i, r in enumerate(rows):
        draw_text(c, r, cx, y + sz * 0.95 + i * sz * 1.15, sz, col(colr, a), weight, "center")
    yb = y + sz * 1.15 * len(rows) + 4
    if sub:
        ss = fit_size(sub, max_w, size * 0.72, size * 0.55)
        draw_text(c, ellipsize(sub, max_w, ss), cx, yb + ss * 0.95, ss, col(tpl.T["text2"], a), "Regular", "center")
        yb += ss * 1.25
    return yb


def legend(c, tpl: Template, x: float, y: float, items: list[dict], a: float = 1.0, w: float = 380,
           title: str | None = None) -> float:
    """A legend card. Items: {"mark": "hub"|"dot"|"line"|"dash"|"icon", "label", "sub"?, "icon"?, "tone"?}."""
    if a <= 0.01:
        return 0.0
    row = 70
    h = 34 + (40 if title else 0) + row * len(items)
    card(c, tpl, x, y, w, h, a)
    yy = y + 26
    if title:
        draw_text(c, title.upper() if not tpl.jitter else title, x + 26, yy + 18, 20, col(tpl.T["text2"], a), "SemiBold")
        yy += 40
    for it in items:
        colr = role_color(tpl, it.get("tone") or "accent")
        mx, my = x + 46, yy + 22
        m = it.get("mark", "dot")
        if m == "hub":
            hub(c, tpl, mx, my, 15, a, 0.5, colr)
        elif m == "dot":
            node_dot(c, tpl, mx, my, 7, a, colr)
        elif m in ("line", "dash"):
            p = paint(col(colr, a), 3)
            if m == "dash":
                p.setPathEffect(skia.DashPathEffect.Make([8, 7], 0))
            c.drawLine(mx - 20, my, mx + 20, my, p)
        else:
            assets.draw_icon(c, it.get("icon"), mx, my, 30, colr, a, 2)
        draw_text(c, ellipsize(it["label"], w - 110, 22, "SemiBold"), x + 84, my - 2, 22, col(tpl.T["text"], a), "SemiBold")
        if it.get("sub"):
            draw_text(c, ellipsize(it["sub"], w - 110, 18), x + 84, my + 24, 18, col(tpl.T["text2"], a))
        yy += row
    return h


# ------------------------------------------------------------------ nodes, hubs, connectors, packets
def node_dot(c, tpl, x, y, r, a=1.0, colr=None, hl=0.0):
    colr = colr or tpl.conn["active"]
    if tpl.glow:
        halo(c, x, y, r * 4.2, colr, (0.55 + 0.4 * hl) * a)
    c.drawCircle(x, y, r, paint(col("#FFFFFF" if tpl.dark else colr, a)))
    if tpl.dark:
        c.drawCircle(x, y, r, paint(col(colr, a), max(1.5, r * 0.35)))


def hub(c, tpl, x, y, r, a=1.0, beat=0.0, colr=None):
    """A regional hub: concentric rings with a breathing outer ring."""
    colr = colr or tpl.conn["active"]
    if tpl.glow:
        halo(c, x, y, r * 3.4, colr, 0.45 * a)
    c.drawCircle(x, y, r * (1.6 + 0.35 * beat), paint(col(colr, (0.45 - 0.3 * beat) * a), 2))
    c.drawCircle(x, y, r * 1.15, paint(col(colr, 0.85 * a), 2.5))
    c.drawCircle(x, y, r * 0.62, paint(col("#FFFFFF" if tpl.dark else colr, a)))


def ortho_path(pts: list[tuple[float, float]], radius: float = 22.0) -> skia.Path:
    """A polyline with rounded elbows."""
    p = skia.Path()
    p.moveTo(*pts[0])
    for i in range(1, len(pts) - 1):
        (x0, y0), (x1, y1), (x2, y2) = pts[i - 1], pts[i], pts[i + 1]
        l1, l2 = math.hypot(x1 - x0, y1 - y0), math.hypot(x2 - x1, y2 - y1)
        rr = min(radius, l1 / 2, l2 / 2)
        if rr < 1:
            p.lineTo(x1, y1)
        else:
            p.arcTo(x1, y1, x2, y2, rr)
    p.lineTo(*pts[-1])
    return p


def curve_path(a: tuple[float, float], b: tuple[float, float], bend: float = 0.25) -> skia.Path:
    """A smooth curve from a to b, bowed sideways by `bend` of its length."""
    (x0, y0), (x1, y1) = a, b
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    dx, dy = x1 - x0, y1 - y0
    p = skia.Path()
    p.moveTo(x0, y0)
    p.quadTo(mx - dy * bend, my + dx * bend, x1, y1)
    return p


def trim(path: skia.Path, k0: float, k1: float) -> tuple[skia.Path, float]:
    """The part of `path` between fractions k0 and k1 of its length; also returns the full length."""
    pm = skia.PathMeasure(path, False)
    L = pm.getLength()
    out = skia.Path()
    if L > 0 and k1 > k0:
        pm.getSegment(L * clamp(k0), L * clamp(k1), out, True)
    return out, L


def point_at(path: skia.Path, k: float) -> tuple[float, float, float, float]:
    pm = skia.PathMeasure(path, False)
    L = pm.getLength()
    pos, tan = pm.getPosTan(L * clamp(k))
    return pos.x(), pos.y(), tan.x(), tan.y()


def arrowhead(c, x, y, tx, ty, size, color: int, sketch_seed: int | None = None, tpl=None):
    nx, ny = -ty, tx
    p = skia.Path()
    p.moveTo(x, y)
    p.lineTo(x - tx * size + nx * size * 0.55, y - ty * size + ny * size * 0.55)
    p.lineTo(x - tx * size * 0.72, y - ty * size * 0.72)
    p.lineTo(x - tx * size - nx * size * 0.55, y - ty * size - ny * size * 0.55)
    p.close()
    c.drawPath(p, paint(color))


def stroke(c, tpl: Template, path: skia.Path, a: float = 1.0, progress: float = 1.0, dashed: bool = False,
           color: str | None = None, width: float | None = None, arrow: bool = True, glow: bool | None = None,
           seed: int = 0, flow: float | None = None) -> None:
    """Draws a connector with draw-on `progress` (path trim), optional dash, arrowhead at the drawn end,
    glow (template default) and sketch jitter. `flow` animates the dash offset (marching ants)."""
    if a <= 0.01 or progress <= 0.001:
        return
    colr = color or tpl.conn["color"]
    w = width or tpl.conn["width"]
    seg, L = trim(path, 0.0, progress)
    if tpl.jitter:
        seg = sketchify(seg, seed, tpl.jitter * 0.9)
    p = paint(col(colr, a), w)
    if dashed:
        d = tpl.conn["dash"]
        p.setPathEffect(skia.DashPathEffect.Make(list(d), -(flow or 0.0) * 40))
    if (tpl.glow if glow is None else glow):
        glow_stroke(c, seg, colr, a, w)
    c.drawPath(seg, p)
    if arrow and progress > 0.97 and L > 30:
        x, y, tx, ty = point_at(path, 1.0)
        arrowhead(c, x, y, tx, ty, 10 + w * 2.6, col(colr, a))


def packet(c, tpl: Template, path: skia.Path, k: float, a: float = 1.0, color: str | None = None, r: float = 9.0) -> None:
    """A packet travelling along the real connector path with a short glowing trail."""
    if a <= 0.01 or k < 0 or k > 1:
        return
    colr = color or tpl.conn["active"]
    tail, _ = trim(path, max(0.0, k - 0.16), k)
    if tail.countPoints():
        if tpl.glow:
            glow_stroke(c, tail, colr, a, r * 0.5)
        c.drawPath(tail, paint(col(colr, 0.55 * a), r * 0.9))
    x, y, _, _ = point_at(path, k)
    if tpl.glow:
        halo(c, x, y, r * 3.6, colr, 0.75 * a)
    c.drawCircle(x, y, r, paint(col("#FFFFFF" if tpl.dark else colr, a)))
    c.drawCircle(x, y, r, paint(col(colr, a), 3))
