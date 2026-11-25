"""The "dev_scene" motion effect: premium developer-tool scenes on black (claude-orange-dark), one layout per script line.

A generic, unbranded code editor (explorer sidebar, tabs, line numbers, minimap, terminal panel), a warm syntax theme,
typed code, kinetic keyword pops, a pinned file-name heading, light rays behind the active window, and scene
transitions drawn by the scenes themselves (scenes are joined by "cut"): match cut, whip pan with motion blur,
zoom-through, push-through, mask reveal and a terracotta wipe. The channel's pixel mascot gets a cream rim light.

Spec: {"treatment": "motion", "effect": "dev_scene", "kind": one of KINDS, "file": pinned heading text,
       "tin": transition in, "tout": transition out, "pops": [{"text", "at"}], "mascot": {...}, ...kind fields}
Every label is >= 30 px; key text stays between y 230 and 1530 (Instagram's top 220 and bottom 380 px are kept free).
"""
from __future__ import annotations
import math, re
import skia
from . import assets, design as D
from .design import col, clamp, lerp, ease_out, ease_in_out, spring

W, H = 1080.0, 1920.0
P = dict(bg="#0E0D0C", panel="#171615", editor="#131211", border="#2A2725", text="#F4F1EA", text2="#A8A097",
         acc="#D97757", bright="#F0A07E", rust="#B85C3C", ok="#7FB77E", bad="#E5604D",
         key="#F0A07E", string="#E8C9A0", comment="#8F877D", punct="#A8A097")   # comment: #7D756C is 4.1:1, too low
FS = 30.0
CW = 18.0          # JetBrains Mono advance at 30 px
LHC = 44.0         # code line height
SAFE_TOP, SAFE_BOTTOM = 230.0, 1530.0
KINDS = ("hook", "claude_md", "local_md", "mcp", "settings", "rules", "skills", "agents", "hooks", "takeaway")


def io(x):                                     # ease-in-out cubic
    return ease_in_out(clamp(x))


def txt(c, s, x, y, color, a=1.0, size=FS, weight="Regular", mono=False, align="left"):
    if a > 0.01 and s:
        D.draw_text(c, s, x, y, max(size, 30.0), col(color, clamp(a)), weight, align, mono=mono)


def tw(s, size=FS, weight="Regular", mono=False):
    return D.text_width(s, max(size, 30.0), weight, mono)


def box(c, x, y, w, h, r=16, fill=None, stroke=None, sw=2.0, a=1.0, shadow=False):
    rr = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), r, r)
    if shadow and a > 0.05:
        D.soft_shadow(c, x, y + 14, w, h, r, "#000000", 0.55 * a, 26)
    if fill:
        c.drawRRect(rr, D.paint(col(fill, a)))
    if stroke:
        c.drawRRect(rr, D.paint(col(stroke, a), sw))
    return rr


# ------------------------------------------------------------------ syntax (warm theme)
def tokens(line: str, lang: str) -> list[tuple[str, str]]:
    if lang == "json":
        out, i = [], 0
        for m in re.finditer(r'"[^"]*"|[{}\[\],:]', line):
            if m.start() > i:
                out.append((line[i:m.start()], P["text"]))
            s = m.group()
            if s.startswith('"'):
                is_key = line[m.end():].lstrip().startswith(":")
                out.append((s, P["key"] if is_key else P["string"]))
            else:
                out.append((s, P["punct"]))
            i = m.end()
        out.append((line[i:], P["text"]))
        return out
    if lang == "md":
        if line.startswith("#"):
            return [(line, P["key"])]
        if line.startswith("- "):
            return [("- ", P["punct"]), (line[2:], P["text"])]
        if line.startswith("@"):
            return [(line, P["string"])]
        if line.startswith("<!--"):
            return [(line, P["comment"])]
        return [(line, P["text"])]
    if lang == "yaml":
        if line.strip() == "---":
            return [(line, P["punct"])]
        m = re.match(r"(\s*)([\w-]+)(:)(.*)", line)
        if m:
            return [(m.group(1), P["text"]), (m.group(2), P["key"]), (":", P["punct"]), (m.group(4), P["string"])]
        m = re.match(r"(\s*- )(.*)", line)
        if m:
            return [(m.group(1), P["punct"]), (m.group(2), P["string"])]
        return [(line, P["text"])]
    if lang == "sh":
        if line.lstrip().startswith("#"):
            return [(line, P["comment"])]
        out = []
        for part in re.split(r"('[^']*'|\"[^\"]*\")", line):
            out.append((part, P["string"] if part[:1] in "'\"" else P["text"]))
        return out
    return [(line, P["text"])]


def code_line(c, line, x, y, lang, n=None, a=1.0, color=None):
    """Draws one code line (first n characters); returns the x after the last drawn character."""
    left = len(line) if n is None else max(0, int(n))
    for s, colr in tokens(line, lang):
        if left <= 0:
            break
        part = s[:left]
        txt(c, part, x, y, color or colr, a, mono=True)
        x += len(part) * CW
        left -= len(part)
    return x


def typed(lines, t, t0, cps=34.0):
    """Characters revealed per line at time t when typing starts at t0 (a short pause after each line)."""
    out, clock = [], t0
    for ln in lines:
        dur = len(ln) / cps
        out.append(clamp((t - clock) / max(dur, 1e-3)) * len(ln))
        clock += dur + 0.06
    return out, clock


# ------------------------------------------------------------------ the generic editor window
def window(c, x, y, w, h, title="", a=1.0, glow=0.0):
    """A window: soft shadow, panel, 52 px title bar with three dots and a centred mono title."""
    if glow > 0:
        D.halo(c, x + w / 2, y + h / 2, max(w, h) * 0.62, P["acc"], 0.20 * glow * a)
    box(c, x, y, w, h, 18, P["panel"], P["border"], 2, a, shadow=True)
    for i in range(3):
        c.drawCircle(x + 30 + i * 24, y + 26, 7, D.paint(col("#3A3633", a)))
    if title:
        txt(c, title, x + w / 2, y + 37, P["text2"], a, mono=True, align="center")
    c.drawLine(x, y + 52, x + w, y + 52, D.paint(col(P["border"], a), 2))
    return y + 52


