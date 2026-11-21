"""Vendored assets: every file has a licence entry, icons and the map load and draw."""
import numpy as np
import skia
from exposit import config
from exposit.render import assets

LIC = (config.ASSETS / "LICENSES.md").read_text(encoding="utf-8")


def _listed(family: str) -> set[str]:
    line = next(l for l in LIC.splitlines() if l.startswith(family + ":"))
    return set(line.split(":", 1)[1].split())


def test_every_icon_file_has_a_licence_entry():
    for fam, d in assets.ICON_DIRS.items():
        files = {p.stem for p in d.glob("*.svg")}
        assert files, fam
        assert files == _listed(fam), f"{fam}: files and LICENSES.md list differ: {files ^ _listed(fam)}"
    for needed in ("Lucide", "Kubernetes", "world-atlas", "Natural Earth", "Caveat", "OFL-Caveat.txt", "LICENSE-lucide.txt"):
        assert needed in LIC
    for f in ("licenses/LICENSE-lucide.txt", "licenses/LICENSE-world-atlas.txt", "fonts/OFL-Caveat.txt"):
        assert (config.ASSETS / f).exists(), f


def test_every_font_file_has_its_licence():
    for f in assets.FONT_FILES.values():
        assert (config.ASSETS / "fonts" / f).exists(), f
        assert assets.typeface(next(k for k, v in assets.FONT_FILES.items() if v == f)) is not None
    for lic in ("OFL-Caveat.txt", "OFL-IMFellEnglish.txt", "OFL-PressStart2P.txt", "OFL-Inter.txt", "OFL-JetBrainsMono.txt"):
        assert "SIL OPEN FONT LICENSE" in (config.ASSETS / "fonts" / lic).read_text(encoding="utf-8").upper(), lic


def test_aliases_and_kind_defaults_resolve_to_vendored_icons():
    for a, target in assets.ALIASES.items():
        assert assets.resolve(a) == target, a
    for kind, name in assets.KIND_ICON.items():
        assert assets.resolve(name), (kind, name)
    assert assets.resolve("no-such-icon") is None
    assert assets.icon_for({"kind": "pod"}) == "k8s:pod"
    assert assets.icon_for({"kind": "pod", "icon": "database"}) == "database"


def test_icons_draw_recoloured():
    surf = skia.Surface(200, 100)
    c = surf.getCanvas()
    c.clear(skia.ColorWHITE)
    assert assets.draw_icon(c, "server", 50, 50, 80, "#FF0000")
    assert assets.draw_icon(c, "k8s:pod", 150, 50, 80, "#00AA00")
    assert not assets.draw_icon(c, "nope", 50, 50, 80, "#FF0000")
    a = surf.toarray()[:, :, :3].astype(int)       # BGRA on this platform or RGBA; check both channels
    left, right = a[:, :100], a[:, 100:]
    red_like = ((np.abs(left[..., 0] - 255) < 40) & (left[..., 1] < 60)) | ((np.abs(left[..., 2] - 255) < 40) & (left[..., 1] < 60))
    assert red_like.sum() > 200, "the Lucide icon takes the requested colour"
    assert ((right[..., 1] > 120) & (right[..., 0] < 80) & (right[..., 2] < 80)).sum() > 500, "the Kubernetes icon is recoloured"


def test_world_map_projects_known_places():
    w = assets.world()
    assert len(w["rings"]) > 100 and len(w["dots"]) // 2 > 3000
    proj = assets.MapProjection((0, 0, 1920, 1080), "robinson")
    lx, ly = proj(-0.13, 51.5)        # London
    sx, sy = proj(151.2, -33.9)       # Sydney
    nx, ny = proj(-74.0, 40.7)        # New York
    assert nx < lx < sx and ly < ny < sy
    assert 0 <= nx <= 1920 and 0 <= sy <= 1080
    path = assets.land_path(proj)
    assert path.countPoints() > 4000
    assert path.contains(*proj(20.0, 0.0)), "central Africa is land"
    assert not path.contains(*proj(-30.0, 0.0)), "the mid-Atlantic is sea"
    arc = assets.great_circle(-74.0, 40.7, -0.13, 51.5)
    assert max(p[1] for p in arc) > 51.5, "a New York to London great circle bends north"
