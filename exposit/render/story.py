"""Clean diagram scenes for "What happens when you type claude?" (dev_scene kinds st_*): no editor UI, big shapes on
black (claude-orange-dark). The story: `$ claude`, a stack of files is read into context, then each file's job.
Bound onto devscenes.Scene like ide.SCENES. Labels >= 30 px, key text between y 230 and 1530.
"""
from __future__ import annotations
import math
import skia
from . import assets, design as D
from .design import col, clamp, lerp, ease_out, spring
from .devscenes import P, W, H, txt, tw, box, io, typed, chip, CW

STACK = ["CLAUDE.md", "CLAUDE.local.md", "settings.json", ".mcp.json", "skills/", "agents/"]
SX, SW, SH, STEP = 540.0, 620.0, 92.0, 22.0          # the context stack: centre x, card size, step between cards
STACK_BOTTOM = 1260.0


def file_card(c, x, y, w, h, name, a=1.0, hl=0.0, sub=None, size=36):
    """A file card: rounded panel, file icon, mono name; hl adds the orange edge and glow."""
    if hl > 0:
        D.halo(c, x + w / 2, y + h / 2, max(w, h) * 0.6, P["acc"], 0.18 * hl * a)
    box(c, x, y, w, h, 16, P["panel"], D.mix(P["border"], P["acc"], hl), 2.5, a, shadow=True)
    ic = "folder" if name.endswith("/") else "file-text"
    assets.draw_icon(c, ic, x + 44, y + h / 2, 34, P["bright"], a, 2)
    txt(c, name, x + 80, y + h / 2 + size * 0.36, P["text"], a, size, mono=True)
    if sub:
        txt(c, sub, x + w - 24, y + h / 2 + 11, P["text2"], a, 30, align="right")


def stack_pos(i, n=len(STACK)):
    """Card i of the stack (0 = top): the stack grows upward from STACK_BOTTOM."""
    return SX - SW / 2, STACK_BOTTOM - SH - (n - 1 - i) * (SH + STEP)


def draw_stack(c, t, t0=0.0, a=1.0, upto=None, label=True, skip=()):
    n = len(STACK)
    if label:
        txt(c, "Context", SX, stack_pos(0)[1] - 34, P["text2"], a * io((t - t0) / 0.4), 34, "SemiBold", align="center")
    for j in range(n - 1, -1, -1):                     # the bottom card lands first
        if STACK[j] in skip:
            continue
        order = n - 1 - j
        k = io((t - t0 - 0.1 * order) / 0.35) if upto is None else 1.0
        if k <= 0:
            continue
        x, y = stack_pos(j)
        yy = lerp(-200, y, k)
        file_card(c, x, yy, SW, SH, STACK[j], a)
        if k >= 1 and 0 <= t - t0 - 0.1 * order - 0.35 < 0.15:     # a small landing bump
            c.drawLine(x + 30, y + SH + 6, x + SW - 30, y + SH + 6, D.paint(col(P["acc"], 0.6 * a), 3))


# ------------------------------------------------------------------ S1
def st_hook(self, c, t):
    fall = self.w("stack", 3.4, -0.45)
    up = io((t - fall + 0.3) / 0.6)
    y = lerp(960, 420, up)
    n = int(len("claude") * clamp((t - 0.3) / 0.5))
    f = D.make_font(72, "Regular", mono=True)
    s = "$ " + "claude"[:n]
    wdt = f.measureText("$ claude")
    x0 = W / 2 - wdt / 2
    D.put_text(c, "$", x0, y, f, col(P["acc"]))
    D.put_text(c, "claude"[:n], x0 + f.measureText("$ "), y, f, col(P["text"]))
    cx = x0 + f.measureText(s) + 6
    if t < 1.0 or int(t * 2.4) % 2 == 0:
        c.drawRect(skia.Rect.MakeXYWH(cx, y - 56, 34, 66), D.paint(col(P["acc"])))
    enter = 1.0
    if t > enter:                                       # Enter: an orange pulse ripples out
        for j in range(3):
            q = (t - enter - 0.18 * j) / 1.1
            if 0 < q < 1:
                c.drawCircle(W / 2, y - 20, 60 + 520 * ease_out(q), D.paint(col(P["acc"], 0.55 * (1 - q)), 4))
    if t > fall:
        draw_stack(c, t, fall)


