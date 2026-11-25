"""A generic modern dark code editor for the dev_scene effect (no app logo, no product name, no brand): title bar with
back/forward arrows, a centred search box and window controls; a 56 px activity bar; an explorer with chevrons,
file-type colour icons, "U" for untracked and dimmed ignored files; tabs (an italic preview tab, a close "x"),
breadcrumbs, line numbers, current-line highlight, a minimap; a bottom panel with PROBLEMS / OUTPUT / TERMINAL and a
PowerShell-style prompt with a block cursor; a terracotta status bar.

Everything is drawn at 30 px or more in the 1080x1920 space between y 236 and 1524, so a crop or push-in only ever
enlarges it. Scenes for the IDE kinds (ide_hook, ide_claude_md, ide_local, ide_settings, ide_skills, ide_hooks) and
the takeaway cards (takeaway_step) are at the bottom; they are methods bound onto devscenes.Scene.
"""
from __future__ import annotations
import math
import skia
from . import assets, design as D
from .design import col, clamp, lerp, ease_out, spring
from .devscenes import P, W, H, txt, tw, box, io, typed, pop, chip, CW

I = dict(editor="#1F1F1F", side="#181818", border="#2B2B2B", text="#CCCCCC", dim="#8B8B8B", text2="#9D9D9D",
         line="#262626", sel="#37373D", key="#4FC1FF", string="#CE9178", comment="#6A9955", punct="#CCCCCC",
         acc="#D97757", glow="#F0A07E", status="#D97757", status_text="#1A1918", untracked="#73C991", modified="#E2C08D",
         err="#F14C4C", ok="#73C991")
# status-bar text: cream on #D97757 measures 2.8:1, so the bar keeps its colour and uses dark text (5.6:1)
FILE_ICON = {"md": "#7E9CA8", "json": "#CBCB41", "sh": "#89E051", "ts": "#4FC1FF", "": "#9D9D9D"}
Y0, Y1 = 236.0, 1524.0
TITLE_H, STATUS_H, ACT_W = 60.0, 46.0, 56.0
ROW = 46.0
LH = 46.0


def tokens(line, lang):
    import re
    if lang == "md":
        if line.startswith("#"):
            return [(line, I["key"])]
        if line.startswith("- "):
            return [("- ", I["dim"]), (line[2:], I["text"])]
        if line.startswith("@"):
            return [(line, I["string"])]
        return [(line, I["text"])]
    if lang == "json":
        out, i = [], 0
        for m in re.finditer(r'"[^"]*"|[{}\[\],:]', line):
            if m.start() > i:
                out.append((line[i:m.start()], I["text"]))
            s = m.group()
            if s.startswith('"'):
                out.append((s, I["key"] if line[m.end():].lstrip().startswith(":") else I["string"]))
            else:
                out.append((s, I["punct"]))
            i = m.end()
        out.append((line[i:], I["text"]))
        return out
    if lang == "yaml":
        if line.strip() == "---":
            return [(line, I["dim"])]
        m = re.match(r"(\s*)([\w-]+)(:)(.*)", line)
        if m:
            return [(m.group(1), I["text"]), (m.group(2), I["key"]), (":", I["punct"]), (m.group(4), I["string"])]
        return [(line, I["text"])]
    if lang == "sh":
        if line.lstrip().startswith("#"):
            return [(line, I["comment"])]
        out = []
        for part in re.split(r"('[^']*'|\"[^\"]*\")", line):
            out.append((part, I["string"] if part[:1] in "'\"" else I["text"]))
        return out
    return [(line, I["text"])]


def code(c, line, x, y, lang, n=None, a=1.0, color=None):
    left = len(line) if n is None else max(0, int(n))
    for s, colr in tokens(line, lang):
        if left <= 0:
            break
        part = s[:left]
        txt(c, part, x, y, color or colr, a, mono=True)
        x += len(part) * CW
        left -= len(part)
    return x


def ftype(name):
    return name.rsplit(".", 1)[-1] if "." in name.lstrip(".") else ("json" if name.endswith(".json") else "")


