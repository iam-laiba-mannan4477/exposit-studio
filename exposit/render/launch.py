"""Launch-control-room scenes for "How do you ship a 212 GB game to millions at midnight?" (dev_scene kinds ml_*),
in the midnight-launch template: clean neon-line diagrams on night navy-purple. No game art, no logos, no mascot.
General launch techniques are drawn as "how a launch like this works", not as anyone's internal architecture.
Labels >= 30 px; key text between y 230 and 1530. Bound onto devscenes.Scene like story.SCENES."""
from __future__ import annotations
import functools, math
import skia
from . import assets, design as D
from .design import col, clamp, lerp, ease_out, spring
from .devscenes import W, H, txt, tw, box, io, chip

L = dict(bg="#0D0B1A", panel="#1A1630", border="#2E2850", text="#F4F1EA", text2="#A9A3C2", orange="#FF8A3D",
         pink="#FF4F9A", teal="#3DD6D0", red="#E5604D")


def pal():
    return L


@functools.lru_cache(maxsize=1)
def land_dots(step: float = 3.0):
    """(lon, lat) of land points on a coarse grid (Natural Earth land, already in the studio's assets)."""
    from .motion import _land_cells, _is_land
    cells = _land_cells()
    out = []
    lat = -54.0
    while lat < 76:
        lon = -178.0
        while lon < 180:
            if _is_land(cells, lon, lat):
                out.append((lon, lat))
            lon += step
        lat += step * 0.8
    return tuple(out)


def map_xy(lon, lat, x0=40.0, y0=600.0, w=1000.0):
    x, y = assets.robinson(lon, lat)
    return x0 + (x + 1) / 2 * w, y0 + (0.51 - y) * w * 0.5


def node(c, x, y, label, icon=None, colr=None, a=1.0, w=None, sub=None, glow=0.0, size=34):
    colr = colr or L["teal"]
    w = w or tw(label, size, "SemiBold") + (110 if icon else 60)
    h = 96 if not sub else 132
    if glow > 0:
        D.halo(c, x, y, max(w, h) * 0.7, colr, 0.22 * glow * a)
    box(c, x - w / 2, y - h / 2, w, h, 20, L["panel"], colr, 3, a, shadow=True)
    tx = x - w / 2 + (82 if icon else 30)
    if icon:
        assets.draw_icon(c, icon, x - w / 2 + 44, y - (14 if sub else 0), 36, colr, a, 2.2)
    txt(c, label, tx, y + (size * 0.36 if not sub else -6), L["text"], a, size, "SemiBold")
    if sub:
        txt(c, sub, tx, y + 40, colr, a, 30, "Medium")
    return w, h


def arrow(c, x0, y0, x1, y1, k, colr, a=1.0, width=4.0):
    if k <= 0:
        return
    xe, ye = lerp(x0, x1, k), lerp(y0, y1, k)
    c.drawLine(x0, y0, xe, ye, D.paint(col(colr, a), width))
    if k > 0.97:
        ang = math.atan2(y1 - y0, x1 - x0)
        D.arrowhead(c, x1, y1, math.cos(ang), math.sin(ang), 18, col(colr, a))


def server(c, x, y, a=1.0, red=0.0, shake=0.0, t=0.0):
    dx = shake * 10 * math.sin(t * 80)
    colr = D.mix(L["teal"], L["red"], red)
    if red > 0:
        D.halo(c, x + dx, y, 200, L["red"], 0.35 * red * a)
    box(c, x - 70 + dx, y - 90, 140, 180, 16, L["panel"], colr, 3, a, shadow=True)
    for i in range(4):
        c.drawLine(x - 46 + dx, y - 54 + i * 36, x + 46 + dx, y - 54 + i * 36, D.paint(col(colr, 0.8 * a), 3))
        c.drawCircle(x + 34 + dx, y - 66 + i * 36, 5, D.paint(col(colr, a)))


