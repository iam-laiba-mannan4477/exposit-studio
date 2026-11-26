"""Animation styles as "style packs": a template (palette, fonts, card and badge rules, procedural background and
card texture) plus motion rules (frame-rate feel, frame jitter, default effects) and a post-process chain.

Every texture here is procedural (no image files). Fonts are OFL (Inter, Caveat, JetBrains Mono, IM FELL English,
Press Start 2P; see exposit/assets/LICENSES.md).

Post-processing runs in numpy on the finished RGBA frame (the renderer already reads each frame back for ffmpeg).
This skia build blits images fast but runs colour filters, blend modes and translucent shader fills ~100x slower than
expected (about 200 ms for a 1080x1920 frame), so grain, vignette, sepia, flicker, scanlines, halftone, paper
texture, chromatic edge, pixelation and palette reduction are vectorised array operations with cached masks.
"""
from __future__ import annotations
import functools, math
import numpy as np
import skia
from . import design as D
from .design import Template, col, mix

# ================================================================== procedural backgrounds and card textures


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def _bg_solid(c, color: str, W, H, top: str | None = None):
    p = skia.Paint()
    if top:
        p.setShader(skia.GradientShader.MakeLinear([skia.Point(0, 0), skia.Point(0, H)], [col(top), col(color)]))
        c.drawRect(skia.Rect.MakeWH(W, H), p)
    else:
        c.drawRect(skia.Rect.MakeWH(W, H), D.paint(col(color)))


def bg_whiteboard(c, W, H):
    _bg_solid(c, "#F7F8F6", W, H, "#FFFFFF")
    for i, (x, y, r, a) in enumerate([(0.2, 0.8, 0.4, 0.05), (0.85, 0.25, 0.3, 0.04)]):     # faint marker ghosts
        c.drawCircle(W * x, H * y, max(W, H) * r, D.blur(D.paint(col("#9AA3AD", a)), 80))
    c.drawRect(skia.Rect.MakeXYWH(0, H - 26, W, 26), D.paint(col("#C9CDD2")))             # the board's tray


def bg_sketchnote(c, W, H):
    _bg_solid(c, "#F6F0E2", W, H)
    p = D.paint(col("#D9CDB4", 0.9))
    for x in range(36, int(W), 36):
        for y in range(36, int(H), 36):
            c.drawCircle(x, y, 1.6, p)


def bg_minimal(c, W, H):
    _bg_solid(c, "#F3F0E8", W, H)


def bg_limited(c, W, H):
    _bg_solid(c, "#FFE8C2", W, H)
    p = skia.Path()
    p.moveTo(0, H * 0.72); p.cubicTo(W * 0.3, H * 0.62, W * 0.7, H * 0.84, W, H * 0.7); p.lineTo(W, H); p.lineTo(0, H); p.close()
    c.drawPath(p, D.paint(col("#FFD08A")))
    c.drawCircle(W * 0.85, H * 0.12, min(W, H) * 0.09, D.paint(col("#FFF3DA")))


def bg_neon(c, W, H):
    _bg_solid(c, "#0A0320", W, H, "#1B0838")
    hz = H * 0.66                                              # horizon: a neon grid floor in perspective
    c.drawRect(skia.Rect.MakeLTRB(0, hz, W, H), D.paint(col("#12052B")))
    for i in range(-14, 15):
        c.drawLine(W / 2 + i * 40, hz, W / 2 + i * W * 0.22, H, D.paint(col("#FF2BD6", 0.55), 2))
    y, k = hz, 6.0
    while y < H:
        c.drawLine(0, y, W, y, D.paint(col("#FF2BD6", 0.55), 2))
        y += k
        k *= 1.28
    m = skia.Path()                                           # low-poly mountains on the horizon
    pts = [(0, hz), (W * 0.12, hz - H * 0.08), (W * 0.24, hz - H * 0.03), (W * 0.38, hz - H * 0.12), (W * 0.52, hz - H * 0.05),
           (W * 0.66, hz - H * 0.10), (W * 0.82, hz - H * 0.04), (W, hz - H * 0.09), (W, hz)]
    m.moveTo(*pts[0]); [m.lineTo(*q) for q in pts[1:]]; m.close()
    c.drawPath(m, D.paint(col("#2A0E5C")))
    c.drawPath(m, D.paint(col("#19F5FF", 0.7), 2.5))
    c.drawCircle(W * 0.5, hz - H * 0.05, min(W, H) * 0.12, D.blur(D.paint(col("#FF6AD5", 0.35)), 40))


def bg_grunge(c, W, H):
    _bg_solid(c, "#050806", W, H)
    r = _rng(7)
    for _ in range(40):                                       # damp patches
        x, y, s = r.random() * W, r.random() * H, 40 + r.random() * 260
        c.drawCircle(x, y, s, D.blur(D.paint(col("#1A2A1A", 0.35)), s * 0.4))


def bg_pixel(c, W, H):
    _bg_solid(c, "#1D2B53", W, H)
    r = _rng(3)
    for _ in range(140):
        x, y = int(r.random() * W / 8) * 8, int(r.random() * H / 8) * 8
        c.drawRect(skia.Rect.MakeXYWH(x, y, 8, 8), D.paint(col("#FFF1E8" if r.random() > 0.6 else "#83769C")))


def bg_engraving(c, W, H):
    _bg_solid(c, "#EEE4CF", W, H)
    p = D.paint(col("#2A1F17", 0.12), 1.6)
    for i in range(-int(H), int(W), 14):                      # engraved hatching in the margins
        c.drawLine(i, 0, i + H, H, p)
    c.drawRect(skia.Rect.MakeXYWH(40, 40, W - 80, H - 80), D.paint(col("#EEE4CF")))
    c.drawRect(skia.Rect.MakeXYWH(40, 40, W - 80, H - 80), D.paint(col("#1A1410"), 4))
    c.drawRect(skia.Rect.MakeXYWH(54, 54, W - 108, H - 108), D.paint(col("#1A1410"), 1.5))


