"""Motion: transitions between scenes, focus dimming, easing."""
import sys
from pathlib import Path

import numpy as np
import pytest
import skia

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import render_gallery as gallery                      # noqa: E402
from exposit.render import design, engine             # noqa: E402

SC = {s["id"]: s for s in gallery.scenes()}


def _pixels(surf):
    return np.asarray(surf.makeImageSnapshot().toarray())[..., :3].astype(int)


def _scene(sid, tp="noir-network", **extra):
    s = SC[sid]
    return dict(s["spec"], theme=tp, **extra), gallery.timing_for(s["narration"])


@pytest.mark.parametrize("kind", ["crossfade", "slide", "push", "match"])
def test_transitions_blend_from_the_previous_scene(kind):
    w, h = 480, 270
    pspec, ptm = _scene("iconflow")
    spec, tm = _scene("sequence", transition=kind)          # shares the "user" element with iconflow
    prev = engine.build(pspec, ptm, "noir-network")
    img = engine.last_frame(prev, w, h, False)
    tr = engine.build(spec, tm, "noir-network")
    shift = engine._match_shift(tr, prev, w, h)
    if kind == "match":
        assert shift != (0.0, 0.0), "a shared element gives the match cut somewhere to start from"
    mid, plain, end = skia.Surface(w, h), skia.Surface(w, h), skia.Surface(w, h)
    engine.transition_frame(mid.getCanvas(), tr, engine.TRANSITION_SECONDS * 0.4, w, h, False, img, kind, shift)
    engine.transition_frame(plain.getCanvas(), engine.build(spec, tm, "noir-network"), engine.TRANSITION_SECONDS * 0.4,
                            w, h, False, None, kind)
    assert np.abs(_pixels(mid) - _pixels(plain)).mean() > 2, "mid-transition shows the previous scene"
    engine.transition_frame(end.getCanvas(), tr, 1.0, w, h, False, img, kind, shift)
    p2 = skia.Surface(w, h)
    engine.transition_frame(p2.getCanvas(), engine.build(spec, tm, "noir-network"), 1.0, w, h, False, None, kind)
    assert np.abs(_pixels(end) - _pixels(p2)).mean() < 1, "after the transition the scene is drawn as usual"


def test_previous_scene_does_not_fade_out_before_a_transition():
    spec, tm = _scene("iconflow")
    tr = engine.build(spec, tm, "paper")
    img = engine.last_frame(tr, 320, 180, False)
    px = img.toarray()[..., :3].astype(int)
    assert px.std() > 5, "the last frame still shows the scene, not a blank fade"


def test_focus_dims_others_to_35_percent():
    assert abs((1 - design.DIM) - 0.35) < 1e-9


def test_easing_library():
    assert design.ease_out(0) == 0 and design.ease_out(1) == 1
    assert design.ease_in_out(0.5) == pytest.approx(0.5)
    assert max(design.spring(x / 100) for x in range(101)) > 1.0, "spring overshoots a little"
    assert design.spring(1.0) == pytest.approx(1.0)
    assert design.stagger(0.3, 0.0, 2, 0.1, 0.5) < design.stagger(0.3, 0.0, 0, 0.1, 0.5)


def test_unknown_transition_is_listed():
    assert set(engine.TRANSITIONS) == {"fade", "crossfade", "slide", "push", "match"}
