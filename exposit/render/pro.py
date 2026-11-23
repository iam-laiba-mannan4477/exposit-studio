"""Professional treatments: iconflow, map, sequence, cards, compare, stat.

Each is declarative: the spec names entities, links, places, messages or cards, and cues tied to spoken words animate
them. Landscape scenes draw in a 1920x1080 space, portrait (9:16) in 1080x1920. Everything follows the size system in
design.py (phone first): headings 72-88 px, entity labels 44, body 36, nothing under 30; icons at least 150 px in 9:16
and 120 in 16:9; connectors 6-8 px. In 9:16 the content fills the band y 260..1500 below the heading. Text is always
fitted, wrapped (balanced) or ellipsized to its box. Only what the spec states is drawn: no numbers or places are
invented here, and the stat strip shows a number only when it names the research fact behind it.
"""
from __future__ import annotations
import math
import skia
from . import assets, design as D
from .design import col, clamp, lerp, ease_out, ease_in_out, spring

SAFE_PORTRAIT = (D.PORTRAIT_X[0], D.PORTRAIT_BAND[0], D.PORTRAIT_X[1], D.PORTRAIT_BAND[1])   # x0, y0, x1, y1


def _engine():
    from . import engine
    return engine


class ProTreatment:
    """Base for the new treatments. Shares the Scene (cues, word timing) with the original treatments."""
    drift = 0.02

    def __init__(self, sc):
        self.sc = sc
        self.tpl = sc.tpl
        self.portrait = bool(getattr(sc, "portrait", False))
        self.CX, self.CY = (540.0, 880.0) if self.portrait else (960.0, 560.0)
        self.W, self.H = (1080.0, 1920.0) if self.portrait else (1920.0, 1080.0)
        self.S = D.sizes(self.portrait)
        self.top = D.content_top(sc.spec, self.portrait)
        self.bottom = D.band_bottom(sc) - 10 if self.portrait else 1020.0
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

    @property
    def R(self):
        return self.S["icon"] / 2

    def tone_for(self, e, default=None):
        """A tone for an icon badge: the spec's, or (pastel and tinted styles) one by kind."""
        if e.get("tone"):
            return e["tone"]
        if self.tpl.icon["style"] in ("pastel", "tint"):
            return _engine().KIND_COLOR.get(e.get("kind", ""), default)
        return None


# ================================================================== iconflow
CHIP_GAP = 32 * 1.8 + 2 * 22 + 2 * 18          # a chip and clear space above and below it, between badge rows


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
            x0, x1, y0, y1 = 80.0, 1000.0, self.top, self.bottom - 14
        else:
            x0, x1, y0, y1 = 100.0, 1820.0, self.top, self.bottom
        self.cell_w = (x1 - x0) / max(1, cols)
        self.side = self.portrait and cols == 1
        self.r = max(self.S["icon"] / 2, min(95.0, 0.22 * self.cell_w, 0.2 * (y1 - y0) / max(1, rows)))
        self.no_subs = False
        lab_h = max((self._lab_h(e["id"]) for e in els), default=0.0)
        block = 2 * self.r + (0 if self.side else lab_h)   # badge + label; rows spread with equal gaps
        need_gap = (CHIP_GAP if self._has_chips() and not self.portrait else 70.0)
        if rows > 1 and rows * block + (rows - 1) * need_gap > y1 - y0 and not self.side:
            self.no_subs = True                           # short band (captions on): sub-lines are optional, gaps are not
            lab_h = max((self._lab_h(e["id"]) for e in els), default=0.0)
            block = 2 * self.r + lab_h
        gap = max(need_gap, (y1 - y0 - rows * block) / max(1, rows - 1)) if rows > 1 else 0.0
        oy = y0 + max(0.0, (y1 - y0 - rows * block - (rows - 1) * gap) / 2)
        for eid, (cx_i, ry_i) in grid.items():
            cx = 120.0 + self.r if self.side else x0 + (cx_i + 0.5) * (x1 - x0) / cols
            cy = oy + ry_i * (block + gap) + self.r
            self.pos[eid] = (cx - self.r, cy - self.r, 2 * self.r, 2 * self.r)
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
                    l.setdefault("offset", (j - (len(group) - 1) / 2) * 78)
        for l in out:
            l["path"] = self._route(l)
        return out

    def _maxw(self):
        return min(self.cell_w - 30, 440.0)

    def _lab_h(self, eid):
        """Height of the label block under a badge (0 when labels sit beside the badges)."""
        if getattr(self, "side", False):
            return 0.0
        e = self.sc.els[eid]
        return 16 + D.label_block_h(e.get("label", eid), self._maxw(), self.S["label"], self._sub(e))

    def draw_labels(self, c, t):
        """Only the labels (on their plates), drawn again above an effect such as the focus frame's dimming."""
        sc, tpl = self.sc, self.tpl
        for eid in sc.order:
            e = sc.els[eid]
            k = self.appear(eid, t)
            if k <= 0:
                continue
            x, y, w, h = self.pos[eid]
            cx, cy = x + w / 2, y + h / 2
            if self.side:
                self._label_side(c, e, cx, cy, ease_out(k), sc.highlight(eid, t), 0.0)
            else:
                D.label_under(c, tpl, e.get("label", eid), cx, cy + self.r + 16, self._maxw(), self.S["label"],
                              ease_out((k - 0.2) / 0.8), self._sub(e), hl=sc.highlight(eid, t), plate=True)

    def _gap_mid(self, l, y):
        """For a vertical link, the middle of the clear gap between the upper label block and the lower badge."""
        a, b = self.center(l["from"]), self.center(l["to"])
        up, lo = (l["from"], l["to"]) if a[1] < b[1] else (l["to"], l["from"])
        y0 = self.center(up)[1] + self.r + self._lab_h(up)
        y1 = self.center(lo)[1] - self.r
        return (y0 + y1) / 2 if y1 > y0 else y

    def _sub(self, e):
        return None if getattr(self, "no_subs", False) else e.get("sub")

    def _has_chips(self):
        return bool(self.sc.events_of("chip")) or any(isinstance(l, dict) and l.get("label") for l in self.sc.spec.get("links") or [])

    def _route(self, l):
        ax, ay = self.center(l["from"])
        bx, by = self.center(l["to"])
        R = self.r + 18
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
            return D.ortho_path([(ax + off, ay + s * (R + down_a)), (ax + off, by + off), (bx - sx * R, by + off)], 30)
        sx = 1 if bx > ax else -1
        s = 1 if by > ay else -1
        return D.ortho_path([(ax + sx * R, ay + off), (bx + off, ay + off), (bx + off, by - s * (R + up_b))], 30)

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
            D.stroke(c, tpl, l["path"], (1 - D.DIM * dim * (1 - hl)), k, dashed=bool(l.get("dashed")), color=colr,
                     seed=l["i"], flow=t if l.get("dashed") else None)
        for eid in sc.order:
            e = sc.els[eid]
            x, y, w, h = self.pos[eid]
            cx, cy = x + w / 2, y + h / 2
            k = self.appear(eid, t)
            if k <= 0:
                continue
            hl = sc.highlight(eid, t)
            D.badge(c, tpl, assets.icon_for(e), cx, cy, self.r, ease_out(k * 1.6), hl, dim, spring(k), tone=self.tone_for(e),
                    seed=sum(map(ord, eid)))
            if self.side:
                self._label_side(c, e, cx, cy, ease_out(k), hl, dim)
            else:
                a = ease_out((k - 0.2) / 0.8)                  # labels are never dimmed
                yb = D.label_under(c, tpl, e.get("label", eid), cx, cy + self.r + 16, self._maxw(), self.S["label"], a, self._sub(e), hl=hl, plate=True)
                nt = sc.note(eid, t)
                if nt:
                    D.draw_text(c, D.ellipsize(nt[0], self._maxw(), 30, mono=True), cx, yb + 40, 30,
                                col(D.text_on(tpl, tpl.T["teal"]), nt[1]), mono=True, align="center")
        chip_sz = 32
        for e in sc.events_of("chip"):
            if t < e["t"]:
                continue
            l = self._find_link(e)
            if l is None:
                continue
            kk = clamp((t - e["t"]) / 0.45)
            x, y, tx, ty = D.point_at(l["path"], float(e.get("pos", 0.5)))
            if self.side:
                x = max(x, 60 + 170)
            elif self.portrait and abs(ty) > 0.9:          # vertical link: the chip sits beside it, clear of labels
                cw, _ = D.chip_size(tpl, e.get("text", ""), e.get("icon") or "check", chip_sz, 440)
                x = x - cw / 2 - 26 if x - cw - 26 >= SAFE_PORTRAIT[0] else x + cw / 2 + 26
                y = self._gap_mid(l, y)
            D.chip(c, tpl, x, y + float(e.get("dy", 0)), e.get("text", ""), e.get("icon") or {"success": "check", "fail": "x"}.get(e.get("tone", "")),
                   e.get("tone", "neutral"), ease_out(kk), spring(kk), chip_sz, max_w=420 if not self.portrait else 440)
        for l in self.links:                              # static chips declared on the link itself
            if l.get("label") and self.link_progress(l, t) > 0.9:
                kk = clamp((self.link_progress(l, t) - 0.9) / 0.1)
                x, y, _, _ = D.point_at(l["path"], 0.5)
                D.chip(c, tpl, x, y, l["label"], l.get("icon"), l.get("tone", "neutral"), kk, spring(kk), chip_sz,
                       max_w=420 if not self.portrait else 440)
        for e, k in sc.packets(t):
            l = self._find_link(e)
            if l is None:
                continue
            rev = l["from"] == e.get("to") and l["to"] == e.get("from")
            kk = ease_in_out(k)
            D.packet(c, tpl, l["path"], 1 - kk if rev else kk, 1 - clamp((k - 1) / 0.4) if k > 1 else 1.0,
                     D.role_color(tpl, e["tone"]) if e.get("tone") else None)

    def _label_side(self, c, e, cx, cy, k, hl, dim):
        tpl = self.tpl
        a = k
        x = cx + self.r + 32
        maxw = SAFE_PORTRAIT[2] - x
        rows, sz = D.fit_block(e.get("label", e["id"]), maxw, 2, self.S["label"], 36, "SemiBold")
        sub = e.get("sub")
        srows, ss = D.fit_block(sub, maxw, 2, 32, 30) if sub else ([], 0)
        total = len(rows) * sz * 1.12 + len(srows) * ss * 1.18
        y = cy - total / 2 + sz * 0.9
        D.text_plate(c, tpl, [(r, sz, "SemiBold") for r in rows] + [(r, ss, "Regular") for r in srows],
                     None, cy - total / 2, cy + total / 2, a, x_left=x)
        colr = D.mix(tpl.T["text"], tpl.conn["active"], 0.25 * hl) if tpl.dark else tpl.T["text"]
        for j, r in enumerate(rows):
            D.draw_text(c, r, x, y + j * sz * 1.12, sz, D.col(colr, a), "SemiBold")
        for j, r in enumerate(srows):
            D.draw_text(c, r, x, y + len(rows) * sz * 1.12 + 4 + j * ss * 1.18, ss, D.col(tpl.T["text2"], a))

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
MAP_COLOURS = {   # land fill, edge, dot, glow under the land (None: no glow)
    "noir-network": dict(fill="#0F2E5E", edge="#2E6BC2", dot="#8CCBFF", glow="#2D7BEA"),
    "blueprint": dict(fill="#16488F", edge="#DCE8FF", dot="#EAF2FF", glow="#9CC3FF"),
    "paper": dict(fill="#DCE3EC", edge="#C3CDD9", dot="#B6C2D1", glow=None),
    "sketch": dict(fill="#EFEDE6", edge="#9A968C", dot="#B9B4A8", glow=None),
}


