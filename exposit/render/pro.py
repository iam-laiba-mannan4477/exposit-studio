"""Professional treatments: iconflow, map, sequence, cards, compare, stat.

Each is declarative: the spec names entities, links, places, messages or cards, and cues tied to spoken words animate
them. Landscape scenes draw in a 1920x1080 space, portrait (9:16) in 1080x1920 with all text between y 220 and 1500
and x 60 and 1020 (the platform's own interface covers the rest). Text is always fitted, wrapped or ellipsized to its
box. Only what the spec states is drawn: no numbers or places are invented here.
"""
from __future__ import annotations
import math
import skia
from . import assets, design as D
from .design import col, clamp, lerp, ease_out, ease_in_out, spring

SAFE_PORTRAIT = (60.0, 220.0, 1020.0, 1500.0)       # x0, y0, x1, y1 for text in 9:16


def _engine():
    from . import engine
    return engine


class ProTreatment:
    """Base for the new treatments. Shares the Scene (cues, word timing) with the original treatments."""
    drift = 0.03

    def __init__(self, sc):
        self.sc = sc
        self.tpl = sc.tpl
        self.portrait = bool(getattr(sc, "portrait", False))
        self.CX, self.CY = (540.0, 860.0) if self.portrait else (960.0, 540.0)
        self.W, self.H = (1080.0, 1920.0) if self.portrait else (1920.0, 1080.0)
        self.pos: dict[str, tuple[float, float, float, float]] = {}
        self.layout()

    # ---- shared API used by the engine (camera, centre, packets)
    def layout(self): ...
    def draw(self, c, t): ...

    def center(self, eid):
        x, y, w, h = self.pos.get(eid, (self.CX, self.CY, 0, 0))
        return x + w / 2, y + h / 2

    def camera(self, t):
        """Gentle drift only: a slow push of a few percent around the centre, so nothing reaches the frame edge."""
        k = ease_in_out(t / max(0.1, self.sc.dur))
        return 1.0 + self.drift * k, self.CX, self.CY

    # ---- helpers
    def appear(self, eid, t, dur=0.55):
        return clamp((t - self.sc.show_at.get(eid, 0.0)) / dur)

    def focus(self, t):
        return self.sc.any_highlight(t)

    def cue_t(self, at, default=0.0):
        v = self.sc.cue_time(at) if at is not None else None
        return default if v is None else v

    def label_size(self):
        return 34 if self.portrait else 32


