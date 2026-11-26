"""Optional Blender 3D: detection, fallback, cache hits and script generation (no Blender needed; the subprocess is
mocked), plus one integration render that runs only when Blender is installed."""
import json
from pathlib import Path

import pytest

from exposit.render import blender3d as B


@pytest.fixture(autouse=True)
def _fresh_info():
    B._info.clear()
    yield
    B._info.clear()


def test_detection_order(monkeypatch, tmp_path):
    exe = tmp_path / "blender.exe"
    exe.write_text("x")
    monkeypatch.setenv("BLENDER_PATH", str(exe))
    assert B.find_blender() == str(exe)                               # 1. BLENDER_PATH
    monkeypatch.setenv("BLENDER_PATH", "")
    monkeypatch.setattr(B.glob, "glob", lambda p: [r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
                                                   r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"])
    assert "4.2" in B.find_blender()                                  # 2. the newest Program Files install
    monkeypatch.setattr(B.glob, "glob", lambda p: [])
    monkeypatch.setattr(B.shutil, "which", lambda n: "/usr/bin/blender")
    assert B.find_blender() == "/usr/bin/blender"                     # 3. PATH
    monkeypatch.setattr(B.shutil, "which", lambda n: None)
    assert B.find_blender() is None


def test_missing_blender_falls_back_to_2d(monkeypatch):
    monkeypatch.setattr(B, "find_blender", lambda: None)
    spec = {"id": "s4", "title": "The platform", "treatment": "blender3d", "shot": "layers3d",
            "labels": [{"text": "Teams", "anchor": "Teams"}, {"text": "Platform", "anchor": "Platform"}]}
    assert B.render_shot(spec, Path("."), 64, 64) is None
    fb = B.fallback_spec(spec)
    assert fb["treatment"] == "motion" and fb["effect"] == "stacking_cards" and fb["items"][0]["title"] == "Teams"
    from exposit.render import engine
    tr = engine.build(spec, {"duration": 2.0, "sentences": [], "words": []}, "navy-gold", portrait=True)
    assert type(tr).__name__ == "MotionScene"                        # the production still renders
    assert not B.wanted({"three_d": "auto"})


def test_brief_can_switch_3d_off(monkeypatch):
    monkeypatch.setattr(B, "find_blender", lambda: "blender")
    monkeypatch.setattr(B.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": "Blender 4.2.0"})())
    assert B.wanted({}) and not B.wanted({"three_d": "off"})


@pytest.mark.parametrize("shot", B.SHOT_TYPES + ("test",))
def test_scripts_compile_and_never_render_text(shot):
    src = B.script_for({"shot": shot})
    compile(src, f"<{shot}>", "exec")                                 # valid Python without bpy
    low = src.lower()
    assert "text_add" not in low and '"font"' not in low and "'font'" not in low   # no text objects in 3D
    assert "--factory-startup" not in src                            # flags belong on the command line


def _fake_popen(calls):
    from PIL import Image

    class P:
        def __init__(self, cmd, stdout=None, stderr=None):
            calls.append(cmd)
            assert cmd[1:3] == ["-b", "--factory-startup"] and "--threads" in cmd
            args = json.loads(Path(cmd[-1]).read_text(encoding="utf-8"))
            out = Path(args["out"])
            for i in range(1, args["frames"] + 1):
                im = Image.new("RGBA", (args["w"], args["h"]), (0, 0, 0, 0))
                im.paste((200, 150, 60, 255), (2, 2, args["w"] - 2, args["h"] - 2))
                im.save(out / f"f_{i:04d}.png")
            (out / "anchors.json").write_text(json.dumps({"frames": args["frames"], "anchors": {"a": [[0.5, 0.5, 1]] * args["frames"]},
                                                          "progress": [0.0] * args["frames"]}))

        def wait(self, timeout=None):
            return 0

        def kill(self):
            pass
    return P


def test_render_is_cached(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(B, "find_blender", lambda: "blender")
    monkeypatch.setattr(B.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": "Blender 4.2.0"})())
    monkeypatch.setattr(B.subprocess, "Popen", _fake_popen(calls))
    spec = {"shot": "stack3d", "frames": 2, "params": {"cards": ["a"]}}
    d1 = B.render_shot(spec, tmp_path, 16, 16)
    d2 = B.render_shot(spec, tmp_path, 16, 16)
    assert d1 == d2 and len(calls) == 1                               # the second call is a cache hit
    assert (d1 / "done.json").exists() and (d1 / "blender.log").exists()
    assert B.render_shot(dict(spec, params={"cards": ["a", "b"]}), tmp_path, 16, 16) != d1   # a new spec renders again


def test_transparent_only_frames_are_rejected(monkeypatch, tmp_path):
    from PIL import Image

    class Empty:
        def __init__(self, cmd, stdout=None, stderr=None):
            args = json.loads(Path(cmd[-1]).read_text(encoding="utf-8"))
            for i in range(1, args["frames"] + 1):
                Image.new("RGBA", (args["w"], args["h"]), (0, 0, 0, 0)).save(Path(args["out"]) / f"f_{i:04d}.png")
            (Path(args["out"]) / "anchors.json").write_text("{}")

        def wait(self, timeout=None):
            return 0
    monkeypatch.setattr(B, "find_blender", lambda: "blender")
    monkeypatch.setattr(B.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": "Blender 4.2.0"})())
    monkeypatch.setattr(B.subprocess, "Popen", Empty)
    assert B.render_shot({"shot": "test", "frames": 2}, tmp_path, 16, 16) is None


def test_timeout_kills_and_falls_back(monkeypatch, tmp_path):
    killed = []

    class Slow:
        def __init__(self, *a, **k):
            pass

        def wait(self, timeout=None):
            if not killed:
                raise B.subprocess.TimeoutExpired("blender", timeout)
            return -9

        def kill(self):
            killed.append(True)
    monkeypatch.setattr(B, "find_blender", lambda: "blender")
    monkeypatch.setattr(B.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": "Blender 4.2.0"})())
    monkeypatch.setattr(B.subprocess, "Popen", Slow)
    monkeypatch.setattr(B, "timeout_for", lambda *a, **k: 0)
    assert B.render_shot({"shot": "test", "frames": 2}, tmp_path, 16, 16) is None and killed


def test_storyboard_gate_limits_3d_shots():
    from exposit import gates
    sc = [{"id": f"s{i}", "title": "t", "sentences": [{"text": "word " * 25, "claims": []}]} for i in range(1, 6)]
    shots = [{"id": f"s{i}", "treatment": "blender3d", "shot": "layers3d", "labels": [], "cues": [{"at": 0.5, "action": "pulse"}] * 6}
             for i in range(1, 6)]
    g = gates.storyboard_gate({"scenes": shots}, {"scenes": sc}, {"model": {}})
    crit = {c["name"]: c for c in g["criteria"]}
    assert not crit["3D shots: at most 2-3 per 60 s, known types, labels >= 30 px"]["passed"]


@pytest.mark.skipif(not B.find_blender(), reason="Blender is not installed")
def test_integration_two_frames(tmp_path):
    d = B.render_shot({"shot": "stack3d", "frames": 2, "params": {"cards": ["a", "b"]}}, tmp_path, 64, 64)
    assert d is not None and (d / "f_0002.png").exists()


def test_render_size_caps_the_3d_layer():
    assert B.render_size(1080, 1920) == (720, 1280)
    assert B.render_size(540, 960) == (540, 960)
    assert B.render_size(1920, 1080) == (1280, 720)


def test_memory_watchdog_aborts(monkeypatch, tmp_path):
    killed = []

    class Hungry:
        pid = 1

        def __init__(self, *a, **k):
            pass

        def wait(self, timeout=None):
            if not killed:
                raise B.subprocess.TimeoutExpired("blender", timeout)
            return -9

        def kill(self):
            killed.append(True)
    notes = []
    monkeypatch.setattr(B, "find_blender", lambda: "blender")
    monkeypatch.setattr(B.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": "Blender 5.3.0"})())
    monkeypatch.setattr(B.subprocess, "Popen", Hungry)
    monkeypatch.setattr(B, "_rss", lambda pid: 3_000_000_000)
    assert B.render_shot({"shot": "test", "frames": 2}, tmp_path, 16, 16, log=notes.append) is None
    assert killed and "aborted" in notes[-1]


@pytest.mark.parametrize("shot", B.SHOT_TYPES + ("test",))
def test_every_anchor_belongs_to_an_object(shot):
    import re
    calls = re.findall(r"anchor\(([^\n]*)\)", B.BUILDERS[shot])
    assert calls and all("parent=" in c or "of=" in c for c in calls), calls


@pytest.mark.slow
@pytest.mark.skipif(not B.find_blender(), reason="Blender is not installed")
@pytest.mark.parametrize("shot", ["layers3d", "path3d", "stack3d", "network3d", "device3d"])
def test_anchors_land_inside_their_objects_on_screen(shot, tmp_path):
    """Renders 3 tiny frames and checks every label anchor sits inside its object's projected bounds."""
    params = {"layers3d": {"layers": [{"name": "a"}, {"name": "b", "glow": True}, {"name": "c"}], "sink": 2},
              "stack3d": {"cards": ["a", "b"]}}.get(shot, {})
    d = B.render_shot({"shot": shot, "frames": 6, "params": params}, tmp_path, 90, 160)
    assert d is not None
    a = json.loads((d / "anchors.json").read_text())
    for name, pts in a["anchors"].items():
        for f, ((x, y, z), (x0, y0, x1, y1)) in enumerate(zip(pts, a["bounds"][name])):
            if z <= 0 or not (0 <= x <= 1 and 0 <= y <= 1):
                continue                                   # behind the camera or out of frame on this frame
            m = 0.02
            assert x0 - m <= x <= x1 + m and y0 - m <= y <= y1 + m, f"{shot}:{name} frame {f + 1} outside its object"
    if shot == "path3d":                                   # the badges' anchor rides the block along the road
        (xa, ya, _), (xb, yb, _) = a["anchors"]["mover"][0], a["anchors"]["mover"][-1]
        assert abs(xb - xa) + abs(yb - ya) > 0.1, "the mover anchor does not move"
