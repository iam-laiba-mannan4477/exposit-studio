"""Motion effects: ten reusable "scroll effects" translated to video, in 9:16 and 16:9.

Two kinds:
- Wrapper effects, listed in any scene's "effects": [{"type": ...}] and applied around its treatment by the engine:
  parallax (depth layers behind the scene), pinned_heading (the heading stays while the content scrolls under it),
  focus_frame (a highlight frame slides between elements on spoken words, dimming the rest).
- Content effects, drawn by the "motion" treatment ({"treatment": "motion", "effect": ...}): card_zoom_3d,
  line_reveal, marquee, card_carousel, model_3d, stacking_cards, scroll_demo.

3D is done here, without a GPU: card corners are projected with a pinhole camera and the card image is mapped onto
that quad (a projective matrix from skia's polyToPoly); the low-poly models are projected triangles with flat shading,
back-face culling and a painter's depth sort, meshes built once and cached.
"""
from __future__ import annotations
import functools, math
import skia
from . import assets, design as D
from .design import col, clamp, lerp, ease_out, ease_in_out, spring
from .pro import ProTreatment

WRAPPERS = ("parallax", "pinned_heading", "focus_frame")
CONTENT = ("card_zoom_3d", "line_reveal", "marquee", "card_carousel", "model_3d", "stacking_cards", "scroll_demo",
           "globe", "flat_map", "split_compare", "cache_split", "project_tree", "dev_scene")
EFFECTS = WRAPPERS + CONTENT
MODELS = ("server_rack", "cube", "globe", "database", "datacenter")


# ================================================================== 3D helpers
def rot(p, ax: float, ay: float, az: float = 0.0):
    x, y, z = p
    if ax:
        y, z = y * math.cos(ax) - z * math.sin(ax), y * math.sin(ax) + z * math.cos(ax)
    if ay:
        x, z = x * math.cos(ay) + z * math.sin(ay), -x * math.sin(ay) + z * math.cos(ay)
    if az:
        x, y = x * math.cos(az) - y * math.sin(az), x * math.sin(az) + y * math.cos(az)
    return x, y, z


def project(p, cx: float, cy: float, f: float = 1400.0):
    """Pinhole projection of a camera-space point (z grows away from the viewer) to the screen."""
    x, y, z = p
    k = f / max(1.0, f + z)
    return cx + x * k, cy + y * k, k


def quad_matrix(w: float, h: float, quad, perspective: bool = False) -> skia.Matrix:
    """The matrix that maps the rectangle (0, 0, w, h) onto the screen quad (tl, tr, br, bl). By default an affine fit
    through the quad's centre and edge midpoints: CPU raster draws affine images several times faster than projective
    ones, and at the angles used here the difference is a slight lack of foreshortening. perspective=True is exact."""
    m = skia.Matrix()
    if perspective:
        m.setPolyToPoly([skia.Point(0, 0), skia.Point(w, 0), skia.Point(w, h), skia.Point(0, h)], [skia.Point(*q) for q in quad])
        return m
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = quad
    cx, cy = (x0 + x1 + x2 + x3) / 4, (y0 + y1 + y2 + y3) / 4
    rx, ry = ((x1 + x2) - (x0 + x3)) / 4, ((y1 + y2) - (y0 + y3)) / 4        # half the width vector
    dx, dy = ((x3 + x2) - (x0 + x1)) / 4, ((y3 + y2) - (y0 + y1)) / 4        # half the height vector
    m.setAll(2 * rx / w, 2 * dx / h, cx - rx - dx, 2 * ry / w, 2 * dy / h, cy - ry - dy, 0, 0, 1)
    return m


def card_quad(w: float, h: float, center3, ax: float, ay: float, cx: float, cy: float, f: float = 1400.0):
    """Screen quad of a w x h card centred at center3 (camera space) and rotated by (ax, ay); also its depth scale."""
    corners = [(-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0)]
    out = []
    for p in corners:
        x, y, z = rot(p, ax, ay)
        x, y, z = x + center3[0], y + center3[1], z + center3[2]
        sx, sy, _ = project((x, y, z), cx, cy, f)
        out.append((sx, sy))
    return out, f / max(1.0, f + center3[2])


def draw_image_quad(c, img: skia.Image, w: float, h: float, quad, alpha: float = 1.0, shade: float = 0.0,
                    shade_color: str = "#000000") -> None:
    """Maps img onto the quad. `alpha` fades it (entrances); `shade` darkens it while keeping it opaque (depth)."""
    c.save()
    c.concat(quad_matrix(w, h, quad))
    c.drawImageRect(img, skia.Rect.MakeWH(img.width(), img.height()), skia.Rect.MakeWH(w, h),
                    skia.SamplingOptions(skia.FilterMode.kLinear), skia.Paint(Alphaf=alpha) if alpha < 0.999 else None)
    if shade > 0.01:
        c.drawRoundRect(skia.Rect.MakeXYWH(6, 6, w - 12, h - 12), 18, 18, D.paint(col(shade_color, clamp(shade) * alpha)))
    c.restore()


_card_cache: dict = {}
BIG = dict(R=100.0, title=72, body=44, pad=56)              # the zoomed hero card
SMALL = dict(R=70.0, title=50, body=34, pad=40)


def card_height(item: dict, w: float, big: bool = False) -> float:
    """The height a card needs for its icon, title and body at width w: cards are sized to their content."""
    S = BIG if big else SMALL
    h = S["pad"] + 2 * S["R"] + 30
    rows, sz = D.fit_block(item.get("title", ""), w - 2 * S["pad"], 2, S["title"], 48, "Bold")
    h += len(rows) * sz * 1.08 + 12
    if item.get("text"):
        brows, bs = D.fit_block(item["text"], w - 2 * S["pad"] - 10, 3, S["body"], 30)
        h += len(brows) * bs * 1.2 + 10
    return h + S["pad"]


def card_image(tpl, w: int, h: int, item: dict, key, accent: bool = False, big: bool = False) -> skia.Image:
    """A card (icon, title, body) rendered once into an image at 1.5x, for mapping onto a 3D quad."""
    k = (tpl.name, w, h, key, accent, big)
    img = _card_cache.get(k)
    if img is not None:
        return img
    s = 1.5
    surf = skia.Surface(int(w * s), int(h * s))
    c = surf.getCanvas()
    c.clear(skia.ColorTRANSPARENT)
    c.scale(s, s)
    T = tpl.T
    r0 = tpl.card["radius"]                                   # opaque backing: cards in 3D must not show through
    c.drawRoundRect(skia.Rect.MakeXYWH(6, 6, w - 12, h - 12), r0, r0, D.paint(col(T["bg0"] if tpl.dark else "#FFFFFF")))
    D.card(c, tpl, 6, 6, w - 12, h - 12, 1.0, 1.0 if accent else 0.0, 0.0, seed=hash(str(key)) % 97)
    S = BIG if big else SMALL
    R = min(S["R"], h * 0.2)
    top = max(0.0, (h - card_height(item, w, big)) / 2)       # content centred when the card is taller than it
    D.badge(c, tpl, assets.resolve(item.get("icon")) or "box", w / 2, top + S["pad"] + R, R, 1.0, tone=item.get("tone"), seed=3)
    rows, sz = D.fit_block(item.get("title", ""), w - 2 * S["pad"], 2, S["title"], 48, "Bold")
    y = top + S["pad"] + 2 * R + 30
    for j, r in enumerate(rows):
        D.draw_text(c, r, w / 2, y + sz * 0.9 + j * sz * 1.08, sz, col(T["text"]), "Bold", "center")
    y += len(rows) * sz * 1.08 + 12
    if item.get("text"):
        brows, bs = D.fit_block(item["text"], w - 2 * S["pad"] - 10, 3, S["body"], 30)
        for j, r in enumerate(brows):
            D.draw_text(c, r, w / 2, y + bs + j * bs * 1.2, bs, col(T["text2"]), "Regular", "center")
    img = surf.makeImageSnapshot()
    if len(_card_cache) > 256:
        _card_cache.clear()
    _card_cache[k] = img
    return img


# ================================================================== low-poly meshes (cached)
def _box(x0, y0, z0, x1, y1, z1, tag=0):
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    quads = [(0, 1, 2, 3), (5, 4, 7, 6), (4, 0, 3, 7), (1, 5, 6, 2), (4, 5, 1, 0), (3, 2, 6, 7)]
    tris = []
    for a, b, c_, d in quads:
        tris.append((v[a], v[b], v[c_], tag))
        tris.append((v[a], v[c_], v[d], tag))
    return tris


RACK_UNITS = 6


@functools.lru_cache(maxsize=1)
def _land_cells() -> frozenset:
    d = assets.world()["dots"]
    step = assets.world().get("dot_step_deg", 1.5)
    return frozenset((round(d[i] / step), round(d[i + 1] / step)) for i in range(0, len(d), 2))


def _is_land(cells, lon: float, lat: float) -> bool:
    step = 1.5
    i, j = round(lon / step - 0.5) + 0.5, round(lat / step - 0.5) + 0.5
    for di in (-0.5, 0.5):
        for dj in (-0.5, 0.5):
            if (round(lon / step + di), round(lat / step + dj)) in cells:
                return True
    return False