def editor(c, x, y, w, h, *, title="my-project", explorer=None, tabs=(), lines=(), lang="md", n=None, a=1.0,
           hl=None, term=None, term_h=0.0, glow=0.0, cursor=True, t=0.0, explorer_w=300.0):
    """Explorer [(name, depth, state)] with state in "", "active", "dim", "ignored", "lit"; tabs [(name, active)];
    code lines with per-line typed counts n; a terminal panel [(text, color)] at the bottom. Returns geometry."""
    top = window(c, x, y, w, h, title, a, glow)
    g = {"top": top, "rows": {}, "x": x, "y": y, "w": w, "h": h}
    ex_w = explorer_w if explorer is not None else 0.0
    if explorer is not None:
        c.drawRect(skia.Rect.MakeXYWH(x + 2, top, ex_w, h - (top - y) - term_h - 2), D.paint(col("#141312", a)))
        txt(c, "EXPLORER", x + 22, top + 42, P["text2"], a, 30, "SemiBold")
        for i, (name, depth, state) in enumerate(explorer):
            ry = top + 92 + i * 46
            if ry > y + h - term_h - 20:
                break
            colr = {"active": P["text"], "dim": P["text2"], "ignored": P["text2"], "lit": P["bright"]}.get(state, P["text"])
            if state == "active":
                box(c, x + 8, ry - 32, ex_w - 16, 44, 8, "#2A2018", None, 0, a)
                c.drawRect(skia.Rect.MakeXYWH(x + 8, ry - 32, 4, 44), D.paint(col(P["acc"], a)))
            ic = "folder" if name.endswith("/") else "file-text"
            assets.draw_icon(c, ic, x + 28 + depth * 20, ry - 10, 26, P["acc"] if state in ("active", "lit") else P["text2"], a, 2.0)
            label = name if len(name) * CW + 48 + depth * 20 < ex_w - 10 else name[: int((ex_w - 70 - depth * 20) / CW) - 1] + "…"
            txt(c, label, x + 48 + depth * 20, ry, colr, a * (0.75 if state in ("dim", "ignored") else 1.0), mono=True)
            if state == "ignored":
                c.drawLine(x + 48 + depth * 20, ry - 9, x + 48 + depth * 20 + tw(label, mono=True), ry - 9, D.paint(col(P["text2"], a), 2))
            g["rows"][name] = (x + 8, ry - 32, ex_w - 16, 44)
        c.drawLine(x + ex_w, top, x + ex_w, y + h - term_h, D.paint(col(P["border"], a), 2))
    cx0 = x + ex_w
    # tabs
    tx = cx0 + 4
    for name, active in tabs:
        wtab = tw(name, mono=True) + 40
        if active:
            c.drawRect(skia.Rect.MakeXYWH(tx, top, wtab, 56), D.paint(col(P["editor"], a)))
            c.drawRect(skia.Rect.MakeXYWH(tx, top, wtab, 3), D.paint(col(P["acc"], a)))
        txt(c, name, tx + 20, top + 39, P["text"] if active else P["text2"], a, mono=True)
        g.setdefault("tab", (tx, top, wtab, 56)) if active else None
        tx += wtab + 2
    ctop = top + 58
    c.drawRect(skia.Rect.MakeXYWH(cx0 + 2, ctop, w - ex_w - 4, h - (ctop - y) - term_h - 2), D.paint(col(P["editor"], a)))
    # code
    ln_x = cx0 + 16
    code_x = cx0 + 70
    g.update(code_x=code_x, code_y=ctop + 46)
    last = (code_x, ctop + 46)
    for i, ln in enumerate(lines):
        ly = ctop + 46 + i * LHC
        if ly > y + h - term_h - 16:
            break
        k = None if n is None else n[i]
        if k is not None and k <= 0:
            continue
        if hl is not None and i in (hl if isinstance(hl, (list, tuple, set)) else [hl]):
            c.drawRect(skia.Rect.MakeXYWH(cx0 + 2, ly - 32, w - ex_w - 34, LHC), D.paint(col("#2A2018", a)))
            c.drawRect(skia.Rect.MakeXYWH(cx0 + 2, ly - 32, 4, LHC), D.paint(col(P["acc"], a)))
        D.draw_text(c, str(i + 1).rjust(2), ln_x, ly, 30, col(P["text2"], 0.6 * a), "Regular", mono=True)
        ex = code_line(c, ln, code_x, ly, lang, k, a)
        last = (ex, ly)
    if cursor and int(t * 2.2) % 2 == 0:
        c.drawRect(skia.Rect.MakeXYWH(last[0] + 2, last[1] - 26, 3, 32), D.paint(col(P["acc"], a)))
    g["cursor"] = last
    # minimap: tiny bars, one per line
    mx = x + w - 26
    for i, ln in enumerate(lines):
        k = len(ln) if n is None else n[i]
        if k > 0:
            c.drawRect(skia.Rect.MakeXYWH(mx, ctop + 12 + i * 6, min(18, 0.4 * k), 3), D.paint(col(P["text2"], 0.35 * a)))
    # terminal panel
    if term_h > 0:
        ty = y + h - term_h
        c.drawRect(skia.Rect.MakeXYWH(x + 2, ty, w - 4, term_h - 2), D.paint(col("#100F0E", a)))
        c.drawLine(x, ty, x + w, ty, D.paint(col(P["border"], a), 2))
        txt(c, "TERMINAL", x + 22, ty + 40, P["text2"], a, 30, "SemiBold")
        g["term_y"] = ty + 92
        for j, item in enumerate(term or []):
            s, colr = item[0], item[1]
            k = item[2] if len(item) > 2 else None
            yy = ty + 92 + j * LHC
            if yy > y + h - 10:
                break
            if s.startswith("$ "):
                txt(c, "$", x + 24, yy, P["acc"], a, mono=True)
                code_line(c, s[2:], x + 24 + 2 * CW, yy, "sh", None if k is None else k - 2, a, colr)
            else:
                code_line(c, s, x + 24, yy, "sh", k, a, colr)
    return g


def rays(c, cx, cy, t, a=1.0):
    """Soft light rays behind the active window: a few long, very faint warm wedges, slowly turning."""
    if a <= 0.01:
        return
    for i in range(5):
        ang = -math.pi / 2 + (i - 2) * 0.32 + 0.05 * math.sin(t * 0.4 + i)
        p = skia.Path()
        p.moveTo(cx, cy)
        L = 1300
        p.lineTo(cx + math.cos(ang - 0.06) * L, cy + math.sin(ang - 0.06) * L)
        p.lineTo(cx + math.cos(ang + 0.06) * L, cy + math.sin(ang + 0.06) * L)
        p.close()
        pt = skia.Paint(AntiAlias=True)
        pt.setShader(skia.GradientShader.MakeRadial(skia.Point(cx, cy), L, [col(P["acc"], 0.10 * a), col(P["acc"], 0.0)]))
        c.drawPath(p, pt)


