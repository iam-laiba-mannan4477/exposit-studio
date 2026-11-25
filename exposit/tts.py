"""Narration. Each sentence is synthesised separately, so sentence boundaries are exact.
Word times inside a sentence are estimated from word length unless an aligner is installed."""
from __future__ import annotations
import json, re
from pathlib import Path
import numpy as np
import soundfile as sf
from . import config, store

SR = 24000
_kokoro = None

PRONUNCIATION = {  # written form -> spoken form, applied before synthesis only
    "NGINX": "engine X", "nginx": "engine X", "kubectl": "kube control", "DNS": "D N S", "NLB": "N L B",
    "HTTP": "H T T P", "HTTPS": "H T T P S", "AWS": "A W S", "IP": "I P", "URL": "U R L",
    "CI/CD": "C I C D", "LLMOps": "L L M ops", "DevSecOps": "dev sec ops", "AI": "eh eye", "IaC": "eye eh see", "us-east-1": "U S East 1", "CDN": "C D N",
    "CLAUDE.local.md": "Claude dot local dot M D", "CLAUDE.md": "Claude dot M D", ".mcp.json": "dot M C P dot jay-son",
    "settings.local.json": "settings dot local dot jay-son", "settings.json": "settings dot jay-son", ".claude": "dot Claude",
    ".gitignore": "dot git-ignore", "JSON": "jay-son",   # spelled so the tokenizer reads eɪ aɪ / aɪ eɪ siː
}


# The table as it was before entries were added (2026-11-23). Narration recorded with it stays valid while none of the
# added entries applies to its words.
LEGACY_PRONUNCIATION = {
    "NGINX": "engine X", "nginx": "engine X", "kubectl": "kube control", "DNS": "D N S", "NLB": "N L B",
    "HTTP": "H T T P", "HTTPS": "H T T P S", "AWS": "A W S", "IP": "I P", "URL": "U R L",
}


def applied(sentences: list[str], table: dict | None = None) -> dict:
    """The pronunciation entries that actually change these sentences (the part that matters for a cache key)."""
    table = PRONUNCIATION if table is None else table
    text = " ".join(sentences)
    return {k: v for k, v in table.items() if re.search(rf"(?<![A-Za-z0-9]){re.escape(k)}(?![A-Za-z0-9])", text)}


def spoken(text: str, extra: dict | None = None) -> str:
    table = dict(PRONUNCIATION, **(extra or {}))
    for k in sorted(table, key=len, reverse=True):
        text = re.sub(rf"(?<![A-Za-z0-9]){re.escape(k)}(?![A-Za-z0-9])", table[k], text)
    return text


def engines() -> list[dict]:
    out = []
    m = config.MODELS
    ok = (m / "voices-v1.0.bin").exists() and any(m.glob("kokoro-v1.0*.onnx"))
    out.append({"id": "kokoro", "name": "Kokoro (local, free)", "available": ok,
                "note": "" if ok else "Model files missing: run install.ps1 or scripts/download-models.ps1"})
    return out


def kokoro():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        model = sorted(config.MODELS.glob("kokoro-v1.0*.onnx"))
        if not model or not (config.MODELS / "voices-v1.0.bin").exists():
            raise RuntimeError("Kokoro model files are missing. Run scripts/download-models (see README).")
        _kokoro = Kokoro(str(model[0]), str(config.MODELS / "voices-v1.0.bin"))
    return _kokoro


def unload() -> None:
    """Free the voice model before rendering to keep memory low."""
    global _kokoro
    _kokoro = None


def voices() -> list[str]:
    try:
        return [v for v in kokoro().get_voices() if v[:2] in ("af", "am", "bf", "bm")]
    except Exception:
        return []


def _trim(a: np.ndarray, thr: float = 0.004) -> np.ndarray:
    idx = np.where(np.abs(a) > thr)[0]
    if len(idx) == 0:
        return a
    return a[max(0, idx[0] - 600): min(len(a), idx[-1] + 2400)]


def synth_sentence(text: str, voice: str, speed: float, lang: str = "en-us", pron: dict | None = None) -> np.ndarray:
    key = store.sha("kokoro", spoken(text, pron), voice, speed, lang)      # the spoken form: table changes take effect
    f = config.DATA / "cache" / "tts" / f"{key}.npy"
    if f.exists():
        return np.load(f)
    samples, sr = kokoro().create(spoken(text, pron), voice=voice, speed=float(speed), lang=lang)
    a = _trim(np.asarray(samples, dtype=np.float32))
    np.save(f, a)
    return a


def _word_weights(words: list[str]) -> list[float]:
    out = []
    for w in words:
        base = max(1.0, len(re.sub(r"[^A-Za-z0-9]", "", spoken(w))) * 1.0) + 1.2
        if w[-1:] in ",;:":
            base += 2.5
        if w[-1:] in ".?!":
            base += 1.0
        out.append(base)
    return out


def narrate_scene(sentences: list[str], out_wav: Path, voice: str = "am_michael", speed: float = 1.0,
                  gap: float = 0.22, lang: str = "en-us", pron: dict | None = None) -> dict:
    """Synthesise a scene. Returns the timing document and writes the wav."""
    chunks, timing_s, words = [], [], []
    t = 0.0
    for si, s in enumerate(sentences):
        a = synth_sentence(s, voice, speed, lang, pron)
        d = len(a) / SR
        ws = s.split()
        wt = _word_weights(ws)
        tot = sum(wt) or 1.0
        lead, tail = 0.03, 0.10
        span = max(0.05, d - lead - tail)
        acc = 0.0
        for w, wgt in zip(ws, wt):
            s0 = t + lead + span * acc / tot
            acc += wgt
            words.append({"w": w, "s": round(s0, 3), "e": round(t + lead + span * acc / tot, 3), "si": si})
        timing_s.append({"text": s, "s": round(t, 3), "e": round(t + d, 3)})
        chunks.append(a)
        t += d
        if si < len(sentences) - 1:
            chunks.append(np.zeros(int(gap * SR), dtype=np.float32))
            t += gap
    audio = np.concatenate(chunks) if chunks else np.zeros(SR, dtype=np.float32)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_wav), audio, SR)
    timing = {"duration": round(len(audio) / SR, 3), "sentences": timing_s, "words": words,
              "alignment": "sentence-exact, word-estimated", "voice": voice, "speed": speed}
    out_wav.with_suffix(".timing.json").write_text(json.dumps(timing, indent=1), encoding="utf-8")
    return timing