@functools.lru_cache(maxsize=8)
def mesh(name: str) -> tuple:
    """Triangles ((p0, p1, p2, tag), ...) in model space, roughly unit size; tag 1 marks accent parts."""
    tris = []
    if name == "cube":
        tris = _box(-1, -1, -1, 1, 1, 1)
    elif name == "server_rack":
        tris = _box(-0.75, -1.5, -0.6, 0.75, 1.5, 0.6)
        for i in range(RACK_UNITS):                            # rack units standing out of the front
            y0 = -1.32 + i * 0.44
            tris += _box(-0.64, y0, -0.70, 0.64, y0 + 0.34, -0.6, tag=2)
    elif name == "datacenter":                                # main hall, loading bay annex, rooftop plant, lit windows
        tris = _box(-1.7, -0.6, -0.85, 0.9, 0.75, 0.85)           # main hall
        tris += _box(0.9, -0.05, -0.85, 1.75, 0.75, 0.6)           # loading bay annex (lower)
        for j in range(3):                                         # roll-up doors on the bay
            x0 = 1.0 + j * 0.25
            tris += _box(x0, 0.2, -0.9, x0 + 0.19, 0.75, -0.85, tag=2)
        tris += _box(0.95, -0.1, -1.05, 1.7, -0.05, -0.85, tag=2)  # canopy over the bay
        for r in range(3):                                         # rows of lit windows
            for q in range(7):
                x0 = -1.55 + q * 0.33
                y0 = -0.42 + r * 0.33
                tris += _box(x0, y0, -0.9, x0 + 0.2, y0 + 0.15, -0.85, tag=1)
        for x in (-1.35, -0.75, -0.15, 0.45):                      # rooftop cooling units
            tris += _box(x - 0.2, -0.92, -0.45, x + 0.2, -0.6, 0.05, tag=2)
        tris += _box(-1.6, -1.25, 0.35, -1.52, -0.6, 0.43, tag=2)  # mast
        tris += _box(-0.35, 0.3, -0.95, -0.05, 0.75, -0.85, tag=2) # entrance
    elif name == "database":
        seg = 24
        for k in range(3):                                     # three stacked discs
            y0, y1 = -1.2 + k * 0.85, -1.2 + k * 0.85 + 0.7
            for i in range(seg):
                a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
                p0, p1 = (math.cos(a0), math.sin(a0)), (math.cos(a1), math.sin(a1))
                tris.append(((p0[0], y0, p0[1]), (p1[0], y0, p1[1]), (p1[0], y1, p1[1]), k % 2))
                tris.append(((p0[0], y0, p0[1]), (p1[0], y1, p1[1]), (p0[0], y1, p0[1]), k % 2))
                tris.append(((0, y0, 0), (p1[0], y0, p1[1]), (p0[0], y0, p0[1]), 2))
                tris.append(((0, y1, 0), (p0[0], y1, p0[1]), (p1[0], y1, p1[1]), 2))
    elif name == "globe":
        t = (1 + 5 ** 0.5) / 2
        vs = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
              (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
        fs = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
              (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
        norm = lambda p: tuple(x / math.sqrt(sum(y * y for y in p)) for x in p)
        faces = [tuple(norm(vs[i]) for i in f) for f in fs]
        for _ in range(3):                                      # subdivide three times: 1280 faces
            nf = []
            for a, b, c_ in faces:
                ab, bc, ca = norm(tuple((x + y) / 2 for x, y in zip(a, b))), norm(tuple((x + y) / 2 for x, y in zip(b, c_))), norm(tuple((x + y) / 2 for x, y in zip(c_, a)))
                nf += [(a, ab, ca), (b, bc, ab), (c_, ca, bc), (ab, bc, ca)]
            faces = nf
        cells = _land_cells()
        for a, b, c_ in faces:                                  # Natural Earth land (the vendored 1.5 degree grid)
            m = norm(tuple((x + y + z) / 3 for x, y, z in zip(a, b, c_)))
            lat = math.degrees(math.asin(clamp(-m[1], -1, 1)))
            lon = math.degrees(math.atan2(m[0], -m[2]))
            land = _is_land(cells, lon, lat)
            r = 1.36 if land else 1.3                           # land raised a little above the ocean
            tris.append(((a[0] * r, a[1] * r, a[2] * r), (b[0] * r, b[1] * r, b[2] * r), (c_[0] * r, c_[1] * r, c_[2] * r), 1 if land else 0))
    return tuple(tris)


def draw_model(c, tpl, name: str, cx: float, cy: float, size: float, ay: float, ax: float = -0.42, alpha: float = 1.0,
               neon: bool | None = None) -> None:
    """A low-poly model: projected, back-face culled, depth sorted, flat shaded; neon edges on dark templates."""
    T = tpl.T
    neon = tpl.dark if neon is None else neon
    body = tpl.icon.get("badge") or T["accent"]
    if name == "globe":                                        # dark ocean, bright land
        base = {0: D.mix(T["bg0"], body, 0.55) if tpl.dark else "#AFC4DA", 1: tpl.conn["active"] if tpl.dark else "#2F8F5B"}
    else:
        base = {0: (D.mix(body, "#0B1220", 0.55 if name == "server_rack" else 0.62) if name in ("server_rack", "datacenter") else body) if tpl.dark else "#C9D6E6", 1: tpl.conn["active"], 2: D.mix(body, "#0B1220", 0.45) if tpl.dark else "#8BA0BA"}
    lx, ly, lz = -0.35, -0.62, -0.70                         # towards the light: up, left, towards the viewer
    out = []
    for p0, p1, p2, tag in mesh(name):
        q = [rot(p, ax, ay) for p in (p0, p1, p2)]
        q = [(x * size, y * size, z * size + 600) for x, y, z in q]
        ux, uy, uz = (q[1][0] - q[0][0], q[1][1] - q[0][1], q[1][2] - q[0][2])
        vx, vy, vz = (q[2][0] - q[0][0], q[2][1] - q[0][1], q[2][2] - q[0][2])
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        nx, ny, nz = nx / ln, ny / ln, nz / ln
        if nz > 0:                                            # face the normal towards the camera
            nx, ny, nz = -nx, -ny, -nz
        s = [project(p, cx, cy, 1400.0) for p in q]
        area = (s[1][0] - s[0][0]) * (s[2][1] - s[0][1]) - (s[1][1] - s[0][1]) * (s[2][0] - s[0][0])
        if area >= 0:                                          # back face (screen winding)
            continue
        lam = 0.42 + 0.58 * max(0.0, nx * lx + ny * ly + nz * lz)
        e3 = [math.dist(q[0], q[1]), math.dist(q[1], q[2]), math.dist(q[2], q[0])]
        out.append((sum(p[2] for p in q) / 3, s, tag, lam, e3.index(max(e3))))
    out.sort(key=lambda r: -r[0])
    edge = D.paint(col(tpl.conn["active"], 0.7 * alpha), 1.8) if neon else D.paint(col(T["line"], 0.5 * alpha), 1.0)
    hi = D.paint(col("#FFFFFF" if neon else tpl.conn["active"], 0.85 * alpha), 2.2)
    thin = name == "globe"
    if thin:                                                  # convex and culled: no overlaps, so faces can be
        batches: dict = {}                                    # batched by shade (12 levels), ocean first, then land
        for _, s_, tag, lam, _d in out:
            key = (tag, round(lam * 12))
            pth = batches.setdefault(key, skia.Path())
            pth.moveTo(s_[0][0], s_[0][1]); pth.lineTo(s_[1][0], s_[1][1]); pth.lineTo(s_[2][0], s_[2][1]); pth.close()
        for (tag, lv), pth in sorted(batches.items()):
            shade = D.mix("#000000", base.get(tag, base[0]), lv / 12)
            c.drawPath(pth, D.paint(col(shade, alpha)))
            if tag == 1:                                      # seal hairline gaps where they show (bright land)
                c.drawPath(pth, D.paint(col(shade, alpha), 1.2))
        if neon:
            land = skia.Path()
            for (tag, lv), pth in batches.items():
                if tag == 1:
                    land.addPath(pth)
            c.drawPath(land, D.paint(col(tpl.conn["active"], 0.35 * alpha), 1.0))
        out = []
    for _, s, tag, lam, diag in out:
        p = skia.Path()
        p.moveTo(s[0][0], s[0][1]); p.lineTo(s[1][0], s[1][1]); p.lineTo(s[2][0], s[2][1]); p.close()
        ed = skia.Path()                                       # outline without the triangle's diagonal (quad edges)
        for k in range(3):
            if k != diag:
                ed.moveTo(s[k][0], s[k][1]); ed.lineTo(s[(k + 1) % 3][0], s[(k + 1) % 3][1])
        b = base.get(tag, base[0])
        shade = D.mix("#000000", b, lam)
        fill = D.paint(col(shade, alpha))
        c.drawPath(p, fill)
        if thin:                                              # globe: seal hairline gaps, edges only on land
            c.drawPath(p, D.paint(col(shade, alpha), 1.2))
            if tag == 1 and neon:
                c.drawPath(p, D.paint(col(tpl.conn["active"], 0.35 * alpha), 1.0))
        else:
            c.drawPath(p, fill_seal := D.paint(col(shade, alpha), 1.0))
            if name != "database":                            # the database reads by its rims instead
                c.drawPath(ed, hi if tag == 2 else edge)
    if name == "server_rack":
        _rack_front(c, tpl, cx, cy, size, ax, ay, alpha)
    elif name == "database":
        _disk_rims(c, tpl, cx, cy, size, ax, ay, alpha)


def _visible_front(ax: float, ay: float) -> bool:
    return rot((0, 0, -1), ax, ay)[2] < -0.05


def _rack_front(c, tpl, cx, cy, size, ax, ay, alpha):
    """Front-panel lines and status LEDs on each rack unit, drawn when the front faces the camera."""
    if not _visible_front(ax, ay):
        return
    P = lambda x, y, z: project(tuple(v * size if i < 2 else v * size + 600 for i, v in enumerate(rot((x, y, z), ax, ay))), cx, cy, 1400.0)[:2]
    line = D.paint(col("#FFFFFF" if tpl.dark else "#24364F", 0.55 * alpha), 2)
    leds = ("#3EE3A0", "#38D6F5", "#3EE3A0", "#FFC04D", "#3EE3A0", "#38D6F5")
    for i in range(RACK_UNITS):
        y0 = -1.32 + i * 0.44
        for k in (0.10, 0.17, 0.24):                           # vent lines across the unit
            a, b = P(-0.52, y0 + k, -0.705), P(0.18, y0 + k, -0.705)
            c.drawLine(a[0], a[1], b[0], b[1], line)
        for j, dx in enumerate((0.36, 0.48)):                  # two status LEDs
            x, y = P(dx, y0 + 0.17, -0.705)
            colr = leds[(i + j) % len(leds)]
            if tpl.dark:
                D.halo(c, x, y, 16, colr, 0.8 * alpha)
            c.drawCircle(x, y, max(3.0, size * 0.028), D.paint(col(colr, alpha)))


def _disk_rims(c, tpl, cx, cy, size, ax, ay, alpha):
    """Bright rims where the database's disks meet, so the stacked bands read clearly."""
    P = lambda x, y, z: project(tuple(v * size if i < 2 else v * size + 600 for i, v in enumerate(rot((x, y, z), ax, ay))), cx, cy, 1400.0)[:2]
    rim = D.paint(col("#FFFFFF" if tpl.dark else tpl.conn["active"], 0.75 * alpha), 2.4)
    for k in range(3):
        for y in (-1.2 + k * 0.85, -1.2 + k * 0.85 + 0.7):
            pts = []
            for i in range(25):
                a = 2 * math.pi * i / 24
                x, z = math.cos(a), math.sin(a)
                if rot((x, 0, z), ax, ay)[2] > 0.15:           # only the near half of each rim
                    if len(pts) > 1:
                        path = skia.Path(); path.moveTo(*pts[0]); [path.lineTo(*q) for q in pts[1:]]; c.drawPath(path, rim)
                    pts = []
                    continue
                pts.append(P(x, y, z))
            if len(pts) > 1:
                path = skia.Path(); path.moveTo(*pts[0]); [path.lineTo(*q) for q in pts[1:]]; c.drawPath(path, rim)


# ================================================================== wrapper effects (applied by the engine)
_layer_cache: dict = {}


def parallax_layers(c, tpl, W: float, H: float, t: float, dur: float, layers: int = 4, a: float = 1.0) -> None:
    """Depth without decoration: 2-3 faint line grids (far: fine and slow; near: wider and faster) drift sideways
    and slightly up, so the scene reads as layered. No floating shapes or particles in any template."""
    layers = int(clamp(layers, 2, 3)) if layers else 2
    pan = ease_in_out(t / max(0.1, dur))
    colr = tpl.conn["active"] if tpl.dark else tpl.T["line"]
    for i in range(layers):
        depth = (i + 1) / layers                              # 0 far .. 1 near
        step = 60.0 + 90.0 * depth
        dx = -(pan * W * 0.12 * (0.3 + depth)) % step
        dy = -(pan * H * 0.03 * depth) % step
        p = D.paint(col(colr, (0.05 + 0.04 * depth) * a), 1.0 + depth)
        x = dx
        while x < W:
            c.drawLine(x, 0, x, H, p)
            x += step
        y = dy
        while y < H:
            c.drawLine(0, y, W, y, p)
            y += step


def pinned_scroll(t: float, dur: float, distance: float, start: float = 0.15) -> float:
    """How far the content has scrolled under a pinned heading at time t."""
    return distance * ease_in_out((t / max(0.1, dur) - start) / (1 - start - 0.12))


def heading_mask(c, tpl, W: float, top: float) -> None:
    """A band of background over the scrolled content behind the pinned heading, fading out below it."""
    T = tpl.T

    def band(cc):                                             # built once, blitted (see focus_frame)
        p = skia.Paint()
        p.setShader(skia.GradientShader.MakeLinear([skia.Point(0, top - 60), skia.Point(0, top + 10)],
                                                   [col(T["bg0"], 1.0), col(T["bg0"], 0.0)]))
        cc.drawRect(skia.Rect.MakeLTRB(0, 0, W, top - 60), D.paint(col(T["bg0"])))
        cc.drawRect(skia.Rect.MakeLTRB(0, top - 60, W, top + 10), p)
    D.sprite(c, ("heading-mask", tpl.name, int(W), int(top)), 0, 0, W, top + 10, band, 0.97)


FOCUS_DIM = 0.45                                             # the rest keeps about 55% of its strength


def focus_frame(c, tpl, rects: list, times: list, t: float, W: float, H: float, a: float = 1.0) -> None:
    """A rounded highlight frame that slides between rectangles at their times, dimming everything outside it."""
    if not rects or t < times[0]:
        return
    i = max(j for j, tt in enumerate(times) if t >= tt)
    k = ease_in_out((t - times[i]) / 0.55)
    r0 = rects[max(0, i - 1)] if i > 0 else rects[0]
    r1 = rects[i]
    x, y, w, h = (lerp(p, q, k) for p, q in zip(r0, r1))
    appear = ease_out((t - times[0]) / 0.4) * a
    rr = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), 26, 26)
    # Everything but the frame, dimmed. Built opaque with a clear hole and blitted with alpha: this skia build fills
    # translucent colours ~100x slower than it blits a translucent image.
    q = [round(v / 4) * 4 for v in (x, y, w, h)]
    M = 400

    def dim(cc):
        cc.drawColor(col(tpl.T["bg0"]))
        hole = skia.Paint(AntiAlias=True, BlendMode=skia.BlendMode.kClear)
        cc.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(q[0] + M, q[1] + M, q[2], q[3]), 26, 26), hole)
    D.sprite(c, ("focus-dim", tpl.name, tuple(q), int(W), int(H)), -M, -M, W + 2 * M, H + 2 * M, dim, FOCUS_DIM * appear)
    if tpl.glow:                                              # glow from widening strokes: no per-size blur cache
        frame = skia.Path()
        frame.addRRect(rr)
        D.glow_stroke(c, frame, tpl.conn["active"], appear, 5)
    c.drawRRect(rr, D.paint(col(tpl.conn["active"], appear), 5))
    for (px, py, dx, dy) in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
        c.drawLine(px, py + dy * 34, px, py, D.paint(col("#FFFFFF" if tpl.dark else tpl.T["text"], appear), 7))
        c.drawLine(px, py, px + dx * 34, py, D.paint(col("#FFFFFF" if tpl.dark else tpl.T["text"], appear), 7))