def pop(c, text, x, y, t, t0, size=88, hold=1.0, color=None):
    """A kinetic keyword: springs in on its word, holds, fades. Heavy display face."""
    k_in = clamp((t - t0) / 0.32)
    if k_in <= 0 or t > t0 + hold + 0.3:
        return
    a = min(k_in * 1.4, 1 - clamp((t - t0 - hold) / 0.3))
    s = 0.6 + 0.4 * spring(k_in)
    f = D.make_font(size, "Bold")
    wdt = f.measureText(text)
    c.save()
    c.translate(x, y)
    c.scale(s, s)
    pad = 26
    box(c, -wdt / 2 - pad, -size * 0.86, wdt + 2 * pad, size * 1.16, 18, P["bg"], P["acc"], 3, a * 0.92)
    D.put_text(c, text, -wdt / 2, size * 0.12, f, col(color or P["bright"], a))
    c.restore()


def heading(c, text, a=1.0):
    """The pinned file name, top left, just below the platform's top bar."""
    c.drawCircle(64, 262, 8, D.paint(col(P["acc"], a)))
    txt(c, text, 84, 273, P["text"], a, 32, mono=True)


def chip(c, x, y, text, colr=None, a=1.0, fill=None, icon=None):
    w = tw(text, 30, "Medium") + 32 + (36 if icon else 0)
    box(c, x, y - 24, w, 48, 24, fill or P["panel"], colr or P["acc"], 2, a)
    if icon:
        assets.draw_icon(c, icon, x + 30, y, 26, colr or P["acc"], a, 2.2)
    txt(c, text, x + 16 + (36 if icon else 0), y + 10, colr or P["text"], a, 30, "Medium")
    return w


# ------------------------------------------------------------------ transitions (drawn inside the scenes)
TR_DUR = 0.36


def transform_for(kind, k, focus=(540.0, 900.0), incoming=True):
    """(matrix, alpha, blur copies) for a transition at progress k (0 = start of the effect, 1 = done)."""
    m = skia.Matrix()
    fx, fy = focus
    if kind == "whip":
        dx = (1 - io(k)) * W * (1.0 if incoming else -1.0) if incoming else -io(k) * W
        m.setTranslate(dx, 0)
        return m, 1.0, 5 if 0.05 < k < 0.95 else 0
    if kind == "zoom":
        s = lerp(0.55, 1.0, io(k)) if incoming else lerp(1.0, 5.0, io(k) ** 2)
        m.setScale(s, s, fx, fy)
        return m, (clamp(k * 2) if incoming else 1 - clamp((k - 0.5) * 2)), 0
    if kind == "push":
        s = lerp(0.86, 1.0, io(k)) if incoming else lerp(1.0, 1.35, io(k))
        m.setScale(s, s, W / 2, H / 2)
        return m, (io(k) if incoming else 1 - io(k)), 0
    return m, 1.0, 0


