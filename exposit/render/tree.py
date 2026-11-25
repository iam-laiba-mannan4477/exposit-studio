"""The "project_tree" motion effect: a project-structure diagram that builds step by step across several scenes.

Left: a file tree (Lucide folder/file icons, thin connector lines). Right: one explanation card per entry, each joined
to its own tree row by a thin arrow. A pinned title sits on top. Every scene of the sequence carries the same "tree"
and "cards"; "done" lists the rows built in earlier scenes, "build" the rows this scene builds on its words, so
consecutive scenes joined by a "cut" read as one continuous build.

Spec (all optional except tree):
  tree:   [{"id", "name", "depth", "dir": bool, "icon", "card": "text", "tag", "note", "term": ["names in tree -a"]}]
  title, pill:            the pinned title ("Claude Code") and the outlined pill under it ("Project Structure")
  footnote:               a small card shown when the whole diagram lights up
  phase:  "hook" | "build" | "recap"
  done:   [row ids already built]
  build:  [{"rows": [ids], "at": cue}]     the first row with a card is the entry; the others are its children
  git_strike: [{"row", "at"}]               a "git" badge with a strike-through, on that row's card
  legacy: {"row", "at"}                     the row's "tag" chip appears on that word
  frontmatter: {"row", "at", "until", "lines": [...], "push": row id}   camera push in, a code panel, pull back
  hook_flow: {"row", "at", "until"}        tool call -> script -> allow / block, beside the row
  recap:  {"keep": [ids], "dim_at": cue, "all_at": cue}
  hook:   {"command": "tree -a", "prompt": "~/my-project $", "summary": "8 directories, 13 files", "morph_at": cue}

Layout is computed once and is the same in every scene (and in the final frame). check_layout() verifies that each
arrow ends on its own row's card, that arrows do not cross, that nothing leaves the frame and that text is >= 30 px.
"""
from __future__ import annotations
import functools, math
import skia
from . import assets, design as D
from .design import col, clamp, lerp, ease_out, ease_in_out, spring

W, H = 1080.0, 1920.0
PALETTES = {
    "dark": dict(TEXT="#F4F1EA", MUTED="#8A8580", ACC="#D97757", ACC_T="#D97757", RUST="#B85C3C", OK="#6FBF73", BAD="#E5534B",
                 CARD="#1E1C1A", PANEL="#141312", BG="#1A1918", DIMB="#4A3A32", BAND=None, BAND_T="#F4F1EA", GLOW=0.30),
    # claude-orange: cream page, peach cards. Grey, accent text and the title band are the nearest shades of the brief's
    # colours that reach 4.5:1 (#9A938B, #D97757 as text, and cream on #D97757 measure 2.7-2.8:1).
    "orange-dark": dict(TEXT="#F4F1EA", MUTED="#A8A097", ACC="#D97757", ACC_T="#F0A07E", RUST="#B85C3C", OK="#7FB77E", BAD="#E5604D",
                        CARD="#171615", PANEL="#131211", BG="#0E0D0C", DIMB="#2A2725", BAND=None, BAND_T="#F4F1EA", GLOW=0.30),
    "orange": dict(TEXT="#1F1E1D", MUTED="#635C55", ACC="#D97757", ACC_T="#9E4528", RUST="#B85C3C", OK="#2E7D32", BAD="#C0392B",
                   CARD="#F6DCCB", PANEL="#FBF8F2", BG="#F4F1EA", DIMB="#E3B9A0", BAND="#A44A2C", BAND_T="#F4F1EA", GLOW=0.22),
}
TEXT = MUTED = ACC = ACC_T = RUST = OK = BAD = CARD = PANEL = BG = DIMB = BAND = BAND_T = GLOW = None


def set_palette(name: str) -> None:
    globals().update(PALETTES[{"claude-orange": "orange", "claude-orange-dark": "orange-dark"}.get(name, "dark")])


set_palette("dark")
FS = 30.0                    # every label: tree rows, card text, tags (the floor of the size system)
IND = 26.0                   # indent per depth
ICON = 32.0
TREE_X = 34.0
CARD_X, CARD_R = 524.0, 1050.0
TOP, BOTTOM = 262.0, 1880.0
LH = 36.0                    # card line height
PAD = 14.0                   # card padding
GAP = 10.0                   # between cards


def _mono_w(s: str) -> float:
    return D.text_width(s, FS, "Regular", mono=True)


def _wrap_card(text: str) -> list[str]:
    """Each sentence starts a new line; a sentence wraps (balanced) if it does not fit."""
    out = []
    for sent in [x.strip() for x in text.replace(". ", ".\n").split("\n") if x.strip()]:
        out += D.wrap(sent, CARD_R - CARD_X - 2 * PAD, FS, "Regular")
    return out


@functools.lru_cache(maxsize=8)
def _layout_cached(key: str):
    import json
    return _layout(json.loads(key))


def layout(spec: dict) -> dict:
    import json
    return _layout_cached(json.dumps({k: spec.get(k) for k in ("tree", "footnote", "pill", "lane", "band", "foot_inset")}, sort_keys=True))