# ================================================================== content effects: the "motion" treatment
class MotionScene(ProTreatment):
    """{"treatment": "motion", "effect": one of CONTENT, ...}. See visual_planner.md for each effect's fields."""
    drift = 0.0

    def layout(self):
        self.effect = self.sc.spec.get("effect", "marquee")

    def camera(self, t):
        return 1.0, self.CX, self.CY

    def _times(self, items, step=0.9, first=0.5):
        """When each item appears. The first is always on screen within 0.25 s: a scene never starts empty."""
        out, prev = [], first - step
        for it in items:
            tt = self.cue_t(it.get("at"), prev + step)
            if not out:
                tt = min(tt, 0.25)
            out.append(tt)
            prev = tt
        return out

    def draw(self, c, t):
        getattr(self, "_" + self.effect, self._marquee)(c, t)

    # ---- 16 premium developer-tool scenes (see devscenes.py)
    def _dev_scene(self, c, t):
        if not hasattr(self, "_dev"):
            from .devscenes import Scene
            self._dev = Scene(self)
        self._dev.draw(c, t)

    # ---- 15 project-structure diagram that builds across scenes (see tree.py)
    def _project_tree(self, c, t):
        if not hasattr(self, "_tree"):
            from .tree import Tree
            self._tree = Tree(self)
        self._tree.draw(c, t)

    # ---- 3 card zoom
    def _card_zoom_3d(self, c, t):
        sp, tpl = self.sc.spec, self.tpl
        item = sp.get("card") or (sp.get("items") or [{}])[0]
        at = self.cue_t(sp.get("at"), 0.4)
        k = ease_out((t - at) / (1.6 * self.sc.motion))
        w = 860.0 if self.portrait else 900.0
        h = card_height(item, w, big=True)
        img = card_image(tpl, int(w), int(h), item, ("zoom", item.get("title")), True, big=True)
        cy = self.top + (self.bottom - self.top) / 2
        z = lerp(1800.0, -180.0, k)
        kr = ease_out(k / 0.55)                               # the tilt settles while the card is still small:
        quad, _ = card_quad(w, h, (0, 0, z), lerp(0.5, 0.0, kr), lerp(-0.95, 0.0, kr), self.CX, cy)   # rotated draws cost by area
        if tpl.glow:
            D.halo(c, self.CX, cy, w * 0.7, tpl.conn["active"], 0.35 * k)   # fixed size: one cached glow
        draw_image_quad(c, img, w, h, quad, clamp(k * 3))

    # ---- 4 line-by-line reveal
    def _line_reveal(self, c, t):
        sp, tpl, T = self.sc.spec, self.tpl, self.tpl.T
        lines = sp.get("lines", [])
        mono = bool(sp.get("code"))
        times = self._times(lines, 0.8)
        if self.portrait:
            px, pw = 80.0, 920.0
        else:
            px, pw = 160.0, 1600.0
        py, ph = self.top + 10, self.bottom - self.top - 20
        size = float(sp.get("size", 38 if mono else 60))
        inner = pw - (96 if mono else 0)
        rows = []
        for l in lines:
            wt = "Bold" if l.get("accent") else ("Regular" if mono else "SemiBold")
            rr, sz = D.fit_block(l["text"], inner, 2, size, 30, wt) if not mono else \
                ([D.ellipsize(l["text"], inner, D.fit_size(l["text"], inner, size, 34 if size >= 34 else 30, mono=True), mono=True)],
                 D.fit_size(l["text"], inner, size, 34 if size >= 34 else 30, mono=True))
            rows.append((rr, sz, l, wt))
        lh = 1.55 if mono else 1.25
        content = sum(len(r) * sz * lh for r, sz, _, _ in rows) + 18 * len(rows)
        if mono:                                               # a code panel sized to its lines, centred in the band
            full = ph
            ph = min(full, max(content + 78 + 140, full * 0.55))
            py = py + (full - ph) / 2
            D.card(c, tpl, px, py, pw, ph, 1.0, fill=T["bg0"] if tpl.dark else "#0F1B2D")
            for i, dot in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
                c.drawCircle(px + 40 + i * 34, py + 38, 11, D.paint(col(dot)))
            if sp.get("title"):
                D.draw_text(c, sp["title"], px + pw / 2, py + 50, 30, col("#B8C7DD"), "Medium", "center", mono=True)
            c.drawLine(px, py + 78, px + pw, py + 78, D.paint(col("#FFFFFF", 0.12), 2))
            y = py + 78 + max(40.0, (ph - 78 - content) * 0.35)
            x0 = px + 48
        else:
            y = py + max(0.0, (ph - content) / 2)
            x0 = px
        for (rr, sz, l, wt), tt in zip(rows, times):
            if t < tt:
                y += len(rr) * sz * lh + 18
                continue
            k = ease_in_out((t - tt) / 0.5)
            if mono:
                colr = {"ok": "#7EE787", "err": "#FF7B72", "dim": "#9DB0C8"}.get(l.get("tone", ""), "#7FE3FF" if l.get("accent") else "#E6EDF3")
            else:
                colr = D.text_on(tpl, tpl.conn["active"]) if l.get("accent") else T["text"]
            for r in rr:
                tw = D.text_width(r, sz, wt, mono)
                c.save()
                c.clipRect(skia.Rect.MakeLTRB(x0 - 4, y - 4, x0 + tw * k + 6, y + sz * 1.4))
                D.draw_text(c, r, x0, y + sz, sz, col(colr), wt, mono=mono)
                c.restore()
                if k < 1:                                     # the wipe edge
                    c.drawRect(skia.Rect.MakeXYWH(x0 + tw * k, y + 2, 6, sz * 1.2), D.paint(col(tpl.conn["active"])))
                y += sz * lh
            y += 18

    # ---- 5 sideways text
    def _marquee(self, c, t):
        """Rows of large text sliding sideways. Optional "lines" are captions ({"text", "at"}): from its spoken word a
        caption shows at 72 px or more on its own opaque band across the middle, and the rows stop moving behind it."""
        sp, tpl, T = self.sc.spec, self.tpl, self.tpl.T
        rows = sp.get("rows") or [{"text": sp.get("text", "TECHHUB")}]
        caps = sp.get("lines") or []
        ctimes = self._times(caps, 1.5, 1.0) if caps else []
        first = ctimes[0] if ctimes else None
        tm = min(t, first) if first is not None else t           # the rows pause while a caption is up
        n = len(rows)
        size = sp.get("size", 190 if self.portrait else 210)
        span = self.bottom - self.top
        for i, r in enumerate(rows):
            txt = (r["text"].upper() if sp.get("upper", True) else r["text"]) + "  ·  "
            f = D.make_font(size, "Bold")
            tw = f.measureText(txt)
            d = 1 if i % 2 == 0 else -1
            speed = float(r.get("speed", 260 + 70 * i))
            off = (tm * speed * d) % tw
            y = self.top + span * (i + 0.5) / n + size * 0.35
            colr = D.text_on(tpl, tpl.conn["active"]) if r.get("accent") else T["text"]
            x = -off
            while x < self.W:
                D.draw_text(c, txt, x, y, size, col(colr, 1.0 if r.get("accent") or i % 2 == 0 else 0.92), "Bold")
                x += tw
        cur = max((j for j, tt in enumerate(ctimes) if t >= tt), default=None)
        if cur is not None:
            k = ease_out((t - ctimes[cur]) / 0.35)
            cap = caps[cur]
            maxw = (self.W - 160)
            rows_, sz = D.fit_block(cap["text"], maxw, 2, float(cap.get("size", 96)), 72, "Bold")
            bh = len(rows_) * sz * 1.12 + 120
            by = self.top + span / 2 - bh / 2
            band = tpl.T["bg0"] if tpl.dark else tpl.card["fill"]
            D.sprite(c, ("marquee-band", tpl.name, int(self.W), int(bh)), 0, by, self.W, bh,
                     lambda cc: (cc.drawColor(col(band)),
                                 cc.drawLine(0, 3, self.W, 3, D.paint(col(tpl.conn["active"]), 6)),
                                 cc.drawLine(0, bh - 3, self.W, bh - 3, D.paint(col(tpl.conn["active"]), 6))), k)
            colr = D.text_on(tpl, tpl.conn["active"], band) if cap.get("accent") else D.text_on(tpl, T["text"], band)
            for j, r in enumerate(rows_):
                D.draw_text(c, r, self.W / 2, by + 60 + sz * 0.9 + j * sz * 1.12 + (1 - k) * 20, sz, col(colr, k), "Bold", "center")

    # ---- 6 card arc carousel
    def _card_carousel(self, c, t):
        sp, tpl = self.sc.spec, self.tpl
        items = sp.get("items", [])
        if not items:
            return
        times = self._times(items, 1.0, 0.3)
        act = sum(ease_in_out((t - tt) / 0.6) for tt in times[1:])   # continuous index of the card in front
        band = self.bottom - self.top - 110                    # same layout with or without the (optional) counter
        w, h = (640.0, min(900.0, band - 40)) if self.portrait else (480.0, min(640.0, band - 40))
        cy = self.top + band / 2 + 10
        R = 900.0 if self.portrait else 1100.0
        step = 0.42 if self.portrait else 0.36
        order = []
        for i, it in enumerate(items):
            th = (i - act) * step
            if abs(th) > 1.45:
                continue
            x, z = R * math.sin(th), R * (1 - math.cos(th))
            order.append((z, i, it, th, x))
        order.sort(key=lambda o: -o[0])
        for z, i, it, th, x in order:
            front = 1 - clamp(abs(th) / step)
            img = card_image(tpl, int(w), int(h), it, ("car", i, it.get("title")), front > 0.5, big=self.portrait)
            quad, _ = card_quad(w, h, (x, 0, z), 0.0, th * 0.9, self.CX, cy)
            draw_image_quad(c, img, w, h, quad, 1.0, 0.72 * clamp(abs(th) / 1.2), tpl.T["bg0"])
        lab = sp.get("counter")
        if lab:
            cur = min(len(items), int(act + 0.5) + 1)
            D.chip(c, tpl, self.CX, self.bottom - 40, f"{cur} / {len(items)}  {lab}", None, "info", 1.0, 1.0, 32)

    # ---- 7 fixed 3D model
    def _model_3d(self, c, t):
        """A rotating model. Options: "headline" (large text above the model, shown from the first frame); "zoom_in"
        ({"from": 0.55, "dur": 1.0}: grows into place, continuing a camera push from the previous shot); "push_out"
        ({"at_end": 0.8, "to": 2.6}: the camera pushes into the model at the end, fading, into the next shot); for the
        globe "points" and "globe_arcs"; "start" sets the starting turn (radians)."""
        sp, tpl = self.sc.spec, self.tpl
        nxt = sp.get("then")
        if nxt:                                               # one scene, two shots: push into the first, open the second
            tc = self.cue_t(nxt.get("at"), self.sc.dur / 2)
            if t >= tc:
                saved = self.sc.spec
                self.sc.spec = dict({k: v for k, v in saved.items() if k not in ("then", "push_out", "zoom_in", "headline", "label", "sub", "model", "start", "scale")}, **nxt)
                try:
                    return self._model_3d(c, t - tc)
                finally:
                    self.sc.spec = saved
            sp = dict(sp, push_out={"at_end": 0.8, "to": 2.8, "_end": tc})
        name = sp.get("model", "server_rack")
        k = ease_out(t / 0.8)
        top = self.top
        if sp.get("headline"):
            top = self._headline(c, sp["headline"], t)
        cy = top + (self.bottom - top) * (0.44 if sp.get("label") else 0.5)
        mult, fade = 1.0, 1.0
        zi = sp.get("zoom_in")
        if zi:
            k = 1.0                                           # on screen from the first frame, already growing
            mult *= lerp(float(zi.get("from", 0.55)), 1.0, ease_out(t / float(zi.get("dur", 1.0))))
        po = sp.get("push_out")
        if po:
            end = float(po.get("_end", self.sc.dur))
            t0 = end - float(po.get("at_end", 0.8))
            f = ease_in_out(clamp((t - t0) / max(0.1, end - t0)))
            mult *= lerp(1.0, float(po.get("to", 2.6)), f)
            fade = 1.0 - 0.85 * f
        size = (300.0 if self.portrait else 250.0) * (0.85 + 0.15 * k) * float(sp.get("scale", 1.0)) * mult
        if tpl.glow:                                          # fixed radius: one cached glow even while zooming
            D.halo(c, self.CX, cy, (300.0 if self.portrait else 250.0) * 2.2 * float(sp.get("scale", 1.0)), tpl.conn["active"], 0.25 * k * fade)
        if name in ("server_rack", "datacenter"):            # swings, so the front stays in view
            ay = 0.3 * math.sin(t * float(sp.get("spin", 0.55))) + float(sp.get("start", 0.28))
        else:
            ay = t * float(sp.get("spin", 0.55)) + float(sp.get("start", 0.6))
        draw_model(c, tpl, name if name in MODELS else "cube", self.CX, cy, size, ay, alpha=k * fade)
        if name == "globe" and (sp.get("points") or sp.get("globe_arcs")):
            globe_lights(c, tpl, sp.get("points", []), sp.get("globe_arcs", []), self.CX, cy, size, ay, t, k)
        if sp.get("label"):
            ly = min(self.bottom - 120, cy + size * (1.25 if name == "datacenter" else 1.9))
            D.label_under(c, tpl, sp["label"], self.CX, ly, 900, 52, k * fade, sp.get("sub"), plate=True)

    def _headline(self, c, text, t, draw=True, backdrop=False):
        """Large text at the top of the band (72 px or more), readable from the first frame. Returns the y below it.
        With backdrop, a cached dark gradient sits behind it so it stays readable over imagery (a zoomed globe)."""
        tpl = self.tpl
        maxw = self.W - 140
        rows, sz = D.fit_block(text, maxw, 3, 96.0 if self.portrait else 88.0, 72, "Bold")
        k = ease_out((t + 0.25) / 0.45)
        y = self.top + 20
        if not draw:
            return y + len(rows) * sz * 1.1 + 40
        if backdrop:
            bh = y + len(rows) * sz * 1.1 + 120
            bg = tpl.T["bg0"]

            def grad(cc, W=self.W, bh=bh, bg=bg):
                p = skia.Paint()
                p.setShader(skia.GradientShader.MakeLinear([skia.Point(0, bh * 0.55), skia.Point(0, bh)],
                                                           [col(bg, 0.92), col(bg, 0.0)]))
                cc.drawRect(skia.Rect.MakeWH(W, bh * 0.55), D.paint(col(bg, 0.92)))
                cc.drawRect(skia.Rect.MakeXYWH(0, bh * 0.55, W, bh * 0.45), p)
            D.sprite(c, ("headline-backdrop", tpl.name, int(self.W), int(bh)), 0, 0, self.W, bh, grad, 1.0)
        for j, r in enumerate(rows):
            D.draw_text(c, r, self.CX, y + sz * 0.92 + j * sz * 1.1 + (1 - k) * 24, sz, col(tpl.T["text"], k), "Bold", "center")
        return y + len(rows) * sz * 1.1 + 40

    # ---- 11 the real Earth: textured globe and regional map, one camera language (fly-to, zoom, motion blur)
    def _key_time(self, k, i, prev):
        if "at_end" in k:
            return self.sc.dur - float(k["at_end"])
        if i == 0:
            return 0.0
        return max(prev, self.cue_t(k.get("at"), prev + 1.5) - float(k.get("lead", 0.0)))   # "lead": arrive as the word is spoken

    def _cam(self, t, flat=False):
        """Camera (lat, lon, zoom) at time t from "fly" keyframes [{place | lat/lon, zoom | span, at | at_end, fly}].
        Each move eases over "fly" s; long globe moves dip the zoom (fly-to). For flat maps "span" is the width in
        degrees of longitude (zoom = 60 / span)."""
        from . import earth
        sp = self.sc.spec
        keys = sp.get("fly") or [{"lat": 30, "lon": 0, "zoom": 1.0}]
        zof = lambda k, z: (60.0 / float(k["span"])) if "span" in k else float(k.get("zoom", z))
        cur = keys[0]
        lat, lon = earth.resolve(cur) if ("place" in cur or "lat" in cur) else (30.0, 0.0)
        zoom = zof(cur, 1.0)
        prev = 0.0
        for i, k in enumerate(keys[1:], 1):
            tt = self._key_time(k, i, prev)
            prev = tt
            if t <= tt:
                break
            la1, lo1 = earth.resolve(k) if ("place" in k or "lat" in k) else (lat, lon)
            z1 = zof(k, zoom)
            f = clamp((t - tt) / float(k.get("fly", 1.6)))
            e = ease_in_out(f)
            dlon = (lo1 - lon + 540) % 360 - 180
            dist = math.hypot(la1 - lat, dlon)
            dip = 1.0
            if not flat and (zoom > 1.2 or z1 > 1.2):
                dip = 1.0 - min(0.45, dist / 200.0) * math.sin(math.pi * e)
            lat, lon = lat + (la1 - lat) * e, lon + dlon * e
            zoom = math.exp(math.log(zoom) + (math.log(z1) - math.log(zoom)) * e) * dip
            if f < 1:
                break
        if not flat:
            lon += float(sp.get("drift", 1.2)) * t                 # a slow turn keeps it alive
        return lat, lon, zoom

    def _at(self, item, i, default):
        if "at_frac" in item:
            return float(item["at_frac"]) * self.sc.dur
        return self.cue_t(item.get("at"), default)

    def _earth_overlays(self, c, t, proj, base_alt=0.0, depth=1.0):
        """Arcs (draw on, then light-trail packets) and places: "kind": "region" (large ring, label and Region code),
        "edge" (small bright point, label optional) or a city marker. Labels slide in."""
        from . import earth
        sp, tpl = self.sc.spec, self.tpl
        for a in sp.get("arcs", []):
            at = self._at(a, 0, 0.6)
            if t < at:
                continue
            p0, p1 = earth.resolve(a["from"] if isinstance(a["from"], dict) else {"place": a["from"]}), \
                earth.resolve(a["to"] if isinstance(a["to"], dict) else {"place": a["to"]})
            gc = earth.great_circle(p0, p1, 64)
            span = math.radians(max(1.0, math.dist(p0, p1)))
            pts, vis = [], []
            for la, lo, f in gc:
                x, y, v = proj(la, lo, float(a.get("lift", 0.12)) * min(1.0, span) * math.sin(math.pi * f))
                pts.append((x, y)); vis.append(v)
            draw = ease_out((t - at) / float(a.get("dur", 1.3)))
            n = int(draw * (len(pts) - 1))
            colr = D.role_color(tpl, a["tone"]) if a.get("tone") else tpl.conn["active"]
            path, on = skia.Path(), False
            for i in range(n + 1):
                if vis[i]:
                    path.lineTo(*pts[i]) if on else path.moveTo(*pts[i])
                on = vis[i]
            p = D.paint(col(colr, 0.95), float(a.get("width", 5)))
            if a.get("dashed"):
                p.setPathEffect(skia.DashPathEffect.Make([18, 12], -t * 40))
            c.drawPath(path, D.blur(D.paint(col(colr, 0.5), 12), 8))
            c.drawPath(path, p)
            if draw >= 1 and a.get("packets", 1):
                per = float(a.get("period", 1.8))
                q = ((t - at - float(a.get("dur", 1.3))) / per) % 1.0
                seen = [pt for pt, v in zip(pts, vis) if v]
                if len(seen) > 2:
                    earth.light_trail(c, seen, q, colr if not a.get("packet_color") else a["packet_color"])
        compact = sp.get("labels") == "compact"
        L = earth.Labels(self.W, self.H, (self.top, self.bottom)) if compact else None
        if compact:
            for a in sp.get("arcs", []):                       # labels keep clear of the arcs
                if t >= self._at(a, 0, 0.6):
                    p0 = earth.resolve(a["from"] if isinstance(a["from"], dict) else {"place": a["from"]})
                    p1 = earth.resolve(a["to"] if isinstance(a["to"], dict) else {"place": a["to"]})
                    pts = [proj(la, lo, 0.0) for la, lo, f in earth.great_circle(p0, p1, 24)]
                    L.avoid_points([(x, y) for x, y, v in pts if v])
        for i, ct in enumerate(sp.get("cities", [])):
            at = self._at(ct, i, 0.3 + 0.12 * i)
            k = ease_out((t - at) / 0.4)
            if k <= 0:
                continue
            la, lo = earth.resolve(ct)
            x, y, v = proj(la, lo, 0.0)
            if not v or not (-50 < x < self.W + 50 and -50 < y < self.H + 50):
                continue
            colr = D.role_color(tpl, ct["tone"]) if ct.get("tone") else None
            kind = ct.get("kind", "city")
            if compact:
                until = self._at({"at": ct["until"]}, i, 1e9) if ct.get("until") is not None else 1e9
                if t > until + 0.4:
                    continue
                kk = k * (1.0 - clamp((t - until) / 0.4))
                if kind == "alert":
                    earth.alert_pulse(c, x, y, kk, t)
                elif kind == "focus":
                    earth.focus_pulse(c, x, y, kk, t + i * 0.3)
                elif kind == "region":
                    earth.small_ring(c, x, y, kk, "#FFB84D")
                    c.drawCircle(x, y, 5, D.paint(col("#FFB84D", kk)))
                else:
                    earth.small_point(c, x, y, kk, colr or tpl.conn["active"])
                if ct.get("label") or kind in ("focus", "region") and ct.get("place"):
                    L.add(c, x, y, ct.get("label", ct.get("place")), ct.get("code", ""), kk,
                          "#FF8A8A" if kind == "alert" else "#F2F6FC", pref=ct.get("side", "right"))
                continue
            if kind == "region":
                earth.region_marker(c, tpl, x, y, ct.get("label", ct.get("place")), ct.get("code", ""), k, t + i * 0.37,
                                    colr, ct.get("side", "right"), self.W)
            elif kind == "edge":
                earth.edge_point(c, tpl, x, y, k, t + i * 0.53, colr, ct.get("label"), self.W)
            else:
                earth.city_marker(c, tpl, x, y, ct.get("label", ct.get("place")), k, t + i * 0.37, colr, ct.get("hub", False),
                                  ct.get("side", "right"), float(ct.get("size", 44)), self.W)

    def _globe(self, c, t):
        """The textured Earth. "fly": camera keyframes; "sun": {lat, lon} or omitted for night; "cities", "arcs";
        "headline" (with "headline_at": it appears on that cue, over the globe); "cy" (0..1 of the band) or "cy_px";
        "from_point": {"bg": [r, g, b], "point": [r, g, b], "fade": s}: the first frame is that flat colour with a
        glowing point at the centre of the frame (a clip's last frame), which opens into the globe."""
        from . import earth
        sp = self.sc.spec
        over = sp.get("headline_at") is not None
        top = self._headline(c, sp["headline"], t, draw=False) if sp.get("headline") and not over else self.top
        lat, lon, zoom = self._cam(t)
        R = (0.5 if self.portrait else 0.36) * (self.W if self.portrait else self.H * 1.3) * zoom
        cy = float(sp["cy_px"]) if "cy_px" in sp else top + (self.bottom - top) * float(sp.get("cy", 0.54))
        g = earth.Globe(self.W, self.H, self.CX, cy, R, lat, lon)
        sun = sp.get("sun")
        fp = sp.get("from_point")
        g.render(c, (float(sun["lat"]), float(sun["lon"])) if sun else None, float(sp.get("night_gain", 1.7)),
                 1.0 if fp else ease_out((t + 0.3) / 0.5))
        self._globe_layers(c, t, g)
        self._earth_overlays(c, t, g.project)
        self._tags(c, t)
        if sp.get("counter"):
            self._map_counter(c, t, sp["counter"], (40.0, self.top, self.W - 80, self.bottom - self.top))
        if fp:
            k = clamp(t / float(fp.get("fade", 0.6)))
            if k < 1:
                bg = "#%02x%02x%02x" % tuple(fp.get("bg", (5, 12, 26)))
                pt = "#%02x%02x%02x" % tuple(fp.get("point", (56, 214, 255)))
                c.drawRect(skia.Rect.MakeWH(self.W, self.H), D.paint(col(bg, 1.0 - ease_in_out(k))))
                D.halo(c, self.CX, cy, 46, pt, 1.0 - k)
                c.drawCircle(self.CX, cy, 9, D.paint(col("#FFFFFF", 1.0 - k)))
        if sp.get("headline"):
            if over:
                ha = self.cue_t(sp.get("headline_at"), 0.5)
                hu = self.cue_t(sp.get("headline_until"), 1e9) if sp.get("headline_until") is not None else 1e9
                if ha <= t < hu + 0.4:
                    c.saveLayerAlpha(None, int(255 * (1.0 - clamp((t - hu) / 0.4)))) if t > hu else c.save()
                    self._headline(c, sp["headline"], t - ha, backdrop=True)
                    c.restore()
            else:
                self._headline(c, sp["headline"], t, backdrop=True)

    def _globe_layers(self, c, t, g):
        """Background layers: every AWS Region as a small ring ("all_regions") and every CloudFront edge location as a
        small point ("all_edges"); edges light up in a quick wave from "edges_from" (seconds or a cue)."""
        from . import earth
        sp = self.sc.spec
        a0 = self.cue_t(sp.get("layers_from"), 0.0) if sp.get("layers_from") is not None else 0.0
        if t < a0:
            return
        e0 = self.cue_t(sp.get("edges_from"), a0) if sp.get("edges_from") is not None else a0
        for i, p in enumerate(sp.get("all_edges", [])):
            k = ease_out((t - e0 - 0.9 * ((i * 0.618) % 1.0)) / 0.35)
            if k > 0:
                x, y, v = g.project(float(p["lat"]), float(p["lon"]))
                if v:
                    earth.small_point(c, x, y, k)
        ka = ease_out((t - a0) / 0.5)
        for p in sp.get("all_regions", []):
            x, y, v = g.project(float(p["lat"]), float(p["lon"]))
            if v:
                earth.small_ring(c, x, y, ka)

    def _tags(self, c, t):
        """Word tags: small pills at the top of the band that appear on their spoken word ("tags": [{"text", "at"}])."""
        y = self.top + 10
        for tg in self.sc.spec.get("tags", []):
            at = self.cue_t(tg.get("at"), 0.5)
            k = ease_out((t - at) / 0.35)
            if k <= 0:
                continue
            size = 40.0
            w = D.text_width(tg["text"], size, "SemiBold") + 48
            x = self.CX - w / 2 + (1 - k) * 30
            c.drawRoundRect(skia.Rect.MakeXYWH(x, y, w, size * 1.6), size * 0.8, size * 0.8, D.paint(col("#050B16", 0.85 * k)))
            c.drawRoundRect(skia.Rect.MakeXYWH(x, y, w, size * 1.6), size * 0.8, size * 0.8, D.paint(col(self.tpl.conn["active"], 0.8 * k), 2.5))
            D.draw_text(c, tg["text"], x + 24, y + size * 1.12, size, col("#F2F6FC", k), "SemiBold")
            y += size * 1.6 + 14

    def _flat_map(self, c, t):
        """A regional map of the same NASA imagery with Natural Earth borders and coastlines, under a camera:
        "fly": [{place | lat/lon, span (degrees of longitude across), at | at_end, fly}] pans and zooms smoothly, with
        motion blur while it moves; "cities" with "kind" region / edge / city ("at_frac" staggers them); "arcs";
        "legend": [{"mark": "region" | "edge", "label"}]; "counter": {"value", "suffix", "label", "source", "at"} counts
        up from the first frame beside the map. "region" ([lon0, lon1, lat0, lat1]) is a fixed view without "fly"."""
        from . import earth
        sp, tpl = self.sc.spec, self.tpl
        x0, y0 = (40.0, self.top + 10) if self.portrait else (100.0, self.top + 10)
        rect = (x0, y0, self.W - 2 * x0, self.bottom - y0 - 10)
        if sp.get("fly"):
            views = []
            for dt in ((0.0, 1.0),) if self.sc.spec.get("motion_blur") is False else ((2 / 90, 1.0), (1 / 90, 0.5), (0.0, 0.34)):
                lat, lon, zoom = self._cam(max(0.0, t - dt[0]), flat=True)
                views.append((earth.View.at(rect, lat, lon, 60.0 / zoom), dt[1]))
            moving = abs(views[0][0].lon_c - views[-1][0].lon_c) + abs(views[0][0].lat_c - views[-1][0].lat_c) > 0.004 * views[-1][0].span \
                or abs(views[0][0].span / views[-1][0].span - 1) > 0.004
            if not moving:
                views = views[-1:]
                views[0] = (views[0][0], 1.0)
            view = views[-1][0]
        else:
            view = earth.View.region(rect, tuple(sp.get("region", (-12, 32, 34, 62))))
            views = [(view, 1.0)]
        c.save()
        c.clipRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(*rect), 24, 24), skia.ClipOp.kIntersect, True)
        c.drawRect(skia.Rect.MakeXYWH(*rect), D.paint(col("#02060E")))
        for v, a in views:
            v.draw(c, sp.get("texture", "night"), float(sp.get("night_gain", 1.7)), a)
        if sp.get("borders", True):
            view.borders(c)
        self._earth_overlays(c, t, lambda la, lo, alt: (*view.project(la, lo, depth=1.03), True))
        c.restore()
        c.drawRoundRect(skia.Rect.MakeXYWH(*rect), 24, 24, D.paint(col(tpl.conn["active"], 0.35), 2))
        if sp.get("legend"):
            earth.legend(c, tpl, sp["legend"], rect[0] + 24, rect[1] + 24)
        if sp.get("counter"):
            self._map_counter(c, t, sp["counter"], rect)

    def _map_counter(self, c, t, ctr, rect):
        """A sourced counter in a card at the foot of the map: on screen at once, counting up to its spoken word."""
        tpl, T = self.tpl, self.tpl.T
        cue = self.cue_t(ctr.get("at"), 1.5)
        k = ease_out(clamp((t - 0.05) / max(0.8, cue + 0.4)))
        val = float(ctr.get("value", 0))
        shown = f"{val * k:,.0f}{ctr.get('suffix', '') if k > 0.98 else ''}"
        w, h = rect[2] - 60, 250.0
        x, y = rect[0] + 30, rect[1] + rect[3] - h - 30
        D.card(c, tpl, x, y, w, h, 1.0)
        acc = D.text_on(tpl, tpl.conn["active"])
        D.draw_text(c, shown, x + 40, y + 150, 140, col(acc), "Bold")
        lw = D.text_width(f"{val:,.0f}{ctr.get('suffix', '')}", 140, "Bold") + 70
        rows, ls = D.fit_block(ctr.get("label", ""), w - lw - 40, 2, 48, 36, "SemiBold")
        for j, r in enumerate(rows):
            D.draw_text(c, r, x + lw, y + 92 + j * ls * 1.15, ls, col(T["text"]), "SemiBold")
        if ctr.get("source"):
            D.draw_text(c, D.ellipsize("Source: " + ctr["source"], w - 80, 30), x + 40, y + h - 28, 30, col(T["text2"]))

    # ---- 13 split card: the same need, a far source and a near one ("top" and "bottom" rows)
    def _split_compare(self, c, t):
        """{"rows": [{"title", "from": {"icon", "label"}, "to": {"icon", "label"}, "via": "truck", "far": true,
        "note", "tone", "at"}]}: each row a card with a source, a destination and a travel arrow whose length shows
        the distance; a vehicle travels it (slowly when far). Rows are on screen at once; the trip starts on its word."""
        sp, tpl, T = self.sc.spec, self.tpl, self.tpl.T
        rows = sp.get("rows", [])[:2]
        band = self.bottom - self.top
        h = (band - 40) / max(1, len(rows)) - 30
        for i, r in enumerate(rows):
            y = self.top + 20 + i * (h + 30)
            x, w = 50.0, self.W - 100
            k = ease_out((t - 0.05 - 0.15 * i) / 0.4)
            D.card(c, tpl, x, y + (1 - k) * 30, w, h, k)
            colr = D.role_color(tpl, r.get("tone", "info"))
            D.draw_text(c, r.get("title", ""), x + 40, y + 70, 52, col(colr if tpl.dark else T["text"], k), "Bold")
            if r.get("note"):
                D.draw_text(c, r["note"], x + w - 40, y + 70, 36, col(T["text2"], k), "Regular", "right")
            cy = y + h * 0.58
            far = bool(r.get("far"))
            x0 = x + 120
            x1 = x + w - 120 if far else x0 + 330
            R = 70.0
            D.badge(c, tpl, assets.resolve(r["from"]["icon"]) or "box", x0, cy, R, k, tone=r.get("tone"))
            D.badge(c, tpl, assets.resolve(r["to"]["icon"]) or "user", x1, cy, R, k)
            D.label_under(c, tpl, r["from"].get("label", ""), x0, cy + R + 16, 300, 38, k)
            D.label_under(c, tpl, r["to"].get("label", ""), x1, cy + R + 16, 300, 38, k)
            path = skia.Path()
            path.moveTo(x0 + R + 20, cy)
            path.lineTo(x1 - R - 20, cy)
            at = self.cue_t(r.get("at"), 0.6 + i)
            dk = ease_out((t - at) / 0.6)
            D.stroke(c, tpl, path, 0.95, max(0.25, dk) * k, dashed=far, color=colr, width=7.0, arrow=True, seed=i)
            per = 3.0 if far else 1.0
            q = ((t - at) / per) % 1.0 if t >= at else 0.0
            vx = lerp(x0 + R + 40, x1 - R - 40, ease_in_out(q))
            if t >= at:
                assets.draw_icon(c, r.get("via", "truck"), vx, cy - 52, 64, colr)

    # ---- 14 cache hit / miss split screen with a real-response panel
    def _cache_split(self, c, t):
        """Top: "Cache hit" (edge -> viewer, short, green). Bottom: "Cache miss" (edge -> origin -> edge -> viewer,
        then "copy kept"). A small panel shows real response headers ("proof": [{"text", "tone", "at"}],
        "proof_title"). Cues: "hit_at", "miss_at", "fetch_at", "keep_at"."""
        sp, tpl, T = self.sc.spec, self.tpl, self.tpl.T
        ok, bad, info = D.role_color(tpl, "success"), D.role_color(tpl, "fail"), D.role_color(tpl, "info")
        band = self.bottom - self.top
        proof_h = 230.0 if sp.get("proof") else 0.0
        h = (band - proof_h - 60) / 2 - 15
        R = 62.0

        def node(icon, label, x, y, k, tone=None):
            D.badge(c, tpl, assets.resolve(icon) or "box", x, y, R, k, tone=tone)
            D.label_under(c, tpl, label, x, y + R + 14, 260, 36, k)

        def leg(x0, y0, x1, y1, k, colr, dashed=False, seed=0):
            p = skia.Path(); p.moveTo(x0, y0); p.lineTo(x1, y1)
            D.stroke(c, tpl, p, 0.95, k, dashed=dashed, color=colr, width=7.0, arrow=True, seed=seed)
            return p

        # hit
        y = self.top + 10
        x, w = 50.0, self.W - 100
        c0 = ease_out((t - 0.05) / 0.4)
        D.card(c, tpl, x, y, w, h, c0)
        D.draw_text(c, "Cache hit", x + 40, y + 66, 50, col(ok, c0), "Bold")
        cy = y + h * 0.58
        ex, vx = x + 200, x + w - 200
        node("server", "Edge", ex, cy, c0, "success")
        node("user", "Viewer", vx, cy, c0)
        ha = self.cue_t(sp.get("hit_at"), 0.5)
        hk = ease_out((t - ha) / 0.5)
        if t < ha + 0.3:                                      # the request goes in and the edge checks its cache
            req = skia.Path(); req.moveTo(vx - R - 16, cy - 30); req.lineTo(ex + R + 16, cy - 30)
            D.packet(c, tpl, req, ((t - 0.2) / 1.1) % 1.0, c0 * (1.0 - clamp((t - ha) / 0.3)), info)
            for cx_, cy_ in ((ex, cy), (ex2_pre := x + 200, y + h + 30 + h * 0.62)):
                q = (t * 1.2) % 1.0
                c.drawCircle(cx_, cy_, R + 8 + 30 * q, D.paint(col(info, 0.6 * (1 - q) * c0), 3))
        p = leg(ex + R + 16, cy, vx - R - 16, cy, max(0.2, hk) * c0, ok, seed=1)
        if t > ha + 0.5:
            D.packet(c, tpl, p, ((t - ha - 0.5) / 1.0) % 1.0, 1.0, ok)
        # miss
        y2 = y + h + 30
        D.card(c, tpl, x, y2, w, h, c0)
        D.draw_text(c, "Cache miss", x + 40, y2 + 66, 50, col(bad, c0), "Bold")
        cy2 = y2 + h * 0.62
        ex2, vx2, ox, oy = x + 200, x + w - 200, x + w / 2, y2 + 150
        node("server", "Edge", ex2, cy2, c0, "fail")
        node("user", "Viewer", vx2, cy2, c0)
        ma = self.cue_t(sp.get("miss_at"), 1.5)
        fa = self.cue_t(sp.get("fetch_at"), ma + 0.8)
        ka = self.cue_t(sp.get("keep_at"), fa + 1.0)
        node("server-cog", "Origin", ox, oy, ease_out((t - ma) / 0.4) * c0)
        k1 = ease_out((t - ma) / 0.5)
        k2 = ease_out((t - fa) / 0.5)
        k3 = ease_out((t - fa - 0.6) / 0.5)
        if k1 > 0:
            leg(ex2 + R, cy2 - R * 0.6, ox - R - 10, oy + 10, k1, bad, True, 2)
        if k2 > 0:
            leg(ox - R - 10, oy + 40, ex2 + R + 10, cy2 - R * 0.2, k2, info, False, 3)
        if k3 > 0:
            p3 = leg(ex2 + R + 16, cy2 + 10, vx2 - R - 16, cy2 + 10, k3, ok, False, 4)
            if t > fa + 1.1:
                D.packet(c, tpl, p3, ((t - fa - 1.1) / 1.0) % 1.0, 1.0, ok)
        kk = ease_out((t - ka) / 0.4)
        if kk > 0:
            D.chip(c, tpl, ex2, cy2 - R - 40, "Copy kept", "refresh-cw", "info", kk, 1.0, 34)
        # proof
        if sp.get("proof"):
            py = self.bottom - proof_h
            D.card(c, tpl, x, py, w, proof_h - 10, c0, fill=T["bg0"] if tpl.dark else "#0F1B2D")
            D.draw_text(c, sp.get("proof_title", "real response"), x + 30, py + 42, 30, col("#9DB0C8", c0), "Regular", mono=True)
            for j, ln in enumerate(sp["proof"]):
                la = self.cue_t(ln.get("at"), 0.3 + j)
                lk = ease_out((t - la) / 0.3)
                if lk > 0:
                    colr = {"ok": "#7EE787", "err": "#FF7B72"}.get(ln.get("tone", ""), "#C9D6E8")
                    D.draw_text(c, ln["text"], x + 30, py + 96 + j * 52, 34, col(colr, lk), "Regular", mono=True)

    # ---- 8 stacking cards
    def _stacking_cards(self, c, t):
        sp, tpl = self.sc.spec, self.tpl
        items = sp.get("items", [])
        times = self._times(items, 0.9)
        w, h = (900.0, 300.0) if self.portrait else (1100.0, 300.0)
        x = self.CX - w / 2
        base_y = self.bottom - h - 40
        shown = [i for i, tt in enumerate(times) if t >= tt]
        for i in shown:
            depth = sum(ease_out((t - times[j]) / 0.5) for j in shown if j > i)   # how many cards sit on top of it
            if depth > 4.2:
                continue
            k = ease_out((t - times[i]) / 0.55)
            s = 0.92 ** depth
            yy = base_y - depth * float(sp.get("peek", 110 if self.portrait else 70)) + (1 - k) * 500
            cw, ch = w * s, h * s
            cx0 = self.CX - cw / 2
            a = clamp(k * 3)                                  # quick fade: slides in nearly opaque
            D.soft_shadow(c, cx0, yy + 18, cw, ch, 26, "#000000", 0.35 * a, 20)
            img = card_image(tpl, int(w), int(h), items[i], ("stack", i, items[i].get("title")), depth < 0.5)
            quad = [(cx0, yy), (cx0 + cw, yy), (cx0 + cw, yy + ch), (cx0, yy + ch)]
            draw_image_quad(c, img, w, h, quad, a, 0.22 * depth, tpl.T["bg0"])

    # ---- 10 scroll-triggered demo
    def _scroll_demo(self, c, t):
        sp, tpl, T = self.sc.spec, self.tpl, self.tpl.T
        lines = sp.get("lines", [])
        times = self._times(lines, 0.7)
        x0 = 60.0 if self.portrait else 200.0
        w = 960.0 if self.portrait else 1520.0
        y0, y1 = self.top + 10, self.bottom - 10
        h = y1 - y0
        D.card(c, tpl, x0, y0, w, h, 1.0, fill=T["bg0"] if tpl.dark else "#0F1B2D")
        for i, colr in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
            c.drawCircle(x0 + 40 + i * 34, y0 + 38, 11, D.paint(col(colr)))
        title = sp.get("terminal_title") or sp.get("title", "terminal")
        D.draw_text(c, title, x0 + w / 2, y0 + 50, 30, col("#B8C7DD"), "Medium", "center", mono=True)
        c.drawLine(x0, y0 + 78, x0 + w, y0 + 78, D.paint(col("#FFFFFF", 0.12), 2))
        size = float(sp.get("font", 32))                       # larger for a phone when the lines are few
        lh = size * 1.56
        rows = []                                             # long lines wrap onto continuation rows
        for l, tt in zip(lines, times):
            room = (w - 120) if l.get("cmd") else (w - 90)
            for j, part in enumerate(_wrap_mono(l["text"], room, size)):
                rows.append((dict(l, text=part, cont=j > 0, full=l["text"], off=sum(len(p) for p in _wrap_mono(l["text"], room, size)[:j])), tt))
        shown = [(l, tt) for l, tt in rows if t >= tt]
        view_top, view_h = y0 + 100, h - 130
        content_h = len(shown) * lh
        target = max(0.0, content_h - view_h)
        prev_target = max(0.0, (len(shown) - 1) * lh - view_h)
        kk = ease_out((t - shown[-1][1]) / 0.35) if shown else 1.0
        scroll = lerp(prev_target, target, kk)
        c.save()
        c.clipRect(skia.Rect.MakeXYWH(x0 + 10, view_top - 6, w - 20, view_h + 12))
        for j, (l, tt) in enumerate(shown):
            yy = view_top + j * lh - scroll + size
            txt = l["text"]
            if l.get("cmd"):
                full = l.get("full", txt)
                n = int(len(full) * clamp((t - tt) / max(0.3, 0.035 * len(full)))) - l.get("off", 0)
                if n <= 0:
                    continue
                if not l.get("cont"):
                    D.draw_text(c, "$", x0 + 34, yy, size, col("#7EE787"), mono=True)
                D.draw_text(c, txt[:n], x0 + 74, yy, size, col("#F0F6FC"), mono=True)
            else:
                colr = {"ok": "#7EE787", "err": "#FF7B72", "dim": "#9DB0C8"}.get(l.get("tone", ""), "#C9D6E8")
                D.draw_text(c, D.ellipsize(txt, w - 90, size, mono=True), x0 + 34, yy, size, col(colr), mono=True)
        c.restore()
        if shown and int(t * 2.2) % 2 == 0:
            c.drawRect(skia.Rect.MakeXYWH(x0 + 34, min(y1 - 40, view_top + len(shown) * lh - scroll + 6), 18, 34),
                       D.paint(col("#F0F6FC", 0.8)))