def ide(c, t, *, explorer=None, ex_w=330.0, tabs=(), crumbs=(), lines=(), lang="md", n=None, cur=None, hl=None,
        panel=None, panel_h=360.0, status_lang="Markdown", a=1.0, glow=0.0, git_badge=2, under=None, prompt_cursor=True,
        prompt="PS C:\\my-project> ", typed_cmd=None):
    """Draws the editor window across the full width; returns geometry (rows, code origin, terminal origin)."""
    g = {"rows": {}}
    if glow > 0:
        D.halo(c, W / 2, (Y0 + Y1) / 2, 760, P["acc"], 0.16 * glow * a)
    box(c, 0, Y0, W, Y1 - Y0, 14, I["editor"], I["border"], 2, a, shadow=True)
    # title bar: back/forward, a centred search box, window controls (no logo, no product name)
    c.drawRect(skia.Rect.MakeXYWH(0, Y0, W, TITLE_H), D.paint(col(I["side"], a)))
    assets.draw_icon(c, "arrow-left", 40, Y0 + 30, 28, I["dim"], a, 2)
    assets.draw_icon(c, "arrow-right", 84, Y0 + 30, 28, I["dim"], a, 2)
    box(c, 300, Y0 + 10, 480, 42, 10, "#242424", I["border"], 2, a)
    assets.draw_icon(c, "search", 330, Y0 + 31, 24, I["dim"], a, 2)
    txt(c, "my-project", 540, Y0 + 42, I["text"], a, 30, align="center")
    for i, ic in enumerate(("minus", "square", "x")):
        assets.draw_icon(c, ic, W - 150 + i * 50, Y0 + 30, 24, I["dim"], a, 2)
    c.drawLine(0, Y0 + TITLE_H, W, Y0 + TITLE_H, D.paint(col(I["border"], a), 2))
    top = Y0 + TITLE_H
    bottom = Y1 - STATUS_H
    # activity bar
    c.drawRect(skia.Rect.MakeXYWH(0, top, ACT_W, bottom - top), D.paint(col(I["side"], a)))
    for i, ic in enumerate(("files", "search", "git-branch", "play", "blocks", "flask-conical")):
        y = top + 40 + i * 64
        active = i == 0
        if active:
            c.drawRect(skia.Rect.MakeXYWH(0, y - 26, 2, 52), D.paint(col(I["acc"], a)))
        assets.draw_icon(c, ic, ACT_W / 2, y, 30, I["text"] if active else I["dim"], a, 2)
        if ic == "git-branch" and git_badge:
            c.drawCircle(ACT_W / 2 + 13, y + 12, 12, D.paint(col(I["acc"], a)))
            D.draw_text(c, str(git_badge), ACT_W / 2 + 13, y + 21, 22, col(I["status_text"], a), "Bold", "center")
    assets.draw_icon(c, "settings", ACT_W / 2, bottom - 36, 30, I["dim"], a, 2)
    c.drawLine(ACT_W, top, ACT_W, bottom, D.paint(col(I["border"], a), 2))
    x = ACT_W
    # explorer
    if explorer is not None:
        c.drawRect(skia.Rect.MakeXYWH(x, top, ex_w, bottom - top), D.paint(col(I["side"], a)))
        txt(c, "EXPLORER", x + 20, top + 44, I["text2"], a, 30, "SemiBold")
        assets.draw_icon(c, "ellipsis", x + ex_w - 30, top + 34, 26, I["dim"], a, 2)
        for i, row in enumerate(explorer):
            name, depth, state = row[0], row[1], row[2]
            k = row[3] if len(row) > 3 else 1.0
            ry = top + 96 + i * ROW
            if ry > (bottom - (panel_h if panel is not None else 0)) - 10 or k <= 0:
                continue
            ra = a * k
            if state == "selected":
                c.drawRect(skia.Rect.MakeXYWH(x, ry - 32, ex_w, ROW), D.paint(col(I["sel"], ra)))
                c.drawRect(skia.Rect.MakeXYWH(x, ry - 32, 2, ROW), D.paint(col(I["acc"], ra)))
            if state == "lit":
                c.drawRect(skia.Rect.MakeXYWH(x, ry - 32, ex_w, ROW), D.paint(col("#3A2A20", ra)))
            ix = x + 22 + depth * 22
            is_dir = name.endswith("/")
            if is_dir:
                assets.draw_icon(c, "chevron-down" if (len(row) > 4 and row[4]) else "chevron-right", ix, ry - 10, 22, I["dim"], ra, 2)
                ix += 22
            else:
                ix += 22
                ext = ftype(name)
                c.drawRoundRect(skia.Rect.MakeXYWH(ix - 11, ry - 22, 22, 24), 4, 4, D.paint(col(FILE_ICON.get(ext, FILE_ICON[""]), ra)))
            colr = I["dim"] if state == "ignored" else (I["untracked"] if state == "U" else (I["modified"] if state == "M" else I["text"]))
            label = name
            room = ex_w - (ix + 20 - x) - 40
            if len(label) * CW > room:
                label = label[: max(3, int(room / CW) - 1)] + "…"
            txt(c, label, ix + 20, ry, colr, ra, mono=True)
            if state in ("U", "M"):
                txt(c, state, x + ex_w - 34, ry, colr, ra, 30, "SemiBold")
            g["rows"][name] = (x, ry - 32, ex_w, ROW, ix)
        c.drawLine(x + ex_w, top, x + ex_w, bottom, D.paint(col(I["border"], a), 2))
        x += ex_w
    ex0 = x
    ed_bottom = bottom - (panel_h if panel is not None else 0)
    # tabs
    tx = ex0
    for name, active, *rest in tabs:
        preview = bool(rest and rest[0])
        wt = tw(name, mono=True) + 90
        c.drawRect(skia.Rect.MakeXYWH(tx, top, wt, 56), D.paint(col(I["editor"] if active else I["side"], a)))
        if active:
            c.drawRect(skia.Rect.MakeXYWH(tx, top, wt, 2), D.paint(col(I["acc"], a)))
        c.save()
        if preview:                                     # an italic preview tab, by a slight skew
            c.translate(tx + 20, top + 40); c.skew(-0.2, 0); c.translate(-(tx + 20), -(top + 40))
        txt(c, name, tx + 20, top + 40, I["text"] if active else I["dim"], a, mono=True)
        c.restore()
        assets.draw_icon(c, "x", tx + wt - 30, top + 29, 22, I["dim"], a, 2)
        c.drawLine(tx + wt, top, tx + wt, top + 56, D.paint(col(I["border"], a), 2))
        tx += wt
        if active:
            g["tab"] = (tx - wt, top, wt, 56)
    c.drawRect(skia.Rect.MakeXYWH(tx, top, W - tx, 56), D.paint(col(I["side"], a)))
    # breadcrumbs
    bx = ex0 + 20
    for i, cr in enumerate(crumbs):
        txt(c, cr, bx, top + 98, I["text2"], a, 30)
        bx += tw(cr, 30) + 10
        if i < len(crumbs) - 1:
            assets.draw_icon(c, "chevron-right", bx + 6, top + 88, 20, I["dim"], a, 2)
            bx += 26
    cy0 = top + 160
    gx = ex0 + 64
    g.update(code_x=gx, code_y=cy0, ed_bottom=ed_bottom, ex0=ex0)
    last = (gx, cy0)
    for i, ln in enumerate(lines):
        y = cy0 + i * LH
        if y > ed_bottom - 12:
            break
        k = None if n is None else n[i]
        if cur is not None and i == cur:
            c.drawRect(skia.Rect.MakeXYWH(ex0, y - 33, W - ex0 - 70, LH), D.paint(col(I["line"], a)))
        if hl is not None and i == hl:
            c.drawRect(skia.Rect.MakeXYWH(ex0, y - 33, W - ex0 - 70, LH), D.paint(col("#3A2A20", a)))
            c.drawRect(skia.Rect.MakeXYWH(ex0, y - 33, 3, LH), D.paint(col(I["acc"], a)))
        D.draw_text(c, str(i + 1), ex0 + 44, y, 30, col(I["dim"], a), "Regular", "right", mono=True)
        if k is not None and k <= 0:
            continue
        end = code(c, ln, gx, y, lang, k, a)
        last = (end, y)
        if under and under[0] == i and under[1] > 0:                 # a red squiggly underline flash
            p = skia.Path()
            p.moveTo(gx, y + 10)
            for j in range(int((end - gx) / 12)):
                p.lineTo(gx + (j + 1) * 12, y + (14 if j % 2 == 0 else 8))
            c.drawPath(p, D.paint(col(I["err"], under[1] * a), 3))
    g["cursor"] = last
    # minimap
    mx = W - 60
    c.drawRect(skia.Rect.MakeXYWH(mx - 6, top + 56, 66, ed_bottom - top - 56), D.paint(col("#1B1B1B", a)))
    for i, ln in enumerate(lines):
        k = len(ln) if n is None else n[i]
        if k > 0:
            c.drawRect(skia.Rect.MakeXYWH(mx, top + 72 + i * 7, min(46, 0.9 * k), 3),
                       D.paint(col(I["key"] if ln.startswith("#") or '":' in ln else I["dim"], 0.55 * a)))
    # bottom panel
    if panel is not None:
        py = ed_bottom
        c.drawRect(skia.Rect.MakeXYWH(ACT_W, py, W - ACT_W, panel_h), D.paint(col(I["side"], a)))
        c.drawLine(ACT_W, py, W, py, D.paint(col(I["border"], a), 2))
        px = ACT_W + 24
        for name in ("PROBLEMS", "OUTPUT", "TERMINAL"):
            act = name == "TERMINAL"
            txt(c, name, px, py + 42, I["text"] if act else I["dim"], a, 30, "SemiBold" if act else "Regular")
            w2 = tw(name, 30, "SemiBold" if act else "Regular")
            if act:
                c.drawRect(skia.Rect.MakeXYWH(px, py + 52, w2, 2), D.paint(col(I["acc"], a)))
            px += w2 + 34
        ty = py + 104
        g["term_y"] = ty
        for j, item in enumerate(panel):
            s, colr = item[0], item[1]
            k = item[2] if len(item) > 2 else None
            yy = ty + j * LH
            if yy > Y1 - STATUS_H - 8:
                break
            if s.startswith("PS "):
                head = prompt
                txt(c, head, ACT_W + 24, yy, I["text2"], a, mono=True)
                rest = s[len(head):]
                end = code(c, rest, ACT_W + 24 + len(head) * CW, yy, "sh", None if k is None else k, a, colr)
            else:
                end = code(c, s, ACT_W + 24, yy, "sh", k, a, colr)
            if j == len(panel) - 1 and prompt_cursor and int(t * 2.2) % 2 == 0:
                c.drawRect(skia.Rect.MakeXYWH(end + 4, yy - 26, 16, 32), D.paint(col(I["text"], a)))
            g["last_term"] = (end, yy)
    # status bar
    c.drawRect(skia.Rect.MakeXYWH(0, Y1 - STATUS_H, W, STATUS_H), D.paint(col(I["status"], a)))
    sx = 20
    assets.draw_icon(c, "git-branch", sx + 12, Y1 - STATUS_H / 2, 24, I["status_text"], a, 2.4)
    sx += 36
    for item in ("main", "0 errors 0 warnings"):
        txt(c, item, sx, Y1 - 12, I["status_text"], a, 30, "Medium")
        sx += tw(item, 30, "Medium") + 28
    rx = W - 20
    for item in reversed(("Ln 1, Col 1", "UTF-8", "LF", status_lang)):
        wdt = tw(item, 30, "Medium")
        rx -= wdt
        if rx < sx + 10:
            break
        txt(c, item, rx, Y1 - 12, I["status_text"], a, 30, "Medium")
        rx -= 22
    return g