# ------------------------------------------------------------------ S2
MD = ["## Commands", "npm test, npm run build", "## Stack", "TypeScript, Node 20", "## Conventions", "small, focused PRs"]


def st_claude_md(self, c, t):
    grow = io(t / 0.7)                                  # match cut: the top card of the stack becomes the document
    x0, y0 = stack_pos(0)
    dx, dy, dw, dh = 110.0, 360.0, 860.0, 560.0
    x, y, w, h = lerp(x0, dx, grow), lerp(y0, dy, grow), lerp(SW, dw, grow), lerp(SH, dh, grow)
    if grow < 1:
        draw_stack(c, 99, 0, 1 - grow, skip=("CLAUDE.md",), label=False)
    D.halo(c, x + w / 2, y + h / 2, 520, P["acc"], 0.14 * grow)
    box(c, x, y, w, h, 22, P["panel"], P["acc"], 3, 1, shadow=True)
    assets.draw_icon(c, "file-text", x + 50, y + 56, 40, P["bright"], 1, 2)
    txt(c, "CLAUDE.md", x + 90, y + 70, P["text"], 1, 44, mono=True)
    if grow >= 1:
        c.drawLine(x + 30, y + 110, x + w - 30, y + 110, D.paint(col(P["border"]), 2))
        n = typed(MD, t, 0.8, 40)[0]
        for i, ln in enumerate(MD):
            if n[i] <= 0:
                continue
            head = ln.startswith("#")
            txt(c, ln[: int(n[i])], x + 50, y + 176 + i * 62, P["key"] if head else P["text"], 1, 36 if head else 34, mono=True)
    # every session: the same card loads into session 1, 2, 3
    ks = self.w("every", 3.0, -0.1)
    if t > ks:
        for j in range(3):
            q = io((t - ks - 0.22 * j) / 0.35)
            if q <= 0:
                continue
            sx = 210 + j * 330
            box(c, sx - 140, 1060, 280, 230, 20, P["panel"], P["border"], 2, q, shadow=True)
            txt(c, f"Session {j + 1}", sx, 1110, P["text2"], q, 32, "SemiBold", align="center")
            mini_y = lerp(960, 1160, io((t - ks - 0.22 * j - 0.1) / 0.35))
            box(c, sx - 110, mini_y, 220, 70, 12, "#2A2018", P["acc"], 2, q)
            txt(c, "CLAUDE.md", sx, mini_y + 46, P["text"], q, 30, mono=True, align="center")
        loop = io((t - ks) / 0.9)                       # a looping arrow under the sessions
        p = skia.Path()
        p.addArc(skia.Rect.MakeXYWH(150, 1320, 780, 120), 200, 140 * loop)
        c.drawPath(p, D.paint(col(P["acc"], 0.9), 4))
        if loop >= 1:
            D.arrowhead(c, 930 - 10, 1370, 0.2, -1, 18, col(P["acc"]))