def _layout(spec: dict) -> dict:
    global TOP, LH, PAD
    global BOTTOM
    lane = bool(spec.get("lane"))                            # room for the mascot: above the first card, beside the footnote
    TOP, LH, PAD = (362.0, 35.0, 12.0) if lane else (262.0, 36.0, 14.0)
    BOTTOM = 1880.0
    if spec.get("band"):                                     # an explicit vertical band (e.g. inside platform safe zones)
        TOP, BOTTOM, LH, PAD = float(spec["band"][0]), float(spec["band"][1]), 34.0, 11.0
    rows = [dict(r) for r in spec["tree"]]
    foot = spec.get("footnote")
    foot_w = W - 2 * TREE_X - (230 if lane else float(spec.get("foot_inset") or 0))
    foot_lines = D.wrap(foot, foot_w - 2 * PAD, FS, "Regular") if foot else []
    foot_h = len(foot_lines) * LH + 2 * PAD - 8 if foot else 0.0
    bottom = BOTTOM - (foot_h + 16 if foot else 0)
    for r in rows:
        r["x"] = TREE_X + r["depth"] * IND                    # icon centre is x + ICON/2
        r["tx"] = r["x"] + ICON + 10                          # text start
        r["tw"] = _mono_w(r["name"])
        r["end"] = r["tx"] + r["tw"]
        if r.get("tag"):
            r["tag_x"] = r["end"] + 14
            r["tag_w"] = D.text_width(r["tag"], FS, "Medium") + 26
            r["end"] = r["tag_x"] + r["tag_w"]
        r["note_lines"] = D.wrap(r["note"], CARD_X - 40 - r["tx"], FS, "Regular") if r.get("note") else []
        if r.get("card"):
            r["lines"] = _wrap_card(r["card"])
            r["h"] = len(r["lines"]) * LH + 2 * PAD - 8

    def place(P, gap):
        """Rows top to bottom at pitch >= P; each entry row sits inside its card's height, so its arrow is a short
        horizontal line; cards stack without overlap. Returns the bottom used."""
        ry, cy = TOP + 6, TOP - 12
        for r in rows:
            if r.get("card"):
                y = max(ry, cy + min(r["h"] / 2, 44))
                r["cy"] = max(cy, y - r["h"] / 2)
                cy = r["cy"] + r["h"] + gap
            else:
                y = ry
            r["y"] = y
            ry = y + P + len(r["note_lines"]) * LH * 0.9 + float(r.get("space_after", 0))
        return max(ry - P + 26, cy - gap)

    P, gap = 60.0, 12.0
    while place(P, gap) > bottom and P > (41 if spec.get("band") else 44):
        P -= 1.0
        gap = max(8.0, gap - 0.25)
    spare = bottom - place(P, gap)
    if spare > 0:                                          # spread what is left between the rows
        P += spare / len(rows)
        place(P, gap)
    stack: list[int] = []
    for i, r in enumerate(rows):
        while stack and rows[stack[-1]]["depth"] >= r["depth"]:
            stack.pop()
        r["parent"] = stack[-1] if stack else None
        stack.append(i)
    cards = [{"row": r["id"], "lines": r["lines"], "h": r["h"], "y": r["cy"], "x": CARD_X, "w": CARD_R - CARD_X,
              "arrow": ((r["end"] + 10, r["y"]), (CARD_X - 4, r["y"]))} for r in rows if r.get("card")]
    out = {"rows": rows, "cards": {c["row"]: c for c in cards}, "pitch": P, "bottom": place(P, gap)}
    if foot:
        out["foot"] = {"lines": foot_lines, "x": TREE_X, "y": BOTTOM - foot_h, "w": foot_w, "h": foot_h}
    return out


def check_layout(spec: dict) -> list[str]:
    """Problems with the final diagram, as sentences (empty when it is right)."""
    L = layout(spec)
    errs = []
    rows, cards = L["rows"], L["cards"]
    by_id = {r["id"]: r for r in rows}
    ends = []
    for rid, cd in cards.items():
        (x0, y0), (x1, y1) = cd["arrow"]
        r = by_id[rid]
        if abs(y0 - r["y"]) > 0.5 or x0 < r["end"]:
            errs.append(f"arrow for {rid} does not start at its row")
        hit = [k for k, c2 in cards.items() if c2["y"] <= y1 <= c2["y"] + c2["h"] and abs(x1 - c2["x"]) < 12]
        if hit != [rid]:
            errs.append(f"arrow for {rid} ends on {hit}")
        if x1 - x0 < 18:
            errs.append(f"arrow for {rid} is too short ({x1 - x0:.0f} px)")
        ends.append((y0, y1, rid))
    ends.sort()
    for a, b in zip(ends, ends[1:]):
        if b[1] < a[1]:
            errs.append(f"arrows for {a[2]} and {b[2]} cross")
    cl = sorted(cards.values(), key=lambda c: c["y"])
    for a, b in zip(cl, cl[1:]):
        if b["y"] < a["y"] + a["h"] + 6:
            errs.append(f"cards {a['row']} and {b['row']} overlap")
    for r in rows:
        if r["end"] > CARD_X - 24:
            errs.append(f"row {r['id']} runs into the card column ({r['end']:.0f} px)")
    for c in cards.values():
        if c["y"] < TOP - 12 or c["y"] + c["h"] > BOTTOM + 1:
            errs.append(f"card {c['row']} leaves the band")
        for ln in c["lines"]:
            if D.text_width(ln, FS) > c["w"] - 2 * PAD + 0.5:
                errs.append(f"card {c['row']} line too wide: {ln}")
    ft = L.get("foot")
    if ft:
        low = max([r["y"] + 14 + len(r["note_lines"]) * LH * 0.9 for r in rows] + [c["y"] + c["h"] for c in cards.values()])
        if low > ft["y"] - 6:
            errs.append(f"the footnote overlaps the diagram by {low - ft['y'] + 6:.0f} px")
    if L["pitch"] < FS * 1.3:
        errs.append(f"row pitch {L['pitch']:.0f} px is too tight for {FS:.0f} px text")
    return errs