# ================================================================== the scenes (bound onto devscenes.Scene)
TREE_FULL = [("my-project/", 0, "", 1, True), ("CLAUDE.md", 1, ""), ("CLAUDE.local.md", 1, "U"), (".mcp.json", 1, ""),
             (".claude/", 1, "", 1, True), ("settings.json", 2, ""), ("settings.local.json", 2, "ignored"), ("rules/", 2, ""),
             ("skills/", 2, ""), ("commands/", 2, ""), ("agents/", 2, ""), ("hooks/", 2, ""), ("build/", 1, "ignored"), ("src/", 1, "")]
HOOK_MD = ["# my-project", "## Rules", "- Never delete build/", "- Run tests before commit"]


def _cam(self, t, z0, z1, x0, x1, y0, y1, t0, dur):
    k = io((t - t0) / dur)
    return lerp(z0, z1, k), lerp(x0, x1, k), lerp(y0, y1, k)


def ide_hook(self, c, t):
    """Frame 0: the IDE, CLAUDE.md says "Never delete build/" and the terminal shows `rm -rf build/` (illustrative).
    The rule flashes red, "Ignored your rule?" pops, then the camera pulls back as the explorer tree expands."""
    expand = self.at(self.sp.get("expand_at"), self.w("Here's", 3.6, -0.1))
    rows = []
    for i, r in enumerate(TREE_FULL):
        if i < 2 or r[0] == "build/" or r[0] == "src/":
            rows.append(r)
        else:
            k = io((t - expand - 0.03 * i) / 0.25)
            rows.append((r[0], r[1], r[2], k) + tuple(r[4:]))
    flash = 0.0
    if 0.25 < t < 2.4:
        flash = 0.5 + 0.5 * math.cos((t - 0.25) * 9)
    elif t >= 2.4:
        flash = 1.0
    panel = [("PS C:\\my-project> claude", None), ("> rm -rf build/", I["err"]), ("build/ removed", I["dim"])]
    ide(c, t, explorer=rows, tabs=[("CLAUDE.md", True)], crumbs=("my-project", "CLAUDE.md", "# Rules"),
        lines=HOOK_MD, lang="md", cur=2, panel=panel, panel_h=330, under=(2, flash), glow=1.0, prompt_cursor=False, ex_w=360)
    txt(c, "illustrative example", ACT_W + 24, Y1 - STATUS_H - 24, I["dim"], 1, 30)


