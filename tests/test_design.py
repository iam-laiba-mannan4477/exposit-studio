"""Design rules checked on the rendered style gallery (every treatment x template x format):
- no text below the minimum size (30 px in the 1080-wide space);
- every text colour reads at 4.5:1 or better against what it actually sits on (sampled from a render with the text
  hidden, the text colour blended with its own alpha);
- balanced line breaks: no line ends on a stop word ("the / origin").
"""
import io
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import render_gallery as gallery                      # noqa: E402
from exposit.render import design, engine              # noqa: E402

TEMPLATES = ["premium-technical", *design.NEW_TEMPLATES]
SCENES = gallery.scenes()
CASES = [(s["id"], tp, p) for s in SCENES for tp in TEMPLATES for p in (False, True)]


def _render_logged(scene, template, portrait, scale, hide):
    design.TEXT_LOG = []
    design.HIDE_TEXT[0] = hide
    try:
        png = gallery.render(scene, template, portrait, scale)
        return np.asarray(Image.open(io.BytesIO(png)).convert("RGB")), design.TEXT_LOG
    finally:
        design.TEXT_LOG = None
        design.HIDE_TEXT[0] = False


def _lum(rgb):
    c = np.asarray(rgb, dtype=float) / 255
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]


def _contrast(l1, l2):
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("sid,template,portrait", CASES, ids=[f"{a}-{b}-{'9x16' if c else '16x9'}" for a, b, c in CASES])
def test_text_size_and_contrast(sid, template, portrait):
    scene = next(s for s in SCENES if s["id"] == sid)
    scale = 0.25
    bg, log = _render_logged(scene, template, portrait, scale, hide=True)
    assert log, "the scene draws some text"
    H, W = bg.shape[:2]
    small, low = [], []
    for item in log:
        if item["size"] < design.MIN_TEXT - 0.01:
            small.append((item["text"], item["size"]))
        x0, y0, x1, y1 = item["rect"]
        x0, y0 = max(0, int(x0)), max(0, int(y0))
        x1, y1 = min(W, int(np.ceil(x1))), min(H, int(np.ceil(y1)))
        if x1 - x0 < 1 or y1 - y0 < 1:
            continue                                   # off-frame (outside the visible stage)
        under = bg[y0:y1, x0:x1].reshape(-1, 3)
        lum = _lum(under)
        bg_rgb = under[np.argsort(lum)[len(lum) // 2]]   # the median pixel by luminance
        argb = item["color"]
        a = ((argb >> 24) & 255) / 255
        if a < 0.05:
            continue                                   # not drawn yet (animation start)
        fg = np.array([(argb >> 16) & 255, (argb >> 8) & 255, argb & 255], dtype=float)
        shown = a * fg + (1 - a) * bg_rgb
        cr = _contrast(float(_lum(shown)), float(_lum(bg_rgb)))
        if cr < 4.5:
            low.append((item["text"], round(cr, 2)))
    assert not small, f"text below {design.MIN_TEXT} px: {small}"
    assert not low, f"text under 4.5:1 contrast: {low}"


def test_wrap_never_ends_a_line_on_a_stop_word():
    design.set_active(design.template("paper"))
    f = design.make_font(44, "SemiBold")
    for s in ["Your request often never reaches the origin", "Edge caches, regional caches and the origin",
              "A hit is answered by a nearby edge", "Copies expire by the Cache-Control header"]:
        for w in (300, 420, 560, 700):
            rows = design.wrap_font(s, f, w)
            assert " ".join(rows).split() == s.split(), "wrapping keeps every word"
            for r in rows[:-1]:
                if all(design._is_stop(x) for x in r.split()):
                    continue                   # a line of nothing but stop words ("by a") in a very narrow column
                assert not design._is_stop(r.split()[-1]), (s, w, rows)


def test_wrap_is_balanced():
    design.set_active(design.template("paper"))
    f = design.make_font(44, "SemiBold")
    rows = design.wrap_font("Edge caches, regional caches and the origin", f, 900)
    widths = [f.measureText(r) for r in rows]
    assert len(rows) == 2 and min(widths) > 0.6 * max(widths), rows


def test_make_font_never_goes_below_the_minimum():
    for tp in TEMPLATES:
        design.set_active(design.template(tp))
        assert design.make_font(12).getSize() >= design.MIN_TEXT


def test_stat_strip_shows_numbers_only_with_a_source():
    design.set_active(design.template("paper"))
    tpl = design.template("paper")
    import skia
    surf = skia.Surface(1080, 400)
    design.TEXT_LOG = []
    try:
        design.stat_strip(surf.getCanvas(), tpl, 0, 0, 1080, [
            {"icon": "server", "label": "Edge locations", "value": "600+"},                  # no source: no number
            {"icon": "clock", "label": "Default TTL", "value": "24 h", "claim": "c4"}], 1.0, True)
        drawn = [i["text"] for i in design.TEXT_LOG]
    finally:
        design.TEXT_LOG = None
    assert "600+" not in drawn and "24 h" in drawn


@pytest.mark.parametrize("captions,limit", [(False, 1500.0), (True, 1340.0)])
def test_portrait_content_band_follows_the_caption_setting(captions, limit):
    """9:16 content may reach y 1500 with burned-in captions off and stops at y 1340 with them on: every drawn
    string (captions themselves excluded) ends above the limit, and without captions the content really uses the
    room below 1340."""
    lowest = []
    for s in SCENES:
        tm = gallery.timing_for(s["narration"])
        spec = dict(s["spec"], theme="paper")
        tr = engine.build(spec, tm, "paper", portrait=True, captions=captions)
        t = gallery.most_complete_t(spec, tm)
        tr.sc.dur = max(tr.sc.dur, t + 0.4)
        import skia
        surf = skia.Surface(1080, 1920)
        design.TEXT_LOG = []
        try:
            engine.draw_frame(surf.getCanvas(), tr, t, 1080, 1920, captions=False)
            log = design.TEXT_LOG
        finally:
            design.TEXT_LOG = None
        bottom = max(i["rect"][3] for i in log)
        assert bottom <= limit + 2, f"{s['id']}: text reaches y {bottom:.0f} (limit {limit:.0f})"
        lowest.append(bottom)
    if not captions:
        assert max(lowest) > 1340, "without captions the band below 1340 is used"