# ------------------------------------------------------------------ S1
def ml_hook(self, c, t):
    fire = self.w("midnight.", 3.0, -0.2)
    # the counter
    n = int(212 * ease_out(clamp(t / 1.1)))
    f = D.make_font(170, "Bold")
    s = f"{n} GB"
    D.put_text(c, s, W / 2 - f.measureText("212 GB") / 2, 440, f, col(L["text"]))
    # the sales estimate, with its source, on the word
    ks = io((t - self.at(self.sp.get("sold_at"), 1e9)) / 0.4)
    if ks > 0:
        txt(c, "32.5 million sold before release", W / 2, 520, L["orange"], ks, 40, "SemiBold", align="center")
        txt(c, "Take-Two SEC filing", W / 2, 566, L["text2"], ks, 30, align="center")
    # a field of console dots across a dark map, lighting west to east
    dots = land_dots()
    for lon, lat in dots:
        k = clamp((t - 0.3 - (lon + 180) / 360 * 1.2) / 0.3)
        if k <= 0:
            continue
        x, y = map_xy(lon, lat)
        c.drawCircle(x, y, 3.2, D.paint(col(L["teal"], 0.55 * k)))
    # the clock hits 00:00
    # every dot fires at one server
    sx, sy = 540.0, 1290.0
    if t > fire:
        q = clamp((t - fire) / 0.6)
        for i, (lon, lat) in enumerate(dots[::3]):
            x, y = map_xy(lon, lat)
            c.drawLine(x, y, lerp(x, sx, q), lerp(y, sy - 90, q), D.paint(col(L["teal"], 0.10), 1.5))
    clock = "23:59" if t < fire else "00:00"
    cf = D.make_font(64, "Regular", mono=True)
    cw_ = cf.measureText(clock)
    box(c, W / 2 - cw_ / 2 - 24, 1020, cw_ + 48, 84, 16, L["bg"], L["orange"] if t >= fire else L["border"], 2, 1)
    D.put_text(c, clock, W / 2 - cw_ / 2, 1084, cf, col(L["orange"] if t >= fire else L["text2"]))
    hit = clamp((t - fire - 0.55) / 0.3)
    server(c, sx, sy, 1.0, red=hit, shake=hit * (1 - clamp((t - fire - 1.6) / 0.6)), t=t)


# ------------------------------------------------------------------ S2
DAYS = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]


def ml_preload(self, c, t):
    x0, x1, y = 90.0, 990.0, 520.0
    txt(c, "Preload window", 90, 380, L["text2"], io(t / 0.4), 34, "SemiBold")
    c.drawLine(x0, y, x1, y, D.paint(col(L["border"]), 6))
    fill = clamp((t - 0.4) / max(1.0, self.dur * 0.55))
    c.drawLine(x0, y, lerp(x0, x1 - (x1 - x0) / 9, fill), y, D.paint(col(L["teal"]), 10))
    for i, d in enumerate(DAYS):
        x = lerp(x0, x1, i / 9)
        launch = d == 19
        c.drawCircle(x, y, 10 if launch else 7, D.paint(col(L["orange"] if launch else (L["teal"] if fill * 9 >= i else L["text2"]))))
        if d in (10, 13, 16, 19):
            txt(c, f"Nov {d}", x, y + 56, L["orange"] if launch else L["text"], 1, 30, "Medium", align="center")
    txt(c, "launch", x1, y - 30, L["orange"], 1, 30, "SemiBold", align="center")
    # the comparison graph: one spike at midnight vs the same bytes spread over the window
    gx0, gy0, gw, gh = 110.0, 760.0, 860.0, 520.0
    k = io((t - 0.8) / 0.5)
    c.drawLine(gx0, gy0 + gh, gx0 + gw, gy0 + gh, D.paint(col(L["border"], k), 3))
    c.drawLine(gx0, gy0, gx0, gy0 + gh, D.paint(col(L["border"], k), 3))
    txt(c, "traffic", gx0 + 14, gy0 + 30, L["text2"], k, 30)
    q = io((t - 1.2) / 1.4)
    spike = skia.Path()
    spike.moveTo(gx0, gy0 + gh - 4)
    for i in range(41):
        xx = gx0 + gw * i / 40
        yy = gy0 + gh - 4 - (gh - 40) * math.exp(-((i - 38) / 1.6) ** 2)
        spike.lineTo(xx, yy)
    part, _ = D.trim(spike, 0.0, max(0.001, q))
    pp = D.paint(col(L["red"], 0.9), 4)
    pp.setPathEffect(skia.DashPathEffect.Make([14, 10], 0))
    c.drawPath(part, pp)
    flat = skia.Path()
    flat.moveTo(gx0, gy0 + gh - 4)
    for i in range(41):
        xx = gx0 + gw * i / 40
        yy = gy0 + gh - 4 - (gh * 0.22) * clamp(i / 3) * (1 if i < 38 else 0.8)
        flat.lineTo(xx, yy)
    part2, _ = D.trim(flat, 0.0, max(0.001, io((t - 1.6) / 1.4)))
    c.drawPath(part2, D.paint(col(L["teal"]), 5))
    chip(c, gx0 + 20, gy0 + gh + 70, "all at midnight", L["red"], k, fill=L["bg"])
    chip(c, gx0 + 420, gy0 + gh + 70, "spread over the window", L["teal"], k, fill=L["bg"])