# ================================================================== iconflow
class IconFlow(ProTreatment):
    """Entities as icon badges with labels under them, joined by orthogonal or curved connectors with rounded elbows,
    arrowheads, solid or dashed (return) styles and label chips; packets travel the real connector path."""

    def layout(self):
        sc = self.sc
        els = [sc.els[i] for i in sc.order]
        n = max(1, len(els))
        has_grid = any("col" in e or "row" in e for e in els)
        if has_grid:
            cols = max(int(e.get("col", 0)) for e in els) + 1
            rows = max(int(e.get("row", 0)) for e in els) + 1
            grid = {e["id"]: (int(e.get("col", 0)), int(e.get("row", 0))) for e in els}
        else:
            cols, rows = n, 1
            grid = {e["id"]: (i, 0) for i, e in enumerate(els)}
        if self.portrait:                                  # transpose: columns become rows, top to bottom
            grid = {k: (r, c) for k, (c, r) in grid.items()}
            cols, rows = rows, cols
            x0, x1, y0, y1 = 120.0, 960.0, 330.0, 1400.0
        else:
            x0, x1, y0, y1 = 110.0, 1810.0, 200.0, 900.0
        self.R = R = min(84.0 if not self.portrait else 78.0,
                         0.26 * (x1 - x0) / max(1, cols), 0.22 * (y1 - y0) / max(1, rows))
        self.cell_w = (x1 - x0) / max(1, cols)
        self.side = self.portrait and cols == 1
        for eid, (cx_i, ry_i) in grid.items():
            cx = 250.0 if self.side else x0 + (cx_i + 0.5) * (x1 - x0) / cols
            cy = y0 + (ry_i + 0.5) * (y1 - y0) / rows - (0 if self.side else 24)
            self.pos[eid] = (cx - R, cy - R, 2 * R, 2 * R)
        self.grid = grid
        self.links = self._links()

    def _links(self):
        sc = self.sc
        raw = sc.spec.get("links")
        if raw is None:
            raw = [[a, b] for a, b in zip(sc.order, sc.order[1:])]
        out = []
        for i, l in enumerate(raw):
            if isinstance(l, (list, tuple)):
                l = {"from": l[0], "to": l[1]}
            if l.get("from") not in self.pos or l.get("to") not in self.pos:
                continue
            out.append(dict(l, i=i))
        pairs = {}
        for l in out:
            pairs.setdefault(frozenset((l["from"], l["to"])), []).append(l)
        for group in pairs.values():                     # two links between the same pair run side by side
            if len(group) > 1:
                for j, l in enumerate(group):
                    l.setdefault("offset", (j - (len(group) - 1) / 2) * 64)
        for l in out:
            l["path"] = self._route(l)
        return out

    def _lab_h(self, eid):
        """Height of the label block under a badge (0 when labels sit beside the badges)."""
        if self.side:
            return 0.0
        e = self.sc.els[eid]
        size = self.label_size()
        rows, sz = D.fit_block(e.get("label", eid), min(self.cell_w - 24, 420), 2, size, size * 0.72, "SemiBold")
        return 14 + len(rows) * sz * 1.15 + (size * 0.72 * 1.25 if e.get("sub") else 0) + 8

    def _route(self, l):
        ax, ay = self.center(l["from"])
        bx, by = self.center(l["to"])
        R = self.R + 16
        down_a = self._lab_h(l["from"]) if by > ay + 2 else 0.0     # leaving downward from a
        up_b = self._lab_h(l["to"]) if ay > by + 2 else 0.0         # arriving from below into b
        off = float(l.get("offset", 0.0))
        style = l.get("style", "ortho")
        if style == "curve":
            d = math.hypot(bx - ax, by - ay) or 1
            ux, uy = (bx - ax) / d, (by - ay) / d
            return D.curve_path((ax + ux * R, ay + uy * R), (bx - ux * R, by - uy * R), float(l.get("bend", 0.18)))
        if abs(ay - by) < 2 or style == "straight" and abs(ay - by) < abs(ax - bx):
            s = 1 if bx > ax else -1
            return D.ortho_path([(ax + s * R, ay + off), (bx - s * R, by + off)])
        if abs(ax - bx) < 2 or style == "straight":
            s = 1 if by > ay else -1
            return D.ortho_path([(ax + off, ay + s * (R + down_a)), (bx + off, by - s * (R + up_b))])
        if self.portrait:                                 # down first, then across
            s = 1 if by > ay else -1
            sx = 1 if bx > ax else -1
            return D.ortho_path([(ax + off, ay + s * (R + down_a)), (ax + off, by + off), (bx - sx * R, by + off)], 26)
        sx = 1 if bx > ax else -1
        s = 1 if by > ay else -1
        return D.ortho_path([(ax + sx * R, ay + off), (bx + off, ay + off), (bx + off, by - s * (R + up_b))], 26)

    def link_progress(self, l, t):
        sc = self.sc
        start = max(sc.show_at.get(l["from"], 0), sc.show_at.get(l["to"], 0)) + 0.25
        for e in sc.events_of("draw"):
            if e.get("link") == l["i"] or (e.get("from") == l["from"] and e.get("to") == l["to"]):
                start = e["t"]
        if l.get("at") is not None:
            start = self.cue_t(l["at"], start)
        return ease_out((t - start) / (0.7 * sc.motion))

    def draw(self, c, t):
        sc, tpl = self.sc, self.tpl
        dim = self.focus(t)
        for l in self.links:
            k = self.link_progress(l, t)
            tone = l.get("tone")
            colr = D.role_color(tpl, tone) if tone in ("success", "fail", "info") else None
            hl = max(sc.highlight(l["from"], t), sc.highlight(l["to"], t)) if dim else 1.0
            D.stroke(c, tpl, l["path"], (1 - 0.6 * dim * (1 - hl)), k, dashed=bool(l.get("dashed")), color=colr,
                     seed=l["i"], flow=t if l.get("dashed") else None)
        for eid in sc.order:
            e = sc.els[eid]
            x, y, w, h = self.pos[eid]
            cx, cy = x + w / 2, y + h / 2
            k = self.appear(eid, t)
            if k <= 0:
                continue
            hl = sc.highlight(eid, t)
            tone = e.get("tone") or (_engine().KIND_COLOR.get(e.get("kind", ""), None) if tpl.icon["style"] == "pastel" else None)
            D.badge(c, tpl, assets.icon_for(e), cx, cy, self.R, ease_out(k * 1.6), hl, dim, spring(k), tone=tone,
                    seed=sum(map(ord, eid)))
            maxw = min(self.cell_w - 24, 400 if not self.portrait else 420)
            if self.portrait and self._side_label(eid):
                self._label_side(c, e, cx, cy, ease_out(k), hl, dim)
            else:
                a = ease_out((k - 0.2) / 0.8) * (1 - 0.65 * dim * (1 - hl))
                yb = D.label_under(c, tpl, e.get("label", eid), cx, cy + self.R + 14, maxw, self.label_size(), a, e.get("sub"), hl=hl)
                nt = sc.note(eid, t)
                if nt:
                    D.draw_text(c, D.ellipsize(nt[0], maxw, 22, mono=True), cx, yb + 30, 22, col(tpl.T["teal"], nt[1]), mono=True, align="center")
        for e in sc.events_of("chip"):
            if t < e["t"]:
                continue
            l = self._find_link(e)
            if l is None:
                continue
            kk = clamp((t - e["t"]) / 0.45)
            x, y, _, _ = D.point_at(l["path"], float(e.get("pos", 0.5)))
            if self.side:
                x = max(x, 60 + 150)
            D.chip(c, tpl, x, y + float(e.get("dy", 0)), e.get("text", ""), e.get("icon") or {"success": "check", "fail": "x"}.get(e.get("tone", "")),
                   e.get("tone", "neutral"), ease_out(kk), spring(kk), 25 if not self.portrait else 28,
                   max_w=380 if not self.portrait else 520)
        for l in self.links:                              # static chips declared on the link itself
            if l.get("label") and self.link_progress(l, t) > 0.9:
                kk = clamp((self.link_progress(l, t) - 0.9) / 0.1)
                x, y, _, _ = D.point_at(l["path"], 0.5)
                D.chip(c, tpl, x, y, l["label"], l.get("icon"), l.get("tone", "neutral"), kk, spring(kk), 24 if not self.portrait else 27,
                       max_w=360 if not self.portrait else 500)
        for e, k in sc.packets(t):
            l = self._find_link(e)
            if l is None:
                continue
            rev = l["from"] == e.get("to") and l["to"] == e.get("from")
            kk = ease_in_out(k)
            D.packet(c, tpl, l["path"], 1 - kk if rev else kk, 1 - clamp((k - 1) / 0.4) if k > 1 else 1.0,
                     D.role_color(tpl, e["tone"]) if e.get("tone") else None)

    def _side_label(self, eid):
        return self.side

    def _label_side(self, c, e, cx, cy, k, hl, dim):
        tpl = self.tpl
        a = k * (1 - 0.65 * dim * (1 - hl))
        x = cx + self.R + 28
        maxw = SAFE_PORTRAIT[2] - x
        rows, sz = D.fit_block(e.get("label", e["id"]), maxw, 2, 38, 26, "SemiBold")
        sub = e.get("sub")
        ss = 26
        total = len(rows) * sz * 1.15 + (ss * 1.3 if sub else 0)
        y = cy - total / 2 + sz * 0.9
        colr = D.mix(tpl.T["text"], tpl.conn["active"], 0.35 * hl) if tpl.dark else tpl.T["text"]
        for j, r in enumerate(rows):
            D.draw_text(c, r, x, y + j * sz * 1.15, sz, D.col(colr, a), "SemiBold")
        if sub:
            D.draw_text(c, D.ellipsize(sub, maxw, ss), x, y + len(rows) * sz * 1.15 + 4, ss, D.col(tpl.T["text2"], a))

    def _find_link(self, e):
        if "link" in e:
            return next((l for l in self.links if l["i"] == e["link"]), None)
        a, b = e.get("from"), e.get("to")
        for l in self.links:
            if (l["from"], l["to"]) == (a, b):
                return l
        for l in self.links:
            if (l["from"], l["to"]) == (b, a):
                return l
        return None