def ide_hook_camera(self, t):
    expand = self.at(self.sp.get("expand_at"), self.w("Here's", 3.6, -0.1))
    return _cam(self, t, 1.14, 1.0, 0.0, W / 2, 1040, 880, expand - 0.2, 0.9)   # zoom about the left edge: it stays in frame


def ide_claude_md(self, c, t):
    md = ["# my-project", "## Commands", "- npm test", "## Stack", "- TypeScript, Node 20", "## Conventions",
          "- Small, focused PRs", "@docs/architecture.md"]
    n = typed(md, t, 0.4, 44)[0]
    rows = [("my-project/", 0, "", 1, True), ("CLAUDE.md", 1, "selected"), ("CLAUDE.local.md", 1, "U"), (".mcp.json", 1, ""),
            (".claude/", 1, ""), ("src/", 1, "")]
    ide(c, t, explorer=rows, tabs=[("CLAUDE.md", True)], crumbs=("my-project", "CLAUDE.md", "# Commands"), lines=md,
        lang="md", n=n, cur=min(7, int(sum(1 for k in n if k > 0)) - 1), panel=None, glow=1.0, ex_w=400)
    lift = io((t - self.w("loaded", 2.0)) / 0.7)
    if lift > 0:                                         # into the context window, at the bottom of the editor
        bx, by, bw, bh = 420.0, 1340.0, 600.0, 66.0
        box(c, bx - 20, by - 70, bw + 40, bh + 100, 16, I["side"], I["border"], 2, lift, shadow=True)
        txt(c, "Context window", bx, by - 24, I["text2"], lift, 30, "SemiBold")
        box(c, bx, by, bw, bh, 12, "#262626", I["border"], 2, lift)
        fill = io((t - self.w("loaded", 2.0) - 0.3) / 0.8) * 0.42
        if fill > 0:
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(bx + 4, by + 4, max(1, bw * fill - 8), bh - 8), 9, 9), D.paint(col(I["acc"])))
            txt(c, "CLAUDE.md", bx + 18, by + 44, I["status_text"], clamp(fill / 0.2), 30, "SemiBold")