# ------------------------------------------------------------------ S3
def st_local(self, c, t):
    k = io(t / 0.6)
    # CLAUDE.md steps back, CLAUDE.local.md slides out from behind it
    box(c, 110, 360, 560, 400, 22, P["panel"], P["border"], 2, 1 - 0.45 * k, shadow=True)
    txt(c, "CLAUDE.md", 160, 430, P["text2"], 1 - 0.45 * k, 40, mono=True)
    lx = lerp(110, 410, k)
    box(c, lx, 520, 560, 400, 22, P["panel"], P["acc"], 3, 1, shadow=True)
    assets.draw_icon(c, "file-text", lx + 50, 580, 40, P["bright"], 1, 2)
    txt(c, "CLAUDE.local.md", lx + 88, 594, P["text"], 1, 40, mono=True)
    for i, ln in enumerate(("my sandbox URL", "my shortcuts")):
        txt(c, "- " + ln, lx + 50, 680 + i * 56, P["text2"], io((t - 0.6 - 0.2 * i) / 0.3), 34, mono=True)
    # git tries to grab it and bounces off the .gitignore shield
    tg = self.w("git", 2.4, -0.6)
    shield = io((t - tg) / 0.4)
    sx, sy = lx + 280, 1060
    if shield > 0:
        D.halo(c, sx, sy, 160, P["ok"], 0.15 * shield)
        assets.draw_icon(c, "shield", sx, sy, 130, P["ok"], shield, 2.2)
        txt(c, "gitignored", sx, sy + 120, P["ok"], shield, 34, "SemiBold", align="center")
    q = clamp((t - tg - 0.3) / 1.4)
    if q > 0:
        gx = lerp(110, sx - 170, ease_out(min(1.0, q * 2)))
        if q > 0.5:
            gx = lerp(sx - 170, 140, io((q - 0.5) / 0.5))
        c.drawCircle(gx, 1320, 56, D.paint(col(P["panel"])))
        c.drawCircle(gx, 1320, 56, D.paint(col(P["bad"] if q > 0.5 else P["text2"]), 3))
        assets.draw_icon(c, "git-branch", gx, 1320, 46, P["text"], 1, 2.2)
        txt(c, "git", gx, 1420, P["text2"], 1, 32, "SemiBold", align="center")


# ------------------------------------------------------------------ S4
def st_gate(self, c, t):
    gy, gx = 860.0, 540.0
    # the gate: two posts and a bar, settings.json under it
    for px in (gx - 230, gx + 230):
        box(c, px - 22, gy - 170, 44, 340, 10, P["panel"], P["acc"], 3, 1, shadow=True)
    c.drawRect(skia.Rect.MakeXYWH(gx - 230, gy - 180, 460, 16), D.paint(col(P["acc"])))
    box(c, 150, 1120, 780, 170, 18, "#131211", P["border"], 2, 1, shadow=True)
    txt(c, ".claude/settings.json", 180, 1170, P["text2"], 1, 30, mono=True)
    txt(c, '"deny": ["Bash(rm -rf *)"]', 180, 1240, P["string"], 1, 34, mono=True)
    calls = [("npm test", 0.4, True), ("git push", 1.4, True), ("rm -rf build", self.w("run,", 3.6, -0.6), False)]
    for name, t0, ok in calls:
        q = clamp((t - t0) / 1.6)
        if q <= 0:
            continue
        lane = gy + (-60 if ok else 60)
        if ok:
            x = lerp(-40, 1120, io(q))
            colr = P["ok"] if x > gx else P["text"]
        else:
            x = lerp(-40, gx - 330, io(min(1.0, q * 1.6)))
            colr = P["bad"] if q > 0.62 else P["text"]
        wdt = tw(name, 32, "Medium") + 40
        chip(c, x - wdt / 2, lane, name, colr, 1, fill=P["panel"])
        if not ok and q > 0.62:
            qq = io((q - 0.62) / 0.2)
            txt(c, "✗ denied", gx - 330, lane + 80, P["bad"], qq, 34, "SemiBold", align="center")