class MapScene(ProTreatment):
    """World (or regional) map with places at real lat/lon: pulsing hubs, light-points at edges, great-circle arcs
    that draw on, region callout cards, a legend panel and a stat strip. Only places, links and numbers given in the
    spec are shown; `"auto_arcs": "nearest-hub"` adds arcs from each edge to its nearest hub (both in the spec)."""
    drift = 0.02

    def _parts(self):
        sc = self.sc
        lg = sc.spec.get("legend") or {}
        strip = (sc.spec.get("strip") or {}).get("items") or []
        return lg.get("items", [])[:4], lg.get("title"), strip

    def layout(self):
        sc = self.sc
        items, title, strip = self._parts()
        aspect = 0.507                                      # Robinson world map, height / width
        if sc.spec.get("window"):                           # a cropped region has its own aspect
            pr = assets.MapProjection((0.0, 0.0, 1000.0, 1000.0), sc.spec.get("projection", "robinson"), tuple(sc.spec["window"]))
            lo0, lo1, la0, la1 = sc.spec["window"]
            (x0, y0), (x1, y1) = pr(lo0, la1), pr(lo1, la0)
            aspect = max(0.3, min(1.2, abs(y1 - y0) / max(1.0, abs(x1 - x0))))
        if self.portrait:                                   # map, callout slot, one-row legend, compact strip
            self.strip_h = D.stat_strip(None, self.tpl, 0, 0, 960, strip, 0.0, False) if strip else 0.0
            self.legend_items, self.legend_title = [dict(i, sub=None) for i in items], None
            lg_h = D.legend_row(None, self.tpl, 0, 0, 960, self.legend_items, 0.0) if items else 0.0
            self.card_h = 170.0 if sc.events_of("card") else 0.0
            others = [h for h in (self.card_h, lg_h, self.strip_h) if h]
            map_h = min(1040 * aspect, self.bottom - self.top - sum(others) - 20 * len(others))
            map_w = map_h / aspect                          # the map gives way when the band is short (captions on)
            parts = [map_h] + others
            gap = max(20.0, min(40.0, (self.bottom - self.top - sum(parts)) / max(1, len(parts) - 1)))
            y = self.top + max(0.0, (self.bottom - self.top - sum(parts) - gap * (len(parts) - 1)) / 2)
            rect = (540.0 - map_w / 2, y, map_w, map_h)
            y += map_h + gap
            self.card_slot = (60.0, y, 960.0, self.card_h)
            y += (self.card_h + gap) if self.card_h else 0
            self.legend_rect = (60.0, y, 960.0, lg_h)
            y += (lg_h + gap) if lg_h else 0
            self.strip_rect = (60.0, y, 960.0, self.strip_h)
        else:
            self.legend_items, self.legend_title = items, title
            self.strip_h = D.stat_strip(None, self.tpl, 0, 0, 1720, strip, 0.0, False) if strip else 0.0
            avail_h = self.bottom - self.top - (self.strip_h + 24 if strip else 0)
            right = 540.0 if items else 0.0
            mw = min(1840 - right, avail_h / aspect)
            mh = mw * aspect
            x0 = 40.0 + (1840 - right - mw) / 2
            rect = (x0, self.top + (avail_h - mh) / 2, mw, mh)
            lg_h = D.legend(None, self.tpl, 0, 0, items, 0.0, 500, title) if items else 0.0
            self.legend_rect = (1880 - 500, self.top + (avail_h - lg_h) / 2, 500.0, lg_h)
            self.strip_rect = (100.0, self.bottom - self.strip_h, 1720.0, self.strip_h)
        win = sc.spec.get("window")
        self.proj = assets.MapProjection(rect, sc.spec.get("projection", "robinson"), tuple(win) if win else None)
        for e in sc.spec.get("elements", []):
            if "lat" in e and "lon" in e:
                x, y = self.proj(float(e["lon"]), float(e["lat"]))
                self.pos[e["id"]] = (x - 1, y - 1, 2, 2)
        self.arcs = []
        for i, a in enumerate(self._arc_specs()):
            if a.get("from") in self.pos and a.get("to") in self.pos:
                fa, fb = sc.els[a["from"]], sc.els[a["to"]]
                pts = assets.great_circle(float(fa["lon"]), float(fa["lat"]), float(fb["lon"]), float(fb["lat"]), 40)
                xy = [self.proj(lo, la) for lo, la in pts]
                if max(abs(xy[i][0] - xy[i + 1][0]) for i in range(len(xy) - 1)) > 400:   # crosses the antimeridian:
                    xy = [xy[0], xy[-1]]                                              # use the flat-map route
                p = self._lift(xy, lift=len(xy) == 2)
                self.arcs.append(dict(a, i=i, path=p))
        self._layer = None

    def _arc_specs(self):
        sc = self.sc
        arcs = list(sc.spec.get("arcs", []))
        if sc.spec.get("auto_arcs") == "nearest-hub":
            els = [e for e in sc.spec.get("elements", []) if "lat" in e and "lon" in e]
            hubs = [e for e in els if e.get("kind") in ("hub", "region", "datacenter")]
            have = {frozenset((a["from"], a["to"])) for a in arcs}
            for e in els:
                if e.get("kind", "edge") not in ("edge", "pop", "user", "users", "client") or not hubs:
                    continue
                h = min(hubs, key=lambda h: _gc_dist(e, h))
                if frozenset((e["id"], h["id"])) not in have:
                    arcs.append({"from": e["id"], "to": h["id"], "minor": True})
                    have.add(frozenset((e["id"], h["id"])))
        return arcs

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

    def _style(self):
        if self.tpl.name in ("noir-network", "blueprint"):
            return "halftone"
        return self.sc.spec.get("style") or "dots"

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
        x, y, w, h = self.proj.rect
        cc.clipRect(skia.Rect.MakeXYWH(x - 40, y - 40, w + 80, h + 80))
        tpl, T = self.tpl, self.tpl.T
        mc = MAP_COLOURS.get(tpl.name, dict(fill=T["panel"], edge=T["line"], dot=T["line"], glow=T["accent"] if tpl.dark else None))
        style = self._style()
        land = assets.land_path(self.proj)
        if style == "solid":
            if mc["glow"]:
                cc.drawPath(land, D.blur(D.paint(col(mc["glow"], 0.35)), 18))
            cc.drawPath(land, D.paint(col(mc["fill"], 0.95)))
            cc.drawPath(land, D.paint(col(mc["edge"], 0.9), 1.2))
        else:
            rr = max(2.0, min(4.6, 3.4 * w / 1800 * 1.7))
            if style == "halftone":                          # glowing dotted land: a soft glow under bright dots
                cc.drawPath(land, D.blur(D.paint(col(mc["glow"], 0.55)), 22))
                cc.drawPath(land, D.paint(col(mc["fill"], 0.55)))
                for i, (dx, dy) in enumerate(assets.land_dots(self.proj)):
                    k = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(dx * 0.031 + dy * 0.047) * math.cos(dx * 0.013 - dy * 0.021))
                    cc.drawCircle(dx, dy, rr * k * 1.05, D.paint(col(mc["dot"], 0.55 + 0.45 * k)))
            else:
                p = D.paint(col(mc["dot"], 0.9))
                for (dx, dy) in assets.land_dots(self.proj):
                    cc.drawCircle(dx, dy, rr, p)
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
        ks = [self._arc_k(a, t) for a in self.arcs]
        minor_done = all(k >= 1 for a, k in zip(self.arcs, ks) if a.get("minor"))
        if minor_done and any(a.get("minor") for a in self.arcs):     # finished static arcs: one cached layer
            D.sprite(c, ("map-minor-arcs", id(self), tpl.name), 0, 0, self.W, self.H,
                     lambda cc: [self._draw_arc(cc, a, 1.0, 0.0) for a in self.arcs if a.get("minor")])
        for a, k in zip(self.arcs, ks):
            if a.get("minor") and minor_done:
                continue
            self._draw_arc(c, a, k, t)
        for e in sc.spec.get("elements", []):
            if e["id"] not in self.pos:
                continue
            k = self.appear(e["id"], t)
            if k <= 0:
                continue
            x, y = self.center(e["id"])
            hl = sc.highlight(e["id"], t)
            al = ease_out(k) * (1 - D.DIM * dim * (1 - hl))
            colr = D.role_color(tpl, e["tone"]) if e.get("tone") else None
            kind = e.get("kind", "edge")
            if kind in ("hub", "region", "origin", "datacenter"):
                D.hub(c, tpl, x, y, 17 * spring(k) * (1 + 0.25 * hl), al, D.pulse(t + (x % 7) * 0.13), colr)
            elif e.get("icon") or kind in ("user", "users", "client", "browser", "phone"):
                D.badge(c, tpl, assets.icon_for(e), x, y, 40, al, hl, 0, spring(k), seed=int(x))
            else:
                D.light_point(c, tpl, x, y, 8 * spring(k) * (1 + 0.3 * hl), al, colr, hl)
            if e.get("label") and e.get("show_label", True):
                self._place_label(c, e, x, y, ease_out(k), hl)     # labels keep full contrast under focus
        for e in sc.events_of("card"):
            if t >= e["t"] and e.get("target") in self.pos:
                self._region_card(c, e, ease_out((t - e["t"]) / 0.45))
        for e, k in sc.packets(t):
            arc = next((a for a in self.arcs if (a["from"], a["to"]) in ((e.get("from"), e.get("to")), (e.get("to"), e.get("from")))), None)
            if arc:
                rev = arc["from"] != e.get("from")
                kk = ease_in_out(k)
                D.packet(c, tpl, arc["path"], 1 - kk if rev else kk, 1 - clamp((k - 1) / 0.4) if k > 1 else 1.0)
        lg = sc.spec.get("legend")
        if lg and self.legend_items:
            la = ease_out((t - self.cue_t(lg.get("at"), 0.8)) / 0.5)
            x, y, w, _ = self.legend_rect
            if self.portrait:
                D.legend_row(c, tpl, x, y, w, self.legend_items, la)
            else:
                D.legend(c, tpl, x, y, self.legend_items, la, w, self.legend_title)
        st = (sc.spec.get("strip") or {})
        if st.get("items"):
            sa = ease_out((t - self.cue_t(st.get("at"), 1.1)) / 0.5)
            x, y, w, _ = self.strip_rect
            D.stat_strip(c, tpl, x, y, w, st["items"], sa, False)

    def _arc_k(self, a, t):
        sc = self.sc
        start = self.cue_t(a.get("at"), max(sc.show_at.get(a["from"], 0), sc.show_at.get(a["to"], 0)) + 0.3)
        return ease_out((t - start) / (0.9 * sc.motion))

    def _draw_arc(self, c, a, k, t):
        tpl = self.tpl
        colr = D.role_color(tpl, a["tone"]) if a.get("tone") else tpl.conn["active"]
        minor = bool(a.get("minor"))
        D.stroke(c, tpl, a["path"], 0.7 if minor else 0.95, k, dashed=a.get("dashed", not minor), color=colr,
                 width=4.0 if minor else 6.0, min_width=4.0, arrow=bool(a.get("arrow")), seed=a["i"],
                 flow=None if minor else t, glow=False if minor else None)

    def _place_label(self, c, e, x, y, a, hl):
        tpl = self.tpl
        size = 40 if self.portrait else 32
        mono = tpl.label_mono
        lab = D.ellipsize(e["label"], 440, size, "SemiBold", mono)
        w = D.text_width(lab, size, "SemiBold", mono)
        rx = self.proj.rect[0] + self.proj.rect[2]
        right = x + 28 + w < min(rx, self.W - 60)
        lx = x + 28 if right else x - 28 - w
        ly = y - 18
        if self.portrait:
            lx = clamp(lx, SAFE_PORTRAIT[0], SAFE_PORTRAIT[2] - w)
        bg = tpl.T["bg0"] if tpl.dark else "#FFFFFF"
        c.drawRoundRect(skia.Rect.MakeXYWH(lx - 10, ly - size * 0.95, w + 20, size * 1.4), 10, 10, D.paint(col(bg, 0.88 * a)))
        D.draw_text(c, lab, lx, ly, size, col(D.mix(tpl.T["text"], tpl.conn["active"], 0.25 * hl), a), "SemiBold", mono=mono)

    def _region_card(self, c, e, k):
        tpl = self.tpl
        x, y = self.center(e["target"])
        w = 470 if not self.portrait else 560
        title, body = e.get("title", ""), e.get("text", "")
        rows, sz = D.fit_block(body, w - 48, 2, 34, 30)
        h = 92 + len(rows) * sz * 1.22
        px, py, pw, ph = self.proj.rect
        if self.portrait:                                   # in its own slot under the map, with a leader line up
            sx, sy, sw, sh = self.card_slot
            w, h = sw, sh
            rows, sz = D.fit_block(body, w - 48, 1, 38, 30)
            cx, cy = sx, sy
        else:
            cx = clamp(x - w / 2, px, px + pw - w)
            cy = clamp(y + 60, py, py + ph - h) if y < py + ph / 2 else clamp(y - h - 60, py, py + ph - h)
        lx = cx + w / 2
        lp = D.paint(col(tpl.conn["active"], 0.85 * k), 3)
        lp.setPathEffect(skia.DashPathEffect.Make([8, 7], 0))
        c.drawLine(x, y, lx, cy + (h if cy < y else 0), lp)
        D.card(c, tpl, cx, cy + (1 - k) * 18, w, h, k)
        yy = cy + (1 - k) * 18
        ts = D.fit_size(title, w - 48, 44 if self.portrait else 36, 30, "Bold")
        D.draw_text(c, D.ellipsize(title, w - 48, ts, "Bold"), cx + 24, yy + 54, ts,
                    col(D.text_on(tpl, tpl.conn["active"] if tpl.dark else tpl.T["accent"], tpl.card["fill"]), k), "Bold")
        for j, r in enumerate(rows):
            D.draw_text(c, r, cx + 24, yy + 104 + j * sz * 1.22, sz, col(tpl.T["text"], k))