def ide_local(self, c, t):
    ign = self.w("Add", 2.6, 0.1)
    cmd = "PS C:\\my-project> echo CLAUDE.local.md >> .gitignore"
    kcmd = clamp((t - ign) / 0.9)
    done = t > ign + 1.0
    rows = [("my-project/", 0, "", 1, True), ("CLAUDE.md", 1, ""), ("CLAUDE.local.md", 1, "ignored" if done else "U"),
            (".gitignore", 1, "M" if done else ""), (".mcp.json", 1, ""), (".claude/", 1, "")]
    panel = [("PS C:\\my-project> git status --short", None), ("?? CLAUDE.local.md", I["untracked"])]
    if t > ign:
        panel.append((cmd, None, int(len(cmd) * kcmd) - 18))
    if done:
        panel += [("PS C:\\my-project> git status --short", None), (" M .gitignore", I["modified"])]
    lines = ["# Personal notes", "- Sandbox: :3001", "- Use pnpm here"]
    ide(c, t, explorer=rows, tabs=[("CLAUDE.md", False), ("CLAUDE.local.md", True, True)],
        crumbs=("my-project", "CLAUDE.local.md"), lines=lines, lang="md", n=typed(lines, t, 0.2, 50)[0], cur=0,
        panel=panel, panel_h=520, glow=0.8, ex_w=400)


