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


def test_export_tab_lists_cover_png_for_download(client):
    pid = cli.create_from_example(fmt="9:16")
    director.write_cover(pid, director.render_settings(pid), {"scenes": []})
    names = [f["name"] for f in client.get(f"/api/productions/{pid}").json()["exports"]]
    assert "cover.png" in names
    r = client.get(f"/api/productions/{pid}/file/cover.png")
    assert r.status_code == 200 and r.content[:4] == b"\x89PNG"


def test_regenerate_cover_uses_the_cover_headline(client):
    pid = cli.create_from_example(fmt="9:16")
    assert client.put(f"/api/productions/{pid}/brief", json={"cover_headline": "Where tech makes sense."}).status_code == 200
    from exposit.render import design
    design.TEXT_LOG = []
    try:
        r = client.post(f"/api/productions/{pid}/cover")
        texts = " ".join(t["text"] for t in design.TEXT_LOG)
    finally:
        design.TEXT_LOG = None
    assert r.status_code == 200 and r.json()["name"] == "cover.png"
    assert "makes sense." in texts and "HTTP request" not in texts.split("makes sense.")[0][-40:]
    assert "cover.png" in [f["name"] for f in client.get(f"/api/productions/{pid}").json()["exports"]]