class Scene:
    def __init__(self, ms):
        self.ms = ms
        self.sp = ms.sc.spec
        self.dur = ms.sc.dur
        self.kind = self.sp.get("kind", "hook")
        from . import mascot as M
        self.M = M
        m = self.sp.get("mascot")
        self.mascot = M.Mascot(m, ms.cue_t) if m and M.available() else None
        self._diagram = None

    def at(self, cue, default=0.0):
        if isinstance(cue, (int, float)):
            return float(cue)
        return self.ms.cue_t(cue, default)

    def w(self, word, default=0.0, off=0.0):
        return self.ms.cue_t({"word": word}, default) + off

    # ---- the frame
    def draw(self, c, t):
        rec = skia.PictureRecorder()
        pc = rec.beginRecording(skia.Rect.MakeWH(W, H))
        z, fx, fy = self.camera(t)
        pc.save()
        pc.translate(fx, fy); pc.scale(z, z); pc.translate(-fx, -fy)
        getattr(self, "_" + self.kind)(pc, t)
        pc.restore()
        self._overlays(pc, t)
        pic = rec.finishRecordingAsPicture()
        tin, tout = self.sp.get("tin"), self.sp.get("tout")
        m, a, blur = skia.Matrix(), 1.0, 0
        if tin in ("whip", "zoom", "push") and t < TR_DUR:
            m, a, blur = transform_for(tin, t / TR_DUR, self._focus("in"), True)
        elif tout in ("whip", "zoom", "push") and t > self.dur - TR_DUR:
            m, a, blur = transform_for(tout, (t - (self.dur - TR_DUR)) / TR_DUR, self._focus("out"), False)
        if tin == "mask" and t < 0.5:                       # a circle reveal from the focus point
            fx2, fy2 = self._focus("in")
            r = io(t / 0.5) * math.hypot(W, H)
            c.save()
            p = skia.Path(); p.addCircle(fx2, fy2, max(1.0, r))
            c.clipPath(p, skia.ClipOp.kIntersect, True)
        if blur:                                            # motion blur for the whip: faint copies along the move
            step = 26.0 * (1 if tin == "whip" and t < TR_DUR else -1)
            for j in range(1, blur + 1):
                mm = skia.Matrix.Concat(skia.Matrix.Translate(step * j, 0), m)
                c.drawPicture(pic, mm, skia.Paint(Alphaf=0.16))
        m.postTranslate(*self.shake(t))
        c.drawPicture(pic, m, skia.Paint(Alphaf=clamp(a)) if a < 0.999 else None)
        if tin == "mask" and t < 0.5:
            c.restore()
        self._wipe(c, t)

    def _focus(self, which):
        f = self.sp.get("focus_" + which)
        return tuple(f) if f else (W / 2, 900.0)

    def camera(self, t):
        """A slow drift (1.0 -> 1.03) plus a push-in on each key word ("push": [{"at", "x", "y", "z"}])."""
        if self.kind == "takeaway" and t > self.w("Start", 3.0, 0.1):
            return 1.0, W / 2, 900.0                          # the saved frame: no drift, the mascot's perch stays exact
        z = 1.0 + 0.03 * io(t / max(self.dur, 0.1))
        fx, fy = self.sp.get("drift_focus", (W / 2, 900.0))
        for p in self.sp.get("push", []):
            t0 = self.at(p.get("at"), 0)
            k = io((t - t0) / 0.7) * (1 - io((t - t0 - float(p.get("hold", 1.6))) / 0.7))
            if k > 0:
                z *= lerp(1.0, float(p.get("z", 1.08)), k)
                fx, fy = lerp(fx, p.get("x", fx), k), lerp(fy, p.get("y", fy), k)
        return z, fx, fy

    def _overlays(self, c, t):
        if self.sp.get("file"):
            heading(c, self.sp["file"])
        for p in self.sp.get("pops", []):
            pop(c, p["text"], p.get("x", W / 2), p.get("y", 1440), t, self.at(p.get("at"), 0), p.get("size", 80),
                p.get("hold", 1.0), p.get("color"))
        if self.mascot:
            self.mascot.draw(c, t, 1.0, None, rim=P["text"], shadow=True)

    def _wipe(self, c, t):
        if self.sp.get("wipe_in"):
            k = io(t / 0.5)
            if k < 1:
                c.drawRect(skia.Rect.MakeLTRB(W * k, 0, W, H), D.paint(col(P["acc"])))
        wo = self.sp.get("wipe_out")
        if wo:
            t0 = self.dur - 0.45 if wo is True else self.at(wo, self.dur - 0.45)
            k = io((t - t0) / 0.45)
            if k > 0:
                k2 = io((t - t0 - 0.55) / 0.45) if wo is not True else 0.0    # a mid-scene wipe also uncovers
                c.drawRect(skia.Rect.MakeLTRB(W * k2, 0, W * k, H), D.paint(col(P["acc"])))

    # ================================================================== S1 hook
    TREE_LINES = [".", "├── .claude", "│   ├── agents", "│   │   ├── code-reviewer.md", "│   │   └── security-auditor.md",
                  "│   ├── commands", "│   │   └── deploy.md", "│   ├── hooks", "│   │   └── validate-bash.sh",
                  "│   ├── rules", "│   │   ├── code-style.md", "│   │   └── testing.md", "│   ├── settings.json",
                  "│   ├── settings.local.json", "│   └── skills", "│       ├── fix-issue", "│       │   └── SKILL.md",
                  "│       └── review", "│           └── SKILL.md", "├── .mcp.json", "├── CLAUDE.local.md", "└── CLAUDE.md"]

    KEEP = {"CLAUDE.md", "CLAUDE.local.md", ".mcp.json", "settings.json", "settings.local.json", "rules", "skills", "agents", "hooks"}

    def card3d(self, i):
        """Where tree line i flies to: a deterministic scatter in depth."""
        r1 = (math.sin(i * 12.9898) * 43758.5453) % 1.0
        r2 = (math.sin(i * 78.233) * 12543.123) % 1.0
        r3 = (math.sin(i * 39.425) * 24634.634) % 1.0
        return (lerp(120, 960, r1), lerp(420, 1420, r2), lerp(0, 1500, r3))

    def _hook(self, c, t):
        cmd_t0, enter = 0.35, 0.95
        if t < enter + 0.12:                                # black, a blinking cursor, `claude` typed, Enter
            n = int(len("claude") * clamp((t - cmd_t0) / 0.45))
            txt(c, "$", 120, 900, P["acc"], 1, 40, mono=True)
            txt(c, "claude"[:n], 160, 900, P["text"], 1, 40, mono=True)
            if int(t * 2.6) % 2 == 0 or n < 6:
                c.drawRect(skia.Rect.MakeXYWH(162 + n * 24, 868, 18, 40), D.paint(col(P["acc"])))
            return
        # tree -a cascades, then flies apart into floating file cards in depth
        t1 = enter + 0.12
        fly = io((t - self.w("Here", t1 + 1.3)) / 1.6)
        x0, y0 = 70.0, 360.0
        txt(c, "$ tree -a", x0, y0, P["acc"], 1 - fly, mono=True)
        items = []
        for i, ln in enumerate(self.TREE_LINES):
            lt = t1 + 0.04 * i
            if t < lt:
                break
            sx, sy = x0, y0 + 46 * (i + 1)
            X, Y, Z = self.card3d(i)
            z = lerp(0, Z, fly) + 900 * fly ** 2           # the camera dollies forward through the cards
            f = 1400.0 / (1400.0 + max(-1300.0, z - 900 * fly))
            px = lerp(sx, X, fly)
            py = lerp(sy, Y, fly)
            px = W / 2 + (px - W / 2) * f
            py = 900 + (py - 900) * f
            items.append((z, px, py, f, ln, i))
        for z, px, py, f, ln, i in sorted(items, key=lambda q: -q[0]):
            name = ln.replace("│", " ").replace("├──", "").replace("└──", "").strip()
            if fly <= 0.02:
                txt(c, ln, px, py, P["text"] if i else P["acc"], 1, mono=True)
                continue
            if name not in self.KEEP:                       # only the key files fly on as cards
                fade = 1 - clamp(fly * 4)
                if fade > 0.01:
                    txt(c, ln, lerp(x0, px, 0.2 * fly), lerp(y0 + 46 * (i + 1), py, 0.2 * fly), P["text2"], fade, mono=True)
                continue
            s = max(0.35, min(2.2, f))
            depth_a = clamp(1.25 - (1 - f) * 0.9) if f < 1 else clamp(2.4 - f)
            c.save()
            c.translate(px, py); c.scale(s, s)
            wdt = len(name) * CW + 70
            prefix = ln[: len(ln) - len(ln.lstrip("│├└─ "))]
            ta = 1 - clamp(fly * 4)
            if ta > 0.01:
                txt(c, prefix, -len(prefix) * CW, 0, P["text2"], ta, mono=True)
            box(c, -16, -34, wdt, 50, 10, P["panel"], P["acc"] if name.endswith(".md") and "CLAUDE" in name else P["border"], 2, fly * depth_a)
            assets.draw_icon(c, "file-text" if "." in name[1:] else "folder", 6, -9, 24, P["acc"], fly * depth_a, 2)
            txt(c, name, 30, 0, P["text"], depth_a if fly > 0.02 else 1, mono=True)
            c.restore()

    def scatter_positions(self, t_fly_end=1.0):
        out = {}
        for i, ln in enumerate(self.TREE_LINES):
            X, Y, Z = self.card3d(i)
            z = Z + 900
            f = 1400.0 / (1400.0 + z - 900)
            out[i] = (W / 2 + (X - W / 2) * f, 900 + (Y - 900) * f, f, ln.replace("│", " ").replace("├──", "").replace("└──", "").strip())
        return out

    # ================================================================== S2 CLAUDE.md
    MD = ["# my-project", "## Commands", "- npm test", "- npm run build", "## Conventions", "- TypeScript strict mode",
          "- Small, focused PRs", "@docs/architecture.md"]
    EXPL = [("CLAUDE.md", 0, "active"), ("CLAUDE.local.md", 0, ""), (".mcp.json", 0, ""), (".claude/", 0, ""),
            ("src/", 0, ""), ("docs/", 0, "")]

    def _claude_md(self, c, t):
        ex, ey, ew, eh = 50.0, 330.0, 980.0, 860.0
        k = io(t / 0.7)                                     # match cut: the floating cards fly into the editor
        rays(c, ex + ew / 2, ey + 40, t, 0.8 * k)
        lift = io((t - self.w("loaded", 2.4)) / 0.9)
        n, _ = typed(self.MD, t, 0.75, 46)
        g = editor(c, ex, ey, ew, eh, title="my-project", explorer=self.EXPL, tabs=[("CLAUDE.md", True)], lines=self.MD,
                   lang="md", n=n, a=k, glow=k, t=t)
        if k < 1:
            sc = self.scatter_positions()
            for i, (px, py, f, name) in sc.items():
                if name not in self.KEEP:
                    continue
                q = io(t / 0.7)
                target = g["rows"].get(name if name != "." else "CLAUDE.md")
                tx_, ty_ = (target[0] + 40, target[1] + 32) if target else (ex + 160, ey + 120)
                if name == "CLAUDE.md":
                    tx_, ty_ = g.get("tab", (ex + 300, ey + 52, 0, 0))[0] + 20, ey + 52 + 39
                x = lerp(px, tx_, q); y = lerp(py, ty_, q)
                s = lerp(max(0.35, min(2.2, f)), 1.0, q)
                c.save(); c.translate(x, y); c.scale(s, s)
                a2 = (1 - q) if name != "CLAUDE.md" else 1 - q * 0.9
                box(c, -16, -34, len(name) * CW + 70, 50, 10, P["panel"], P["acc"] if name == "CLAUDE.md" else P["border"], 2, a2)
                txt(c, name, 30, 0, P["text"], a2, mono=True)
                c.restore()
        # the file lifts out and pours into the context window bar
        bx, by, bw, bh = 70.0, 1300.0, 940.0, 70.0
        if lift > 0:
            txt(c, "Context window", bx, by - 22, P["text2"], lift, 30, "SemiBold")
            box(c, bx, by, bw, bh, 14, P["panel"], P["border"], 2, lift)
            fill = io((t - self.w("loaded", 2.4) - 0.35) / 0.9) * 0.30
            if fill > 0:
                p = skia.Paint(AntiAlias=True)
                p.setShader(skia.GradientShader.MakeLinear([skia.Point(bx, 0), skia.Point(bx + bw * fill, 0)], [col(P["rust"]), col(P["acc"])]))
                c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(bx + 4, by + 4, max(1, bw * fill - 8), bh - 8), 10, 10), p)
                txt(c, "CLAUDE.md", bx + 22, by + 46, P["bg"], clamp(fill / 0.2), 30, "SemiBold")
            for j in range(6):                              # the file's lines drop into the bar
                q = clamp((t - self.w("loaded", 2.4) - j * 0.08) / 0.5)
                if 0 < q < 1:
                    yy = lerp(ey + 140 + j * 44, by + 30, io(q))
                    xx = lerp(ex + 370, bx + 30 + bw * 0.28 * q, io(q))
                    c.drawRect(skia.Rect.MakeXYWH(xx, yy, 200 * (1 - q) + 30, 10), D.paint(col(P["bright"], 0.8 * (1 - q))))

    # ================================================================== S3 CLAUDE.local.md
    LOCAL = ["# Personal notes", "- Sandbox: :3001", "- Use pnpm here"]

    def _local_md(self, c, t):
        ign = self.w("add", 2.8, 0.2)
        typed_echo = clamp((t - ign) / 1.0)
        ignored = t > ign + 1.15
        expl = [("CLAUDE.md", 0, ""), ("CLAUDE.local.md", 0, "ignored" if ignored else "active"), (".gitignore", 0, ""),
                (".mcp.json", 0, ""), (".claude/", 0, "")]
        ex, ey, ew = 50.0, 320.0, 980.0
        rays(c, W / 2, ey + 40, t, 0.6)
        g = editor(c, ex, ey, ew, 520, title="my-project", explorer=expl, tabs=[("CLAUDE.md", False), ("CLAUDE.local.md", True)],
                   lines=self.LOCAL, lang="md", n=typed(self.LOCAL, t, 0.3, 50)[0], t=t, cursor=False, explorer_w=500)
        if ignored:
            r = g["rows"]["CLAUDE.local.md"]
            chip(c, r[0] + 330, r[1] + r[3] / 2, "ignored", P["text2"], io((t - ign - 1.15) / 0.3))
        echo = "$ echo CLAUDE.local.md >> .gitignore"
        term = [("$ git status --short", None), ("?? CLAUDE.local.md", P["bad"])]
        if t > ign:
            term += [(echo, None, int(len(echo) * typed_echo))]
        if t > ign + 1.15:
            term += [("$ git status --short", None), (" M .gitignore", P["ok"])]
        editor(c, ex, 880, ew, 600, title="terminal", term=term, term_h=600 - 52, t=t, cursor=False)

    # ================================================================== S4 .mcp.json
    MCP = ["{", '  "mcpServers": {', '    "github": {', '      "type": "http",',
           '      "url": "https://api.githubcopilot.com/mcp/"', "    }", "  }", "}"]

    def _mcp(self, c, t):
        cut = self.w("GitHub", 2.4, -0.25)
        if t < cut:
            hl = min(4, max(1, int((t - 0.3) / 0.45) + 1))
            rays(c, W / 2, 360, t, 0.7)
            editor(c, 30, 330, 1020, 560, title="my-project", tabs=[(".mcp.json", True)], lines=self.MCP, lang="json", hl=hl, t=t, glow=1)
            return
        # mask reveal into a hub-and-spoke diagram
        k = io((t - cut) / 0.5)
        c.save()
        p = skia.Path(); p.addCircle(W / 2, 860, max(1.0, k * 1400))
        c.clipPath(p, skia.ClipOp.kIntersect, True)
        hub = (W / 2, 860)
        spokes = [("GitHub", "git-branch", (250, 520)), ("Postgres", "database", (830, 520)), ("Jira", "list", (540, 1240))]
        for j, (name, ic, (sx, sy)) in enumerate(spokes):
            kj = io((t - cut - 0.15 - 0.15 * j) / 0.5)
            path = skia.Path(); path.moveTo(*hub); path.lineTo(lerp(hub[0], sx, kj), lerp(hub[1], sy, kj))
            c.drawPath(path, D.paint(col(P["acc"], 0.9), 4))
            if kj >= 1:
                q = ((t - cut) * 0.8 + j * 0.33) % 1.0               # data pulses, both ways
                for qq in (q, 1 - q):
                    c.drawCircle(lerp(hub[0], sx, qq), lerp(hub[1], sy, qq), 9, D.paint(col(P["bright"])))
            wdt = tw(name, 34, "SemiBold") + 110
            box(c, sx - wdt / 2, sy - 50, wdt, 100, 18, P["panel"], P["border"], 2, kj, shadow=True)
            assets.draw_icon(c, ic, sx - wdt / 2 + 44, sy, 34, P["bright"], kj, 2.2)
            txt(c, name, sx - wdt / 2 + 80, sy + 12, P["text"], kj, 34, "SemiBold")
        D.halo(c, hub[0], hub[1], 220, P["acc"], 0.25)
        box(c, hub[0] - 170, hub[1] - 60, 340, 120, 24, P["panel"], P["acc"], 3, 1, shadow=True)
        txt(c, "Claude Code", hub[0], hub[1] + 13, P["text"], 1, 40, "Bold", align="center")
        kt = io((t - self.w("team.", cut + 2.0, -0.4)) / 0.4)
        if kt > 0:
            bx, by = 300.0, 1420.0
            box(c, bx, by - 42, 480, 84, 42, P["panel"], P["acc"], 2, kt)
            for j in range(3):
                c.drawCircle(bx + 50 + j * 40, by, 26, D.paint(col(["#B85C3C", "#D97757", "#F0A07E"][j], kt)))
                c.drawCircle(bx + 50 + j * 40, by, 26, D.paint(col(P["panel"], kt), 3))
                assets.draw_icon(c, "user", bx + 50 + j * 40, by, 26, P["bg"], kt, 2.4)
            txt(c, "shared with team", bx + 170, by + 11, P["text"], kt, 32, "SemiBold")
        c.restore()

    # ================================================================== S5 settings.json
    SET = ["{", '  "permissions": {', '    "deny": ["Bash(rm -rf *)"]', "  }", "}"]

    def _settings(self, c, t):
        stack_t = self.w("settings.local.json", 6.0, -0.2)
        if t < stack_t + 0.4:
            a = 1 - io((t - stack_t) / 0.4)
            n = typed(self.SET, t, 0.5, 40)[0]
            run = self.w("enforced:", 2.4)
            term = []
            if t > run:
                cmd = "$ rm -rf ./build"
                term = [(cmd, None, int(len(cmd) * clamp((t - run) / 0.6)))]
            if t > run + 0.8:
                term.append(("✗ Denied by permissions", P["bad"]))
            expl = [(".claude/", 0, ""), ("settings.json", 1, "active"), ("settings.local.json", 1, ""), ("rules/", 1, ""),
                    ("skills/", 1, ""), ("agents/", 1, "")]
            rays(c, W / 2, 340, t, 0.7 * a)
            self._g = editor(c, 30, 320, 1020, 1000, title="my-project", explorer=expl, tabs=[("settings.json", True)], lines=self.SET,
                             lang="json", n=n, hl=2 if t > 1.6 else None, term=term, term_h=330, a=a, t=t, glow=a, explorer_w=330)
            if t > run + 0.8:
                q = io((t - run - 0.8) / 0.3)
                c.drawRect(skia.Rect.MakeXYWH(32, 1320 - 330 + 70, 1016, 6), D.paint(col(P["bad"], 0.6 * q * a)))
            return
        # precedence, highest first (code.claude.com/docs/en/settings): stacking cards
        txt(c, "Settings precedence, highest first", 60, 400, P["text2"], 1, 32, "SemiBold")
        cards = [("Managed settings", "", P["border"]), ("Command line arguments", "", P["border"]),
                 ("settings.local.json", "personal", P["acc"]), ("settings.json", "project", P["border"]),
                 ("~/.claude/settings.json", "user", P["border"])]
        for j, (name, tag, edge) in enumerate(cards):
            order = [0, 1, 3, 4, 2][j] if False else j
            t_in = stack_t + 0.4 + (0.18 * j if j != 2 else 0.18 * 5 + 0.2)   # the local file slides in last, on its place
            q = io((t - t_in) / 0.45)
            if q <= 0:
                continue
            y = 460 + j * 170
            x = 60 + (1 - q) * (900 if j == 2 else 0)
            yy = y + (1 - q) * (60 if j != 2 else 0)
            box(c, x, yy, 960, 140, 18, P["panel"], edge, 3 if j == 2 else 2, q, shadow=True)
            txt(c, str(j + 1), x + 40, yy + 86, P["text2"], q, 40, "Bold")
            txt(c, name, x + 100, yy + 84, P["text"], q, 34, mono=True)
            if tag:
                chip(c, x + 960 - tw(tag, 30, "Medium") - 70, yy + 72, tag, P["bright"] if j == 2 else P["text2"], q)

    # ================================================================== S6 rules/
    RULE = ["---", "paths:", '  - "src/api/**"', "---", "Validate input at", "every handler."]

    def _rules(self, c, t):
        fan = io((t - 0.2) / 0.8)
        # isometric file stack: two cards fan out
        for j, name in enumerate(("testing.md", "code-style.md")):
            c.save()
            c.translate(330 + fan * (j * 60), 860 - fan * (j * 300))
            c.concat(skia.Matrix.MakeAll(1, -0.18, 0, 0.32, 0.92, 0, 0, 0, 1))
            box(c, -260, -200, 560, 420, 20, P["panel"], P["acc"] if j == 1 else P["border"], 2.5, 1, shadow=True)
            txt(c, name, -220, -140, P["text"], 1, 32, mono=True)
            if j == 1:
                for i, ln in enumerate(self.RULE):
                    code_line(c, ln, -220, -80 + i * 44, "yaml" if i < 4 else "md", None, io((t - 0.6 - 0.12 * i) / 0.3))
            c.restore()
        # mini tree: files under src/api light up on "path"
        lit = io((t - self.w("path.", 2.6, -0.3)) / 0.4)
        files = [("src/", 0, None), ("api/", 1, True), ("users.ts", 2, True), ("orders.ts", 2, True), ("web/", 1, False), ("app.tsx", 2, False)]
        x0, y0 = 660.0, 1000.0
        box(c, x0 - 30, y0 - 70, 400, 380, 18, P["panel"], P["border"], 2, fan)
        for i, (nm, d, on) in enumerate(files):
            y = y0 + i * 52
            colr = P["bright"] if on and lit > 0.5 else (P["text"] if on is None else P["text2"])
            assets.draw_icon(c, "folder" if nm.endswith("/") else "file-text", x0 + d * 26 + 12, y - 10, 26,
                             P["bright"] if on and lit > 0.5 else P["text2"], fan, 2)
            txt(c, nm, x0 + d * 26 + 36, y, colr, fan, mono=True)
            if on and lit > 0:
                D.halo(c, x0 + d * 26 + 120, y - 10, 90, P["acc"], 0.25 * lit)

    # ================================================================== S7 skills/
    SKILL = ["---", "name: review", "description: Reviews the diff", "  for bugs and style", "---"]

    def _skills(self, c, t):
        slash = 0.35
        open_t = slash + 0.3
        pick = self.at(self.sp.get("pick_at"), 3.2)
        push = self.at(self.sp.get("push_at"), 4.5)
        flip = self.at(self.sp.get("flip_at"), 7.0)
        if t < push:
            items = [("/review", "Reviews the diff for bugs and style"), ("/fix-issue", "Fixes an issue by number")]
            term = [("$ claude", None), ("> /" + ("review" if t > pick else ""), P["text"])]
            g = editor(c, 30, 330, 1020, 900, title="terminal", term=term, term_h=900 - 52, t=t, cursor=False)
            if t > open_t:
                q = io((t - open_t) / 0.3)
                mx, my = 70.0, 330 + 52 + 92 + LHC + 30
                box(c, mx, my, 940, 2 * 110 + 20, 16, "#1E1C1A", P["border"], 2, q, shadow=True)
                sel = 0
                for j, (nm, desc) in enumerate(items):
                    yy = my + 10 + j * 110
                    if j == sel and t > pick - 0.5:
                        box(c, mx + 8, yy, 924, 100, 12, "#2A2018", P["acc"], 2, q)
                    txt(c, nm, mx + 30, yy + 44, P["bright"] if j == sel else P["text"], q, 32, mono=True)
                    txt(c, desc, mx + 30, yy + 84, P["text2"], q, 30)
            return
        if t < flip:
            k = io((t - push) / 0.6)
            n = typed(self.SKILL, t, push + 0.4, 40)[0]
            expl = [("skills/", 0, ""), ("review/", 1, "lit"), ("SKILL.md", 2, "active"), ("fix-issue/", 1, ""), ("commands/", 0, "dim")]
            rays(c, W / 2, 340, t, 0.7 * k)
            c.save()
            s = lerp(0.8, 1.0, k)
            c.translate(W / 2, 800); c.scale(s, s); c.translate(-W / 2, -800)
            editor(c, 30, 330, 1020, 700, title="my-project", explorer=expl, tabs=[("SKILL.md", True)], lines=self.SKILL, lang="yaml",
                   n=n, a=k, t=t, glow=k, explorer_w=320)
            c.restore()
            return
        # a card flip: commands/ -> the older single-file form, tagged legacy
        q = clamp((t - flip) / 0.7)
        ang = io(q) * math.pi
        sx = abs(math.cos(ang))
        front = ang < math.pi / 2
        c.save()
        c.translate(W / 2, 880); c.scale(max(0.02, sx), 1)
        box(c, -420, -230, 840, 460, 26, P["panel"], P["acc"], 3, 1, shadow=True)
        if front:
            assets.draw_icon(c, "folder", -300, -60, 80, P["bright"], 1, 2)
            txt(c, "commands/", -220, -40, P["text"], 1, 52, mono=True)
            txt(c, "deploy.md", -220, 40, P["text2"], 1, 34, mono=True)
        else:
            txt(c, "commands/", -360, -110, P["bright"], 1, 40, mono=True)
            txt(c, "Older single-file form", -360, -20, P["text"], 1, 40, "SemiBold")
            txt(c, "of skills. Same /name.", -360, 40, P["text"], 1, 40, "SemiBold")
            chip(c, -360, 130, "legacy", P["bright"], clamp((q - 0.6) / 0.3), icon="clock")
        c.restore()

    # ================================================================== S8 agents/
    def _agents(self, c, t):
        main = (W / 2, 470)
        subs = [("code-reviewer", (290, 900), ["Read", "Grep", "Glob"]), ("security-auditor", (790, 900), ["Read", "Grep", "Bash"])]
        box(c, main[0] - 210, main[1] - 60, 420, 120, 24, P["panel"], P["acc"], 3, 1, shadow=True)
        D.halo(c, main[0], main[1], 200, P["acc"], 0.18)
        txt(c, "Main session", main[0], main[1] + 13, P["text"], 1, 38, "Bold", align="center")
        for j, (nm, (sx, sy), tools) in enumerate(subs):
            k = io((t - 0.15 - 0.15 * j) / 0.5)
            p = skia.Path(); p.moveTo(main[0], main[1] + 60); p.lineTo(lerp(main[0], sx, k), lerp(main[1] + 60, sy - 70, k))
            c.drawPath(p, D.paint(col(P["acc"], 0.9), 4))
            box(c, sx - 230, sy - 70, 460, 140, 22, P["panel"], P["border"], 2, k, shadow=True)
            prog = clamp((t - 0.6) / 1.4)
            c.drawArc(skia.Rect.MakeXYWH(sx - 205, sy - 30, 60, 60), -90, 360 * prog, False, D.paint(col(P["bright"], k), 6))
            c.drawCircle(sx - 175, sy, 30, D.paint(col(P["border"], 0.6 * k), 6))
            txt(c, nm, sx - 125, sy + 11, P["text"], k, 32, mono=True)
            for i, tl in enumerate(tools):
                ki = io((t - 0.45 - 0.1 * i - 0.15 * j) / 0.3)
                chip(c, sx - 230 + i * 155, sy + 130, tl, P["bright"], ki, fill="#1E1C1A")
            back = io((t - 1.9 - 0.1 * j) / 0.5)
            if back > 0:
                q = skia.Path(); q.moveTo(sx + (60 if j == 0 else -60), sy - 70)
                q.lineTo(lerp(sx, main[0] + (-90 if j == 0 else 90), back), lerp(sy - 70, main[1] + 60, back))
                c.drawPath(q, D.paint(col(P["ok"], 0.95), 4))
                if back > 0.95:
                    D.arrowhead(c, main[0] + (-90 if j == 0 else 90), main[1] + 62, (main[0] - sx) * 0.002, -1, 18, col(P["ok"]))
        if t > 2.1:
            chip(c, W / 2 - 110, 640, "summary", P["ok"], io((t - 2.1) / 0.3))

    # ================================================================== S9 hooks
    SCRIPT = ["CMD=$(jq -r '.tool_input.command')", "if echo \"$CMD\" | grep -q 'rm -rf'", "then deny; else exit 0; fi"]

    def _hooks(self, c, t):
        y = 560.0
        st = [("PreToolUse", 180.0), ("tool runs", 540.0), ("PostToolUse", 900.0)]
        c.drawLine(80, y, 1000, y, D.paint(col(P["border"]), 6))
        for nm, x in st:
            c.drawCircle(x, y, 18, D.paint(col(P["acc"] if nm == "PreToolUse" else P["text2"])))
            txt(c, nm, x, y - 44, P["text"], 1, 32, "SemiBold" if nm != "tool runs" else "Regular", mono=nm != "tool runs", align="center")
        blk = self.w("block", 2.8)
        # call 1: rm -rf, stops at PreToolUse
        q1 = io((t - 0.2) / max(0.4, blk - 0.9 - 0.2))
        x1 = lerp(60, 180, q1)
        chip(c, x1 - 40, y + 70, "Bash: rm -rf build", P["bad"] if t > blk else P["text"], 1)
        # the hook script in a mini terminal
        k = io((t - 0.7) / 0.4)
        box(c, 60, 760, 960, 280, 16, "#100F0E", P["border"], 2, k, shadow=True)
        txt(c, "validate-bash.sh", 90, 812, P["text2"], k, 30, mono=True)
        n = typed(self.SCRIPT, t, 0.9, 60)[0]
        for i, ln in enumerate(self.SCRIPT):
            code_line(c, ln[:34] if len(ln) > 34 else ln, 90, 870 + i * LHC, "sh", min(n[i], 34), k)
        # BLOCK stamp
        if t > blk:
            q = clamp((t - blk) / 0.22)
            s = lerp(2.4, 1.0, ease_out(q))
            c.save(); c.translate(640, 690); c.rotate(-8); c.scale(s, s)
            box(c, -150, -56, 300, 112, 14, None, P["bad"], 7, q)
            txt(c, "BLOCK", 0, 24, P["bad"], q, 70, "Bold", align="center")
            c.restore()
        # call 2: a safe one passes
        t2 = blk + 0.9
        if t > t2:
            q2 = io((t - t2) / 1.2)
            x2 = lerp(60, 940, q2)
            chip(c, x2 - 80, y + 150, "Bash: npm test", P["ok"], 1)
            if q2 > 0.98:
                assets.draw_icon(c, "circle-check", 1000, y + 150, 44, P["ok"], 1, 2.6)

    def shake(self, t):
        blk = self.w("block", 2.8)
        if self.kind == "hooks" and 0 < t - blk < 0.3:
            a = (1 - (t - blk) / 0.3) * 10
            return a * math.sin((t - blk) * 90), a * math.cos((t - blk) * 70)
        return 0.0, 0.0

    # ================================================================== S10 takeaway + the full diagram
    def _takeaway(self, c, t):
        wipe_at = self.w("Start", 3.0, -0.35)
        if t < wipe_at + 0.5:
            for j, (head, sub, ic, solid) in enumerate((("Guidance", "CLAUDE.md", "file-text", False),
                                                        ("Enforced", "settings + hooks", "lock", True))):
                k = io((t - 0.1 - (self.w("Settings", 1.4) - 0.3 if j else 0)) / 0.45)
                x = 40 + j * 520
                box(c, x, 420, 480, 760, 24, P["panel"], P["acc"] if solid else P["border"], 3 if solid else 2, k, shadow=True)
                if not solid:
                    D.halo(c, x + 240, 700, 220, P["bright"], 0.22 * k * (0.75 + 0.25 * math.sin(t * 3)))
                else:
                    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x + 150, 600, 180, 180), 30, 30), D.paint(col(P["acc"], k)))
                assets.draw_icon(c, ic, x + 240, 690, 110, P["bg"] if solid else P["bright"], k, 2.6 if solid else 2)
                txt(c, head, x + 240, 900, P["text"], k, 52, "Bold", align="center")
                txt(c, sub, x + 240, 970, P["bright"], k, 34, mono=True, align="center")
            return
        self.diagram(c, t)

    def diagram(self, c, t):
        from .tree import Tree
        from types import SimpleNamespace
        if self._diagram is None:
            spec = dict(self.sp["diagram"])
            all_rows = [r["id"] for r in spec["tree"]]
            spec.update(done=all_rows, build=[], phase="recap", no_title=True,
                        recap={"keep": spec.get("keep", []), "dim_at": 0.0, "all_at": 0.0})   # all lit; kept rows glow
            shim = SimpleNamespace(sc=SimpleNamespace(spec=spec, dur=self.dur), tpl=self.ms.tpl, cue_t=lambda at, d=0.0: d if at is None else (float(at) if isinstance(at, (int, float)) else self.ms.cue_t(at, d)))
            self._diagram = Tree(shim)
        k = io((t - self.w("Start", 3.0, 0.2)) / 0.6)
        self._diagram.draw(c, t)
        if k < 1:
            c.drawRect(skia.Rect.MakeWH(W, H), D.paint(col(P["bg"], 1 - k)))


def make(ms):
    return Scene(ms)