def _gc_dist(a, b):
    la1, lo1, la2, lo2 = (math.radians(float(v)) for v in (a["lat"], a["lon"], b["lat"], b["lon"]))
    return math.acos(clamp(math.sin(la1) * math.sin(la2) + math.cos(la1) * math.cos(la2) * math.cos(lo2 - lo1), -1, 1))


# ================================================================== sequence
class Sequence(ProTreatment):
    """Sequence diagram: actors with icons, dashed lifelines, messages that draw left to right with labels,
    curved self-loops with notes, and activation bars while an actor is handling a message."""
    drift = 0.012

    def layout(self):
        sc = self.sc
        self.actors = [sc.els[i] for i in sc.order]
        n = max(1, len(self.actors))
        if self.portrait:
            x0, x1 = 60.0, 1020.0
        else:
            x0, x1 = 200.0, 1720.0
        self.r = self.S["icon"] / 2
        self.col_w = (x1 - x0) / n
        lab_h = max((D.label_block_h(a.get("label", a["id"]), self.col_w - 24, self.S["label"]) for a in self.actors), default=50)
        for i, a in enumerate(self.actors):
            x = x0 + (x1 - x0) * (i + 0.5) / n if n > 1 else (x0 + x1) / 2
            self.pos[a["id"]] = (x - self.r, self.top, 2 * self.r, 2 * self.r)
        self.msgs = [m for m in sc.spec.get("messages", []) if m.get("from") in self.pos and m.get("to") in self.pos]
        self.ly0 = self.top + 2 * self.r + 12 + lab_h + 10
        nm = max(1, len(self.msgs))
        first = self.ly0 + (100 if self.portrait else 80)
        step = min(210.0 if self.portrait else 150.0, (self.bottom - 40 - first) / max(1, nm - 0.4))
        self.rows = [first + i * step for i in range(nm)]
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

    def _tone(self, a):
        if self.tpl.icon["style"] != "pastel":
            return a.get("tone")
        return a.get("tone") or {"browser": "amber", "user": "amber", "client": "amber", "edge": "red", "cache": "red",
                                 "origin": "green", "server": "green"}.get(a.get("kind", ""), "blue")

    def draw(self, c, t):
        sc, tpl, T = self.sc, self.tpl, self.tpl.T
        dim = self.focus(t)
        life_c = T["text2"]
        for i, a in enumerate(self.actors):
            k = D.stagger(t, 0.05, i, 0.12, 0.55, lambda x: x)
            x = self.lx(a["id"])
            hl = sc.highlight(a["id"], t)
            D.badge(c, tpl, assets.icon_for(a), x, self.top + self.r, self.r, ease_out(k), hl, dim, spring(k), tone=self._tone(a), seed=i * 7)
            D.label_under(c, tpl, a.get("label", a["id"]), x, self.top + 2 * self.r + 12, self.col_w - 24, self.S["label"], ease_out(k), a.get("sub"), hl=hl)
            ly0, ly1 = self.ly0, self.bottom
            lp = D.paint(col(life_c, 0.8 * ease_out(k)), 3.5)
            lp.setPathEffect(skia.DashPathEffect.Make([14, 12], 0))
            p = skia.Path()
            p.moveTo(x, ly0)
            p.lineTo(x, lerp(ly0, ly1, ease_out(k)))
            c.drawPath(D.sketchify(p, i, tpl.jitter * 0.7) if tpl.jitter else p, lp)
            if k > 0.95:
                D.arrowhead(c, x, ly1 + 20, 0, 1, 24, col(life_c, 0.8), i, tpl)
        for bar in self._activations():
            eid, i0, i1 = bar
            if t < self.times[i0]:
                continue
            k = ease_out((t - self.times[i0]) / 0.4)
            y0 = self.rows[i0] + 8
            y1 = self.rows[i1] - 8 if i1 is not None and t >= self.times[i1] else lerp(y0, (self.rows[i1] if i1 is not None else self.rows[i0] + self.step * 0.6), clamp((t - self.times[i0]) / 0.8))
            x = self.lx(eid)
            r = skia.Rect.MakeXYWH(x - 13, y0, 26, max(8.0, y1 - y0))
            fill = D.mix(tpl.conn["active"], T["bg0"], 0.55 if tpl.dark else 0.72)
            if tpl.jitter:
                p = skia.Path()
                p.addRect(r)
                c.drawPath(p, D.paint(col(fill, 0.9 * k)))
                c.drawPath(D.sketchify(p, i0, tpl.jitter), D.paint(col(tpl.conn["active"], k), 3))
            else:
                c.drawRoundRect(r, 5, 5, D.paint(col(fill, 0.9 * k)))
                c.drawRoundRect(r, 5, 5, D.paint(col(tpl.conn["active"], k), 2.5))
        cur = max((j for j in range(len(self.msgs)) if t >= self.times[j]), default=-1)
        size = 36
        for i, m in enumerate(self.msgs):
            if t < self.times[i]:
                continue
            k = ease_out((t - self.times[i]) / (0.65 * sc.motion))
            y = self.rows[i]
            xa, xb = self.lx(m["from"]), self.lx(m["to"])
            tone = m.get("tone")
            colr = D.role_color(tpl, tone) if tone else tpl.conn["active"]
            active = 1.0 if i == cur else 0.8
            tcol = col(T["text"], ease_out(k))
            if m["from"] == m["to"]:
                w = min(self.col_w * 0.42, 180)
                h = min(self.step * 0.55, 90)
                p = skia.Path()
                p.moveTo(xa + 16, y - h * 0.35)
                p.cubicTo(xa + w * 1.35, y - h * 0.75, xa + w * 1.35, y + h * 0.95, xa + 20, y + h * 0.55)
                D.stroke(c, tpl, p, active, k, color=colr, seed=i)
                maxw = self.col_w * 0.5 if self.portrait else self.col_w * 0.62
                lx = xa + w * 1.15 + 18
                rows, sz = D.fit_block(m.get("text", ""), min(maxw, (SAFE_PORTRAIT[2] if self.portrait else 1880) - lx), 2, size, 30, "Medium")
                for j, r in enumerate(rows):
                    D.draw_text(c, r, lx, y - 6 - (len(rows) - 1 - j) * sz * 1.12, sz, tcol, "Medium")
                if m.get("note") and k > 0.5:
                    nk = ease_out((k - 0.5) / 0.5)
                    cw, _ = D.chip_size(tpl, m["note"], m.get("icon"), 32, 300)
                    cx = max(xa - 30 - cw / 2, (SAFE_PORTRAIT[0] if self.portrait else 60) + cw / 2)
                    D.chip(c, tpl, cx, y + 40, m["note"], m.get("icon"), m.get("tone", "neutral"), nk, spring(nk), 32, max_w=300)
            else:
                d = 1 if xb > xa else -1
                p = skia.Path()
                p.moveTo(xa + d * 16, y)
                p.lineTo(xb - d * 18, y)
                D.stroke(c, tpl, p, active, k, dashed=bool(m.get("dashed")), color=colr, seed=i, flow=None)
                span = abs(xb - xa) - 44
                rows, sz = D.fit_block(m.get("text", ""), span, 2, size, 30, "Medium")
                lx = (xa + xb) / 2
                for j, r in enumerate(rows):
                    D.draw_text(c, r, lx, y - 22 - (len(rows) - 1 - j) * sz * 1.12, sz, tcol, "Medium", "center")
                if m.get("packet", True) and k < 1:
                    D.packet(c, tpl, p, ease_in_out(k), 1.0, colr)
                if m.get("note") and k > 0.5:
                    nk = ease_out((k - 0.5) / 0.5)
                    D.chip(c, tpl, lx, y + 46, m["note"], m.get("icon"), m.get("tone", "neutral"), nk, spring(nk), 32, max_w=span)

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
    """Title card (big title and subtitle over a backdrop, icon badges with labels), or 2-4 benefit cards (icon,
    title, one line) that slide up and fade in, staggered, filling the frame."""
    drift = 0.015

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
            rect = (20.0, 720.0, 1040.0, 527.0) if self.portrait else (120.0, 140.0, 1680.0, 852.0)
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
            c.drawImage(img, 0, 0, skia.SamplingOptions(skia.FilterMode.kLinear), skia.Paint(Alphaf=(0.75 if tpl.dark else 0.6) * ease_out(t / 0.8)))
            c.restore()
        title, sub = sc.spec.get("title", ""), sc.spec.get("subtitle", "")
        k = ease_out((t - 0.05) / 0.6)
        acc = D.text_on(tpl, tpl.conn["active"] if tpl.dark else T["accent"])
        if self.portrait:
            rows, sz = D.fit_block(title, 920, 3, 132, 80, tpl.title_weight)
            y = 300.0 + sz * 0.85
            for j, r in enumerate(rows):
                D.draw_text(c, r, 80, y + (1 - k) * 30 + j * sz * 1.04, sz, col(T["text"], k), tpl.title_weight)
            y += (len(rows) - 1) * sz * 1.04 + 30
            if sub:
                srows, ss = D.fit_block(sub, 920, 3, 48, 36, "Medium")
                k2 = ease_out((t - 0.35) / 0.6)
                for j, r in enumerate(srows):
                    D.draw_text(c, r, 80, y + ss * 1.1 + j * ss * 1.2 + (1 - k2) * 20, ss, col(acc, k2), "Medium")
        else:
            rows, sz = D.fit_block(title, 1080, 2, 150, 88, tpl.title_weight)
            y = 450.0 - (len(rows) - 1) * sz * 0.5
            for j, r in enumerate(rows):
                D.draw_text(c, r, 120, y + (1 - k) * 30 + j * sz * 1.04, sz, col(T["text"], k), tpl.title_weight)
            if sub:
                k2 = ease_out((t - 0.35) / 0.6)
                srows, ss = D.fit_block(sub, 1050, 2, 54, 40, "Medium")
                for j, r in enumerate(srows):
                    D.draw_text(c, r, 124, y + (len(rows) - 1) * sz * 1.04 + 30 + ss * 1.1 + j * ss * 1.2 + (1 - k2) * 20, ss, col(acc, k2), "Medium")
        n = max(1, len(self.items))
        if self.portrait:
            R = 80.0
            slots = [(80 + 920 * (i + 0.5) / n, self.bottom - 200) for i in range(n)]
            maxw = 920 / n - 20
        else:
            R = 66.0
            ys = [250 + i * (760 / max(1, n - 1)) for i in range(n)] if n > 1 else [540]
            slots = [(1600.0, y - 40) for y in ys]
            maxw = 400.0
        for i, it in enumerate(self.items):
            at = self.cue_t(it.get("at"), 0.7 + i * 0.25)
            kk = clamp((t - at) / 0.55)
            if kk <= 0:
                continue
            x, y = slots[i]
            D.badge(c, tpl, assets.resolve(it.get("icon")) or "circle-check", x, y, R, ease_out(kk), 0, 0, spring(kk), tone=it.get("tone"), seed=i)
            D.label_under(c, tpl, it.get("title", ""), x, y + R + 14, maxw, self.S["label"], ease_out(kk))

    def _pill_room(self) -> float:
        """Width the step pill (count cues) takes at the top right, plus a gap; 0 without one."""
        counts = self.sc.events_of("count")
        if not counts:
            return 0.0
        w = max(D.text_width(f"{e.get('n', 1)} / {e.get('total', 4)}", 28, "SemiBold") + D.text_width(e.get("label", ""), 26, "Medium") + 76
                for e in counts)
        return w + 40

    def _benefits(self, c, t):
        sc, tpl, T = self.sc, self.tpl, self.tpl.T
        n = max(1, len(self.items))
        head = sc.spec.get("title")
        hs = self.S["heading"]
        if self.portrait:
            y0 = D.PORTRAIT_BAND[0] + 10
            if head:
                maxw = 940.0 - self._pill_room()                   # leave room for the step pill beside the heading
                one, s1 = D.fit_block(head, maxw, 1, hs, 72, "Bold")
                rows, sz = (one, s1) if D.text_width(one[0], s1, "Bold") <= maxw and not one[0].endswith("…") else                     D.fit_block(head, maxw, 2, hs, 72, "Bold")
                for j, r in enumerate(rows):
                    D.draw_text(c, r, 70, y0 + sz * 0.9 + j * sz * 1.08, sz, col(T["text"], ease_out(t / 0.5)), "Bold")
                y0 += len(rows) * sz * 1.08 + 50
            gap = 36.0
            h = min(330.0, (self.bottom - y0 - (n - 1) * gap) / n)
            y0 += (self.bottom - y0 - (n * h + (n - 1) * gap)) / 2
            rects = [(70.0, y0 + i * (h + gap), 940.0, h) for i in range(n)]
        else:
            gap = 44.0
            w = min(560.0, (1720 - (n - 1) * gap) / n)
            x0 = (1920 - (n * w + (n - 1) * gap)) / 2
            y0 = 90.0
            if head:
                rows, sz = D.fit_block(head, 1600, 2, hs, 72, "Bold")
                for j, r in enumerate(rows):
                    D.draw_text(c, r, 960, y0 + sz * 0.9 + j * sz * 1.08, sz, col(T["text"], ease_out(t / 0.5)), "Bold", "center")
                y0 += len(rows) * sz * 1.08 + 50
            need = 0.0
            for it in self.items:
                trows, ts = D.fit_block(it.get("title", ""), w - 96, 2, 48, 40, "Bold")
                brows, bs = D.fit_block(it.get("text", ""), w - 96, 4, 36, 30)
                need = max(need, 56 + 132 + 50 + len(trows) * ts * 1.1 + 20 + len(brows) * bs * 1.25 + 50)
            h = min(self.bottom - y0 - 20, need)
            y0 += (self.bottom - y0 - 20 - h) / 2
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
                R = 75.0
                D.badge(c, tpl, assets.resolve(it.get("icon")) or "circle-check", x + 40 + R, yy + h / 2, R, k, hl, 0, spring(k), tone=it.get("tone"), seed=i)
                tx, tw = x + 80 + 2 * R, w - (110 + 2 * R)
                trows, ts = D.fit_block(it.get("title", ""), tw, 2, 48, 40, "Bold")
                brows, bs = D.fit_block(it.get("text", ""), tw, 3, 36, 30)
                total = len(trows) * ts * 1.1 + 12 + len(brows) * bs * 1.22
                ty = yy + (h - total) / 2 + ts * 0.85
                for j, r in enumerate(trows):
                    D.draw_text(c, r, tx, ty + j * ts * 1.1, ts, col(T["text"], k), "Bold")
                by = ty + (len(trows) - 1) * ts * 1.1 + 12
                for j, r in enumerate(brows):
                    D.draw_text(c, r, tx, by + (j + 1) * bs * 1.22, bs, col(T["text2"], k))
            else:
                R = 66.0
                D.badge(c, tpl, assets.resolve(it.get("icon")) or "circle-check", x + 48 + R, yy + 56 + R, R, k, hl, 0, spring(k), tone=it.get("tone"), seed=i)
                trows, ts = D.fit_block(it.get("title", ""), w - 96, 2, 48, 40, "Bold")
                ty = yy + 56 + 2 * R + 50 + ts * 0.8
                for j, r in enumerate(trows):
                    D.draw_text(c, r, x + 48, ty + j * ts * 1.1, ts, col(T["text"], k), "Bold")
                brows, bs = D.fit_block(it.get("text", ""), w - 96, 4, 36, 30)
                by = ty + (len(trows) - 1) * ts * 1.1 + 20
                for j, r in enumerate(brows):
                    D.draw_text(c, r, x + 48, by + (j + 1) * bs * 1.25, bs, col(T["text2"], k))


