"""4-second mascot test on cream (1080x1920, 30 fps): idle -> hop -> glasses drop with shine. Also a strip of key frames."""
import subprocess, sys
from pathlib import Path
R = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(R))
import numpy as np, skia, imageio_ffmpeg
from exposit.render import mascot as M, design as D, styles
O = Path(__file__).parent / "out"; O.mkdir(exist_ok=True)
spec = {"scale": 4, "pos": [340, 1150], "acts": [{"type": "hop", "at": 1.2, "to": [740, 1150]},
                                                  {"type": "glasses", "at": 2.35}]}
m = M.Mascot(spec, lambda at, d=0.0: float(at) if at is not None else d)
W, H, N = 1080, 1920, 120
ff = subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
                       "-r", "30", "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", str(O / "mascot_test.mp4")], stdin=subprocess.PIPE)
keys = {10: "idle", 37: "squash", 40: "rise", 44: "apex", 48: "land", 72: "glasses up", 79: "blink", 84: "sliding", 88: "bounce", 92: "shine"}
strip = []
for i in range(N):
    s = skia.Surface(W, H); c = s.getCanvas(); c.clear(D.col("#F4F1EA"))
    c.drawLine(0, 1150, W, 1150, D.paint(D.col("#D97757"), 3))
    m.draw(c, i / 30)
    img = s.makeImageSnapshot()
    ff.stdin.write(np.array(img.toarray(colorType=skia.kRGBA_8888_ColorType)).tobytes())
    if i in keys:
        strip.append((keys[i], img))
ff.stdin.close(); ff.wait()
sh = skia.Surface(270 * 5, 330 * 2); c = sh.getCanvas(); c.clear(D.col("#F4F1EA"))
D.set_active(D.TEMPLATES["claude-orange"])
for j, (lab, img) in enumerate(strip):
    x, y = (j % 5) * 270, (j // 5) * 330
    c.drawImageRect(img, skia.Rect.MakeXYWH(220, 860, 640, 320), skia.Rect.MakeXYWH(x, y + 40, 270, 135 * 2), skia.SamplingOptions(skia.FilterMode.kNearest))
    D.draw_text(c, lab, x + 135, y + 34, 30, D.col("#1F1E1D"), "SemiBold", "center")
sh.makeImageSnapshot().save(str(O / "mascot_keys.png"))
print("ok")