def bg_silent(c, W, H):
    _bg_solid(c, "#2C2925", W, H, "#3B3631")


def bg_papercraft(c, W, H):
    _bg_solid(c, "#F4E8D8", W, H)
    for i, (colr, y0, amp) in enumerate([("#E9D3C0", 0.68, 0.04), ("#DCC0AA", 0.78, 0.05), ("#CFAE95", 0.88, 0.03)]):
        p = skia.Path()
        p.moveTo(0, H * y0)
        for k in range(1, 9):
            x = W * k / 8
            p.quadTo(x - W / 16, H * (y0 - amp * (1 if k % 2 else -1)), x, H * y0)
        p.lineTo(W, H); p.lineTo(0, H); p.close()
        c.drawPath(p, D.blur(D.paint(col("#7A5A40", 0.25)), 10))
        c.drawPath(p, D.paint(col(colr)))


def bg_puppetry(c, W, H):
    _bg_solid(c, "#060408", W, H)
    for x, y, colr, r in [(0.22, 0.30, "#FF3D7F", 0.55), (0.80, 0.42, "#FFB238", 0.5), (0.5, 0.85, "#3DD6FF", 0.45)]:
        p = skia.Paint()
        p.setShader(skia.GradientShader.MakeRadial(skia.Point(W * x, H * y), max(W, H) * r,
                                                   [col(colr, 0.40), col(colr, 0.0)]))
        c.drawRect(skia.Rect.MakeWH(W, H), p)
    c.drawRect(skia.Rect.MakeXYWH(0, H - 60, W, 60), D.paint(col("#000000")))             # the stage edge


def bg_cardboard(c, W, H):
    _bg_solid(c, "#B4875A", W, H, "#C39466")
    p = D.paint(col("#8E6640", 0.22), 3)
    for y in range(0, int(H), 18):                            # corrugation
        c.drawLine(0, y, W, y, p)


def bg_clay(c, W, H):
    _bg_solid(c, "#F1D6B8", W, H, "#F6E2CB")
    for x, y, r, colr in [(0.15, 0.85, 0.22, "#E8B98F"), (0.9, 0.15, 0.18, "#EBC9A4")]:
        c.drawCircle(W * x, H * y, max(W, H) * r, D.paint(col(colr)))


def tex_hatch(cc, w, h):
    p = D.paint(col("#1A1410", 0.16), 1.4)
    for i in range(-int(h), int(w), 10):
        cc.drawLine(i, h, i + h * 0.6, 0, p)


def tex_paper(cc, w, h):
    r = _rng(int(w) * 7 + int(h))
    for _ in range(int(w * h / 420)):                         # visible paper fibres
        x, y = r.random() * w, r.random() * h
        ang = r.random() * math.pi
        ln = 8 + r.random() * 22
        cc.drawLine(x, y, x + math.cos(ang) * ln, y + math.sin(ang) * ln, D.paint(col("#8A7A60", 0.20), 1.1))


def tex_engraving(cc, w, h):
    """Carved look: a thick ink band inside the edge with cream gouge cuts, and cut-line hatching in one corner."""
    ink, paper = "#1A1410", "#F5EDDA"
    band = 16
    cc.drawRect(skia.Rect.MakeWH(w, band), D.paint(col(ink)))
    cc.drawRect(skia.Rect.MakeXYWH(0, h - band, w, band), D.paint(col(ink)))
    cc.drawRect(skia.Rect.MakeWH(band, h), D.paint(col(ink)))
    cc.drawRect(skia.Rect.MakeXYWH(w - band, 0, band, h), D.paint(col(ink)))
    r = _rng(int(w) * 3 + int(h))
    cut = D.paint(col(paper), 2.6)
    for x in np.arange(10, w - 10, 13):                       # gouge marks across the top and bottom bands
        ln = 6 + r.random() * 8
        cc.drawLine(float(x), 3, float(x + r.random() * 4 - 2), 3 + ln, cut)
        cc.drawLine(float(x), h - 3, float(x + r.random() * 4 - 2), h - 3 - ln, cut)
    for y in np.arange(10, h - 10, 13):
        ln = 6 + r.random() * 8
        cc.drawLine(3, float(y), 3 + ln, float(y + r.random() * 4 - 2), cut)
        cc.drawLine(w - 3, float(y), w - 3 - ln, float(y + r.random() * 4 - 2), cut)
    p = D.paint(col(ink, 0.55), 2.2)                          # cut-line hatching: curved strokes, bottom-right corner
    for k in range(9):
        rr = skia.Rect.MakeXYWH(w - 40 - k * 16, h - 40 - k * 14, (k + 1) * 32, (k + 1) * 28)
        cc.drawArc(rr, 180, 90, False, p)


def tex_cardboard(cc, w, h):
    for y in range(8, int(h), 14):
        cc.drawLine(0, y, w, y, D.paint(col("#7B5634", 0.18), 2.5))
    cc.drawRect(skia.Rect.MakeXYWH(w - 12, 8, 12, h - 8), D.paint(col("#6E4A2A", 0.55)))   # cut edge, for depth
    cc.drawRect(skia.Rect.MakeXYWH(8, h - 12, w - 8, 12), D.paint(col("#6E4A2A", 0.55)))


def tex_fingerprint(cc, w, h):
    cx, cy = w * 0.72, h * 0.35
    for k in range(1, 14):
        rr = skia.Rect.MakeXYWH(cx - k * 9, cy - k * 7, k * 18, k * 14)
        cc.drawArc(rr, 200 + k * 3, 220, False, D.paint(col("#7A3E2E", 0.10), 2))