def ide_settings(self, c, t):
    stack_t = self.w("settings.local.json", 6.0, -0.2)
    if t >= stack_t + 0.4:
        return self._settings(c, t)                      # the precedence stack (the old second half)
    a = 1 - io((t - stack_t) / 0.4)
    lines = ["{", '  "permissions": {', '    "deny": [', '      "Bash(rm -rf *)"', "    ]", "  }", "}"]
    run = self.w("enforced:", 2.2)
    panel = []
    if t > run:
        cmd = "PS C:\\my-project> claude"
        panel = [(cmd, None), ("> rm -rf build/", I["text"], int(15 * clamp((t - run - 0.3) / 0.5)))]
    if t > run + 1.0:
        panel.append(("✗ Denied by permissions", I["err"]))
    rows = [(".claude/", 0, "", 1, True), ("settings.json", 1, "selected"), ("settings.local.json", 1, "ignored"),
            ("rules/", 1, ""), ("skills/", 1, ""), ("hooks/", 1, "")]
    ide(c, t, explorer=rows, tabs=[("settings.json", True)], crumbs=(".claude", "settings.json", "permissions"),
        lines=lines, lang="json", n=typed(lines, t, 0.4, 44)[0], hl=3 if t > 1.4 else None, panel=panel, panel_h=360,
        status_lang="JSON", a=a, glow=a, prompt_cursor=False, ex_w=400)
    if t > run + 1.0:
        txt(c, "illustrative", W - 36, Y1 - STATUS_H - 24, I["dim"], a, 30, align="right")