# ------------------------------------------------------------------ S4
def ml_comcast(self, c, t):
    gx0, gy0, gw, gh = 100.0, 520.0, 880.0, 640.0
    box(c, gx0 - 30, gy0 - 60, gw + 60, gh + 120, 20, L["panel"], L["border"], 2, 1, shadow=True)
    c.save()
    c.clipRect(skia.Rect.MakeXYWH(gx0 - 30, gy0 - 130, gw + 60, gh + 190))
    for i in range(5):
        yy = gy0 + gh * i / 4
        c.drawLine(gx0, yy, gx0 + gw, yy, D.paint(col(L["border"], 0.7), 2))
    q = io(clamp(0.2 + t / max(1.0, self.dur * 0.55)))       # starts part-drawn, so the chart is never empty
    path = skia.Path()
    path.moveTo(gx0, gy0 + gh * 0.8)
    for i in range(1, 61):
        xx = gx0 + gw * i / 60
        base = 0.8 - 0.25 * math.sin(i / 60 * math.pi * 6) * 0.3 - 0.1 * i / 60
        surge = max(0.0, (i - 34) / 26) ** 2 * 1.3                 # climbs off the chart's top edge
        path.lineTo(xx, gy0 + gh * (base - surge))
    part, _ = D.trim(path, 0.0, max(0.001, q))
    c.drawPath(part, D.paint(col(L["teal"]), 5))
    c.restore()
    k0 = io(t / 0.4)                                        # context on screen from the first frame
    txt(c, "Comcast network traffic", gx0, gy0 - 90, L["text"], k0, 40, "SemiBold")
    txt(c, "traffic", gx0 + 14, gy0 + 34, L["text2"], k0, 30)
    bx0 = gx0 + gw * 0.58
    c.drawLine(bx0, gy0 + gh + 24, gx0 + gw, gy0 + gh + 24, D.paint(col(L["orange"], k0), 4))
    c.drawLine(bx0, gy0 + gh + 12, bx0, gy0 + gh + 36, D.paint(col(L["orange"], k0), 4))
    c.drawLine(gx0 + gw, gy0 + gh + 12, gx0 + gw, gy0 + gh + 36, D.paint(col(L["orange"], k0), 4))
    txt(c, "first 48 h of preloads", (bx0 + gx0 + gw) / 2, gy0 + gh + 74, L["orange"], k0, 30, "SemiBold", align="center")
    k = io((t - self.w("largest", 2.0, -0.1)) / 0.4)
    box(c, 90, 1300, 900, 160, 18, L["bg"], L["orange"], 3, k)
    txt(c, "largest single event in", 120, 1360, L["text"], k, 40, "SemiBold")
    txt(c, "its network history", 120, 1420, L["orange"], k, 40, "SemiBold")
    txt(c, "Comcast, via Newsweek", 90, 1505, L["text2"], k, 30)