# ================================================================== compare
class Compare(ProTreatment):
    """Hit versus miss.

    With a "panel" in the spec (the default look): the client, the middle tier in a framed container panel (its title,
    e.g. "Edge", with the cache badge inside) and the origin. The hit path runs client -> panel with a check chip and a
    dashed return; the miss path runs on to the origin with an x chip and a dashed return carrying the result. An
    optional footer shows up to 3 icon chips (benefits).

    Without a panel: two lanes animated in parallel (each a title chip, a row of steps, a packet and a result chip)."""
    drift = 0.012

    def layout(self):
        sp = self.sc.spec
        self.has_panel = bool(sp.get("panel"))
        self.lanes = sp.get("lanes", [])[:2]
        if self.has_panel:
            return self._layout_panel()
        self.paths = []
        self.step_pos = []
        self.r = 60.0 if not self.portrait else 68.0
        for li, lane in enumerate(self.lanes):
            steps = lane.get("steps", [])[:5]
            n = max(1, len(steps))
            if self.portrait:
                cx = 290.0 + li * 500.0
                y0, y1 = self.top + 120, self.bottom - 120
                pts = [(cx, y0 + (y1 - y0) * (i + 0.5) / n) for i in range(n)]
            else:
                cy = self.top + 120 + li * (self.bottom - self.top - 120) / 2
                x0, x1 = 460.0, 1800.0
                pts = [(x0 + (x1 - x0) * (i + 0.5) / n, cy) for i in range(n)]
            self.step_pos.append(pts)
            self.paths.append([self._seg(pts[i], pts[i + 1]) for i in range(len(pts) - 1)])

    def _seg(self, a, b):
        R = self.r + 16
        if self.portrait:
            return D.ortho_path([(a[0], a[1] + R), (b[0], b[1] - R)])
        return D.ortho_path([(a[0] + R, a[1]), (b[0] - R, b[1])])

    # ---- panel layout
    def _layout_panel(self):
        sp = self.sc.spec
        self.footer = sp.get("footer", [])[:3]
        self.r = self.S["icon"] / 2
        P = self._pt
        ph = 104 + 2 * self.r + 16 + (60 if (sp.get("panel") or {}).get("label") else 0) + 30
        if self.portrait:
            self.footer_h = D.stat_strip(None, self.tpl, 0, 0, 960, self.footer, 0.0, True) if self.footer else 0.0
            fixed = 2 * self.r + ph + 2 * self.r + (self.footer_h + 40 if self.footer else 0)
            if self.footer and fixed + 80 > self.bottom - self.top:      # the optional footer gives way first
                self.footer, fixed = [], fixed - self.footer_h - 40
            g = max(40.0, (self.bottom - self.top - fixed) / 2)
            y = self.top
            self.client = (540.0, y + self.r)
            y += 2 * self.r + g
            self.panel_rect = (110.0, y, 860.0, ph)
            y += ph + g
            self.origin = (540.0, y + self.r)
            y += 2 * self.r + 40
            self.footer_rect = (60.0, y, 960.0, self.footer_h)
        else:
            self.footer_h = 100.0 if self.footer else 0.0
            bottom = self.bottom - (self.footer_h + 20 if self.footer else 0)
            mid = (self.top + bottom) / 2 - 10
            self.client = (230.0, mid)
            self.origin = (1690.0, mid)
            self.panel_rect = (660.0, mid - ph / 2 - 10, 600.0, ph)
            self.footer_rect = (100.0, bottom + 30, 1720.0, self.footer_h)
        x, y, w, h = self.panel_rect
        self.cache = (x + w / 2, y + 104 + self.r)
        self.paths = P()

    def _pt(self):
        """The four connectors: hit request and its dashed return; miss onward to the origin and its dashed return."""
        cx, cy = self.client
        ox, oy = self.origin
        x, y, w, h = self.panel_rect
        R = self.r + 22
        if self.portrait:
            return dict(
                hit=D.ortho_path([(cx - 70, cy + R), (cx - 70, y - 12)]),
                hit_back=D.ortho_path([(cx + 70, y - 12), (cx + 70, cy + R)]),
                miss=D.ortho_path([(ox - 70, y + h + 12), (ox - 70, oy - R)]),
                miss_back=D.ortho_path([(ox + 70, oy - R), (ox + 70, y + h + 12)]),
            )
        return dict(
            hit=D.ortho_path([(cx + R, cy - 40), (x - 12, cy - 40)]),
            hit_back=D.ortho_path([(x - 12, cy + 40), (cx + R, cy + 40)]),
            miss=D.ortho_path([(x + w + 12, oy - 40), (ox - R, oy - 40)]),
            miss_back=D.ortho_path([(ox - R, oy + 40), (x + w + 12, oy + 40)]),
        )

    def draw(self, c, t):
        if self.has_panel:
            return self._draw_panel(c, t)
        sc, tpl, T = self.sc, self.tpl, self.tpl.T
        start = self.cue_t(sc.spec.get("at"), 0.4)
        for li, lane in enumerate(self.lanes):
            tone = lane.get("tone", "success" if li == 0 else "fail")
            colr = D.role_color(tpl, tone)
            pts = self.step_pos[li]
            ka = ease_out((t - 0.1 - 0.15 * li) / 0.5)
            ttl = lane.get("title", "")
            if self.portrait:
                D.chip(c, tpl, pts[0][0], self.top + 40, ttl, lane.get("icon"), tone, ka, spring(ka), 32, max_w=470)
            else:
                D.chip(c, tpl, 220, pts[0][1], ttl, lane.get("icon"), tone, ka, spring(ka), 32, max_w=360)
            steps = lane.get("steps", [])[:5]
            per = float(sc.spec.get("step_seconds", 0.9)) * sc.motion
            for i, st in enumerate(steps):
                k = clamp((t - start - i * per) / 0.5)
                x, y = pts[i]
                D.badge(c, tpl, assets.resolve(st.get("icon")) or "circle", x, y, self.r, ease_out(k), 0, 0, spring(k),
                        tone=st.get("tone") if tpl.icon["style"] == "pastel" else None, seed=li * 10 + i)
                if self.portrait:
                    rows, sz = D.fit_block(st.get("label", ""), 200, 2, 36, 30, "SemiBold")
                    side = -1 if li == 0 else 1
                    lx = x + side * (self.r + 20)
                    for j, r in enumerate(rows):
                        D.draw_text(c, r, lx, y - (len(rows) - 1) * sz * 0.55 + j * sz * 1.1 + sz * 0.35, sz,
                                    col(T["text"], ease_out(k)), "SemiBold", "right" if side < 0 else "left")
                else:
                    D.label_under(c, tpl, st.get("label", ""), x, y + self.r + 12, 1340 / max(1, len(steps)) - 30, 36, ease_out(k), st.get("sub"))
                if i < len(self.paths[li]):
                    kp = ease_out((t - start - i * per - 0.25) / (per * 0.75))
                    D.stroke(c, tpl, self.paths[li][i], 1.0, kp, color=colr, seed=li * 10 + i)
                    if 0 < kp < 1:
                        D.packet(c, tpl, self.paths[li][i], kp, 1.0, colr)
            res = lane.get("result")
            if res:
                kr = ease_out((t - start - len(steps) * per) / 0.45)
                x, y = pts[-1]
                ic = res.get("icon") or {"success": "check", "fail": "x"}.get(tone)
                if self.portrait:
                    D.chip(c, tpl, x, y + self.r + 70, res.get("label", ""), ic, res.get("tone", tone), kr, spring(kr), 32, max_w=460)
                else:
                    D.chip(c, tpl, (pts[0][0] + pts[-1][0]) / 2, y + self.r + 130, res.get("label", ""), ic, res.get("tone", tone), kr, spring(kr), 32, max_w=700)

    def _draw_panel(self, c, t):
        sc, tpl, T = self.sc, self.tpl, self.tpl.T
        sp = sc.spec
        start = self.cue_t(sp.get("at"), 0.4)
        per = float(sp.get("step_seconds", 0.8)) * sc.motion
        lanes = {("hit" if (l.get("tone") or "success") == "success" else "miss"): l for l in self.lanes}
        hit, miss = lanes.get("hit", {}), lanes.get("miss", {})
        pal = (sp.get("panel") or {})
        x, y, w, h = self.panel_rect
        ka = ease_out((t - 0.15) / 0.5)
        D.panel(c, tpl, x, y, w, h, pal.get("title", "Edge"), ka, seed=5, sub=pal.get("sub"))
        cxp, cyp = self.cache
        D.badge(c, tpl, assets.resolve(pal.get("icon")) or "database-zap", cxp, cyp, self.r, ka, 0, 0, spring(ka),
                tone=pal.get("tone") or ("amber" if tpl.icon["style"] in ("pastel", "tint") else None), seed=6)
        if pal.get("label"):
            D.label_under(c, tpl, pal["label"], cxp, cyp + self.r + 14, w - 60, self.S["label"], ka)
        for (px, py), ent, i in ((self.client, sp.get("client") or {}, 0), (self.origin, sp.get("origin") or {}, 1)):
            k = ease_out((t - 0.2 - 0.15 * i) / 0.5)
            D.badge(c, tpl, assets.resolve(ent.get("icon")) or ("user" if i == 0 else "server-cog"), px, py, self.r, k, 0, 0, spring(k),
                    tone=ent.get("tone") or ({"0": "amber", "1": "green"}[str(i)] if tpl.icon["style"] in ("pastel", "tint") else None), seed=i)
            lab = ent.get("label", "Client" if i == 0 else "Origin")
            if self.portrait:
                lx = px + self.r + 120
                rows, sz = D.fit_block(lab, SAFE_PORTRAIT[2] - lx, 2, self.S["label"], 36, "SemiBold")
                for j, r in enumerate(rows):
                    D.draw_text(c, r, lx, py + sz * 0.35 - (len(rows) - 1) * sz * 0.55 + j * sz * 1.1, sz, col(T["text"], k), "SemiBold")
            else:
                D.label_under(c, tpl, lab, px, py + self.r + 14, 330, self.S["label"], k, ent.get("sub"))
        succ, fail = D.role_color(tpl, "success"), D.role_color(tpl, "fail")
        info = D.role_color(tpl, miss.get("result", {}).get("tone", "info"))
        steps = [("hit", succ, False, hit.get("title", "Cache hit"), "check", "success"),
                 ("hit_back", succ, True, None, None, None),
                 ("miss", fail, False, miss.get("title", "Cache miss"), "x", "fail"),
                 ("miss_back", info, True, (miss.get("result") or {}).get("label"), (miss.get("result") or {}).get("icon") or "refresh-cw",
                  (miss.get("result") or {}).get("tone", "info"))]
        for i, (key, colr, dashed, label, icon, tone) in enumerate(steps):
            path = self.paths[key]
            kp = ease_out((t - start - i * per) / (per * 0.8))
            D.stroke(c, tpl, path, 1.0, kp, dashed=dashed, color=colr, seed=i, flow=t if dashed else None)
            if 0 < kp < 1:
                D.packet(c, tpl, path, kp, 1.0, colr)
            if label and kp > 0.6:
                kc = ease_out((kp - 0.6) / 0.4)
                mx, my, _, _ = D.point_at(path, 0.5)
                cw, ch = D.chip_size(tpl, label, icon, 32, 460)
                if self.portrait:
                    side = -1 if key in ("hit", "miss") else 1
                    cxx = mx + side * (cw / 2 + 30)
                    cxx = clamp(cxx, SAFE_PORTRAIT[0] + cw / 2, SAFE_PORTRAIT[2] - cw / 2)
                    D.chip(c, tpl, cxx, my, label, icon, tone, kc, spring(kc), 32, max_w=460)
                else:
                    off = -(ch / 2 + 26) if key in ("hit", "miss") else (ch / 2 + 26)
                    D.chip(c, tpl, mx, my + off, label, icon, tone, kc, spring(kc), 32, max_w=460)
        if self.footer:
            kf = ease_out((t - start - 4 * per) / 0.5)
            fx, fy, fw, fh = self.footer_rect
            if self.portrait:
                D.stat_strip(c, tpl, fx, fy, fw, self.footer, kf, True)
            else:
                n = len(self.footer)
                for i, it in enumerate(self.footer):
                    D.chip(c, tpl, fx + fw * (i + 0.5) / n, fy + fh / 2, it.get("label", ""), it.get("icon"), it.get("tone", "info"),
                           ease_out(kf - 0.1 * i), spring(clamp(kf - 0.1 * i)), 34, max_w=fw / n - 30)