# ------------------------------------------------------------------ S6
def st_skills_agents(self, c, t):
    # shelf 1: skills (closed tiles, name + description; one opens on "only when it's needed")
    txt(c, "Skills", 70, 380, P["text2"], 1, 36, "SemiBold")
    c.drawLine(60, 860, 1020, 860, D.paint(col(P["border"]), 4))
    open_t = self.w("only", 2.8, -0.1)
    tiles = [("/review", "Reviews the diff"), ("/fix-issue", "Fixes an issue")]
    for j, (nm, desc) in enumerate(tiles):
        k = io((t - 0.1 - 0.15 * j) / 0.45)
        x = 70 + j * 480
        opened = j == 0 and t > open_t
        if opened:
            q = io((t - open_t) / 0.5)
            hh = lerp(190, 430, q)
            box(c, x, 840 - hh, lerp(440, 900, q), hh, 18, P["panel"], P["acc"], 3, k, shadow=True)
            txt(c, nm + "/SKILL.md", x + 30, 840 - hh + 56, P["bright"], k, 34, mono=True)
            body = ["description: Reviews the diff", "1. Read the changed files", "2. Check style and tests"]
            for i, ln in enumerate(body):
                txt(c, ln, x + 30, 840 - hh + 118 + i * 52, P["text"], clamp((q - 0.4 - 0.15 * i) / 0.3), 32, mono=True)
        elif not (j == 1 and t > open_t + 0.1):
            box(c, x, 650, 440, 190, 18, P["panel"], P["border"], 2, k, shadow=True)
            assets.draw_icon(c, "folder", x + 50, 710, 40, P["bright"], k, 2)
            txt(c, nm, x + 88, 724, P["text"], k, 36, mono=True)
            txt(c, desc, x + 30, 800, P["text2"], k, 32)
    # shelf 2: agents, each in its own sealed context
    txt(c, "Agents", 70, 960, P["text2"], 1, 36, "SemiBold")
    main = (540.0, 1040.0)
    box(c, main[0] - 170, main[1] - 46, 340, 92, 22, P["panel"], P["acc"], 3, 1, shadow=True)
    txt(c, "Main session", main[0], main[1] + 12, P["text"], 1, 34, "Bold", align="center")
    ta = self.w("agent", 4.0, -0.2)
    for j, (nm, bx) in enumerate((("code-reviewer", 290.0), ("security-auditor", 790.0))):
        k = io((t - ta - 0.15 * j) / 0.5)
        if k <= 0:
            continue
        by = 1330.0
        p = skia.Path(); p.moveTo(main[0], main[1] + 46); p.lineTo(lerp(main[0], bx, k), lerp(main[1] + 46, by - 120, k))
        c.drawPath(p, D.paint(col(P["acc"], 0.9), 4))
        c.drawCircle(bx, by, 120 * k, D.paint(col(P["panel"])))
        c.drawCircle(bx, by, 120 * k, D.paint(col(P["bright"], k), 3))
        txt(c, nm, bx, by + 8, P["text"], k, 30, mono=True, align="center")
        txt(c, "own context", bx, by + 52, P["bright"], k, 30, "SemiBold", align="center")
        back = io((t - ta - 1.0 - 0.1 * j) / 0.5)
        if back > 0:
            q = skia.Path(); q.moveTo(bx + (70 if j == 0 else -70), by - 100)
            q.lineTo(lerp(bx, main[0] + (-110 if j == 0 else 110), back), lerp(by - 100, main[1] + 50, back))
            c.drawPath(q, D.paint(col(P["ok"]), 4))
    if t > ta + 1.5:
        chip(c, main[0] - 80, 1190, "summary", P["ok"], io((t - ta - 1.5) / 0.3), fill=P["bg"])