# ------------------------------------------------------------------ S6
def ml_delta(self, c, t):
    # the full game as a grid of chunks; only the changed ones glow and ship
    gx, gy, cols_, rows_, cw = 90.0, 470.0, 10, 8, 52.0
    box(c, gx - 20, gy - 70, cols_ * cw + 40, rows_ * cw + 110, 18, L["panel"], L["border"], 2, 1, shadow=True)
    txt(c, "212 GB full game", gx, gy - 20, L["text"], 1, 34, "SemiBold")
    changed = {(2, 1), (7, 2), (4, 4), (8, 6), (1, 6), (5, 7)}
    glow = io((t - self.w("ship", 1.0)) / 0.5)
    for i in range(cols_):
        for j in range(rows_):
            on = (i, j) in changed
            colr = L["orange"] if on and glow > 0 else L["border"]
            c.drawRect(skia.Rect.MakeXYWH(gx + i * cw + 4, gy + j * cw + 4 + 20, cw - 8, cw - 8),
                       D.paint(col(colr, 1.0 if not on else 0.4 + 0.6 * glow)))
    # the patch slice: only the changed chunks travel
    px, py = 720.0, 600.0
    ship = io((t - self.w("patch", 2.0)) / 0.8)
    box(c, px, py, 280, 120, 18, L["panel"], L["orange"], 3, ship, shadow=True)
    txt(c, "1.07 GB", px + 30, py + 56, L["orange"], ship, 40, "Bold")
    txt(c, "patch (PS5)", px + 30, py + 98, L["text2"], ship, 30)
    for n, (i, j) in enumerate(sorted(changed)):
        q = io((t - self.w("patch", 2.0) - 0.08 * n) / 0.6)
        if 0 < q < 1:
            sx, sy = gx + i * cw + cw / 2, gy + j * cw + cw / 2 + 20
            c.drawRect(skia.Rect.MakeXYWH(lerp(sx, px + 140, q) - 14, lerp(sy, py + 60, q) - 14, 28, 28), D.paint(col(L["orange"])))
    arrow(c, px + 140, py + 140, px + 140, 1100, io((t - self.w("patch", 2.0) - 0.8) / 0.5), L["orange"])
    k2 = io((t - self.w("patch", 2.0) - 1.2) / 0.4)
    node(c, px + 140, 1180, "player", "monitor", L["orange"], k2)
    txt(c, "not another 212 GB", 90, 1420, L["text2"], io((t - self.w("another", 3.0)) / 0.4), 34, "SemiBold")


# ------------------------------------------------------------------ S7
def ml_licence(self, c, t):
    gate_x, gate_y = 760.0, 820.0
    # the gate with its server
    flick = self.w("struggled,", 2.0, -0.2)
    bad = t > flick
    red = (0.5 + 0.5 * math.sin(t * 22)) if bad else 0.0
    for px in (gate_x - 120, gate_x + 120):
        box(c, px - 16, gate_y - 160, 32, 320, 8, L["panel"], L["red"] if bad else L["teal"], 3, 1)
    c.drawRect(skia.Rect.MakeXYWH(gate_x - 120, gate_y - 170, 240, 14), D.paint(col(L["red"] if bad else L["teal"])))
    txt(c, "licence check", gate_x, gate_y + 220, L["text"], 1, 34, "SemiBold", align="center")
    server(c, gate_x, 470, 1.0, red=red if bad else 0.0, t=t)
    if bad:
        chip(c, gate_x - 150, 610, "PSN disrupted", L["red"], io((t - flick) / 0.3), fill=L["bg"])
    # a console with a full download walks up to the gate and waits
    walk = io(t / 1.4)
    cx = lerp(120, 470, walk)
    box(c, cx - 110, gate_y - 70, 220, 140, 18, L["panel"], L["teal"], 3, 1, shadow=True)
    assets.draw_icon(c, "monitor", cx, gate_y - 20, 50, L["teal"], 1, 2.2)
    c.drawRect(skia.Rect.MakeXYWH(cx - 80, gate_y + 34, 160, 12), D.paint(col(L["teal"])))
    txt(c, "100% downloaded", cx, gate_y + 110, L["text2"], 1, 30, align="center")
    if bad and t > flick + 0.4:                        # a waiting spinner
        a0 = (t * 360) % 360
        c.drawArc(skia.Rect.MakeXYWH(cx - 26, gate_y - 140, 52, 52), a0, 270, False, D.paint(col(L["orange"]), 5))
    # the exception: offline play on, one console passes
    ex = self.w("start.", self.dur - 1.6, -0.6)
    k = io((t - ex) / 0.4)
    if k > 0:
        tx, ty = 100.0, 1240.0
        box(c, tx, ty - 40, 420, 80, 40, L["panel"], L["teal"], 2, k)
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(tx + 20, ty - 20, 70, 40), 20, 20), D.paint(col(L["teal"], k)))
        c.drawCircle(tx + 70, ty, 15, D.paint(col(L["bg"], k)))
        txt(c, "offline play: on", tx + 110, ty + 11, L["text"], k, 32, "Medium")
        q = io((t - ex - 0.4) / 1.0)
        px = lerp(330, 1000, q)
        box(c, px - 60, 1360 - 40, 120, 80, 14, L["panel"], L["teal"], 2, k * (1 - clamp((q - 0.85) / 0.15)))
        assets.draw_icon(c, "monitor", px, 1360, 36, L["teal"], k * (1 - clamp((q - 0.85) / 0.15)), 2)
        txt(c, "the exception", 600, 1460, L["text2"], k, 30, align="center")