# ================================================================== map
class MapScene(ProTreatment):
    """World (or regional) map with places at real lat/lon: pulsing hubs, edge dots, great-circle arcs that draw on,
    region callout cards and a legend. Only places and numbers given in the spec are shown."""
    drift = 0.025

    def layout(self):
        sc = self.sc
        if self.portrait:
            rect = (30.0, 560.0, 1020.0, 620.0)
        else:
            rect = (60.0, 150.0, 1800.0, 840.0)
        win = sc.spec.get("window")
        self.proj = assets.MapProjection(rect, sc.spec.get("projection", "robinson"), tuple(win) if win else None)
        for e in sc.spec.get("elements", []):
            if "lat" in e and "lon" in e:
                x, y = self.proj(float(e["lon"]), float(e["lat"]))
                self.pos[e["id"]] = (x - 1, y - 1, 2, 2)
        self.arcs = []
        for i, a in enumerate(sc.spec.get("arcs", [])):
            if a.get("from") in self.pos and a.get("to") in self.pos:
                fa, fb = sc.els[a["from"]], sc.els[a["to"]]
                pts = assets.great_circle(float(fa["lon"]), float(fa["lat"]), float(fb["lon"]), float(fb["lat"]), 40)
                p = skia.Path()
                xy = [self.proj(lo, la) for lo, la in pts]
                p.moveTo(*xy[0])
                for q in xy[1:]:
                    p.lineTo(*q)
                if max(abs(xy[i][0] - xy[i + 1][0]) for i in range(len(xy) - 1)) > 400:   # crosses the antimeridian:
                    xy = [xy[0], xy[-1]]                                              # use the flat-map route
                p = self._lift(xy, lift=len(xy) == 2)
                self.arcs.append(dict(a, i=i, path=p))
        self._layer = None

    def _lift(self, xy, lift: bool = True):
        """Routes on a flat map follow the great circle, lifted upward a little so they read as routes.
        A two-point route (one that would cross the antimeridian) is resampled as a straight line first."""
        if len(xy) < 8:
            (x0, y0), (x1, y1) = xy[0], xy[-1]
            xy = [(lerp(x0, x1, i / 24), lerp(y0, y1, i / 24)) for i in range(25)]
        n = len(xy) - 1
        (x0, y0), (x1, y1) = xy[0], xy[-1]
        L = math.hypot(x1 - x0, y1 - y0)
        top = self.proj.rect[1] + 24
        bowed = [(x, y - math.sin(math.pi * i / n) * min(L * 0.10, 90) * (1.0 if lift else 0.35)) for i, (x, y) in enumerate(xy)]
        chord = [(lerp(y0, y1, i / n)) for i in range(n + 1)]
        f = 1.0
        for (x, y), cy in zip(bowed, chord):
            if y < top and cy > y:
                f = min(f, max(0.0, (cy - top) / (cy - y)))
        p = skia.Path()
        for i, ((x, y), cy) in enumerate(zip(bowed, chord)):
            yy = cy + (y - cy) * f
            if i == 0:
                p.moveTo(x, yy)
            else:
                p.lineTo(x, yy)
        return p

    def _map_layer(self, c):
        """The land, drawn once per scene into an image at the device resolution rounded up to a quarter step
        (the camera drifts by under 3%, so one image serves the whole scene)."""
        s = D.cache_scale(c, 1.05)
        key = (s, int(c.imageInfo().colorType()))
        if self._layer and self._layer[0] == key:
            return self._layer[1], s
        pw, ph = int(self.W * s), int(self.H * s)
        surf = D.layer_surface(c, pw, ph)
        cc = surf.getCanvas()
        cc.clear(skia.ColorTRANSPARENT)
        cc.scale(s, s)
        cc.clipRect(skia.Rect.MakeXYWH(*self.proj.rect))
        tpl, T = self.tpl, self.tpl.T
        style = self.sc.spec.get("style") or ("solid" if tpl.name in ("noir-network",) else "dots")
        land = assets.land_path(self.proj)
        if style == "solid":
            fill = {"noir-network": "#123A78", "paper": "#DCE3EC", "blueprint": "#16488F", "sketch": "#EFEDE6"}.get(tpl.name, T["panel"])
            edge = {"noir-network": "#2E6BC2", "paper": "#C3CDD9", "blueprint": "#DCE8FF", "sketch": "#9A968C"}.get(tpl.name, T["line"])
            if tpl.glow:                                   # drawn once into the cached layer
                cc.drawPath(land, D.blur(D.paint(col("#2D7BEA", 0.35)), 18))
            cc.drawPath(land, D.paint(col(fill, 0.95)))
            cc.drawPath(land, D.paint(col(edge, 0.9), 1.2))
        else:
            dot = {"noir-network": "#3C78C8", "paper": "#C2CCD8", "blueprint": "#DCE8FF", "sketch": "#B9B4A8"}.get(tpl.name, T["line"])
            rr = 3.4 * self.proj.s / (1800 / 2.0) * 1.6 if not self.portrait else 2.6
            rr = max(1.6, min(4.2, rr))
            p = D.paint(col(dot, 0.85))
            for (x, y) in assets.land_dots(self.proj):
                cc.drawCircle(x, y, rr, p)
        img = surf.makeImageSnapshot()
        self._layer = (key, img)
        return img, s

    def draw(self, c, t):
        sc, tpl, T = self.sc, self.tpl, self.tpl.T
        a0 = ease_out(t / 0.6)
        img, s = self._map_layer(c)
        c.save()
        c.scale(1 / s, 1 / s)
        c.drawImage(img, 0, 0, skia.SamplingOptions(skia.FilterMode.kLinear), skia.Paint(Alphaf=a0))
        c.restore()
        dim = self.focus(t)
        for a in self.arcs:
            start = self.cue_t(a.get("at"), max(sc.show_at.get(a["from"], 0), sc.show_at.get(a["to"], 0)) + 0.3)
            k = ease_out((t - start) / (0.9 * sc.motion))
            colr = D.role_color(tpl, a["tone"]) if a.get("tone") else tpl.conn["active"]
            D.stroke(c, tpl, a["path"], 0.85, k, dashed=a.get("dashed", True), color=colr, width=2.2 if not self.portrait else 2.6,
                     arrow=bool(a.get("arrow")), seed=a["i"], flow=t)
        for e in sc.spec.get("elements", []):
            if e["id"] not in self.pos:
                continue
            k = self.appear(e["id"], t)
            if k <= 0:
                continue
            x, y = self.center(e["id"])
            hl = sc.highlight(e["id"], t)
            al = ease_out(k) * (1 - 0.6 * dim * (1 - hl))
            colr = D.role_color(tpl, e["tone"]) if e.get("tone") else None
            kind = e.get("kind", "edge")
            if kind in ("hub", "region", "origin", "datacenter"):
                D.hub(c, tpl, x, y, 13 * spring(k) * (1 + 0.25 * hl), al, D.pulse(t + (x % 7) * 0.13), colr)
            elif e.get("icon") or kind in ("user", "users", "client", "browser", "phone"):
                D.badge(c, tpl, assets.icon_for(e), x, y, 30, al, hl, 0, spring(k), seed=int(x))
            else:
                D.node_dot(c, tpl, x, y, 6.5 * spring(k) * (1 + 0.3 * hl), al, colr, hl)
            if e.get("label") and e.get("show_label", True):
                self._place_label(c, e, x, y, al, hl)
        for e in sc.events_of("card"):
            if t >= e["t"] and e.get("target") in self.pos:
                self._region_card(c, e, ease_out((t - e["t"]) / 0.45))
        for e, k in sc.packets(t):
            arc = next((a for a in self.arcs if (a["from"], a["to"]) in ((e.get("from"), e.get("to")), (e.get("to"), e.get("from")))), None)
            if arc:
                rev = arc["from"] != e.get("from")
                kk = ease_in_out(k)
                D.packet(c, tpl, arc["path"], 1 - kk if rev else kk, 1 - clamp((k - 1) / 0.4) if k > 1 else 1.0, r=8)
        lg = sc.spec.get("legend")
        if lg:
            la = ease_out((t - self.cue_t(lg.get("at"), 0.8)) / 0.5)
            if self.portrait:
                D.legend(c, tpl, 60, 1210, lg.get("items", [])[:3], la, 600, lg.get("title"))
            else:
                D.legend(c, tpl, 70, 1080 - 70 - (34 + 40 * bool(lg.get("title")) + 70 * len(lg.get("items", [])[:4])),
                         lg.get("items", [])[:4], la, 390, lg.get("title"))

    def _place_label(self, c, e, x, y, a, hl):
        tpl = self.tpl
        size = 22 if not self.portrait else 26
        lab = D.ellipsize(e["label"], 300, size, "SemiBold")
        w = D.text_width(lab, size, "SemiBold")
        right = x < self.W - w - 80
        lx = x + 22 if right else x - 22 - w
        ly = y - 14
        if self.portrait:
            lx = clamp(lx, SAFE_PORTRAIT[0], SAFE_PORTRAIT[2] - w)
        bg = tpl.T["bg0"] if tpl.dark else "#FFFFFF"
        c.drawRoundRect(skia.Rect.MakeXYWH(lx - 8, ly - size, w + 16, size * 1.45), 8, 8, D.paint(col(bg, 0.72 * a)))
        D.draw_text(c, lab, lx, ly, size, col(D.mix(tpl.T["text"], tpl.conn["active"], 0.4 * hl), a), "SemiBold")

    def _region_card(self, c, e, k):
        tpl = self.tpl
        x, y = self.center(e["target"])
        w = 330 if not self.portrait else 420
        title, body = e.get("title", ""), e.get("text", "")
        rows, sz = D.fit_block(body, w - 40, 2, 22 if not self.portrait else 26, 16)
        h = 70 + len(rows) * sz * 1.25
        if self.portrait:
            cx = clamp(x - w / 2, SAFE_PORTRAIT[0], SAFE_PORTRAIT[2] - w)
            cy = 330 if y > 760 else 1220
            cy = clamp(cy, SAFE_PORTRAIT[1], SAFE_PORTRAIT[3] - h)
        else:
            cx = clamp(x - w / 2, 60, 1860 - w)
            cy = clamp(y + 60, 130, 1020 - h) if y < 520 else clamp(y - h - 60, 130, 1020 - h)
        lx = cx + w / 2
        lp = D.paint(col(tpl.conn["active"], 0.7 * k), 1.6)
        lp.setPathEffect(skia.DashPathEffect.Make([5, 5], 0))
        c.drawLine(x, y, lx, cy + (h if cy < y else 0), lp)
        D.card(c, tpl, cx, cy + (1 - k) * 18, w, h, k)
        yy = cy + (1 - k) * 18
        ts = D.fit_size(title, w - 40, 24 if not self.portrait else 28, 16, "Bold")
        D.draw_text(c, D.ellipsize(title.upper() if not tpl.jitter else title, w - 40, ts, "Bold"), cx + 20, yy + 40, ts,
                    col(tpl.conn["active"] if tpl.dark else tpl.T["accent"], k), "Bold")
        for j, r in enumerate(rows):
            D.draw_text(c, r, cx + 20, yy + 72 + j * sz * 1.25, sz, col(tpl.T["text"], k))


