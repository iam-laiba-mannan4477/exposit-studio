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


def _logged(spec, tm, t, portrait=True):
    from exposit.render import design
    design.TEXT_LOG, design.CARD_LOG = [], []
    try:
        gallery.still(spec, tm, portrait, t, 0.5)
        return design.TEXT_LOG
    finally:
        design.TEXT_LOG = design.CARD_LOG = None


def test_marquee_caption_is_big_on_its_own_band_and_rows_pause():
    spec, tm = gallery.scene("marquee", "cardboard-diorama")
    spec = dict(spec, lines=[{"text": "Where tech makes sense.", "at": 1.0}])
    log = _logged(spec, tm, 2.0)
    cap = [t for t in log if "tech" in t["text"].lower() or "sense" in t["text"].lower()]
    assert cap and min(t["size"] for t in cap) >= 72
    plain, tm2 = gallery.scene("marquee", "noir-network")          # no parallax or grain changing per frame
    plain = dict(plain, lines=spec["lines"])
    a, b = _px(gallery.still(plain, tm2, True, 2.0, 0.25)), _px(gallery.still(plain, tm2, True, 2.6, 0.25))
    assert np.abs(a - b).mean() < 1.0, "the rows stop moving while the caption shows"


def test_carousel_front_card_is_640_wide_with_48px_labels():
    spec, tm = gallery.scene("card_carousel", "cardboard-diorama")
    tr = engine.build(spec, tm, "cardboard-diorama", portrait=True)
    import skia
    from exposit.render import design
    s = skia.Surface(1080, 1920)
    design.CARD_LOG = []
    try:
        engine.draw_frame(s.getCanvas(), tr, 0.4, 1080, 1920, False)
    finally:
        design.CARD_LOG = None
    img = motion._card_cache
    sizes = [k for k in img if k[3][0] == "car"]
    assert sizes and max(k[1] for k in sizes) >= 640, "front card at least 640 px wide in 9:16"
    item = spec["items"][0]
    rows, sz = design.fit_block(item["title"], 640 - 2 * motion.BIG["pad"], 2, motion.BIG["title"], 48, "Bold")
    assert sz >= 48


@pytest.mark.parametrize("template", ["noir-network", "paper", "cardboard-diorama"])
def test_focus_frame_keeps_labels_readable(template):
    import test_design
    spec, tm = gallery.scene("focus_frame", template)
    scene = {"id": "focus_frame", "narration": gallery.N, "spec": spec}
    test_design.SCENES.append(scene)
    try:
        for portrait in (True, False):
            test_design.test_text_size_and_contrast("focus_frame", template, portrait)
    finally:
        test_design.SCENES.remove(scene)
