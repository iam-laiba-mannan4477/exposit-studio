"""Gate renders for the optional Blender 3D treatment: a 3-second 540x960 sample of each shot type, and the
"Platform engineering, explained" S4 (layers3d) and S5 (path3d) previews. One Blender process at a time.
Prints render time and peak RAM per shot (from each shot's done.json). Without Blender, renders the 2D fallbacks.
Usage: python docs/plans/blender-samples/render_samples.py [samples] [platform]"""
import json, sys, time
from pathlib import Path
R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R))
from exposit.render import engine, blender3d, styles  # noqa: E402,F401

H = Path(__file__).parent
OUT = H / "out"
OUT.mkdir(exist_ok=True)
TIMING = {"duration": 2.6, "sentences": [], "words": []}
NAVY = {"bg": "#0B1220", "base": "#1C2A46", "accent": "#E8B44A", "glow": "#E8B44A", "rim": "#8FB8FF", "text": "#F4F1EA"}

SAMPLES = {
 "layers3d": {"params": {"layers": [{"name": "apps"}, {"name": "platform", "glow": True}, {"name": "infrastructure"}], "sink": 5},
              "labels": [{"text": "apps", "anchor": "apps", "at": 0.3}, {"text": "platform", "anchor": "platform", "at": 0.6},
                         {"text": "infrastructure", "anchor": "infrastructure", "at": 0.9}]},
 "path3d": {"labels": [{"text": "template", "anchor": "start", "at": 0.2}, {"text": "production", "anchor": "end", "at": 0.4}]},
 "stack3d": {"params": {"cards": ["one", "two", "three", "four"]}, "labels": [{"text": "four", "anchor": "four", "at": 1.6}]},
 "network3d": {"labels": [{"text": "hub", "anchor": "hub", "at": 0.3}]},
 "device3d": {"params": {"device": "laptop"}, "labels": [{"text": "laptop", "anchor": "device", "at": 1.2}]},
 "globe3d": {"params": {"texture": str(R / "exposit" / "assets" / "earth" / "day-4096.jpg"), "spin": 30},
             "labels": [{"text": "Earth", "anchor": "globe", "at": 0.5}]},
}
PLATFORM = {
 "S4_layers3d": {"shot": "layers3d", "palette": NAVY, "seconds": 6.0, "camera": {"orbit": 22, "dolly": 1.0, "dof": True},
                 "params": {"layers": [{"name": "Teams"}, {"name": "Internal Developer Platform", "glow": True},
                                       {"name": "Infrastructure tools"}], "sink": 7},
                 "labels": [{"text": "Teams", "anchor": "Teams", "at": 0.6, "side": "left"},
                            {"text": "Internal Developer Platform", "anchor": "Internal Developer Platform", "at": 1.6, "side": "left",
                             "color": "#FFD37A"},
                            {"text": "Infrastructure tools", "anchor": "Infrastructure tools", "at": 2.6, "side": "left"}]},
 "S5_path3d": {"shot": "path3d", "palette": NAVY, "seconds": 6.0, "camera": {"orbit": 10, "dolly": 1.5, "elevation": 34, "distance": 11},
               "labels": [{"text": "template", "anchor": "start", "at": 0.3}, {"text": "production", "anchor": "end", "at": 0.6},
                          {"text": "CI", "anchor": "mover", "progress": 0.25, "dy": -60}, {"text": "security scan", "anchor": "mover", "progress": 0.5, "dy": -60},
                          {"text": "observability", "anchor": "mover", "progress": 0.75, "dy": -60}]},
}


def render(name, spec, theme):
    sp = dict({"id": name, "title": name, "treatment": "blender3d", "_px": [540, 960], "pad_start": 0.2, "pad_end": 0.2}, **spec)
    sp.setdefault("shot", name)
    t0 = time.time()
    info = engine.render_clip(sp, dict(TIMING, duration=float(spec.get("seconds", 3.0)) - 0.4), str(OUT / f"{name}.mp4"),
                              540, 960, 30, theme, False)
    done = [p for p in blender3d.cache_dir().glob("*/done.json") if p.stat().st_mtime >= t0]   # rendered by this call
    d = json.loads(done[0].read_text()) if done else {}
    mode = "3D" if d else "2D fallback (Blender not found)" if not blender3d.available() else "2D fallback (render failed)"
    print(f"{name:14s} {mode:32s} blender {d.get('seconds', '-')} s, peak RAM {d.get('peak_rss_mb', '-')} MB, "
          f"total {time.time() - t0:.1f} s -> {OUT / (name + '.mp4')}", flush=True)


if __name__ == "__main__":
    args = sys.argv[1:] or ["samples", "platform"]
    print("Blender:", blender3d.info().get("path") or "not found", blender3d.info().get("version", ""))
    if "samples" in args:
        for name, spec in SAMPLES.items():
            render(name, dict(spec, seconds=3.0), "claude-orange-dark")
    if "platform" in args:
        for name, spec in PLATFORM.items():
            render(name, spec, "navy-gold")
