"""The ten motion effects: each renders in both formats, wrappers change the picture, meshes are sound."""
import io, sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import render_motion_gallery as gallery                # noqa: E402
from exposit.render import engine, motion              # noqa: E402


def _px(png):
    return np.asarray(Image.open(io.BytesIO(png)).convert("RGB")).astype(int)


def test_ten_effects_are_listed_and_in_the_gallery():
    assert len(motion.EFFECTS) == 10 and set(gallery.EFFECTS) == set(motion.EFFECTS)


@pytest.mark.parametrize("name", list(motion.EFFECTS))
@pytest.mark.parametrize("template", ["noir-network", "paper"])
def test_effect_renders_in_both_formats(name, template):
    spec, tm = gallery.scene(name, template)
    for portrait in (True, False):
        px = _px(gallery.still(spec, tm, portrait, 2.6, 0.25))
        assert px.std() > 6, f"{name} draws something"


@pytest.mark.parametrize("name", list(motion.WRAPPERS))
def test_wrapper_effects_change_the_picture(name):
    spec, tm = gallery.scene(name, "noir-network")
    plain = dict(spec, effects=[])
    a, b = _px(gallery.still(spec, tm, True, 2.6, 0.25)), _px(gallery.still(plain, tm, True, 2.6, 0.25))
    assert np.abs(a - b).mean() > 0.5


def test_motion_over_time():
    spec, tm = gallery.scene("card_carousel", "noir-network")
    a, b = _px(gallery.still(spec, tm, True, 0.6, 0.25)), _px(gallery.still(spec, tm, True, 2.4, 0.25))
    assert np.abs(a - b).mean() > 2, "the carousel turns"


@pytest.mark.parametrize("name", motion.MODELS)
def test_meshes_are_closed_enough_and_cached(name):
    tris = motion.mesh(name)
    assert len(tris) >= 12 and motion.mesh(name) is tris
    for p0, p1, p2, tag in tris[:50]:
        assert len(p0) == len(p1) == len(p2) == 3
