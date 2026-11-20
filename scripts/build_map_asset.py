"""One-off: convert world-atlas land-110m.json (TopoJSON, ISC; data from Natural Earth, public domain) into the
compact asset the renderer reads: land rings as flat [lon, lat, lon, lat, ...] lists rounded to 0.1 degree, plus a
precomputed halftone grid of land points. Run by hand when the source changes:

    python scripts/build_map_asset.py path/to/land-110m.json exposit/assets/map/land-110m.json

Nothing here runs at render time, and nothing is fetched.
"""
from __future__ import annotations
import json, sys


def decode_arcs(topo: dict) -> list[list[tuple[float, float]]]:
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    out = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        out.append(pts)
    return out


def ring_points(arcs, idxs):
    pts: list[tuple[float, float]] = []
    for i in idxs:
        a = arcs[i] if i >= 0 else list(reversed(arcs[~i]))
        pts.extend(a if not pts else a[1:])
    return pts


def polygons(topo: dict, arcs) -> list[list[list[tuple[float, float]]]]:
    polys = []

    def geom(g):
        if g["type"] == "GeometryCollection":
            for x in g["geometries"]:
                geom(x)
        elif g["type"] == "Polygon":
            polys.append([ring_points(arcs, r) for r in g["arcs"]])
        elif g["type"] == "MultiPolygon":
            for p in g["arcs"]:
                polys.append([ring_points(arcs, r) for r in p])
    for obj in topo["objects"].values():
        geom(obj)
    return polys


def inside(px: float, py: float, ring) -> bool:
    c = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if (y1 > py) != (y2 > py) and px < (x2 - x1) * (py - y1) / (y2 - y1) + x1:
            c = not c
    return c


def main(src: str, dst: str, step: float = 1.5) -> None:
    topo = json.load(open(src, encoding="utf-8"))
    arcs = decode_arcs(topo)
    polys = polygons(topo, arcs)
    rings = []
    for poly in polys:
        for ring in poly:
            flat = []
            last = None
            for lon, lat in ring:
                p = (round(lon, 1), round(lat, 1))
                if p != last:
                    flat += [p[0], p[1]]
                    last = p
            if len(flat) >= 8:
                rings.append(flat)
    boxes = []
    for poly in polys:
        outer = poly[0]
        boxes.append((min(p[0] for p in outer), max(p[0] for p in outer), min(p[1] for p in outer), max(p[1] for p in outer), poly))
    dots = []
    lat = -56.0
    while lat <= 82.0:
        lon = -180.0 + step / 2
        while lon < 180.0:
            for x0, x1, y0, y1, poly in boxes:
                if x0 <= lon <= x1 and y0 <= lat <= y1 and inside(lon, lat, poly[0]) and not any(inside(lon, lat, h) for h in poly[1:]):
                    dots += [round(lon, 2), round(lat, 2)]
                    break
            lon += step
        lat += step
    out = {"source": "world-atlas 2.0.2 land-110m.json (ISC), Natural Earth 1:110m land (public domain)",
           "units": "degrees; rings and dots are flat [lon, lat, ...] lists", "dot_step_deg": step,
           "rings": rings, "dots": dots}
    json.dump(out, open(dst, "w", encoding="utf-8"), separators=(",", ":"))
    print(f"{len(rings)} rings, {sum(len(r) for r in rings) // 2} points, {len(dots) // 2} dots")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