# ------------------------------------------------------------------ S7
def st_rules(self, c, t):
    files = [("src/", 0, None), ("components/", 1, None), ("Button.tsx", 2, "btn"), ("api/", 1, None), ("users.ts", 2, "api")]
    x0, y0 = 80.0, 470.0
    t_btn, t_api = 0.4, self.w("reads", 1.8, -0.1)
    box(c, 50, 380, 430, 420, 18, P["panel"], P["border"], 2, 1, shadow=True)
    rows = {}
    for i, (nm, d, tag) in enumerate(files):
        y = y0 + i * 66
        active = (tag == "btn" and t_btn < t < t_api) or (tag == "api" and t >= t_api)
        if active:
            box(c, 60, y - 40, 410, 58, 10, "#2A2018", P["acc"], 2, 1)
        assets.draw_icon(c, "folder" if nm.endswith("/") else "file-text", x0 + d * 30 + 14, y - 11, 28, P["bright"] if active else P["text2"], 1, 2)
        txt(c, nm, x0 + d * 30 + 40, y, P["text"], 1, 32, mono=True)
        rows[tag] = (x0 + d * 30 + 40 + tw(nm, mono=True), y)
    # a cursor moves to Button.tsx, then users.ts
    tgt = rows["btn"] if t < t_api else rows["api"]
    prev = (700.0, 1300.0) if t < t_api else rows["btn"]
    q = io((t - (t_btn - 0.3 if t < t_api else t_api - 0.3)) / 0.4)
    cx, cy = lerp(prev[0], tgt[0] + 10, q), lerp(prev[1], tgt[1] - 6, q)
    p = skia.Path(); p.moveTo(cx, cy); p.lineTo(cx, cy + 40); p.lineTo(cx + 12, cy + 30); p.lineTo(cx + 26, cy + 52)
    p.lineTo(cx + 33, cy + 48); p.lineTo(cx + 20, cy + 26); p.lineTo(cx + 36, cy + 24); p.close()
    c.drawPath(p, D.paint(col(P["text"])))
    # the rule card: asleep (dim) on Button.tsx, awake on users.ts, then into the context stack
    awake = io((t - t_api - 0.2) / 0.4)
    into = io((t - t_api - 0.5) / 0.45)
    rx, ry = lerp(520, 300, into), lerp(380, 1200, into)
    a = 0.45 + 0.55 * awake
    box(c, rx, ry, 510, 420 - 340 * into, 18, P["panel"], D.mix(P["border"], P["acc"], awake), 3, 1, shadow=True)
    txt(c, "api-rules.md", rx + 30, ry + lerp(56, 52, into), P["bright"] if awake > 0.5 else P["text2"], 1, 34, mono=True)
    if into < 0.6:
        for i, ln in enumerate(("---", "paths:", '  - "src/api/**"', "---", "Validate every input.")):
            txt(c, ln, rx + 30, ry + 120 + i * 50, P["key"] if ln.strip().startswith("paths") else P["text"], a * (1 - into / 0.6), 32, mono=True)
    if t_btn < t < t_api and t > t_btn + 0.3:
        txt(c, "not loaded", rx + 480, ry + 56, P["text2"], 1, 30, align="right")
    if awake > 0 and into < 0.6:
        txt(c, "loaded", rx + 480, ry + 56, P["ok"], awake * (1 - into / 0.6), 30, "SemiBold", align="right")
    if into > 0:                                       # the context stack it joins
        txt(c, "Context", 555, 1170, P["text2"], into, 32, "SemiBold", align="center")
        file_card(c, 300, 1300, 510, 80, "CLAUDE.md", into, size=32)
        file_card(c, 300, 1396, 510, 80, "settings.json", into, size=32)


# ------------------------------------------------------------------ S9
def st_payoff(self, c, t):
    wipe_at = self.at(self.sp.get("diagram_at"), self.dur - 3.9)
    if t > wipe_at + 0.45:
        return self.diagram(c, t)
    for j, (head, sub, ic, solid, word) in enumerate((("GUIDES", "CLAUDE.md", "book-open", False, "guides."),
                                                      ("ENFORCES", "settings + hooks", "lock", True, "enforce."))):
        k = io((t - (0.05 if j == 0 else self.w(word, 1.0 + j, -0.25))) / 0.4)   # GUIDES is on screen at once
        x = 40 + j * 520
        box(c, x, 430, 480, 720, 24, P["panel"], P["acc"] if solid else P["border"], 3 if solid else 2, k, shadow=True)
        if not solid:
            D.halo(c, x + 240, 700, 220, P["bright"], 0.22 * k * (0.75 + 0.25 * math.sin(t * 3)))
        else:
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x + 150, 600, 180, 180), 30, 30), D.paint(col(P["acc"], k)))
        assets.draw_icon(c, ic, x + 240, 690, 110, P["bg"] if solid else P["bright"], k, 2.6 if solid else 2)
        s = 0.7 + 0.3 * spring(clamp((t - self.w(word, 1.0 + j, -0.25)) / 0.35))
        c.save(); c.translate(x + 240, 900); c.scale(s, s)
        txt(c, head, 0, 0, P["text"], k, 56, "Bold", align="center")
        c.restore()
        txt(c, sub, x + 240, 970, P["bright"], k, 34, mono=True, align="center")


SCENES = dict(st_hook=st_hook, st_claude_md=st_claude_md, st_local=st_local, st_gate=st_gate,
              st_skills_agents=st_skills_agents, st_rules=st_rules, st_payoff=st_payoff)