# ================================================================== post-process (numpy, on the RGBA frame)
@functools.lru_cache(maxsize=16)
def _vignette_mask(h: int, w: int, strength: float) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / math.sqrt(2)
    m = 1 - strength * np.clip((d - 0.35) / 0.65, 0, 1) ** 1.6
    return (m * 256).astype(np.uint16)[..., None]


@functools.lru_cache(maxsize=8)
def _noise(h: int, w: int) -> np.ndarray:
    return _rng(11).normal(0, 1, (h + 64, w + 64)).astype(np.float32)


@functools.lru_cache(maxsize=16)
def _paper_mask(h: int, w: int, strength: float) -> np.ndarray:
    n = _rng(5).random((h // 4 + 2, w // 4 + 2)).astype(np.float32)
    n = np.repeat(np.repeat(n, 4, 0), 4, 1)[:h, :w]
    fib = _rng(6).random((h, w)).astype(np.float32)
    m = 1 - strength * (0.6 * n + 0.4 * fib)
    return (m * 256).astype(np.uint16)[..., None]


@functools.lru_cache(maxsize=8)
def _halftone_mask(h: int, w: int, cell: int, strength: float) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.hypot((xx % cell) - cell / 2, (yy % cell) - cell / 2) / (cell / 2)
    m = 1 - strength * np.clip(1 - d, 0, 1)
    return (m * 256).astype(np.uint16)[..., None]


SEPIA = (np.array([[0, 0, 0], [112, 66, 20], [255, 240, 205]], np.float32))


@functools.lru_cache(maxsize=1)
def _sepia_lut() -> np.ndarray:
    x = np.arange(256, dtype=np.float32) / 255
    lo, mid, hi = SEPIA
    out = np.where(x[:, None] < 0.5, lo + (mid - lo) * (x[:, None] / 0.5), mid + (hi - mid) * ((x[:, None] - 0.5) / 0.5))
    return np.clip(out, 0, 255).astype(np.uint8)


@functools.lru_cache(maxsize=1)
def _pico8_lut() -> np.ndarray:
    g = (np.arange(32, dtype=np.int32) << 3) + 4
    rgb = np.stack(np.meshgrid(g, g, g, indexing="ij"), -1).reshape(-1, 3)
    d = ((rgb[:, None, :] - PICO8[None]) ** 2).sum(-1)
    return PICO8[d.argmin(-1)].astype(np.uint8)


PICO8 = np.array([[0, 0, 0], [29, 43, 83], [126, 37, 83], [0, 135, 81], [171, 82, 54], [95, 87, 79], [194, 195, 199],
                  [255, 241, 232], [255, 0, 77], [255, 163, 0], [255, 236, 39], [0, 228, 54], [41, 173, 255],
                  [131, 118, 156], [255, 119, 168], [255, 204, 170]], np.int32)


OVERLAY_KINDS = ("grain", "vignette", "paper", "halftone", "scanlines", "flicker", "scratches")
_ov_cache: dict = {}


def _rgba_image(rgb: np.ndarray, alpha: np.ndarray) -> skia.Image:
    """A premultiplied image from 0-255 colour and alpha arrays, in the surface's native BGRA order: an RGBA image
    is converted on every draw in this skia build (~200 ms full-screen) while a BGRA one blits in about 1 ms."""
    a = alpha.astype(np.uint16)
    out = np.empty(alpha.shape + (4,), np.uint8)
    out[..., :3] = ((rgb[..., ::-1].astype(np.uint16) * a[..., None]) // 255).astype(np.uint8)
    out[..., 3] = alpha
    return skia.Image.fromarray(out, skia.kBGRA_8888_ColorType, skia.kPremul_AlphaType)


def _overlay_image(kind: str, w: int, h: int, a: tuple) -> skia.Image:
    key = (kind, w, h, a)
    img = _ov_cache.get(key)
    if img is not None:
        return img
    if kind == "grain":                                         # grey noise, 64 px larger so it can be shifted
        n = _rng(11).normal(0.5, 0.22, (h + 64, w + 64)).clip(0, 1)
        g = (n * 255).astype(np.uint8)
        img = _rgba_image(np.repeat(g[..., None], 3, -1), np.full(g.shape, int(255 * min(1.0, a[0] * 2.2)), np.uint8))
    elif kind == "vignette":
        m = _vignette_mask(h, w, float(a[0]))[..., 0].astype(np.float32) / 256
        img = _rgba_image(np.zeros((h, w, 3), np.uint8), ((1 - m) * 255).astype(np.uint8))
    elif kind == "paper":
        m = _paper_mask(h, w, float(a[0]))[..., 0].astype(np.float32) / 256
        img = _rgba_image(np.full((h, w, 3), (90, 70, 40), np.uint8), ((1 - m) * 255).astype(np.uint8))
    elif kind == "halftone":
        m = _halftone_mask(h, w, max(4, int(a[0] * w / 1080)), float(a[1]))[..., 0].astype(np.float32) / 256
        img = _rgba_image(np.zeros((h, w, 3), np.uint8), ((1 - m) * 255).astype(np.uint8))
    elif kind == "scanlines":
        step = max(2, int(3 * w / 1080))
        al = np.zeros((h, w), np.uint8)
        al[::step] = int(255 * a[0])
        img = _rgba_image(np.zeros((h, w, 3), np.uint8), al)
    if len(_ov_cache) > 48:
        _ov_cache.clear()
    _ov_cache[key] = img
    return img


def overlay(c, ops: tuple, w: int, h: int, frame: int) -> None:
    """The texture part of a style's post chain, as cached image blits drawn over the finished frame (fast in this
    skia build, unlike colour filters or per-pixel array maths)."""
    for op in ops:
        kind, a = op[0], tuple(op[1:])
        if kind not in OVERLAY_KINDS:
            continue
        if kind == "grain":
            oy, ox = (frame * 37) % 64, (frame * 91) % 64
            c.drawImage(_overlay_image(kind, w, h, a), -ox, -oy)
        elif kind == "flicker":
            k = math.sin(frame * 12.9898 % 6.28) * ((frame * 7919) % 13) / 13
            c.drawImage(_solid("#FFFFFF" if k > 0 else "#000000", w, h), 0, 0, skia.SamplingOptions(),   # full-size,
                        skia.Paint(Alphaf=min(1.0, abs(k) * a[0] * 1.5)))                                   # native order
        elif kind == "scratches":
            r = np.random.default_rng(frame)
            for _ in range(int(a[0])):
                x = float(r.random() * w)
                c.drawLine(x, 0, x + float(r.random() * 6 - 3), h, skia.Paint(Color=col("#1A140E", 0.55), StrokeWidth=max(1.0, w / 900)))
        else:
            c.drawImage(_overlay_image(kind, w, h, a), 0, 0)


@functools.lru_cache(maxsize=8)
def _solid(colr: str, w: int, h: int) -> skia.Image:
    v = np.zeros((h, w, 4), np.uint8)
    v[..., :3] = [int(colr[i:i + 2], 16) for i in (5, 3, 1)]
    v[..., 3] = 255
    return skia.Image.fromarray(v, skia.kBGRA_8888_ColorType, skia.kPremul_AlphaType)   # native format: fast blit


def needs_pixels(ops: tuple) -> bool:
    return any(op[0] not in OVERLAY_KINDS for op in ops)


def post_process(arr: np.ndarray, ops: tuple, frame: int) -> np.ndarray:
    """Applies a style's post chain to an RGBA uint8 frame in place and returns it."""
    h, w = arr.shape[:2]
    rgb = arr[..., :3]
    for op in ops:
        kind, a = op[0], op[1:]
        if kind in OVERLAY_KINDS:                               # drawn by overlay() before the read-back
            continue
        if kind == "pixelate":
            b = max(2, int(a[0] * w / 1080))
            small = rgb[b // 2::b, b // 2::b].copy()
            if len(a) > 1 and a[1] == "pico8":                   # nearest PICO-8 colour via a 15-bit lookup table
                idx = ((small[..., 0].astype(np.int32) >> 3) << 10) | ((small[..., 1].astype(np.int32) >> 3) << 5) | (small[..., 2].astype(np.int32) >> 3)
                small = _pico8_lut()[idx]
            elif len(a) > 1 and isinstance(a[1], int):          # posterize to n levels per channel
                step = 256 // a[1]
                small = (small // step) * step + step // 2
            big = np.repeat(np.repeat(small, b, 0), b, 1)[:h, :w]
            rgb[: big.shape[0], : big.shape[1]] = big
        elif kind == "grain":
            n = _noise(h, w)
            oy, ox = (frame * 37) % 64, (frame * 91) % 64
            g = (n[oy:oy + h, ox:ox + w] * (255 * a[0])).astype(np.int16)[..., None]
            rgb[:] = np.clip(rgb.astype(np.int16) + g, 0, 255).astype(np.uint8)
        elif kind == "vignette":
            rgb[:] = ((rgb.astype(np.uint16) * _vignette_mask(h, w, float(a[0]))) >> 8).astype(np.uint8)
        elif kind == "paper":
            rgb[:] = ((rgb.astype(np.uint16) * _paper_mask(h, w, float(a[0]))) >> 8).astype(np.uint8)
        elif kind == "halftone":
            rgb[:] = ((rgb.astype(np.uint16) * _halftone_mask(h, w, max(4, int(a[0] * w / 1080)), float(a[1]))) >> 8).astype(np.uint8)
        elif kind == "sepia":
            lum = ((rgb[..., 0].astype(np.uint16) * 77 + rgb[..., 1].astype(np.uint16) * 150 + rgb[..., 2].astype(np.uint16) * 29) >> 8)
            rgb[:] = _sepia_lut()[lum]
        elif kind == "flicker":
            k = 1 + a[0] * math.sin(frame * 12.9898 % 6.28) * ((frame * 7919) % 13) / 13
            lut = np.clip(np.arange(256) * k, 0, 255).astype(np.uint8)
            rgb[:] = lut[rgb]
        elif kind == "scratches":
            r = np.random.default_rng(frame)
            for _ in range(int(a[0])):
                x = int(r.random() * w)
                rgb[:, x:x + max(1, w // 900)] = (rgb[:, x:x + max(1, w // 900)] * 0.55).astype(np.uint8)
        elif kind == "scanlines":
            step = max(2, int(3 * w / 1080))
            rgb[::step] = (rgb[::step].astype(np.uint16) * int(256 * (1 - a[0])) >> 8).astype(np.uint8)
        elif kind == "chromatic":
            s = max(1, int(a[0] * w / 1080))
            rgb[:, s:, 0] = rgb[:, :-s, 0]
            rgb[:, :-s, 2] = rgb[:, s:, 2]
        elif kind == "contrast":
            x = np.arange(256, dtype=np.float32)
            lut = np.clip((x - 128) * a[0] + 128, 0, 255).astype(np.uint8)
            rgb[:] = lut[rgb]
    return arr


def bg_warm_dark(c, W, H):
    """Deep charcoal with a faint warm glow behind the upper middle (grain and vignette come from the post chain)."""
    _bg_solid(c, "#1A1918", W, H)
    c.drawCircle(W * 0.5, H * 0.42, max(W, H) * 0.42, D.blur(D.paint(col("#3A2A20", 0.32)), 220))


def bg_cream(c, W, H):
    """Warm cream with a faint peach glow (paper grain comes from the post chain)."""
    _bg_solid(c, "#F4F1EA", W, H)
    c.drawCircle(W * 0.5, H * 0.45, max(W, H) * 0.45, D.blur(D.paint(col("#F6DCCB", 0.35)), 220))


def bg_orange_dark(c, W, H):
    """Near-black with a faint warm radial glow at the centre (#1A1512); grain comes from the post chain."""
    _bg_solid(c, "#0E0D0C", W, H)
    p = skia.Paint()
    p.setShader(skia.GradientShader.MakeRadial(skia.Point(W / 2, H * 0.45), max(W, H) * 0.62,
                                               [col("#1A1512"), col("#0E0D0C")]))
    c.drawRect(skia.Rect.MakeWH(W, H), p)


def bg_navy(c, W, H):
    """Dark navy with a faint cool glow at the centre."""
    _bg_solid(c, "#0B1220", W, H)
    p = skia.Paint()
    p.setShader(skia.GradientShader.MakeRadial(skia.Point(W / 2, H * 0.45), max(W, H) * 0.6, [col("#16223A"), col("#0B1220")]))
    c.drawRect(skia.Rect.MakeWH(W, H), p)


# ================================================================== the style packs
class Style:
    def __init__(self, name: str, tier: int, status: str, best_for: str, tpl: Template | None, post: tuple = (),
                 fps: int | None = None, jitter: float = 0.0, effects: tuple = (), why_planned: str = "",
                 intertitles: bool = False, requires: str | None = None):
        self.name, self.tier, self.status, self.best_for, self.tpl = name, tier, status, best_for, tpl
        self.post, self.fps, self.jitter, self.effects, self.why_planned = post, fps, jitter, effects, why_planned
        self.intertitles = intertitles      # silent film: headings become 1.5 s intertitle cards; kinetic scenes are drawn as one
        self.requires = requires            # offered only for videos with this content (e.g. a 3D model)
        if tpl is not None:
            tpl.style = self


def _T(bg0, bg1, panel, line, text, text2, accent, **kw):
    T = dict(bg0=bg0, bg1=bg1, grid=line, panel=panel, line=line, text=text, text2=text2, accent=accent,
             blue=kw.get("blue", accent), teal=kw.get("teal", accent), green=kw.get("green", "#2E9E4F"),
             amber=kw.get("amber", "#D98A00"), red=kw.get("red", "#D2453C"), pink=kw.get("pink", "#C2588F"))
    return T


def _tpl(name, T, *, dark, bg_fn, card, icon, conn, sem=None, glow=False, family="Inter", family_bold=None,
         jitter=0.0, vignette=0.0, title_weight="Bold", texture=None, font_scale=1.0, bold_scale=1.0):
    t = Template(name, T, dark=dark, bg="style", card=card, icon=icon, conn=conn,
                 sem=sem or dict(success=T["green"], fail=T["red"], info=T["accent"], neutral=T["text2"]),
                 glow=glow, family=family, jitter=jitter, vignette=vignette, title_weight=title_weight)
    t.paint_bg, t.card_texture, t.family_bold = bg_fn, texture, family_bold
    t.font_scale, t.bold_scale = font_scale, bold_scale
    return t


def _card(fill, border, width=2.0, radius=16, shadow=0.0, glass=False, **kw):
    return dict(fill=fill, border=border, width=width, radius=radius, shadow=shadow, glass=glass, **kw)


INK = "#1B1F24"
STYLES: dict[str, Style] = {}


def _add(s: Style):
    STYLES[s.name] = s
    if s.tpl is not None:
        D.TEMPLATES[s.name] = s.tpl


# ---- Tier 1
_add(Style("whiteboard", 1, "ready", "algorithms, trade-offs, step-by-step reasoning",
           _tpl("whiteboard", _T("#F7F8F6", "#FFFFFF", "#FFFFFF", INK, INK, "#454B53", "#1E5BD8", red="#C2182F", green="#16793A"),
                dark=False, bg_fn=bg_whiteboard, family="Caveat", jitter=1.8,
                card=_card("#FFFFFF", INK, 2.6, 10), icon=dict(style="outline", color=INK, badge=None, ring=INK, stroke=2.6),
                conn=dict(color=INK, width=6.0, active="#1E5BD8", glow=False, dash=(16, 13)))))
_add(Style("sketchnote", 1, "ready", "concepts with several parts, study notes, trade-offs",
           _tpl("sketchnote", _T("#F6F0E2", "#F6F0E2", "#FFFDF6", "#2A2A2A", "#1F1F1F", "#4F4A40", "#A12A20", blue="#1F6BC2", teal="#13806F"),
                dark=False, bg_fn=bg_sketchnote, family="Caveat", jitter=1.6, texture=tex_paper,
                card=_card("#FFFDF6", "#2A2A2A", 2.4, 14), icon=dict(style="pastel", color="#2A2A2A", badge=None, ring="#2A2A2A", stroke=2.6),
                conn=dict(color="#2A2A2A", width=6.0, active="#A12A20", glow=False, dash=(16, 13))),
           post=(("paper", 0.10),)))
_add(Style("minimal-counter", 1, "ready", "numbers, scale, cost, latency budgets",
           _tpl("minimal-counter", _T("#F3F0E8", "#F3F0E8", "#FFFFFF", "#111111", "#111111", "#4A4A4A", "#C2410C", red="#B91C1C", green="#15803D"),
                dark=False, bg_fn=bg_minimal,
                card=_card("#FFFFFF", "#FFFFFF", 0.5, 4), icon=dict(style="solid", color="#FFFFFF", badge="#111111", ring="#111111", stroke=2.75, shape="square"),
                conn=dict(color="#111111", width=6.0, active="#C2410C", glow=False, dash=(18, 14)))))
_add(Style("limited-animation", 1, "ready", "stories with a few steps; friendly but exact",
           _tpl("limited-animation", _T("#FFE8C2", "#FFE8C2", "#FFFFFF", "#1A1A1A", "#1A1A1A", "#3D3D3D", "#C2381C", blue="#1D6FA3", teal="#0E8C8A", amber="#B7791F"),
                dark=False, bg_fn=bg_limited,
                card=_card("#FFFFFF", "#1A1A1A", 5.0, 22), icon=dict(style="flat", color="#1A1A1A", badge="#FFC914", ring="#1A1A1A", stroke=3.0),
                conn=dict(color="#1A1A1A", width=7.0, active="#C2381C", glow=False, dash=(18, 14))),
           post=(("halftone", 10, 0.10),), fps=12))
_add(Style("low-poly-neon", 1, "ready", "infrastructure, hardware, data centres, networks at scale",
           _tpl("low-poly-neon", _T("#0A0320", "#1B0838", "#1A0B3D", "#5B2A9E", "#F5EDFF", "#C9B6F2", "#FF85EA", blue="#6AA8FF", teal="#19F5FF", green="#38F2A0"),
                dark=True, bg_fn=bg_neon, glow=True, vignette=0.0,
                card=_card("#1A0B3D", "#FF4FDD", 1.8, 14, shadow=0.35, shadow_color="#000000", glass=True),
                icon=dict(style="solid", color="#FFFFFF", badge="#7A2BD6", ring="#FF4FDD", stroke=2.75, shape="square"),
                conn=dict(color="#B06BFF", width=6.5, active="#19F5FF", glow=True, dash=(18, 14))),
           post=(("chromatic", 2), ("vignette", 0.45), ("grain", 0.03)), effects=("parallax",)))
_add(Style("dark-pixel-grunge", 1, "ready", "security, attacks, incidents, breaches",
           _tpl("dark-pixel-grunge", _T("#050806", "#0B110C", "#0C140F", "#2E6B3A", "#D9FFD9", "#9CCF9C", "#39FF14", red="#FF3B3B", amber="#FFD21F", teal="#39FF14"),
                dark=True, bg_fn=bg_grunge, family="Inter", family_bold="Pixel", bold_scale=0.6,
                card=_card("#0C140F", "#39FF14", 2.0, 0), icon=dict(style="outline", color="#D9FFD9", badge=None, ring="#39FF14", stroke=2.5),
                conn=dict(color="#39FF14", width=6.0, active="#FF3B3B", glow=False, dash=(12, 10))),
           post=(("pixelate", 3, 6), ("scanlines", 0.30), ("chromatic", 2), ("grain", 0.035), ("vignette", 0.5))))
_add(Style("pixel-art", 1, "ready", "networking basics, protocols for beginners, retro explainers",
           _tpl("pixel-art", _T("#1D2B53", "#1D2B53", "#29366F", "#FFF1E8", "#FFF1E8", "#C2C3C7", "#FFA300", blue="#29ADFF", teal="#00E436", red="#FF004D", green="#00E436"),
                dark=True, bg_fn=bg_pixel, family_bold="Pixel", bold_scale=0.6,
                card=_card("#29366F", "#FFF1E8", 4.0, 0), icon=dict(style="solid", color="#1D2B53", badge="#FFA300", ring="#FFF1E8", stroke=3.0, shape="square"),
                conn=dict(color="#FFF1E8", width=8.0, active="#FFA300", glow=False, dash=(16, 16))),
           post=(("pixelate", 5, "pico8"),)))
_add(Style("engraving-print", 1, "ready", "history, principles, protocols with a long lineage",
           _tpl("engraving-print", _T("#EEE4CF", "#EEE4CF", "#F5EDDA", "#1A1410", "#1A1410", "#3E342B", "#8E1F20", red="#8E1F20", green="#2E5E2A"),
                dark=False, bg_fn=bg_engraving, family="IMFell", font_scale=1.12, texture=tex_engraving,
                card=_card("#F5EDDA", "#1A1410", 6.0, 2), icon=dict(style="outline", color="#1A1410", badge=None, ring="#1A1410", stroke=3.2),
                conn=dict(color="#1A1410", width=6.0, active="#8E1F20", glow=False, dash=(14, 10))),
           post=(("paper", 0.14), ("grain", 0.04))))
_add(Style("silent-film", 1, "ready", "history of a technology, origin stories, 'how it used to work'",
           _tpl("silent-film", _T("#2C2925", "#3B3631", "#1F1C19", "#D8CDB8", "#F2E9D8", "#CFC3AD", "#F2E9D8", red="#E8D9BE", green="#F2E9D8",
                    amber="#E0C9A0", pink="#D8C3A0", blue="#EADFC8", teal="#EADFC8"),     # sepia palette throughout
                dark=True, bg_fn=bg_silent, family="IMFell", font_scale=1.12,
                card=_card("#1F1C19", "#D8CDB8", 3.0, 6), icon=dict(style="outline", color="#F2E9D8", badge=None, ring="#D8CDB8", stroke=2.6),
                conn=dict(color="#D8CDB8", width=6.0, active="#FFFFFF", glow=False, dash=(14, 10))),
           post=(("grain", 0.09), ("flicker", 0.07), ("scratches", 3), ("vignette", 0.6)), fps=18,   # palette is sepia already
           intertitles=True))
_add(Style("paper-craft", 1, "ready", "architecture overviews, layered systems",
           _tpl("paper-craft", _T("#F4E8D8", "#F4E8D8", "#FFF8EE", "#B88B6A", "#2B211A", "#45372B", "#A63E1F", blue="#2F6F9E", teal="#2E8A7E"),
                dark=False, bg_fn=bg_papercraft, texture=tex_paper,
                card=_card("#FFF8EE", "#E6D2BC", 1.0, 10, shadow=0.35, shadow_color="#5A3A20", tilt=1.5, curl=True),
                icon=dict(style="pastel", color="#2B211A", badge=None, ring="#B88B6A", stroke=2.6),
                conn=dict(color="#8C5E3C", width=6.0, active="#C24E2B", glow=False, dash=(16, 13))),
           post=(("paper", 0.08),)))
_add(Style("shadow-puppetry", 1, "ready", "dramatic stories: failures, outages, before and after",
           _tpl("shadow-puppetry", _T("#060408", "#060408", "#000000", "#FFB238", "#F6E7D0", "#E6CDAE", "#FFCB73", red="#FF5C8A", teal="#3DD6FF", green="#7CF0B5"),
                dark=True, bg_fn=bg_puppetry, glow=True,
                card=_card("#000000", "#FFB238", 2.0, 20), icon=dict(style="silhouette", color="#F6E7D0", badge="#000000", ring="#FFB238", stroke=2.6),
                conn=dict(color="#FFB238", width=6.0, active="#3DD6FF", glow=True, dash=(16, 13))),
           post=(("vignette", 0.5), ("grain", 0.04))))
_add(Style("cardboard-diorama", 1, "ready", "architecture overviews, how parts sit together",
           _tpl("cardboard-diorama", _T("#B4875A", "#C39466", "#D9AE7E", "#6E4A2A", "#1A1009", "#271A0E", "#113A57", red="#9E2A2B", green="#2E6B30", amber="#7A4B10"),
                dark=False, bg_fn=bg_cardboard, texture=tex_cardboard,
                card=_card("#D9AE7E", "#6E4A2A", 2.0, 6, shadow=0.45, shadow_color="#3A2410"),
                icon=dict(style="solid", color="#FFFFFF", badge="#1F5F8B", ring="#6E4A2A", stroke=2.75, shape="square"),
                conn=dict(color="#3F2C1C", width=7.0, active="#1F5F8B", glow=False, dash=(16, 13))),
           post=(("grain", 0.03),), effects=("parallax",)))
_add(Style("claude-warm-dark", 1, "ready", "developer tooling: project structure, config files, CLI workflows",
           _tpl("claude-warm-dark", _T("#1A1918", "#1A1918", "#1E1C1A", "#4A3A32", "#F4F1EA", "#928D87", "#D97757",
                                       red="#E5534B", green="#6FBF73", amber="#D9A557", blue="#D97757", teal="#D97757"),
                dark=True, bg_fn=bg_warm_dark, family_bold="Heavy", bold_scale=0.92,
                card=_card("#1E1C1A", "#D97757", 2.0, 14), icon=dict(style="outline", color="#F4F1EA", badge=None, ring="#D97757", stroke=2.5),
                conn=dict(color="#D97757", width=3.0, active="#D97757", glow=False, dash=(14, 10)),
                sem=dict(success="#6FBF73", fail="#E5534B", info="#D97757", neutral="#8A8580")),
           post=(("vignette", 0.30), ("grain", 0.022))))
_add(Style("claude-orange", 1, "ready", "developer tooling explainers with a warm orange look",
           _tpl("claude-orange", _T("#F4F1EA", "#F4F1EA", "#F6DCCB", "#D97757", "#1F1E1D", "#635C55", "#D97757",
                                    red="#C0392B", green="#2E7D32", amber="#9E4528", blue="#9E4528", teal="#9E4528"),
                dark=False, bg_fn=bg_cream, family_bold="Heavy", bold_scale=0.92,
                card=_card("#F6DCCB", "#D97757", 2.0, 14),
                icon=dict(style="outline", color="#1F1E1D", badge=None, ring="#D97757", stroke=2.5),
                conn=dict(color="#D97757", width=3.0, active="#9E4528", glow=False, dash=(14, 10)),
                sem=dict(success="#2E7D32", fail="#C0392B", info="#9E4528", neutral="#635C55")),
           post=(("paper", 0.05), ("grain", 0.016))))
_add(Style("claude-orange-dark", 1, "ready", "premium developer-tool explainers: editor UI, terminals, diagrams on black",
           _tpl("claude-orange-dark", _T("#0E0D0C", "#171615", "#171615", "#2A2725", "#F4F1EA", "#A8A097", "#D97757",
                                         red="#E5604D", green="#7FB77E", amber="#F0A07E", blue="#F0A07E", teal="#F0A07E"),
                dark=True, bg_fn=bg_orange_dark, family_bold="Heavy", bold_scale=0.92,
                card=_card("#171615", "#2A2725", 2.0, 16, shadow=0.4, shadow_color="#000000"),
                icon=dict(style="outline", color="#F4F1EA", badge=None, ring="#D97757", stroke=2.5),
                conn=dict(color="#D97757", width=4.0, active="#F0A07E", glow=True, dash=(14, 10)),
                sem=dict(success="#7FB77E", fail="#E5604D", info="#F0A07E", neutral="#A8A097")),
           post=(("grain", 0.012),)))
_add(Style("navy-gold", 1, "ready", "platforms, paths and layered systems; calm and premium",
           _tpl("navy-gold", _T("#0B1220", "#16223A", "#16223A", "#2A3A5C", "#F4F1EA", "#9AA8C0", "#E8B44A",
                                red="#F07A6A", green="#7FD1A0", amber="#FFD37A", blue="#8FB8FF", teal="#7FD1C8"),
                dark=True, bg_fn=bg_navy, family_bold="Heavy", bold_scale=0.92,
                card=_card("#16223A", "#2A3A5C", 2.0, 16, shadow=0.4, shadow_color="#000000"),
                icon=dict(style="outline", color="#F4F1EA", badge=None, ring="#E8B44A", stroke=2.5),
                conn=dict(color="#E8B44A", width=4.0, active="#FFD37A", glow=True, dash=(14, 10)),
                sem=dict(success="#7FD1A0", fail="#F07A6A", info="#8FB8FF", neutral="#9AA8C0")),
           post=(("grain", 0.012),)))
# ---- Tier 2
_add(Style("stop-motion-clay", 2, "ready", "light, friendly intros; simple flows",
           _tpl("stop-motion-clay", _T("#F1D6B8", "#F6E2CB", "#FFC9B0", "#7A3E2E", "#3A1E16", "#55301F", "#C2410C", blue="#2F6F9E", teal="#2B8A7E", green="#2F6420"),
                dark=False, bg_fn=bg_clay, texture=tex_fingerprint,
                card=_card("#FFC9B0", "#C27A5E", 2.0, 44, shadow=0.35, shadow_color="#7A3E2E"),
                icon=dict(style="solid", color="#FFFFFF", badge="#D9603B", ring="#7A3E2E", stroke=3.0, shape="square"),
                conn=dict(color="#7A3E2E", width=8.0, active="#C2410C", glow=False, dash=(18, 14))),
           post=(("grain", 0.035),), fps=12, jitter=2.5))
_add(Style("hd-pixel-sprite-3d", 2, "ready", "hardware and infrastructure with a game look",
           _tpl("hd-pixel-sprite-3d", _T("#0B1026", "#141C3D", "#17204A", "#3A4C9A", "#EEF2FF", "#B8C3F0", "#5EE2FF", teal="#5EE2FF", green="#7CFF9B"),
                dark=True, bg_fn=bg_pixel, glow=True, family_bold="Pixel", bold_scale=0.6,
                card=_card("#17204A", "#5EE2FF", 3.0, 0), icon=dict(style="solid", color="#FFFFFF", badge="#3A4C9A", ring="#5EE2FF", stroke=3.0, shape="square"),
                conn=dict(color="#8FA2FF", width=8.0, active="#5EE2FF", glow=False, dash=(16, 16))),
           post=(("pixelate", 4, 8),), requires="model_3d"))
for _n, _why in (("stick-figure-story", "needs posed, rigged characters with readable gestures; a style pack alone cannot draw them"),
                 ("paper-cutout-puppet", "needs jointed cut-out characters; not built"),
                 ("hand-puppet-theatre", "needs puppet characters on a stage; a frame and curtain alone would not be honest")):
    _add(Style(_n, 2, "planned", "incidents and postmortems told as stories", None, why_planned=_why))

READY = tuple(n for n, s in STYLES.items() if s.status == "ready")
INTERTITLE_SECONDS = 1.5


def draw_intertitle(c, tpl, text: str, W: float, H: float, a: float = 1.0, show_text: bool = True) -> None:
    """A silent-film intertitle: a black card with an ornate thin double border and corner flourishes; the text in
    IM FELL, centred. The card is a cached sprite; the text is drawn on top."""
    inset = 70.0 if H > W else 150.0

    def card(cc):
        cc.drawColor(col("#0B0907"))
        x0, y0, x1, y1 = inset, inset * (1.6 if H > W else 0.7), W - inset, H - inset * (1.6 if H > W else 0.7)
        line = D.paint(col("#E9DFC9"), 2.2)
        cc.drawRect(skia.Rect.MakeLTRB(x0, y0, x1, y1), line)
        cc.drawRect(skia.Rect.MakeLTRB(x0 + 14, y0 + 14, x1 - 14, y1 - 14), D.paint(col("#E9DFC9"), 1.2))
        for (cx, cy, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
            p = skia.Path()                                    # a corner flourish: a small scroll and a diamond
            p.moveTo(cx + sx * 14, cy + sy * 46)
            p.cubicTo(cx + sx * 40, cy + sy * 46, cx + sx * 46, cy + sy * 40, cx + sx * 46, cy + sy * 14)
            cc.drawPath(p, D.paint(col("#E9DFC9"), 2))
            d = skia.Path()
            d.moveTo(cx + sx * 30, cy + sy * 22); d.lineTo(cx + sx * 36, cy + sy * 30)
            d.lineTo(cx + sx * 30, cy + sy * 38); d.lineTo(cx + sx * 24, cy + sy * 30); d.close()
            cc.drawPath(d, D.paint(col("#E9DFC9")))
        mid = (y0 + y1) / 2
        for yy in (y0 + (mid - y0) * 0.35, y1 - (y1 - mid) * 0.35):   # thin rules above and below the text
            cc.drawLine(W / 2 - 120, yy, W / 2 + 120, yy, D.paint(col("#E9DFC9"), 1.4))
            cc.drawCircle(W / 2, yy, 4, D.paint(col("#E9DFC9")))
    D.sprite(c, ("intertitle", int(W), int(H)), 0, 0, W, H, card, a)
    if show_text and text:
        rows, sz = D.fit_block(text, W - 2 * inset - 120, 4, 96 if H > W else 88, 56, "Regular")
        total = len(rows) * sz * 1.18
        y = H / 2 - total / 2 + sz * 0.8
        for j, r in enumerate(rows):
            D.draw_text(c, r, W / 2, y + j * sz * 1.18, sz, col("#F2E9D8", a), "Regular", "center")
PLANNED = tuple(n for n, s in STYLES.items() if s.status == "planned")


def style_of(tpl) -> Style | None:
    return getattr(tpl, "style", None)