# ================================================================== drawing
def _txt(c, s, x, y, colr, a=1.0, weight="Regular", mono=False, size=FS, align="left"):
    if a > 0.01:
        D.draw_text(c, s, x, y, size, col(colr, a), weight, align, mono=mono)


def _arrow(c, p0, p1, k, colr, a, width=2.6):
    (x0, y0), (x1, y1) = p0, p1
    path = skia.Path()
    path.moveTo(x0, y0)
    mx = (x0 + x1) / 2
    path.cubicTo(mx, y0, mx, y1, x1, y1)
    part, _ = D.trim(path, 0.0, max(0.001, k))
    c.drawPath(part, D.paint(col(colr, a), width))
    if k > 0.96:
        D.arrowhead(c, x1, y1, 1.0, 0.0, 14, col(colr, a))


def _chip(c, x, y, text, colr, a, fill=None):
    fill = fill or BG
    w = D.text_width(text, FS, "Medium") + 26
    r = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y - 22, w, 44), 22, 22)
    c.drawRRect(r, D.paint(col(fill, a)))
    c.drawRRect(r, D.paint(col(colr, a), 2))
    _txt(c, text, x + 13, y + 10, colr, a, "Medium")
    return w


class Tree:
    """Draws one scene of the sequence. `scene` is the MotionScene (cue times, duration)."""

    def __init__(self, scene):
        self.s = scene
        self.sp = scene.sc.spec
        set_palette(scene.tpl.name)
        from . import mascot as M
        ms = self.sp.get("mascot") or {}
        self.mascot = M.Mascot(ms, scene.cue_t) if ms and M.available() else None
        self.taps = [(scene.cue_t(a.get("at"), 0) + float(a.get("delay", 0)), a["row"])
                     for a in ms.get("acts", []) if a["type"] == "tap" and a.get("row")]
        self.folder = None                                    # (row, opens, closes): the mascot inside a folder
        tin = {a["type"]: (a, scene.cue_t(a.get("at"), 0) + float(a.get("delay", 0))) for a in ms.get("acts", [])
               if a["type"] in ("into_folder", "out_of_folder")}
        if "into_folder" in tin:
            a, t0 = tin["into_folder"]
            self.folder = (a["row"], t0 + 0.3, tin["out_of_folder"][1] + 0.15 if "out_of_folder" in tin else 1e9)
        self.L = layout(self.sp)
        self.rows = self.L["rows"]
        self.by = {r["id"]: r for r in self.rows}
        self.cards = self.L["cards"]
        self.done = set(self.sp.get("done", []))
        self.dur = scene.sc.dur
        # build times
        self.tb: dict[str, float] = {}
        self.entries: list[tuple[float, str]] = []          # (time, entry row id) in this scene
        prev = 0.25
        for b in self.sp.get("build", []):
            t0 = self.s.cue_t(b.get("at"), prev + 1.0)
            for j, rid in enumerate(b["rows"]):
                self.tb[rid] = t0 + 0.22 * j
            ent = next((r for r in b["rows"] if self.by[r].get("card")), None)
            if ent:
                self.entries.append((t0, ent))
            prev = t0
        self.hook = self.sp.get("phase") == "hook"
        if self.hook:
            hk = self.sp.get("hook", {})
            self.morph_at = self.s.cue_t(hk.get("morph_at"), self.dur - 1.6)

    # ---- state helpers
    def built(self, rid, t):
        """0..1: how far this row's build has run (1 for rows from earlier scenes)."""
        if rid in self.done:
            return 1.0
        tb = self.tb.get(rid)
        return 0.0 if tb is None else clamp((t - tb) / 0.6)

    def active_entry(self, t):
        cur = None
        for tt, rid in self.entries:
            if t >= tt:
                cur = rid
        return cur

    def lit(self, rid, t):
        """1 when the row (and its card) is in full colour, 0 when dimmed to grey."""
        rec = self.sp.get("recap")
        if rec:
            dim_at = self.s.cue_t(rec.get("dim_at"), 0.3)
            all_at = self.s.cue_t(rec.get("all_at"), self.dur - 3.4)
            keep = rid in rec.get("keep", []) or self._family(rid) in rec.get("keep", [])
            k_all = ease_in_out((t - all_at) / 0.8)
            if keep:
                return 1.0
            return max(1.0 - ease_in_out((t - dim_at) / 0.5), k_all)
        fam = self._family(rid)
        if not self.by[fam].get("card"):                      # structural rows (my-project/) stay in full colour
            return 1.0
        act = self.active_entry(t)
        if act is None:
            return 0.0
        if fam != act:
            return 0.0
        return ease_out((t - self.tb.get(rid, 0.0)) / 0.4) if rid in self.tb else 1.0

    def _family(self, rid):
        """The entry row a row belongs to: itself if it has a card, else its nearest ancestor with one, or the
        entry built in the same step."""
        r = self.by[rid]
        if r.get("card"):
            return rid
        for b in self.sp.get("build", []) + self.sp.get("_groups", []):
            if rid in b["rows"]:
                ent = next((x for x in b["rows"] if self.by[x].get("card")), None)
                if ent:
                    return ent
        i = r["parent"]
        while i is not None:
            if self.rows[i].get("card"):
                return self.rows[i]["id"]
            i = self.rows[i]["parent"]
        return rid

    def glow(self, rid, t):
        """The terracotta row glow: the active entry while its line is spoken; the kept rows in the recap."""
        rec = self.sp.get("recap")
        if rec:
            if rid in rec.get("keep", []):
                k = ease_out((t - self.s.cue_t(rec.get("dim_at"), 0.3)) / 0.5)
                all_at = self.s.cue_t(rec.get("all_at"), self.dur - 3.4)
                return k * (1 - 0.6 * ease_in_out((t - all_at) / 0.8))
            return 0.0
        if self.active_entry(t) == rid:
            return ease_out((t - self.tb[rid] - 0.15) / 0.4)
        return 0.0

    # ---- camera
    def camera(self, t):
        """(zoom, focus x, focus y) in world space. A gentle follow of the active row; a push into the
        frontmatter row; 1.0 for the recap's final frame."""
        z, fx, fy = 1.0, W / 2, H / 2
        act = self.active_entry(t)
        if act and not self.sp.get("recap"):
            cd = self.cards[act]
            ty = (self.by[act]["y"] + cd["y"] + cd["h"] / 2) / 2
            k = ease_in_out((t - self.tb[act]) / 1.2)
            z = 1.0 + 0.03 * k
            fy = TOP - (TOP - H / 2) / z                       # the top of the diagram stays under the title
        fm = self.sp.get("frontmatter")
        if fm:
            a = self.s.cue_t(fm.get("at"), 1.0)
            u = self.s.cue_t(fm.get("until"), a + 3.0)
            k = min(ease_in_out((t - a) / 0.8), 1 - ease_in_out((t - u) / 0.8))
            if k > 0:
                r = self.by[fm.get("push", fm["row"])]
                z = lerp(z, 1.55, k)
                fx = lerp(fx, r["x"] + 300, k)
                fy = lerp(fy, r["y"] + 120, k)
        # keep the view inside the frame
        hw, hh = W / 2 / z, H / 2 / z
        fx = clamp(fx, hw, W - hw) if z > 1 else W / 2
        if z > 1.1:
            fy = clamp(fy, hh, H - hh)
        return z, fx, fy

    def to_screen(self, cam, x, y):
        z, fx, fy = cam
        return W / 2 + (x - fx) * z, H / 2 + (y - fy) * z

    # ---- the frame
    def draw(self, c, t):
        cam = self.camera(t)
        z, fx, fy = cam
        c.save()
        c.translate(W / 2, H / 2)
        c.scale(z, z)
        c.translate(-fx, -fy)
        if self.hook:
            self._draw_hook_world(c, t)
        else:
            self._draw_tree(c, t, ghost=0.0 if self.sp.get("recap") else 1.0)
            self._draw_cards(c, t)
        c.restore()
        self._focus_frame(c, t, cam)
        self._frontmatter(c, t, cam)
        self._hook_flow(c, t, cam)
        self._title(c, t)
        if self.mascot:
            self.mascot.draw(c, t, 1.0, lambda x, y: self.to_screen(cam, x, y))
        self._wipe(c, t)

    def _wipe(self, c, t):
        """A full-screen terracotta wipe: "wipe_in" uncovers the scene, "wipe_out" covers its last moment."""
        if self.sp.get("wipe_in"):
            k = ease_in_out(t / 0.55)
            if k < 1:
                c.drawRect(skia.Rect.MakeLTRB(W * k, 0, W, H), D.paint(col(ACC)))
        if self.sp.get("wipe_out"):
            k = ease_in_out((t - (self.dur - 0.45)) / 0.45)
            if k > 0:
                c.drawRect(skia.Rect.MakeLTRB(0, 0, W * k, H), D.paint(col(ACC)))

    def _title(self, c, t):
        if self.sp.get("no_title"):
            return
        z = self.camera(t)[0]
        kb = clamp((z - 1.06) / 0.15)
        if kb > 0:                                            # a backdrop while the camera pushes in
            p = skia.Paint()
            p.setShader(skia.GradientShader.MakeLinear([skia.Point(0, 0), skia.Point(0, 290)],
                                                       [col(BG, kb), col(BG, kb), col(BG, 0)], [0, 0.8, 1]))
            c.drawRect(skia.Rect.MakeWH(W, 290), p)
        title, pill = self.sp.get("tree_title", "Claude Code"), self.sp.get("pill", "Project Structure")
        k = 1.0 if not self.hook else ease_out((t - 0.05) / 0.5)
        if BAND:                                              # claude-orange: a pinned terracotta title band
            c.drawRect(skia.Rect.MakeXYWH(0, -400 + 400 * k, W, 236), D.paint(col(BAND)))
            c.drawRect(skia.Rect.MakeXYWH(0, 236 - 400 * (1 - k), W, 12), D.paint(col(ACC)))
            f = D.make_font(100, "Bold")
            tw = f.measureText(title)
            D.put_text(c, title, W / 2 - tw / 2, 132, f, col(BAND_T, k))
            _txt(c, pill, W / 2, 200, BAND_T, k, "SemiBold", size=42, align="center")
            return
        f = D.make_font(96, "Bold")                          # the style pack's heavy face (Archivo Black)
        tw = f.measureText(title)
        D.put_text(c, title, W / 2 - tw / 2, 150 - (1 - k) * 20, f, col(TEXT, k))
        pw = D.text_width(pill, 36, "SemiBold") + 56
        r = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(W / 2 - pw / 2, 176, pw, 58), 29, 29)
        c.drawRRect(r, D.paint(col(ACC, k), 2.4))
        _txt(c, pill, W / 2, 217, TEXT, k, "SemiBold", size=36, align="center")

    # ---- tree
    def _row_alpha(self, r, t):
        b = self.built(r["id"], t)
        return b

    def _draw_tree(self, c, t, ghost=0.0):
        for i, r in enumerate(self.rows):
            b = self.built(r["id"], t)
            if r["parent"] is not None:                       # connector: down from the parent, then across
                p = self.rows[r["parent"]]
                vx = p["x"] + ICON / 2
                k = ease_out(b / 0.5)
                if k > 0 or ghost > 0:
                    a = max(k, ghost * 0.5)
                    lit = self.lit(r["id"], t)
                    colr = D.mix(RUST, ACC, lit) if k > 0 else MUTED
                    y0 = p["y"] + ICON / 2 + 2 if r["parent"] == i - 1 else self._prev_sibling_y(i)
                    yy = lerp(y0, r["y"], k if k > 0 else 1.0)
                    c.drawLine(vx, y0, vx, yy, D.paint(col(colr, a), 2.2))
                    if (k if k > 0 else 1.0) > 0.6:
                        kk = clamp(((k if k > 0 else 1.0) - 0.6) / 0.4)
                        c.drawLine(vx, r["y"], lerp(vx, r["x"] - 2, kk), r["y"], D.paint(col(colr, a), 2.2))
            if b <= 0 and ghost <= 0:
                continue
            self._draw_row(c, r, t, b, ghost)

    def _prev_sibling_y(self, i):
        r = self.rows[i]
        for j in range(i - 1, -1, -1):
            if self.rows[j]["parent"] == r["parent"]:
                return self.rows[j]["y"]
        return self.rows[r["parent"]]["y"] + ICON / 2 + 2

    def _draw_row(self, c, r, t, b, ghost=0.0):
        lit, gl = self.lit(r["id"], t), self.glow(r["id"], t)
        if b <= 0:                                            # a ghost row (after the terminal morph)
            _txt(c, r["name"], r["tx"], r["y"] + 11, MUTED, ghost * 0.45, mono=True)
            return
        if gl > 0.01:
            x0, x1 = r["x"] - 10, r["tx"] + r["tw"] + 12
            rr = skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(x0, r["y"] - 25, x1, r["y"] + 25), 12, 12)
            c.drawRRect(rr, D.paint(col(RUST, GLOW * gl)))
            c.drawRRect(rr, D.paint(col(ACC, 0.9 * gl), 2))
            D.halo(c, (x0 + x1) / 2, r["y"], 130, ACC, 0.18 * gl)
        for tt, rid in self.taps:                             # the mascot taps the row: one pulse
            if rid == r["id"] and 0 <= t - tt < 0.6:
                q = (t - tt) / 0.6
                rr = skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(r["x"] - 10 - 14 * q, r["y"] - 25 - 8 * q,
                                                              r["tx"] + r["tw"] + 12 + 14 * q, r["y"] + 25 + 8 * q), 14, 14)
                c.drawRRect(rr, D.paint(col(ACC, 1 - q), 3))
        k_icon = spring(clamp((b * 0.6 - 0.1) / 0.35))
        icon_col = D.mix(MUTED, ACC, lit)
        if k_icon > 0.01:
            icon = r["icon"]
            if self.folder and self.folder[0] == r["id"] and self.folder[1] <= t <= self.folder[2]:
                icon, icon_col = "folder-open", ACC
            assets.draw_icon(c, icon, r["x"] + ICON / 2, r["y"], ICON * k_icon, icon_col, clamp(k_icon), 2.0)
        ka = ease_out((b * 0.6 - 0.15) / 0.3)
        txt_col = D.mix(MUTED, TEXT, lit)
        c.save()
        c.clipRect(skia.Rect.MakeLTRB(r["tx"] - 4, r["y"] - 30, r["tx"] + (r["tw"] + 8) * ka, r["y"] + 30))
        _txt(c, r["name"], r["tx"], r["y"] + 11, txt_col, 1.0, mono=True)
        c.restore()
        if r.get("tag"):
            lg = self.sp.get("legacy") or {}
            tk = 1.0 if (r["id"] in self.done and lg.get("row") != r["id"]) else \
                ease_out((t - self.s.cue_t(lg.get("at"), 1e9)) / 0.4) if lg.get("row") == r["id"] else 0.0
            if r["id"] in self.done:
                tk = 1.0
            if tk > 0:
                _chip(c, r["tag_x"] + (1 - tk) * 20, r["y"], r["tag"], D.mix(MUTED, ACC_T, max(lit, 0.0)), tk)
        if r.get("note_lines"):
            for j, ln in enumerate(r["note_lines"]):
                _txt(c, ln, r["tx"], r["y"] + 11 + (j + 1) * LH * 0.9, MUTED, ka)

    # ---- cards
    def _draw_cards(self, c, t):
        for rid, cd in self.cards.items():
            b = self.built(rid, t)
            if b <= 0:
                continue
            tb = -10.0 if rid in self.done else self.tb[rid]
            ka = clamp((t - tb - 0.3) / 0.45) if rid not in self.done else 1.0
            kc = ease_out((t - tb - 0.6) / 0.5) if rid not in self.done else 1.0
            lit = self.lit(rid, t)
            acol = D.mix(MUTED, ACC, lit)
            if ka > 0:
                _arrow(c, *cd["arrow"], ease_out(ka), acol, 1.0)
            if kc <= 0:
                continue
            x = cd["x"] + (1 - kc) * 70
            rr = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, cd["y"], cd["w"], cd["h"]), 14, 14)
            c.drawRRect(rr, D.paint(col(CARD, kc)))
            c.drawRRect(rr, D.paint(col(D.mix(DIMB, ACC, lit), kc), 2.0))
            tcol = D.mix(MUTED, TEXT, lit)
            for j, ln in enumerate(cd["lines"]):
                _txt(c, ln, x + PAD, cd["y"] + PAD + 25 + j * LH, tcol, kc)
            self._git_strike(c, rid, t, x, cd, kc)
        ft = self.L.get("foot")
        rec = self.sp.get("recap")
        if ft and rec:
            k = ease_out((t - self.s.cue_t(rec.get("all_at"), self.dur - 3.4) - 0.3) / 0.6)
            if k > 0:
                rr = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(ft["x"], ft["y"] + (1 - k) * 30, ft["w"], ft["h"]), 14, 14)
                c.drawRRect(rr, D.paint(col(CARD, k)))
                eff = skia.DashPathEffect.Make([10, 8], 0)
                p = D.paint(col(ACC, k), 2.0)
                p.setPathEffect(eff)
                c.drawRRect(rr, p)
                for j, ln in enumerate(ft["lines"]):
                    _txt(c, ln, ft["x"] + PAD, ft["y"] + (1 - k) * 30 + PAD + 25 + j * LH, TEXT, k)

    def _git_strike(self, c, rid, t, x, cd, kc):
        hit = next((g for g in self.sp.get("git_strike", []) if g["row"] == rid), None)
        if rid in self.sp.get("_git_done", []):
            k1 = k2 = 1.0
        elif hit:
            at = self.s.cue_t(hit.get("at"), 1.0)
            k1, k2 = ease_out((t - at) / 0.35), ease_out((t - at - 0.35) / 0.35)
        else:
            return
        if k1 <= 0:
            return
        lit = self.lit(rid, t)
        bw = D.text_width("git", FS, "SemiBold") + 58
        bx, by = x + cd["w"] - bw - 12, cd["y"] + 12
        rr = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(bx, by, bw, 42), 21, 21)
        c.drawRRect(rr, D.paint(col(BG, k1 * kc)))
        c.drawRRect(rr, D.paint(col(D.mix(MUTED, TEXT, lit), k1 * kc), 2))
        assets.draw_icon(c, "git-branch", bx + 22, by + 21, 24, D.mix(MUTED, TEXT, lit), k1 * kc, 2.2)
        _txt(c, "git", bx + 40, by + 31, D.mix(MUTED, TEXT, lit), k1 * kc, "SemiBold")
        if k2 > 0:
            c.drawLine(bx - 4, by + 36, bx - 4 + (bw + 8) * k2, by + 6, D.paint(col(D.mix(MUTED, BAD, lit), kc), 4))

    # ---- focus frame: corner brackets that slide to the active card
    def _focus_frame(self, c, t, cam):
        if self.hook or self.sp.get("recap"):
            return
        act = self.active_entry(t)
        if not act:
            return
        prev = None
        for tt, rid in self.entries:
            if rid == act:
                break
            prev = rid
        if prev is None:
            prev = next((r for r in reversed(self.sp.get("done", [])) if r in self.cards), None)
        def rect(rid):
            cd = self.cards[rid]
            x0, y0 = self.to_screen(cam, cd["x"] - 10, cd["y"] - 10)
            x1, y1 = self.to_screen(cam, cd["x"] + cd["w"] + 10, cd["y"] + cd["h"] + 10)
            return x0, y0, x1, y1
        k = ease_in_out((t - self.tb[act] - 0.5) / 0.55)
        r1 = rect(act)
        r0 = rect(prev) if prev else r1
        x0, y0, x1, y1 = (lerp(p, q, k) for p, q in zip(r0, r1))
        a = 1.0 if prev else k
        pt = D.paint(col(TEXT, 0.9 * a), 3)
        for (px, py, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
            c.drawLine(px, py, px + dx * 26, py, pt)
            c.drawLine(px, py, px, py + dy * 26, pt)

    # ---- line 7: the SKILL.md frontmatter
    def _frontmatter(self, c, t, cam):
        fm = self.sp.get("frontmatter")
        if not fm:
            return
        a = self.s.cue_t(fm.get("at"), 1.0)
        u = self.s.cue_t(fm.get("until"), a + 3.0)
        k = min(ease_out((t - a - 0.5) / 0.45), 1 - ease_in_out((t - u) / 0.5))
        if k <= 0:
            return
        r = self.by[fm["row"]]
        sx, sy = self.to_screen(cam, r["tx"], r["y"])
        lines = fm.get("lines", [])
        pw = 980.0
        ph = 74 + len(lines) * 44 + 24
        px = 50.0
        py = sy + 44
        if py + ph > 1880:
            py = sy - 44 - ph
        c.save()
        c.translate(0, (1 - k) * 24)
        rr = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(px, py, pw, ph), 16, 16)
        c.drawRRect(rr, D.paint(col(PANEL, 0.97 * k)))
        c.drawRRect(rr, D.paint(col(ACC, k), 2.4))
        assets.draw_icon(c, "file-text", px + 38, py + 38, 30, ACC, k, 2.0)
        _txt(c, fm.get("file", "review/SKILL.md"), px + 64, py + 49, TEXT, k, mono=True)
        c.drawLine(px, py + 72, px + pw, py + 72, D.paint(col(TEXT, 0.10 * k), 1.5))
        for j, ln in enumerate(lines):
            lk = ease_out((t - a - 0.7 - 0.18 * j) / 0.3)
            y = py + 72 + 44 * (j + 1)
            if ":" in ln and not ln.startswith("-"):
                key, val = ln.split(":", 1)
                _txt(c, key + ":", px + 32, y, ACC_T, lk * k, mono=True)
                _txt(c, val, px + 32 + _mono_w(key + ":"), y, TEXT, lk * k, mono=True)
            else:
                _txt(c, ln, px + 32, y, MUTED, lk * k, mono=True)
        c.restore()
        # a thin leader from the row to the panel
        c.drawLine(sx + 20, sy + 26, sx + 20, py + (1 - k) * 24, D.paint(col(ACC, k), 2.4))

    # ---- line 9: tool call -> validate-bash.sh -> allow / block
    def _hook_flow(self, c, t, cam):
        hf = self.sp.get("hook_flow")
        if not hf:
            return
        a = self.s.cue_t(hf.get("at"), 1.0)
        u = self.s.cue_t(hf.get("until"), self.dur - 0.5)
        k = min(ease_out((t - a) / 0.45), 1 - ease_in_out((t - u) / 0.4))
        if k <= 0:
            return
        r = self.by[hf["row"]]
        _, sy = self.to_screen(cam, r["x"], r["y"])
        px, pw, ph = 40.0, 1000.0, 330.0
        py = sy - 50 - ph
        py += (1 - k) * 30
        box = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(px, py, pw, ph), 16, 16)
        c.drawRRect(box, D.paint(col(PANEL, 0.97 * k)))
        c.drawRRect(box, D.paint(col(ACC, k), 2.4))
        cy = py + ph / 2 + 10
        nodes = [("square-terminal", "tool call", px + 130), ("file-terminal", "validate-bash.sh", px + 470)]
        steps = [ease_out((t - a - 0.2 - 0.45 * i) / 0.4) for i in range(4)]
        for i, (ic, lab, x) in enumerate(nodes):
            kk = steps[i] * k
            rr2 = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x - 46, cy - 76, 92, 92), 18, 18)
            c.drawRRect(rr2, D.paint(col(CARD, kk)))
            c.drawRRect(rr2, D.paint(col(ACC, kk), 2.2))
            assets.draw_icon(c, ic, x, cy - 30, 48, TEXT, kk, 2.0)
            _txt(c, lab, x, cy + 60, TEXT, kk, mono=(i == 1), align="center")
        _txt(c, "PreToolUse", px + 30, py + 48, MUTED, k, mono=True)
        def arr(x0, y0, x1, y1, kk, colr):
            if kk <= 0:
                return
            p = skia.Path(); p.moveTo(x0, y0); p.lineTo(lerp(x0, x1, kk), lerp(y0, y1, kk))
            c.drawPath(p, D.paint(col(colr, k), 3))
            if kk > 0.95:
                ang = math.atan2(y1 - y0, x1 - x0)
                D.arrowhead(c, x1, y1, math.cos(ang), math.sin(ang), 16, col(colr, k))
        arr(px + 186, cy - 30, px + 414, cy - 30, steps[1], ACC)
        ox = px + 760
        arr(px + 526, cy - 40, ox - 30, cy - 92, steps[2], OK)
        arr(px + 526, cy - 20, ox - 30, cy + 32, steps[3], BAD)
        blk = ease_out((t - self.s.cue_t(hf.get("block_at"), 1e9)) / 0.25)
        if blk > 0:                                           # "block" lights up
            rb = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(ox - 30, cy + 4, 160, 72), 36, 36)
            c.drawRRect(rb, D.paint(col(BAD, 0.16 * blk * k)))
            c.drawRRect(rb, D.paint(col(BAD, blk * k), 3))
        for i, (ic, lab, yy, colr) in enumerate((("circle-check", "allow", cy - 100, OK), ("circle-x", "block", cy + 40, BAD))):
            kk = steps[2 + i] * k
            assets.draw_icon(c, ic, ox + 6, yy, 46, colr, kk, 2.4)
            _txt(c, lab, ox + 44, yy + 11, colr, kk, "SemiBold")

    # ---- line 1: the terminal, its output, the morph into the styled tree
    def _term_lines(self):
        """`tree -a` output in C-locale order: (prefix, name, row id or None)."""
        rows = self.rows
        kids: dict = {}
        for i, r in enumerate(rows):
            kids.setdefault(r["parent"], []).append(i)
        out = [("", ".", rows[0]["id"])]

        def walk(i, pre):
            items = []
            for j in kids.get(i, []):
                r = rows[j]
                names = r.get("term") or [r["name"].rstrip("/")]
                items.append((names, j))
            items.sort(key=lambda x: x[0][0].encode())
            for n, (names, j) in enumerate(items):
                last = n == len(items) - 1
                out.append((pre + ("└── " if last else "├── "), names[0], rows[j]["id"]))
                sub = pre + ("    " if last else "│   ")
                for extra in names[1:]:                        # review/SKILL.md is two lines in real output
                    out.append((sub + "└── ", extra, None))
                walk(j, sub)
        walk(0, "")
        return out

    def _draw_hook_world(self, c, t):
        hk = self.sp.get("hook", {})
        cmd, prompt = hk.get("command", "tree -a"), hk.get("prompt", "~/my-project $")
        lines = self._term_lines()
        summary = hk.get("summary", "")
        m = ease_in_out((t - self.morph_at) / 1.1)
        tx, ty, tw = 50.0, 286.0, 980.0
        lh = 44.0
        th = 84 + (len(lines) + 3) * lh + 30
        ka = (1 - m) * ease_out((t - 0.05) / 0.4)
        if ka > 0.01:
            rr = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(tx, ty, tw, th), 16, 16)
            c.drawRRect(rr, D.paint(col(PANEL, ka)))
            c.drawRRect(rr, D.paint(col(DIMB, ka), 2))
            for i, dot in enumerate((MUTED, MUTED, MUTED)):
                c.drawCircle(tx + 36 + i * 30, ty + 36, 9, D.paint(col(dot, 0.7 * ka)))
            c.drawLine(tx, ty + 70, tx + tw, ty + 70, D.paint(col(TEXT, 0.08 * ka), 1.5))
        x0 = tx + 34
        y = ty + 70 + lh
        type_t0, type_t1 = 0.3, 1.2
        n = int(len(cmd) * clamp((t - type_t0) / (type_t1 - type_t0)))
        _txt(c, prompt + " ", x0, y, ACC_T, ka, mono=True)
        px = x0 + _mono_w(prompt + " ")
        _txt(c, cmd[:n], px, y, TEXT, ka, mono=True)
        if t < type_t1 + 0.3 and int(t * 2.4) % 2 == 0:
            c.drawRect(skia.Rect.MakeXYWH(px + _mono_w(cmd[:n]) + 2, y - 24, 16, 30), D.paint(col(TEXT, ka)))
        p0 = type_t1 + 0.25
        for j, (pre, name, rid) in enumerate(lines):
            lt = p0 + 0.045 * j
            if t < lt:
                break
            yy = y + lh * (j + 1)
            if rid is None:
                _txt(c, pre + name, x0, yy, MUTED, ka, mono=True)
                continue
            r = self.by[rid]
            # morph: the name glides from its terminal place to its row; the box-drawing prefix fades
            sx, sy = x0 + _mono_w(pre), yy
            nx, ny = lerp(sx, r["tx"], m), lerp(sy, r["y"] + 11, m)
            _txt(c, pre, x0, yy, MUTED, ka, mono=True)
            label = name if m < 0.5 else r["name"]
            _txt(c, label, nx, ny, D.mix(TEXT, MUTED, m) if rid != self.rows[0]["id"] else TEXT, 1.0 if m < 0.98 else 0.0, mono=True)
        if summary and t > p0 + 0.045 * len(lines):
            _txt(c, summary, x0, y + lh * (len(lines) + 2), MUTED, ka, mono=True)
        # after the morph: ghost rows, then the root row builds
        if m > 0.98:
            self._draw_tree(c, t, ghost=1.0)