# ================================================================== sequence
class Sequence(ProTreatment):
    """Sequence diagram: actors with icons, dashed lifelines, messages that draw left to right with labels,
    self-loops with notes, and activation bars while an actor is handling a message."""
    drift = 0.015

    def layout(self):
        sc = self.sc
        self.actors = [sc.els[i] for i in sc.order]
        n = max(1, len(self.actors))
        if self.portrait:
            x0, x1, self.top, self.bottom = 110.0, 970.0, 300.0, 1460.0
        else:
            x0, x1, self.top, self.bottom = 220.0, 1700.0, 150.0, 1000.0
        self.R = 58.0 if self.portrait else 54.0
        for i, a in enumerate(self.actors):
            x = x0 + (x1 - x0) * (i + 0.5) / n if n > 1 else (x0 + x1) / 2
            self.pos[a["id"]] = (x - self.R, self.top, 2 * self.R, 2 * self.R)
        self.col_w = (x1 - x0) / n
        self.msgs = [m for m in sc.spec.get("messages", []) if m.get("from") in self.pos and m.get("to") in self.pos]
        head = self.top + 2 * self.R + 70
        nm = max(1, len(self.msgs))
        step = min(170.0 if self.portrait else 130.0, (self.bottom - 40 - head) / nm)
        self.rows = [head + 40 + i * step for i in range(nm)]
        self.step = step
        times = []
        prev = 0.6
        for m in self.msgs:
            tt = self.cue_t(m.get("at"), prev + 0.9)
            times.append(tt)
            prev = tt
        self.times = times

    def lx(self, eid):
        return self.center(eid)[0]

    def draw(self, c, t):
        sc, tpl, T = self.sc, self.tpl, self.tpl.T
        a0 = ease_out(t / 0.5)
        dim = self.focus(t)
        for i, a in enumerate(self.actors):
            k = D.stagger(t, 0.05, i, 0.12, 0.55, lambda x: x)
            x = self.lx(a["id"])
            hl = sc.highlight(a["id"], t)
            D.badge(c, tpl, assets.icon_for(a), x, self.top + self.R, self.R, ease_out(k), hl, dim, spring(k),
                    tone=a.get("tone") or ({"browser": "amber", "user": "amber", "client": "amber"}.get(a.get("kind", ""), "red")
                                           if tpl.icon["style"] == "pastel" else None), seed=i * 7)
            D.label_under(c, tpl, a.get("label", a["id"]), x, self.top - 2 * self.R - 6 if False else self.top + 2 * self.R + 8,
                          self.col_w - 20, self.label_size(), ease_out(k), a.get("sub"), hl=hl)
            ly0, ly1 = self.top + 2 * self.R + 62, self.bottom
            lp = D.paint(col(T["text2"] if not tpl.dark else T["line"], 0.75 * ease_out(k)), 2.4)
            lp.setPathEffect(skia.DashPathEffect.Make([10, 9], 0))
            p = skia.Path()
            p.moveTo(x, ly0)
            p.lineTo(x, lerp(ly0, ly1, ease_out(k)))
            c.drawPath(D.sketchify(p, i, tpl.jitter * 0.5) if tpl.jitter else p, lp)
            if k > 0.95:
                D.arrowhead(c, x, ly1 + 14, 0, 1, 14, col(T["text2"] if not tpl.dark else T["line"], 0.75))
        for bar in self._activations():
            eid, i0, i1 = bar
            if t < self.times[i0]:
                continue
            k = ease_out((t - self.times[i0]) / 0.4)
            y0 = self.rows[i0] + 6
            y1 = self.rows[i1] - 6 if i1 is not None and t >= self.times[i1] else lerp(y0, (self.rows[i1] if i1 is not None else self.rows[i0] + self.step * 0.6), clamp((t - self.times[i0]) / 0.8))
            x = self.lx(eid)
            r = skia.Rect.MakeXYWH(x - 9, y0, 18, max(6.0, y1 - y0))
            fill = D.mix(tpl.conn["active"], T["bg0"], 0.55 if tpl.dark else 0.75)
            c.drawRoundRect(r, 4, 4, D.paint(col(fill, 0.9 * k)))
            c.drawRoundRect(r, 4, 4, D.paint(col(tpl.conn["active"], k), 1.5))
        for i, m in enumerate(self.msgs):
            if t < self.times[i]:
                continue
            k = ease_out((t - self.times[i]) / (0.65 * sc.motion))
            y = self.rows[i]
            xa, xb = self.lx(m["from"]), self.lx(m["to"])
            tone = m.get("tone")
            colr = D.role_color(tpl, tone) if tone else tpl.conn["active"]
            active = 1.0 if i == max((j for j in range(len(self.msgs)) if t >= self.times[j]), default=-1) else 0.55
            size = 30 if self.portrait else 28
            if m["from"] == m["to"]:
                w = min(self.col_w * 0.5, 200)
                p = skia.Path()
                p.moveTo(xa + 10, y - 16)
                p.cubicTo(xa + w * 1.15, y - 26, xa + w * 1.15, y + 46, xa + 12, y + 40)
                D.stroke(c, tpl, p, active, k, color=colr, width=2.6, seed=i)
                rows, sz = D.fit_block(m.get("text", ""), self.col_w * 0.62, 2, size, size * 0.7, "Medium")
                for j, r in enumerate(rows):
                    D.draw_text(c, r, xa + 26, y - 30 - (len(rows) - 1 - j) * sz * 1.15, sz, col(T["text"], ease_out(k) * active), "Medium")
            else:
                d = 1 if xb > xa else -1
                p = skia.Path()
                p.moveTo(xa + d * 12, y)
                p.lineTo(xb - d * 14, y)
                D.stroke(c, tpl, p, active, k, dashed=bool(m.get("dashed")), color=colr, width=2.8, seed=i)
                span = abs(xb - xa) - 40
                rows, sz = D.fit_block(m.get("text", ""), span, 2, size, size * 0.68, "Medium")
                lx = min(xa, xb) + 22
                for j, r in enumerate(rows):
                    D.draw_text(c, r, lx, y - 18 - (len(rows) - 1 - j) * sz * 1.15, sz, col(T["text"], ease_out(k) * active), "Medium")
                if m.get("packet", True) and k < 1:
                    D.packet(c, tpl, p, ease_in_out(k), 1.0, colr, 7)
            if m.get("note") and k > 0.5:
                nk = ease_out((k - 0.5) / 0.5)
                D.chip(c, tpl, xa + min(self.col_w * 0.5, 200) * 1.15 + 70 if m["from"] == m["to"] else (xa + xb) / 2, y + 12,
                       m["note"], m.get("icon"), m.get("tone", "neutral"), nk, spring(nk), 22 if not self.portrait else 25,
                       max_w=self.col_w * 1.4)

    def _activations(self):
        """An actor is active from a message it receives until it sends a reply to the sender (or the end)."""
        bars = []
        for i, m in enumerate(self.msgs):
            if m["from"] == m["to"]:
                continue
            end = next((j for j in range(i + 1, len(self.msgs)) if self.msgs[j]["from"] == m["to"] and self.msgs[j]["to"] == m["from"]), None)
            bars.append((m["to"], i, end))
        return bars