def ide_skills(self, c, t):
    pick = self.at(self.sp.get("pick_at"), 3.0)
    push = self.at(self.sp.get("push_at"), 4.5)
    flip = self.at(self.sp.get("flip_at"), 7.0)
    if t >= flip:
        return self._skills(c, t)                        # the commands/ legacy card flip
    rows = [(".claude/", 0, "", 1, True), ("skills/", 1, "lit" if t > push else "", 1, t > push),
            ("review/", 2, "", 1 if t > push else 0, True), ("SKILL.md", 3, "selected", 1 if t > push else 0),
            ("fix-issue/", 2, "", 1 if t > push else 0), ("commands/", 1, "")]
    if t < push:
        panel = [("PS C:\\my-project> claude", None), ("> /" + ("review" if t > pick else ""), I["text"])]
        g = ide(c, t, explorer=rows, tabs=[("README.md", True, True)], crumbs=("my-project",), lines=["# my-project"],
                lang="md", panel=panel, panel_h=720, glow=0.8, prompt_cursor=True)
        if t > 0.6:                                      # the / menu
            q = io((t - 0.6) / 0.3)
            mx, my = ACT_W + 40, g["term_y"] + LH + 20
            box(c, mx, my, 900, 240, 14, "#252526", I["border"], 2, q, shadow=True)
            for j, (nm, desc) in enumerate((("/review", "Reviews the diff for bugs and style"), ("/fix-issue", "Fixes an issue by number"))):
                yy = my + 12 + j * 112
                if j == 0 and t > pick - 0.5:
                    box(c, mx + 8, yy, 884, 100, 10, "#3A2A20", I["acc"], 2, q)
                txt(c, nm, mx + 28, yy + 44, I["glow"] if j == 0 else I["text"], q, 32, mono=True)
                txt(c, desc, mx + 28, yy + 84, I["text2"], q, 30)
        return
    lines = ["---", "name: review", "description: Reviews the diff", "  for bugs and style", "---"]
    ide(c, t, explorer=rows, tabs=[("SKILL.md", True)], crumbs=("skills", "review", "SKILL.md"), lines=lines, lang="yaml",
        n=typed(lines, t, push + 0.3, 40)[0], cur=1, panel=None, status_lang="Markdown", glow=1.0)


def ide_hooks(self, c, t):
    blk = self.w("block", 2.6)
    lines = ["#!/bin/bash", "# PreToolUse: Bash", "CMD=$(jq -r \\", "  '.tool_input.command')", "if echo \"$CMD\" |",
             "   grep -q 'rm -rf'; then", "  deny  # block the call", "fi"]
    panel = [("> Bash: rm -rf build/", I["text"], int(21 * clamp((t - 0.5) / 0.5)))]
    if t > blk:
        panel.append(("✗ blocked by PreToolUse hook", I["err"]))
    if t > blk + 0.9:
        panel += [("> Bash: npm test", I["text"]), ("✓ allowed", I["ok"])]
    rows = [(".claude/", 0, "", 1, True), ("hooks/", 1, "", 1, True), ("validate-bash.sh", 2, "selected"),
            ("settings.json", 1, ""), ("skills/", 1, "")]
    ide(c, t, explorer=rows, tabs=[("validate-bash.sh", True)], crumbs=(".claude", "hooks", "validate-bash.sh"),
        lines=lines, lang="sh", n=typed(lines, t, 0.2, 70)[0], panel=panel, panel_h=420, status_lang="Shell Script",
        glow=1.0, prompt_cursor=False, ex_w=300)
    # the lifecycle strip in the editor's free space: PreToolUse -> tool -> PostToolUse, with the calls travelling
    ly = 890.0
    c.drawLine(420, ly, 1000, ly, D.paint(col(I["border"]), 6))
    for nm, x in (("PreToolUse", 480.0), ("tool", 720.0), ("PostToolUse", 925.0)):
        c.drawCircle(x, ly, 14, D.paint(col(I["acc"] if nm == "PreToolUse" else I["dim"])))
        txt(c, nm, x, ly - 34, I["text"], 1, 30, mono=True, align="center")
    q1 = io((t - 0.4) / max(0.3, blk - 0.6))
    chip(c, lerp(400, 430, q1), ly + 56, "rm -rf build/", I["err"] if t > blk else I["text"], 1, fill=I["side"])
    if t > blk + 0.9:
        q2 = io((t - blk - 0.9) / 1.0)
        chip(c, lerp(400, 820, q2), ly + 112, "npm test", I["ok"], 1, fill=I["side"])
    if t > blk:
        q = clamp((t - blk) / 0.22)
        s = lerp(2.4, 1.0, ease_out(q))
        c.save(); c.translate(905, 775); c.rotate(-8); c.scale(s * 0.75, s * 0.75)
        box(c, -150, -56, 300, 112, 14, "#1F1F1F", I["err"], 7, q)
        txt(c, "BLOCK", 0, 24, I["err"], q, 70, "Bold", align="center")
        c.restore()
    txt(c, "illustrative", W - 36, Y1 - STATUS_H - 24, I["dim"], 1, 30, align="right")


