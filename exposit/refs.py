"""Reference analysis: measurements from a file you supply. Structure and numbers only; nothing is copied.

Works without a model: metadata, shot boundaries, representative frames, editing rhythm, loudness and pauses,
motion level per shot, dominant colours. A transcript is used if you paste one, or produced locally if
faster-whisper is installed. Judgements that need a vision model are listed as unsupported, not guessed.
"""
from __future__ import annotations
import io, json, re, statistics, subprocess, time
from pathlib import Path
import numpy as np
from . import config, store, compose, knowledge

VIDEO = (".mp4", ".mov", ".mkv", ".webm", ".m4v")
IMAGE = (".png", ".jpg", ".jpeg", ".webp")

UNSUPPORTED = [
    {"capability": "Naming the animation style of each shot", "why": "Needs a vision-capable model; none is called here."},
    {"capability": "Classifying camera moves (pan, zoom, orbit)", "why": "Only an overall motion level per shot is measured."},
    {"capability": "Classifying every transition type", "why": "Hard cuts and fades through a dark or flat frame are detected; dissolves between two pictures and wipes are not."},
    {"capability": "Analysing a video from a web address", "why": "Exposit does not download from platforms. Upload a file you are allowed to use."},
]


def rdir(rid: str) -> Path:
    d = config.DATA / "references" / rid
    (d / "frames").mkdir(parents=True, exist_ok=True)
    return d


def create(title: str, filename: str, content: bytes, transcript: str = "", url: str = "") -> dict:
    rid = store.new_id("ref")
    d = rdir(rid)
    kind = "note"
    if filename:
        ext = Path(filename).suffix.lower()
        kind = "video" if ext in VIDEO else "image" if ext in IMAGE else "document"
        (d / ("source" + ext)).write_bytes(content)
    if transcript.strip():
        (d / "transcript.txt").write_text(transcript, encoding="utf-8")
    data = {"kind": kind, "filename": filename, "url": url, "has_transcript": bool(transcript.strip())}
    store.q("INSERT INTO refs VALUES(?,?,?,?,?)", (rid, title or filename or url or "Reference", store.now(), "queued", store.jdump(data)))
    return get(rid)


def get(rid: str) -> dict | None:
    r = store.q("SELECT * FROM refs WHERE id=?", (rid,))
    if not r:
        return None
    d = json.loads(r[0].pop("data") or "{}")
    r[0].update(d)
    f = rdir(rid) / "analysis.json"
    r[0]["analysis"] = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    return r[0]


def all_refs() -> list[dict]:
    return [get(r["id"]) for r in store.q("SELECT id FROM refs ORDER BY created DESC")]


def _ff(args: list[str], timeout: int = 900) -> str:
    r = subprocess.run([config.ffmpeg_exe(), "-hide_banner", *args], capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    return r.stderr


def _grey_frames(path: str, fps: float, w: int = 64, h: int = 36) -> np.ndarray:
    p = subprocess.run([config.ffmpeg_exe(), "-loglevel", "error", "-i", path, "-vf", f"fps={fps},scale={w}:{h},format=gray", "-f", "rawvideo", "-"],
                       capture_output=True, timeout=900)
    a = np.frombuffer(p.stdout, dtype=np.uint8)
    n = len(a) // (w * h)
    return a[: n * w * h].reshape(n, h, w).astype(np.float32)


def fades(path: str, fps: float = 10.0) -> list[float]:
    """Fades through a dark or flat frame: moments where picture contrast collapses to under half of what surrounds it."""
    fr = _grey_frames(path, fps)
    if len(fr) < 5:
        return []
    con = fr.std(axis=(1, 2))
    win = int(fps * 1.5)
    out: list[float] = []
    for i in range(1, len(con) - 1):
        lo, hi = max(0, i - win), min(len(con), i + win + 1)
        around = np.median(con[lo:hi])
        before, after = con[max(0, i - int(fps)):i].max(initial=0), con[i + 1:i + 1 + int(fps)].max(initial=0)
        if con[i] <= con[i - 1] and con[i] <= con[i + 1] and around > 3 and con[i] < 0.5 * around and before > 2 * con[i] and after > 2 * con[i]:
            t = i / fps
            if not out or t - out[-1] > 0.6:
                out.append(round(t, 2))
    return out


def shots(path: str, duration: float, threshold: float = 0.30) -> list[dict]:
    """Shot boundaries: hard cuts (FFmpeg scene score) plus fades through a dark or flat frame."""
    out = _ff(["-i", path, "-vf", f"select='gt(scene,{threshold})',showinfo", "-an", "-f", "null", "-"])
    cuts = {round(float(x), 2): "cut" for x in re.findall(r"pts_time:([\d.]+)", out)}
    for t in fades(path):
        if all(abs(t - c) > 0.6 for c in cuts):
            cuts[t] = "fade"
    marks = sorted((t, k) for t, k in cuts.items() if 0.3 < t < duration - 0.3)
    edges = [(0.0, "start")] + marks + [(duration, "end")]
    return [{"n": i + 1, "start": round(a[0], 2), "end": round(b[0], 2), "length": round(b[0] - a[0], 2), "begins_with": a[1]}
            for i, (a, b) in enumerate(zip(edges, edges[1:])) if b[0] - a[0] > 0.05]


def motion_series(path: str, fps: float = 2.0) -> np.ndarray:
    """Mean absolute difference between small grey frames, sampled at 2 fps."""
    w, h = 64, 36
    p = subprocess.run([config.ffmpeg_exe(), "-loglevel", "error", "-i", path, "-vf", f"fps={fps},scale={w}:{h},format=gray", "-f", "rawvideo", "-"],
                       capture_output=True, timeout=900)
    a = np.frombuffer(p.stdout, dtype=np.uint8)
    n = len(a) // (w * h)
    if n < 2:
        return np.zeros(0)
    fr = a[: n * w * h].reshape(n, h, w).astype(np.float32)
    return np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))