# ================================================================== cards
class Cards(ProTreatment):
    """Title card (big title and subtitle over a backdrop, optional icon badges around it), or a strip of 2-4
    benefit cards (icon, title, one line) that slide up and fade in, staggered."""
    drift = 0.02

    def layout(self):
        sc = self.sc
        self.variant = sc.spec.get("variant", "title")
        self.items = sc.spec.get("items", [])[:4]
        self.backdrop = None
        if self.variant == "title" and sc.spec.get("backdrop") == "map":
            self.backdrop = MapScene.__new__(MapScene)
            self.backdrop.sc, self.backdrop.tpl, self.backdrop.portrait = sc, self.tpl, self.portrait
            self.backdrop.W, self.backdrop.H = self.W, self.H
            self.backdrop.CX, self.backdrop.CY = self.CX, self.CY
            self.backdrop.pos = {}
            win = sc.spec.get("window")
            rect = (30.0, 760.0, 1020.0, 620.0) if self.portrait else (260.0, 160.0, 1660.0, 860.0)
            self.backdrop.proj = assets.MapProjection(rect, "robinson", tuple(win) if win else None)
            self.backdrop.arcs = []
            self.backdrop._layer = None

    def draw(self, c, t):
        if self.variant == "benefits":
            return self._benefits(c, t)
        return self._title(c, t)

    def _title(self, c, t):
        sc, tpl, T = self.sc, self.tpl, self.tpl.T
        if self.backdrop:
            img, s = self.backdrop._map_layer(c)
            c.save()
            c.scale(1 / s, 1 / s)
            c.drawImage(img, 0, 0, skia.SamplingOptions(skia.FilterMode.kLinear), skia.Paint(Alphaf=0.55 * ease_out(t / 0.8)))
            c.restore()
        title, sub = sc.spec.get("title", ""), sc.spec.get("subtitle", "")
        k = ease_out((t - 0.05) / 0.6)
        if self.portrait:
            rows, sz = D.fit_block(title, 900, 3, 112, 64, tpl.title_weight)
            y = 420.0
            for j, r in enumerate(rows):
                D.draw_text(c, r, 90, y + (1 - k) * 30 + j * sz * 1.08, sz, col(T["text"], k), tpl.title_weight)
            y += len(rows) * sz * 1.08 + 10
            if sub:
                srows, ss = D.fit_block(sub, 900, 3, 44, 30, "Medium")
                k2 = ease_out((t - 0.35) / 0.6)
                for j, r in enumerate(srows):
                    D.draw_text(c, r, 90, y + 20 + j * ss * 1.2 + (1 - k2) * 20, ss, col(tpl.conn["active"] if tpl.dark else T["accent"], k2), "Medium")
        else:
            rows, sz = D.fit_block(title, 1080, 2, 138, 72, tpl.title_weight)
            y = 430.0 - (len(rows) - 1) * sz * 0.5
            for j, r in enumerate(rows):
                D.draw_text(c, r, 150, y + (1 - k) * 30 + j * sz * 1.05, sz, col(T["text"], k), tpl.title_weight)
            if sub:
                k2 = ease_out((t - 0.35) / 0.6)
                srows, ss = D.fit_block(sub, 1100, 2, 50, 32, "Medium")
                for j, r in enumerate(srows):
                    D.draw_text(c, r, 154, y + len(rows) * sz * 1.05 + 10 + j * ss * 1.2 + (1 - k2) * 20, ss,
                                col(tpl.conn["active"] if tpl.dark else T["accent"], k2), "Medium")
        slots = ([(1460, 300), (1700, 560), (1460, 820), (1700, 860)] if not self.portrait else
                 [(220, 1150), (540, 1150), (860, 1150), (540, 1380)])
        for i, it in enumerate(self.items):
            at = self.cue_t(it.get("at"), 0.7 + i * 0.25)
            kk = clamp((t - at) / 0.55)
            if kk <= 0:
                continue
            x, y = slots[i]
            R = 70 if not self.portrait else 72
            D.badge(c, tpl, assets.resolve(it.get("icon")) or "circle-check", x, y, R, ease_out(kk), 0, 0, spring(kk), tone=it.get("tone"), seed=i)
            D.label_under(c, tpl, it.get("title", ""), x, y + R + 12, 300, 30 if not self.portrait else 32, ease_out(kk))

    def _benefits(self, c, t):
        sc, tpl, T = self.sc, self.tpl, self.tpl.T
        n = max(1, len(self.items))
        head = sc.spec.get("title")
        if self.portrait:
            x0, w, gap = 90.0, 900.0, 34.0
            h = min(230.0, (1180 - (n - 1) * gap) / n)
            y0 = 330.0 if head else 380.0
            if head:
                rows, sz = D.fit_block(head, 900, 2, 60, 40, "Bold")
                for j, r in enumerate(rows):
                    D.draw_text(c, r, 90, 290 + j * sz * 1.1, sz, col(T["text"], ease_out(t / 0.5)), "Bold")
                y0 = 290 + len(rows) * sz * 1.1 + 30
            rects = [(x0, y0 + i * (h + gap), w, h) for i in range(n)]
        else:
            gap = 40.0
            w = min(540.0, (1700 - (n - 1) * gap) / n)
            x0 = (1920 - (n * w + (n - 1) * gap)) / 2
            h = 420.0
            y0 = 400.0 if head else 330.0
            if head:
                rows, sz = D.fit_block(head, 1500, 2, 76, 48, "Bold")
                for j, r in enumerate(rows):
                    D.draw_text(c, r, 960, 250 + j * sz * 1.1, sz, col(T["text"], ease_out(t / 0.5)), "Bold", "center")
            rects = [(x0 + i * (w + gap), y0, w, h) for i in range(n)]
        dim = self.focus(t)
        for i, (it, (x, y, w, h)) in enumerate(zip(self.items, rects)):
            at = self.cue_t(it.get("at"), 0.4 + i * 0.22)
            k = ease_out((t - at) / 0.6)
            if k <= 0:
                continue
            hl = sc.highlight(it.get("id", f"_{i}"), t)
            yy = y + (1 - k) * 40
            D.card(c, tpl, x, yy, w, h, k, hl, dim, seed=i)
            if self.portrait:
                R = min(54.0, h * 0.3)
                D.badge(c, tpl, assets.resolve(it.get("icon")) or "circle-check", x + 36 + R, yy + h / 2, R, k, hl, 0, spring(k), tone=it.get("tone"), seed=i)
                tx, tw = x + 72 + 2 * R, w - (100 + 2 * R)
                trows, ts = D.fit_block(it.get("title", ""), tw, 1, 40, 26, "Bold")
                brows, bs = D.fit_block(it.get("text", ""), tw, 2, 30, 22)
                total = ts * 1.2 + len(brows) * bs * 1.25
                ty = yy + (h - total) / 2 + ts * 0.9
                D.draw_text(c, trows[0], tx, ty, ts, col(T["text"], k), "Bold")
                for j, r in enumerate(brows):
                    D.draw_text(c, r, tx, ty + ts * 0.5 + 10 + (j + 0.75) * bs * 1.25, bs, col(T["text2"], k))
            else:
                R = 60.0
                D.badge(c, tpl, assets.resolve(it.get("icon")) or "circle-check", x + 44 + R, yy + 48 + R, R, k, hl, 0, spring(k), tone=it.get("tone"), seed=i)
                trows, ts = D.fit_block(it.get("title", ""), w - 88, 2, 42, 28, "Bold")
                ty = yy + 48 + 2 * R + 40 + ts * 0.8
                for j, r in enumerate(trows):
                    D.draw_text(c, r, x + 44, ty + j * ts * 1.15, ts, col(T["text"], k), "Bold")
                brows, bs = D.fit_block(it.get("text", ""), w - 88, 3, 30, 20)
                by = ty + len(trows) * ts * 1.15 + 6
                for j, r in enumerate(brows):
                    D.draw_text(c, r, x + 44, by + 8 + j * bs * 1.3, bs, col(T["text2"], k))