# ---- the three takeaways (line 10 is four scenes: intro, one, two, three; the pads give ~0.35 s between them)
CARDS = [("1", "CLAUDE.md = guidance", "book-open"), ("2", "Must never happen?", "lock", "Deny rule or hook (hooks are the strongest)"),
         ("3", "Start with CLAUDE.md", "rocket", "+ settings.json")]


def takeaway_step(self, c, t):
    step = int(self.sp.get("step", 0))
    if step == 3 and self.sp.get("diagram") and t > self.at(self.sp.get("diagram_at"), self.dur - 3.9) + 0.45:
        return self.diagram(c, t)                        # after the wipe: only the diagram
    txt(c, "3 things to remember", 60, 380, P["text"], 1 if step else io(t / 0.5), 56, "Bold")
    for i in range(3):
        if i + 1 > step:
            break
        new = i + 1 == step
        k = io(t / 0.55) if new else 1.0
        y = 450 + i * 200
        x = 60 + (1 - k) * 600
        box(c, x, y, 960, 170, 22, P["panel"], P["acc"] if new else P["border"], 3 if new else 2, k, shadow=True)
        c.drawCircle(x + 80, y + 85, 46, D.paint(col(P["acc"], k)))
        txt(c, CARDS[i][0], x + 80, y + 104, P["bg"], k, 52, "Bold", align="center")
        assets.draw_icon(c, CARDS[i][2], x + 890, y + 85, 54, P["bright"], k, 2.2)
        txt(c, CARDS[i][1], x + 160, y + (78 if len(CARDS[i]) > 3 else 100), P["text"], k, 40, "SemiBold")
        if len(CARDS[i]) > 3:
            txt(c, CARDS[i][3], x + 160, y + 132, P["bright"], k, 36 if len(CARDS[i][3]) < 30 else 30, "SemiBold")
    if step == 2:                                        # callback: the opening command, now denied
        k = io((t - 0.6) / 0.4)
        bx, by = 60.0, 1080.0
        box(c, bx, by, 960, 300, 16, "#181818", "#2B2B2B", 2, k, shadow=True)
        txt(c, "TERMINAL", bx + 24, by + 44, "#9D9D9D", k, 30, "SemiBold")
        n = int(15 * clamp((t - 0.9) / 0.5))
        txt(c, "PS C:\\my-project>", bx + 24, by + 110, "#9D9D9D", k, mono=True)
        txt(c, "rm -rf build/"[:n], bx + 24 + 18 * CW, by + 110, "#CCCCCC", k, mono=True)
        if t > 1.6:
            q = io((t - 1.6) / 0.25)
            txt(c, "✗ Denied by permissions", bx + 24, by + 170, "#F14C4C", q, mono=True)
            txt(c, "illustrative", bx + 936, by + 270, "#8B8B8B", q, 30, align="right")
    if step == 3 and self.sp.get("diagram"):
        wipe_at = self.at(self.sp.get("diagram_at"), self.dur - 3.9)
        if t > wipe_at + 0.45:
            self.diagram(c, t)


SCENES = dict(ide_hook=ide_hook, ide_claude_md=ide_claude_md, ide_local=ide_local, ide_settings=ide_settings,
              ide_skills=ide_skills, ide_hooks=ide_hooks, takeaway_step=takeaway_step)
