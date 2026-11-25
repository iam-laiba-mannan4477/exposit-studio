"""Joining, subtitles and automated checks, all through ffmpeg."""
from __future__ import annotations
import re, subprocess
from pathlib import Path
from . import config
from .render.engine import caption_chunks


def _run(args: list[str], timeout: int = 1800) -> str:
    r = subprocess.run([config.ffmpeg_exe(), "-hide_banner", *args], capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    return r.stderr + r.stdout


def probe(path: str) -> dict:
    out = _run(["-i", path])
    d = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", out)
    v = re.search(r"Video: (\w+).*?, (\d{2,5})x(\d{2,5})[^\n]*?([\d.]+) fps", out)
    a = re.search(r"Audio: (\w+)[^\n]*?(\d+) Hz", out)
    return {"duration": (int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))) if d else 0.0,
            "vcodec": v.group(1) if v else "", "width": int(v.group(2)) if v else 0, "height": int(v.group(3)) if v else 0,
            "fps": float(v.group(4)) if v else 0.0, "acodec": a.group(1) if a else "", "sample_rate": int(a.group(2)) if a else 0}


def concat(clips: list[str], out: str) -> None:
    lst = Path(out).with_suffix(".txt")
    lst.write_text("".join(f"file '{Path(c).as_posix()}'\n" for c in clips), encoding="utf-8")
    o = _run(["-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", out])
    if not Path(out).exists():
        raise RuntimeError("Joining clips failed: " + o[-400:])


