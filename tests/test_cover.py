"""Cover image written with every export."""
import io

from PIL import Image

from conftest import example
from exposit import cli, director, store
from exposit.render import design, engine


def _cover(portrait, visual=True):
    board = example("board.json")["scenes"]
    vis = next(s for s in board if s["treatment"] in ("iconflow", "cards"))
    tm = {"duration": 6.0, "sentences": [], "words": []}
    design.TEXT_LOG = []
    try:
        png = engine.render_cover("noir-network", "Where tech makes sense.", "TechHub", (vis, tm) if visual else None,
                                  portrait, "TechHub")
        return png, design.TEXT_LOG
    finally:
        design.TEXT_LOG = None


def test_portrait_cover_keeps_its_content_in_the_safe_area():
    png, log = _cover(True)
    assert Image.open(io.BytesIO(png)).size == (1080, 1920)
    texts = [t["text"] for t in log]
    assert "TechHub" in texts and any("Where tech" in t or "makes sense" in t for t in texts)
    for t in log:
        assert 240 <= t["rect"][1] and t["rect"][3] <= 1680, (t["text"], t["rect"])


def test_landscape_cover_and_cover_without_a_visual():
    png, _ = _cover(False)
    assert Image.open(io.BytesIO(png)).size == (1920, 1080)
    png, log = _cover(True, visual=False)
    assert Image.open(io.BytesIO(png)).size == (1080, 1920) and log


def test_export_writes_cover_png(client):
    pid = cli.create_from_example(fmt="9:16")
    rs = director.render_settings(pid)
    out = director.write_cover(pid, rs, {"scenes": []})
    assert out.name == "cover.png" and out.exists()
    assert Image.open(out).size == (1080, 1920)