# ================================================================== compare
class Compare(ProTreatment):
    """Two lanes animated in parallel (cache hit vs cache miss, before vs after). Each lane: a title chip, a row of
    steps joined by connectors, a packet that runs the lane, and a result chip."""
    drift = 0.015

    def layout(self):
        self.lanes = self.sc.spec.get("lanes", [])[:2]
        self.paths = []
        self.step_pos = []
        for li, lane in enumerate(self.lanes):
            steps = lane.get("steps", [])[:5]
            n = max(1, len(steps))
            if self.portrait:
                cx = 290.0 + li * 500.0
                y0, y1 = 470.0, 1240.0
                pts = [(cx, y0 + (y1 - y0) * (i + 0.5) / n) for i in range(n)]
            else:
                cy = 300.0 + li * 420.0
                x0, x1 = 420.0, 1760.0
                pts = [(x0 + (x1 - x0) * (i + 0.5) / n, cy) for i in range(n)]
            self.step_pos.append(pts)
            self.paths.append([self._seg(pts[i], pts[i + 1]) for i in range(len(pts) - 1)])
        self.R = 58.0 if not self.portrait else 54.0

    def _seg(self, a, b):
        R = (58.0 if not self.portrait else 54.0) + 14
        if self.portrait:
            return D.ortho_path([(a[0], a[1] + R), (b[0], b[1] - R)])
        return D.ortho_path([(a[0] + R, a[1]), (b[0] - R, b[1])])

    def draw(self, c, t):
        sc, tpl, T = self.sc, self.tpl, self.tpl.T
        start = self.cue_t(sc.spec.get("at"), 0.4)
        for li, lane in enumerate(self.lanes):
            tone = lane.get("tone", "success" if li == 0 else "fail")
            colr = D.role_color(tpl, tone)
            pts = self.step_pos[li]
            ka = ease_out((t - 0.1 - 0.15 * li) / 0.5)
            ttl = lane.get("title", "")
            if self.portrait:
                D.chip(c, tpl, pts[0][0], 380, ttl, lane.get("icon"), tone, ka, spring(ka), 30, max_w=470)
            else:
                D.chip(c, tpl, 210, pts[0][1], ttl, lane.get("icon"), tone, ka, spring(ka), 30, max_w=330)
            steps = lane.get("steps", [])[:5]
            per = float(sc.spec.get("step_seconds", 0.9)) * sc.motion
            for i, st in enumerate(steps):
                k = clamp((t - start - i * per) / 0.5)
                x, y = pts[i]
                D.badge(c, tpl, assets.resolve(st.get("icon")) or "circle", x, y, self.R, ease_out(k), 0, 0, spring(k),
                        tone=st.get("tone") if tpl.icon["style"] == "pastel" else None, seed=li * 10 + i)
                if self.portrait:
                    w = 220
                    rows, sz = D.fit_block(st.get("label", ""), w, 2, 26, 18, "SemiBold")
                    side = -1 if li == 0 else 1
                    lx = x + side * (self.R + 18)
                    for j, r in enumerate(rows):
                        D.draw_text(c, r, lx, y - (len(rows) - 1) * sz * 0.55 + j * sz * 1.1 + sz * 0.35, sz,
                                    col(T["text"], ease_out(k)), "SemiBold", "right" if side < 0 else "left")
                else:
                    D.label_under(c, tpl, st.get("label", ""), x, y + self.R + 10, 1340 / max(1, len(steps)) - 30, 30, ease_out(k), st.get("sub"))
                if i < len(self.paths[li]):
                    kp = ease_out((t - start - i * per - 0.25) / (per * 0.75))
                    D.stroke(c, tpl, self.paths[li][i], 1.0, kp, color=colr, seed=li * 10 + i)
                    if 0 < kp < 1:
                        D.packet(c, tpl, self.paths[li][i], kp, 1.0, colr, 8)
            res = lane.get("result")
            if res:
                kr = ease_out((t - start - len(steps) * per) / 0.45)
                x, y = pts[-1]
                if self.portrait:
                    D.chip(c, tpl, x, y + self.R + 70, res.get("label", ""), res.get("icon") or {"success": "check", "fail": "x"}.get(tone),
                           res.get("tone", tone), kr, spring(kr), 26, max_w=460)
                else:
                    D.chip(c, tpl, (pts[0][0] + pts[-1][0]) / 2, y + self.R + 120, res.get("label", ""), res.get("icon") or {"success": "check", "fail": "x"}.get(tone),
                           res.get("tone", tone), kr, spring(kr), 28, max_w=700)
        if not self.portrait and len(self.lanes) == 2:
            dp = D.paint(col(T["line"], 0.6), 1.5)
            dp.setPathEffect(skia.DashPathEffect.Make([6, 8], 0))
            c.drawLine(120, 540, 1800, 540, dp)
        elif self.portrait and len(self.lanes) == 2:
            dp = D.paint(col(T["line"], 0.6), 1.5)
            dp.setPathEffect(skia.DashPathEffect.Make([6, 8], 0))
            c.drawLine(540, 450, 540, 1420, dp)


