"""Sound design made from scratch with numpy: a soft ambient bed, cue sounds, and the final mix.
Nothing is downloaded, so there is no licence question."""
from __future__ import annotations
import numpy as np
import soundfile as sf
from scipy.signal import butter, lfilter, resample_poly

SR = 48000


def _lp(x, cutoff):
    b, a = butter(2, cutoff / (SR / 2), btype="low")
    return lfilter(b, a, x)


def music_bed(duration: float, seed: int = 7) -> np.ndarray:
    """A slow pad on a four-chord loop. Quiet by design."""
    n = int(duration * SR)
    t = np.arange(n) / SR
    chords = [[220.0, 261.63, 329.63, 392.0], [174.61, 220.0, 261.63, 329.63], [130.81, 196.0, 261.63, 329.63], [196.0, 246.94, 293.66, 392.0]]
    bar = 6.0
    out = np.zeros(n)
    rng = np.random.default_rng(seed)
    for ci in range(int(duration / bar) + 2):
        ch = chords[ci % 4]
        s0 = int((ci * bar - 1.0) * SR)
        ln = int((bar + 2.0) * SR)
        tt = np.arange(ln) / SR
        env = np.clip(tt / 1.6, 0, 1) * np.clip((bar + 2.0 - tt) / 1.6, 0, 1)
        seg = np.zeros(ln)
        for f in ch:
            for det in (-0.25, 0.0, 0.31):
                seg += np.sin(2 * np.pi * (f + det) * tt + rng.uniform(0, 6.28)) / 12
            seg += np.sin(2 * np.pi * f * 2 * tt) / 60
        seg *= env
        a, b = max(0, s0), min(n, s0 + ln)
        if b > a:
            out[a:b] += seg[a - s0: b - s0]
    out = _lp(out, 1800) * (0.85 + 0.15 * np.sin(2 * np.pi * 0.08 * t))
    return out.astype(np.float32)


def blip(freq: float = 880.0, dur: float = 0.22) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    return (np.sin(2 * np.pi * freq * t) * np.exp(-t * 22) * 0.5 + np.sin(2 * np.pi * freq * 1.5 * t) * np.exp(-t * 30) * 0.2).astype(np.float32)


def whoosh(dur: float = 0.7, seed: int = 3) -> np.ndarray:
    n = int(dur * SR)
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n)
    t = np.arange(n) / n
    env = np.sin(np.pi * t) ** 2
    lo = _lp(x, 900)
    hi = _lp(x, 3500)
    return ((lo * (1 - t) + hi * t) * env * 0.35).astype(np.float32)


def tick() -> np.ndarray:
    t = np.arange(int(0.05 * SR)) / SR
    return (np.sin(2 * np.pi * 1500 * t) * np.exp(-t * 90) * 0.25).astype(np.float32)


SFX = {"packet": lambda: blip(740), "highlight": lambda: blip(988, 0.18), "callout": lambda: blip(587, 0.3),
       "count": lambda: blip(1174, 0.16), "enter": lambda: blip(523, 0.3), "transition": whoosh, "type": tick,
       "soft": lambda: blip(660, 0.2) * 0.45}         # end-slide lines: quieter than cue sounds


def mix(narration: list[tuple[float, str]], events: list[tuple[float, str]], duration: float, out_wav: str,
        music: bool = True, sfx: bool = True, recorded: list[tuple[float, str]] | None = None) -> dict:
    """narration: (start_seconds, wav_path) per scene. events: (time, sfx name). Writes a 48 kHz stereo wav."""
    n = int(duration * SR) + SR // 4
    voice = np.zeros(n, dtype=np.float32)
    for start, path in narration:
        a, sr = sf.read(path, dtype="float32")
        if a.ndim > 1:
            a = a.mean(axis=1)
        if sr != SR:
            a = resample_poly(a, SR, sr).astype(np.float32)
        i = int(start * SR)
        voice[i:i + len(a)] += a[: max(0, n - i)]
    peak = float(np.max(np.abs(voice)) or 1.0)
    voice *= 0.89 / peak
    fx = np.zeros(n, dtype=np.float32)
    if sfx:
        cache: dict = {}
        for tm, name in events:
            if name not in SFX:
                continue
            s = cache.setdefault(name, SFX[name]())
            i = int(tm * SR)
            if 0 <= i < n:
                fx[i:i + len(s)] += s[: n - i]
    bed = np.zeros(n, dtype=np.float32)
    if music:
        bed = music_bed(n / SR)[:n]
        env = _lp(np.abs(voice), 6)                      # follow the voice level
        duck = 1.0 - 0.6 * np.clip(env / 0.08, 0, 1)      # lower the bed while the voice speaks
        fade = np.clip(np.arange(n) / (1.5 * SR), 0, 1) * np.clip((n - np.arange(n)) / (2.0 * SR), 0, 1)
        bed = bed * duck * fade * 0.20
    rec = np.zeros(n, dtype=np.float32)                   # recorded sound (footage effects), at its own level
    for start, path in recorded or []:
        a, sr = sf.read(path, dtype="float32")
        if a.ndim > 1:
            a = a.mean(axis=1)
        if sr != SR:
            a = resample_poly(a, SR, sr).astype(np.float32)
        i = int(start * SR)
        rec[i:i + len(a)] += a[: max(0, n - i)]
    out = voice + fx * 0.16 + bed + rec * 0.8
    out = np.tanh(out * 1.05) / np.tanh(1.05) * 0.94
    stereo = np.stack([out, out], axis=1)
    sf.write(out_wav, stereo, SR)
    return {"duration": n / SR, "peak": float(np.max(np.abs(out))), "music": music, "sfx": sfx}
