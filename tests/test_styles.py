"""Style packs: every ready style renders in both formats, keeps text readable, and planned ones are not offered."""
import io
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import render_gallery as gallery                       # noqa: E402
import test_design                                     # noqa: E402
from exposit.render import design, engine, styles      # noqa: E402

SUBSET = ("iconflow", "stat", "cards-benefits", "kinetic")


def test_seventeen_styles_with_three_planned():
    assert len(styles.STYLES) == 17
    assert set(styles.PLANNED) == {"stick-figure-story", "paper-cutout-puppet", "hand-puppet-theatre"}
    for n in styles.PLANNED:
        assert styles.STYLES[n].why_planned and n not in design.TEMPLATES, "planned styles are not offered as templates"
    for n in styles.READY:
        assert styles.STYLES[n].best_for and design.TEMPLATES[n].style is styles.STYLES[n]


@pytest.mark.parametrize("style", styles.READY)
def test_style_text_is_readable(style):
    for sid in SUBSET:
        for portrait in (True, False):
            test_design.test_text_size_and_contrast(sid, style, portrait)


@pytest.mark.parametrize("style", styles.READY)
def test_style_renders_distinctly(style):
    s = next(x for x in gallery.scenes() if x["id"] == "iconflow")
    a = np.asarray(Image.open(io.BytesIO(gallery.render(s, style, True, 0.2))).convert("RGB")).astype(int)
    b = np.asarray(Image.open(io.BytesIO(gallery.render(s, "noir-network", True, 0.2))).convert("RGB")).astype(int)
    assert np.abs(a - b).mean() > 8, "a style looks different from the default template"


def test_post_process_ops_and_frame_rate_feel():
    arr = np.full((64, 96, 4), 128, np.uint8)
    for st in styles.READY:
        out = styles.post_process(arr.copy(), styles.STYLES[st].post, 3)
        assert out.shape == arr.shape and out.dtype == np.uint8
    tr = engine.build({"id": "x", "treatment": "kinetic", "lines": [{"text": "a", "at": 0}]}, {"duration": 2.0, "sentences": [], "words": []},
                      "limited-animation")
    assert engine.style_time(tr, 1 / 30) == engine.style_time(tr, 2 / 30) == 0.0, "12 fps feel holds drawings"