def mux(video: str, audio: str, out: str) -> None:
    o = _run(["-y", "-i", video, "-i", audio, "-c:v", "copy", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000",
              "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out])
    if not Path(out).exists():
        raise RuntimeError("Muxing failed: " + o[-400:])


def _ts(t: float, sep: str) -> str:
    t = max(0.0, t)
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h:02d}:{m:02d}:{int(s):02d}{sep}{int(round((s - int(s)) * 1000)):03d}"


def subtitles(scenes: list[tuple[float, dict]]) -> tuple[str, str]:
    """scenes: (absolute start of narration, timing). Returns SRT and VTT text."""
    cues = []
    for start, timing in scenes:
        for c in caption_chunks(timing):
            cues.append((start + c["s"], start + c["e"] + 0.15, c["text"]))
    srt = "".join(f"{i}\n{_ts(a, ',')} --> {_ts(b, ',')}\n{t}\n\n" for i, (a, b, t) in enumerate(cues, 1))
    vtt = "WEBVTT\n\n" + "".join(f"{_ts(a, '.')} --> {_ts(b, '.')}\n{t}\n\n" for a, b, t in cues)
    return srt, vtt


EMPTY_FRACTION = 0.015      # under 1.5% of the content band differs from its background: only a heading or nothing


def empty_frames(path: str, skip: list[tuple[float, float]], portrait: bool = True, step: float = 0.25,
                 longest: float = 0.5) -> list[tuple[float, float]]:
    """Stretches longer than `longest` s where the content band (y 260-1500 of 1920 in 9:16) is near-empty background.
    Samples every `step` s at 270 px wide; a pixel counts as content when it differs from its row's median by more than
    22 levels (faint grids and gradients do not count). `skip` holds (start, end) intervals: transitions, the end slide."""
    import numpy as np
    W, H = (270, 480) if portrait else (480, 270)
    y0, y1 = (int(H * 260 / 1920), int(H * 1500 / 1920)) if portrait else (int(H * 0.15), int(H * 0.85))
    raw = subprocess.run([config.ffmpeg_exe(), "-loglevel", "error", "-i", path, "-vf", f"fps={1 / step},scale={W}:{H},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W)[:, y0:y1, :].astype(np.int16)
    frac = (np.abs(fr - np.median(fr, axis=2, keepdims=True)) > 22).mean(axis=(1, 2))
    runs, start = [], None
    for i, f in enumerate(list(frac) + [1.0]):
        t = i * step
        empty = f < EMPTY_FRACTION and not any(a <= t <= b for a, b in skip)
        if empty and start is None:
            start = t
        elif not empty and start is not None:
            if t - start > longest:
                runs.append((round(start, 2), round(t - step, 2)))
            start = None
    return runs


def checks(path: str, expect: dict) -> list[dict]:
    """Automated checks on a finished video. expect: width, height, fps, duration, tolerance."""
    res = []
    p = probe(path)
    res.append({"name": "Dimensions", "passed": p["width"] == expect["width"] and p["height"] == expect["height"],
                "detail": f"{p['width']} x {p['height']}"})
    res.append({"name": "Frame rate", "passed": abs(p["fps"] - expect["fps"]) < 0.01, "detail": f"{p['fps']} fps"})
    tol = expect.get("tolerance", 3.0)
    tail = float(expect.get("exclude_tail", 0.0))        # the end slide is not part of the content length
    main = p["duration"] - tail
    res.append({"name": "Duration", "passed": abs(main - expect["duration"]) <= tol,
                "detail": f"{main:.1f} s (target {expect['duration']:.0f} s, tolerance {tol:.0f} s)"
                          + (f"; end slide {tail:.1f} s not counted" if tail else "")})
    out = _run(["-i", path, "-vf", "blackdetect=d=0.7:pix_th=0.06,freezedetect=n=0.001:d=5", "-af",
                "silencedetect=n=-45dB:d=3,volumedetect", "-f", "null", "-"])
    black = re.findall(r"black_start:([\d.]+)", out)
    res.append({"name": "No black stretches", "passed": not black, "detail": "At " + ", ".join(black) + " s" if black else "None found"})
    frozen = re.findall(r"freeze_start: ([\d.]+)", out)
    res.append({"name": "No frozen picture over 5 s", "passed": not frozen, "detail": "At " + ", ".join(frozen) + " s" if frozen else "None found"})
    sil = re.findall(r"silence_start: ([\d.]+)", out)
    res.append({"name": "No silence over 3 s", "passed": not sil, "detail": "At " + ", ".join(sil) + " s" if sil else "None found"})
    mv = re.search(r"max_volume: (-?[\d.]+) dB", out)
    mean = re.search(r"mean_volume: (-?[\d.]+) dB", out)
    if mv:
        res.append({"name": "Audio does not clip", "passed": float(mv.group(1)) <= -0.3, "detail": f"Peak {mv.group(1)} dB, mean {mean.group(1) if mean else '?'} dB"})
    else:
        res.append({"name": "Audio track present", "passed": False, "detail": "No audio measured"})
    if expect.get("empty_skip") is not None:
        runs = empty_frames(path, expect["empty_skip"], expect["height"] > expect["width"])
        res.append({"name": "No empty frames", "passed": not runs,
                    "detail": ("Near-empty content at " + ", ".join(f"{a:.2f}-{b:.2f} s" for a, b in runs)) if runs else "None found (sampled every 0.25 s)"})
    res.append({"name": "Plays outside the studio", "passed": p["vcodec"] == "h264" and p["acodec"] == "aac", "detail": f"{p['vcodec']} video, {p['acodec']} audio, MP4"})
    if expect.get("end_slide"):
        a, b = expect["end_slide"]
        o2 = _run(["-ss", f"{a:.3f}", "-t", f"{max(0.1, b - a):.3f}", "-i", path, "-af", "volumedetect", "-vn", "-f", "null", "-"])
        mv = re.search(r"mean_volume: (-?[\d.]+) dB", o2)
        level = float(mv.group(1)) if mv else -99.0
        res.append({"name": "End slide is narrated", "passed": level > -40.0,
                    "detail": f"mean {level:.1f} dB over {a:.1f}-{b:.1f} s" + ("" if level > -40.0 else ": no voice on the end slide")})
    return res