# ================================================================== stat
class Stat(ProTreatment):
    """One big number (counting up) or short phrase, a supporting icon, a label and the source line. The spec must
    give the value and its source; nothing is computed or estimated here."""
    drift = 0.015

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
        acc = D.text_on(tpl, tpl.conn["active"] if tpl.dark else T["accent"])
        if self.portrait:
            label_rows, ls = D.fit_block(sc.spec.get("label", ""), 900, 3, 60, 44, "SemiBold")
            src = sc.spec.get("source", "")
            srows, ss = D.fit_block("Source: " + src, 900, 3, 34, 30) if src else ([], 30)
            sz = D.fit_size(final, 920, 320, 120, "Bold")
            R = 120.0
            total = 2 * R + 60 + sz * 0.8 + 60 + len(label_rows) * ls * 1.2 + (40 + len(srows) * ss * 1.25 if src else 0)
            y = self.top + max(0.0, (self.bottom - self.top - total) / 2)
            D.badge(c, tpl, assets.resolve(sc.spec.get("icon")) or "gauge", 540, y + R, R, ki, 0, 0, spring(ki), tone=sc.spec.get("tone"))
            y += 2 * R + 60 + sz * 0.8
            D.draw_text(c, shown, 540, y, sz, col(acc, ease_out((t - at) / 0.4)), "Bold", "center")
            y += 60
            for j, r in enumerate(label_rows):
                D.draw_text(c, r, 540, y + ls * 0.9 + j * ls * 1.2, ls, col(T["text"], ease_out((t - at - 0.3) / 0.5)), "SemiBold", "center")
            y += len(label_rows) * ls * 1.2 + 40
            for j, r in enumerate(srows):
                D.draw_text(c, r, 540, y + ss + j * ss * 1.25, ss, col(T["text2"], ease_out((t - at - 0.6) / 0.5)), "Regular", "center")
        else:
            D.badge(c, tpl, assets.resolve(sc.spec.get("icon")) or "gauge", 440, 450, 120, ki, 0, 0, spring(ki), tone=sc.spec.get("tone"))
            sz = D.fit_size(final, 1100, 260, 120, "Bold")
            D.draw_text(c, shown, 660, 530, sz, col(acc, ease_out((t - at) / 0.4)), "Bold")
            rows, ls = D.fit_block(sc.spec.get("label", ""), 1100, 2, 56, 40, "SemiBold")
            for j, r in enumerate(rows):
                D.draw_text(c, r, 664, 640 + j * ls * 1.2, ls, col(T["text"], ease_out((t - at - 0.3) / 0.5)), "SemiBold")
            src = sc.spec.get("source", "")
            if src:
                srows, ss = D.fit_block("Source: " + src, 1640, 2, 30, 30)
                for j, r in enumerate(srows):
                    D.draw_text(c, r, 140, 920 + j * ss * 1.25, ss, col(T["text2"], ease_out((t - at - 0.6) / 0.5)))


PRO_TREATMENTS = {"iconflow": IconFlow, "map": MapScene, "sequence": Sequence, "cards": Cards, "compare": Compare, "stat": Stat}