def palette(img_bytes: bytes, k: int = 5) -> list[str]:
    from PIL import Image
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB").resize((96, 54))
    q = im.quantize(k)
    pal = q.getpalette()[: k * 3]
    counts = sorted(q.getcolors(), reverse=True)
    return ["#%02X%02X%02X" % tuple(pal[i * 3: i * 3 + 3]) for _, i in counts]


def transcribe(path: str) -> dict:
    try:
        from faster_whisper import WhisperModel  # optional
    except Exception:
        return {"available": False, "note": "No transcript: paste one, or install the optional faster-whisper package (see README)."}
    model = WhisperModel(config.env("EXPOSIT_WHISPER_MODEL", "base.en"), device="cpu", compute_type="int8")
    segs, _ = model.transcribe(path, word_timestamps=True)
    words = [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)} for s in segs for w in (s.words or [])]
    return {"available": True, "source": "faster-whisper (local)", "words": words, "text": " ".join(w["w"] for w in words)}


def analyse(rid: str, ctx=None) -> dict:
    ref = get(rid)
    d = rdir(rid)
    store.q("UPDATE refs SET state='running' WHERE id=?", (rid,))
    say = (lambda m, p: ctx.say(m, p)) if ctx else (lambda m, p: None)
    an: dict = {"analysed": time.time(), "kind": ref["kind"], "unsupported": UNSUPPORTED, "notes": []}
    src = next(iter(d.glob("source.*")), None)
    transcript_text = (d / "transcript.txt").read_text(encoding="utf-8") if (d / "transcript.txt").exists() else ""
    if ref["kind"] == "video" and src:
        say("Reading metadata", 0.05)
        meta = compose.probe(str(src))
        an["metadata"] = meta
        dur = meta["duration"] or 0.0
        say("Finding shot boundaries", 0.2)
        sh = shots(str(src), dur)
        say("Measuring motion", 0.4)
        ms = motion_series(str(src))
        for s in sh:
            seg = ms[int(s["start"] * 2): max(int(s["start"] * 2) + 1, int(s["end"] * 2))]
            m = float(seg.mean()) if len(seg) else 0.0
            s["motion"] = round(m, 2)
            s["motion_level"] = "hold" if m < 0.6 else "gentle" if m < 3 else "busy"
        say("Extracting representative frames", 0.6)
        for s in sh[:40]:
            f = d / "frames" / f"shot-{s['n']:03d}.jpg"
            _ff(["-y", "-ss", f"{(s['start'] + s['end']) / 2:.2f}", "-i", str(src), "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "4", str(f)])
            if f.exists():
                s["frame"] = f.name
                s["palette"] = palette(f.read_bytes())
        lengths = [s["length"] for s in sh] or [dur]
        an["shots"] = sh
        an["rhythm"] = {"shot_count": len(sh), "hard_cuts": sum(x["begins_with"] == "cut" for x in sh), "fades": sum(x["begins_with"] == "fade" for x in sh), "cuts_per_minute": round((len(sh) - 1) / dur * 60, 1) if dur else 0, "median_shot_s": round(statistics.median(lengths), 2),
                        "shortest_shot_s": round(min(lengths), 2), "longest_shot_s": round(max(lengths), 2),
                        "share_of_time_in_motion": round(float((ms > 0.6).mean()), 2) if len(ms) else None,
                        "note": "Boundaries are hard cuts and fades through a dark or flat frame. Dissolves and continuous camera moves are not split, so such a video reads as fewer, longer shots."}
        say("Measuring audio", 0.8)
        out = _ff(["-i", str(src), "-af", "silencedetect=n=-38dB:d=0.35,volumedetect", "-vn", "-f", "null", "-"])
        sil = [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", out)]
        mean = re.search(r"mean_volume: (-?[\d.]+) dB", out)
        peak = re.search(r"max_volume: (-?[\d.]+) dB", out)
        an["audio"] = {"has_audio": bool(meta["acodec"]), "mean_volume_db": float(mean.group(1)) if mean else None, "peak_db": float(peak.group(1)) if peak else None,
                       "pauses": len(sil), "pause_total_s": round(sum(sil), 1), "longest_pause_s": round(max(sil), 2) if sil else 0,
                       "share_silent": round(sum(sil) / dur, 2) if dur else None}
        if not transcript_text:
            say("Transcribing, if a local recogniser is installed", 0.9)
            tr = transcribe(str(src))
            an["transcript"] = {k: v for k, v in tr.items() if k != "words"}
            transcript_text = tr.get("text", "")
    elif ref["kind"] == "image" and src:
        from PIL import Image
        im = Image.open(src)
        an["image"] = {"width": im.width, "height": im.height, "palette": palette(src.read_bytes(), 6)}
    elif ref["kind"] == "document" and src and not transcript_text:
        transcript_text = src.read_text(encoding="utf-8", errors="replace")[:60000]
    if ref.get("url"):
        an["notes"].append("A web address was recorded for reference. Exposit did not fetch it.")
    if transcript_text:
        words = transcript_text.split()
        sents = [s for s in re.split(r"(?<=[.!?])\s+", transcript_text.strip()) if s]
        dur = an.get("metadata", {}).get("duration") or 0
        an["narration"] = {"words": len(words), "sentences": len(sents), "median_sentence_words": statistics.median([len(s.split()) for s in sents]) if sents else 0,
                           "words_per_minute": round(len(words) / dur * 60) if dur else None, "questions": sum(s.strip().endswith("?") for s in sents),
                           "opens_with_question": bool(sents and sents[0].strip().endswith("?")),
                           "note": "Counts only. The wording itself is not stored in the library."}
    (d / "analysis.json").write_text(json.dumps(an, indent=1), encoding="utf-8")
    store.q("UPDATE refs SET state='done' WHERE id=?", (rid,))
    return an


def to_library(rid: str) -> list[dict]:
    """Turns measurements into library items at the 'observation' tier. Numbers and structure only."""
    ref = get(rid)
    an = ref.get("analysis") or {}
    made = []
    base = {"kind": "reference", "category": "Reference analyses", "tier": "observation", "source": f"Reference: {ref['title']}", "date": time.strftime("%Y-%m-%d"),
            "confidence": "measured from one file; one example is not a rule", "reference_id": rid}
    r = an.get("rhythm")
    if r:
        made.append(knowledge.add_item(dict(base, title=f"Editing rhythm of '{ref['title']}'", applies="pacing, scene duration",
                                            body=f"{r['shot_count']} shots ({r.get('hard_cuts', 0)} hard cuts, {r.get('fades', 0)} fades), {r['cuts_per_minute']} changes a minute, median shot {r['median_shot_s']} s (shortest {r['shortest_shot_s']} s, longest {r['longest_shot_s']} s). Picture in motion {int((r.get('share_of_time_in_motion') or 0) * 100)}% of the time.")))
    n = an.get("narration")
    if n:
        made.append(knowledge.add_item(dict(base, title=f"Narration pace of '{ref['title']}'", applies="script length, sentence length",
                                            body=f"{n['words']} words in {n['sentences']} sentences; median sentence {n['median_sentence_words']} words" + (f"; about {n['words_per_minute']} words a minute" if n.get('words_per_minute') else "") + f"; {n['questions']} questions" + ("; opens with a question." if n["opens_with_question"] else "."))))
    a = an.get("audio")
    if a and a.get("has_audio"):
        made.append(knowledge.add_item(dict(base, title=f"Audio pattern of '{ref['title']}'", applies="pauses, loudness",
                                            body=f"{a['pauses']} pauses over 0.35 s, {a['pause_total_s']} s in total, longest {a['longest_pause_s']} s; mean level {a['mean_volume_db']} dB.")))
    return made


def delete(rid: str) -> None:
    import shutil
    shutil.rmtree(config.DATA / "references" / rid, ignore_errors=True)
    store.q("DELETE FROM refs WHERE id=?", (rid,))
