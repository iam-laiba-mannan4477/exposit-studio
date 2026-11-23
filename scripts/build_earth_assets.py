"""Build-time conversion of the NASA textures and Natural Earth 50m vectors into the studio's runtime assets.

Usage: python scripts/build_earth_assets.py <download dir>
The download dir holds day.jpg (Blue Marble NG, Dec 2004, 5400x2700), night.jpg (Black Marble 2016, 3600x1800) and the
three Natural Earth zips (ne_50m_admin_0_boundary_lines_land, ne_50m_coastline, ne_50m_populated_places).
Needs pyshp (requirements-dev.txt). The outputs are committed, so rendering never needs pyshp:
  exposit/assets/earth/day-4096.jpg, night-4096.jpg  (equirectangular, 4096x2048)
  exposit/assets/earth/vectors-50m.json              (borders, coastlines as [lon, lat] lines; places)
"""
import io
import json
import sys
import zipfile
from pathlib import Path

import shapefile                                          # pyshp, build time only
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "exposit" / "assets" / "earth"


def lines(zp: Path) -> list:
    z = zipfile.ZipFile(zp)
    stem = zp.stem
    r = shapefile.Reader(shp=io.BytesIO(z.read(stem + ".shp")), shx=io.BytesIO(z.read(stem + ".shx")),
                         dbf=io.BytesIO(z.read(stem + ".dbf")))
    out = []
    for sh in r.shapes():
        parts = list(sh.parts) + [len(sh.points)]
        for a, b in zip(parts[:-1], parts[1:]):
            pts = [[round(x, 2), round(y, 2)] for x, y in sh.points[a:b]]
            if len(pts) > 1:
                out.append(pts)
    return out


def places(zp: Path) -> list:
    z = zipfile.ZipFile(zp)
    stem = zp.stem
    r = shapefile.Reader(shp=io.BytesIO(z.read(stem + ".shp")), shx=io.BytesIO(z.read(stem + ".shx")),
                         dbf=io.BytesIO(z.read(stem + ".dbf")))
    names = [f[0] for f in r.fields[1:]]
    out = []
    for rec, sh in zip(r.records(), r.shapes()):
        d = dict(zip(names, rec))
        x, y = sh.points[0]
        out.append({"name": d.get("NAME") or d.get("NAMEASCII"), "ascii": d.get("NAMEASCII"), "country": d.get("ADM0NAME"),
                    "lon": round(x, 3), "lat": round(y, 3), "pop": int(d.get("POP_MAX") or 0)})
    return out


def main(src: Path):
    OUT.mkdir(parents=True, exist_ok=True)
    Image.MAX_IMAGE_PIXELS = None
    for name in ("day", "night"):
        im = Image.open(src / f"{name}.jpg").convert("RGB").resize((4096, 2048), Image.LANCZOS)
        im.save(OUT / f"{name}-4096.jpg", quality=88, optimize=True)
    data = {"source": "Natural Earth 1:50m (public domain)",
            "borders": lines(src / "ne_50m_admin_0_boundary_lines_land.zip"),
            "coast": lines(src / "ne_50m_coastline.zip"),
            "places": places(src / "ne_50m_populated_places.zip")}
    (OUT / "vectors-50m.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print({k: len(v) for k, v in data.items() if isinstance(v, list)})


if __name__ == "__main__":
    main(Path(sys.argv[1]))