def _wrap_mono(text: str, room: float, size: float) -> list[str]:
    """Splits a monospace line to fit `room` px, preferring breaks after / . - or a space."""
    cw = D.make_font(size, "Regular", mono=True).measureText("M") or size * 0.6
    n = max(8, int(room / cw))
    out = []
    while len(text) > n:
        cut = max((text.rfind(ch, 0, n) for ch in "/ .-"), default=-1)
        cut = cut + 1 if cut > n // 2 else n
        out.append(text[:cut])
        text = text[cut:]
    return out + [text]


def _globe_xyz(lat: float, lon: float, r: float = 1.38) -> tuple:
    la, lo = math.radians(lat), math.radians(lon)
    return (math.cos(la) * math.sin(lo) * r, -math.sin(la) * r, -math.cos(la) * math.cos(lo) * r)


def globe_lights(c, tpl, points, arcs, cx, cy, size, ay, t, alpha, ax: float = -0.42) -> None:
    """Glowing points and drawn-on arcs on the globe's visible side (same projection as draw_model)."""
    def scr(p):
        q = rot(p, ax, ay)
        return project((q[0] * size, q[1] * size, q[2] * size + 600), cx, cy, 1400.0)[:2], q[2] < -0.12 * size / size
    glow = tpl.conn["active"]
    for i, p in enumerate(points):
        (x, y), vis = scr(_globe_xyz(float(p["lat"]), float(p["lon"])))
        if not vis:
            continue
        k = alpha * ease_out(clamp((t - 0.15 - 0.04 * i) / 0.4))
        pulse = 0.5 + 0.5 * math.sin(t * 4 + i)
        hub = bool(p.get("hub"))
        D.halo(c, x, y, (34 if hub else 20) * (1 + 0.25 * pulse), glow, 0.9 * k)
        c.drawCircle(x, y, 7 if hub else 4.5, D.paint(col("#FFFFFF", k)))
    for j, a in enumerate(arcs):
        p0, p1 = _globe_xyz(*a["from"], r=1.0), _globe_xyz(*a["to"], r=1.0)
        dot = max(-1.0, min(1.0, sum(u * v for u, v in zip(p0, p1))))
        om = math.acos(dot) or 1e-6
        start = float(a.get("at", 0.5))
        f_end = ease_out(clamp((t - start) / 1.4))
        pts = []
        for s in range(41):
            f = s / 40 * f_end
            w0, w1 = math.sin((1 - f) * om) / math.sin(om), math.sin(f * om) / math.sin(om)
            r = 1.38 + 0.32 * math.sin(math.pi * f)
            v = [w0 * u + w1 * w for u, w in zip(p0, p1)]
            pts.append(scr(tuple(x * r for x in v)))
        path, on = skia.Path(), False
        for (x, y), vis in pts:
            if vis:
                path.lineTo(x, y) if on else path.moveTo(x, y)
            on = vis
        if f_end > 0:
            c.drawPath(path, D.blur(D.paint(col(glow, 0.6 * alpha), 10), 6))
            c.drawPath(path, D.paint(col("#FFFFFF", 0.95 * alpha), 4))
            (x, y), vis = pts[-1]
            if vis and f_end < 1:
                D.halo(c, x, y, 30, glow, alpha)
                c.drawCircle(x, y, 8, D.paint(col("#FFFFFF", alpha)))


def wrapper_spec(spec: dict, kind: str) -> dict | None:
    return next((e for e in spec.get("effects", []) if isinstance(e, dict) and e.get("type") == kind), None)