# ================================================================== stat
class Stat(ProTreatment):
    """One big number (counting up) or short phrase, a supporting icon, a label and the source line. The spec must
    give the value and its source; nothing is computed or estimated here."""
    drift = 0.02

    def draw(self, c, t):
        sc, tpl, T = self.sc, self.tpl, self.tpl.T
        at = self.cue_t(sc.spec.get("at"), 0.3)
        k = ease_out((t - at) / (1.4 * sc.motion))
        val = sc.spec.get("value", "")
        prefix, suffix = sc.spec.get("prefix", ""), sc.spec.get("suffix", "")
        if isinstance(val, (int, float)):
            dec = int(sc.spec.get("decimals", 0 if float(val).is_integer() else 1))
            shown = f"{prefix}{val * k:,.{dec}f}{suffix}"
            final = f"{prefix}{val:,.{dec}f}{suffix}"
        else:
            shown = final = f"{prefix}{val}{suffix}"
        ki = ease_out((t - at + 0.2) / 0.5)
        if self.portrait:
            D.badge(c, tpl, assets.resolve(sc.spec.get("icon")) or "gauge", 540, 470, 86, ki, 0, 0, spring(ki), tone=sc.spec.get("tone"))
            sz = D.fit_size(final, 900, 210, 90, "Bold")
            D.draw_text(c, shown, 540, 860, sz, col(tpl.conn["active"] if tpl.dark else T["accent"], ease_out((t - at) / 0.4)), "Bold", "center")
            rows, ls = D.fit_block(sc.spec.get("label", ""), 880, 3, 50, 32, "SemiBold")
            for j, r in enumerate(rows):
                D.draw_text(c, r, 540, 980 + j * ls * 1.2, ls, col(T["text"], ease_out((t - at - 0.3) / 0.5)), "SemiBold", "center")
            src = sc.spec.get("source", "")
            if src:
                srows, ss = D.fit_block("Source: " + src, 880, 2, 26, 18)
                for j, r in enumerate(srows):
                    D.draw_text(c, r, 540, 1380 + j * ss * 1.25, ss, col(T["text2"], ease_out((t - at - 0.6) / 0.5)), "Regular", "center")
        else:
            D.badge(c, tpl, assets.resolve(sc.spec.get("icon")) or "gauge", 520, 470, 110, ki, 0, 0, spring(ki), tone=sc.spec.get("tone"))
            sz = D.fit_size(final, 1050, 230, 100, "Bold")
            D.draw_text(c, shown, 720, 540, sz, col(tpl.conn["active"] if tpl.dark else T["accent"], ease_out((t - at) / 0.4)), "Bold")
            rows, ls = D.fit_block(sc.spec.get("label", ""), 1050, 2, 52, 32, "SemiBold")
            for j, r in enumerate(rows):
                D.draw_text(c, r, 724, 640 + j * ls * 1.2, ls, col(T["text"], ease_out((t - at - 0.3) / 0.5)), "SemiBold")
            src = sc.spec.get("source", "")
            if src:
                D.draw_text(c, D.ellipsize("Source: " + src, 1500, 24), 724, 900, 24, col(T["text2"], ease_out((t - at - 0.6) / 0.5)))


PRO_TREATMENTS = {"iconflow": IconFlow, "map": MapScene, "sequence": Sequence, "cards": Cards, "compare": Compare, "stat": Stat}