# ------------------------------------------------------------------ S8
LESSONS = [("1", "Move the bytes early", "download"), ("2", "Stagger the spike", "clock"), ("3", "Find the single dependency", "lock")]


def ml_lesson(self, c, t):
    words = ("early,", "spike,", "dependency")
    for i, (n, text, ic) in enumerate(LESSONS):
        t0 = 0.1 if i == 0 else self.w(words[i - 1], 1.0 + i, 0.2)
        k = io((t - t0) / 0.45)
        if k <= 0:
            continue
        y = 430 + i * 230
        x = 60 + (1 - k) * 500
        colr = L["red"] if i == 2 else L["orange"]
        box(c, x, y, 960, 190, 22, L["panel"], colr, 3, k, shadow=True)
        c.drawCircle(x + 90, y + 95, 50, D.paint(col(colr, k)))
        txt(c, n, x + 90, y + 115, L["bg"], k, 54, "Bold", align="center")
        assets.draw_icon(c, ic if ic != "download" else "cloud-download", x + 890, y + 95, 54, colr, k, 2.2)
        txt(c, text, x + 170, y + 110, L["text"], k, 42, "SemiBold")
    # card 3 links back to the red licence gate
    kk = io((t - self.w("dependency", 3.0, 0.4)) / 0.5)
    if kk > 0:
        gx, gy = 540.0, 1300.0
        arrow(c, 540, 430 + 2 * 230 + 190, 540, gy - 110, kk, L["red"])
        for px in (gx - 70, gx + 70):
            box(c, px - 10, gy - 90, 20, 180, 6, L["panel"], L["red"], 3, kk)
        c.drawRect(skia.Rect.MakeXYWH(gx - 70, gy - 96, 140, 10), D.paint(col(L["red"], kk)))
        txt(c, "licence check", gx, gy + 140, L["red"], kk, 32, "SemiBold", align="center")


# ------------------------------------------------------------------ S9 (save-worthy)
PIPE = [("Build & release", "build farm, CI", "workflow"), ("Origin", "the master copy", "server"),
        ("CDN edges", "copies near players", "network"), ("Preload window", "bytes move early", "cloud-download"),
        ("Rolling midnight unlock", "time zone by time zone", "clock"),
        ("Licence check", "single point of failure", "lock"), ("Player", "", "monitor")]


def ml_pipeline(self, c, t):
    top, step = 300.0, 172.0
    for i, (name, sub, ic) in enumerate(PIPE):
        k = io((t - 0.15 - 0.22 * i) / 0.4)
        y = top + i * step + 60
        spof = name == "Licence check"
        colr = L["red"] if spof else (L["orange"] if i in (0, 6) else L["teal"])
        if i > 0:
            arrow(c, 540, y - step + 60 + 66, 540, y - 66, k, L["text2"], 1, 3)
        node(c, 540, y, name, ic, colr, k, w=760, sub=sub or None, glow=1.0 if spof else 0.0, size=36)
    if t > 0.15 + 0.22 * 7:
        txt(c, "how a launch like this works", 540, 1520, L["text2"], io((t - 1.9) / 0.4), 30, align="center")


SCENES = dict(ml_hook=ml_hook, ml_preload=ml_preload, ml_comcast=ml_comcast, ml_delta=ml_delta,
              ml_licence=ml_licence, ml_lesson=ml_lesson, ml_pipeline=ml_pipeline)
