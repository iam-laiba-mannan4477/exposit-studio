"""SQLite index and project-folder helpers. The project folder is the source of truth for artefacts;
the database indexes productions, jobs, knowledge, scout items, registry and settings."""
from __future__ import annotations
import hashlib, json, sqlite3, threading, time, uuid
from pathlib import Path
from typing import Any
from . import config

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS productions(id TEXT PRIMARY KEY, title TEXT, created REAL, updated REAL, data TEXT);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, production_id TEXT, kind TEXT, state TEXT, progress REAL,
  message TEXT, created REAL, started REAL, finished REAL, params TEXT, log TEXT, paid INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS knowledge(id TEXT PRIMARY KEY, kind TEXT, title TEXT, body TEXT, category TEXT, tier TEXT,
  source TEXT, date TEXT, applies TEXT, confidence TEXT, status TEXT, data TEXT);
CREATE TABLE IF NOT EXISTS scout_items(id TEXT PRIMARY KEY, source TEXT, kind TEXT, title TEXT, url TEXT, fetched REAL,
  signal_class TEXT, data TEXT);
CREATE TABLE IF NOT EXISTS scout_runs(id TEXT PRIMARY KEY, started REAL, finished REAL, summary TEXT);
CREATE TABLE IF NOT EXISTS registry(id TEXT PRIMARY KEY, name TEXT, url TEXT, category TEXT, licence TEXT,
  maintenance TEXT, cost TEXT, hardware TEXT, status TEXT, updated REAL, data TEXT);
CREATE TABLE IF NOT EXISTS refs(id TEXT PRIMARY KEY, title TEXT, created REAL, state TEXT, data TEXT);
"""


def db() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            # timeout + WAL: a scheduled Scout run is a second process writing the same file while the studio is open
            _conn = sqlite3.connect(str(config.DATA / "exposit.db"), check_same_thread=False, timeout=30)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.executescript(SCHEMA)
            _conn.commit()
        return _conn


def q(sql: str, args: tuple = ()) -> list[dict]:
    with _lock:
        cur = db().execute(sql, args)
        rows = [dict(r) for r in cur.fetchall()]
        db().commit()
        return rows


def new_id(prefix: str = "") -> str:
    return prefix + uuid.uuid4().hex[:10]


def now() -> float:
    return time.time()


def jdump(o: Any) -> str:
    return json.dumps(o, ensure_ascii=False)


def sha(*parts: Any) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(json.dumps(p, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"))
    return h.hexdigest()[:16]


# ---- settings
DEFAULT_SETTINGS = {
    "llm_provider": "bridge",          # bridge | claude_cli | openai | anthropic | none
    "llm_base_url": "http://localhost:11434/v1",
    "llm_model": "",
    "voice_engine": "kokoro",
    "voice": "am_michael",
    "voice_speed": 1.0,
    "burn_captions": True,
    "music": True,
    "sfx": True,
    "scout_daily_in_app": False,
    "scout_github_queries": ["explainer video agent skill", "text-to-speech onnx", "topic:mcp-server video", "programmatic video render"],
    "scout_feeds": ["https://github.com/heygen-com/hyperframes/releases.atom", "https://github.com/remotion-dev/remotion/releases.atom",
                    "https://github.com/ManimCommunity/manim/releases.atom", "https://github.com/thewh1teagle/kokoro-onnx/releases.atom"],
    "scout_youtube_channels": [],
    "scout_hn_queries": ["explainer video", "text to speech", "MCP server"],
    "budget_paid_usd": 0,
    "independent_review": True,
    "scout_last_run": 0,
    "default_review_mode": "final_only",
}


def get_settings() -> dict:
    s = dict(DEFAULT_SETTINGS)
    for r in q("SELECT key,value FROM settings"):
        try:
            s[r["key"]] = json.loads(r["value"])
        except Exception:
            pass
    return s


def set_settings(patch: dict) -> dict:
    for k, v in patch.items():
        if k in DEFAULT_SETTINGS:
            q("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, jdump(v)))
    return get_settings()


# ---- productions
STAGES = ["research", "strategy", "script", "storyboard", "produce", "export"]


def pdir(pid: str) -> Path:
    d = config.DATA / "productions" / pid
    for sub in ("research", "strategy", "script", "storyboard", "audio", "clips", "export", "gates", "history", "versions", "uploads"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    return d


def create_production(brief: dict) -> dict:
    pid = new_id("p")
    data = {"brief": brief, "stages": {s: {"state": "pending"} for s in STAGES}, "final": "not_ready"}
    q("INSERT INTO productions VALUES(?,?,?,?,?)", (pid, brief.get("title") or brief.get("topic", "Untitled")[:80], now(), now(), jdump(data)))
    write_json(pid, "brief.json", brief)
    return get_production(pid)


def get_production(pid: str) -> dict | None:
    rows = q("SELECT * FROM productions WHERE id=?", (pid,))
    if not rows:
        return None
    r = rows[0]
    d = json.loads(r["data"])
    d.update(id=r["id"], title=r["title"], created=r["created"], updated=r["updated"])
    return d


def list_productions() -> list[dict]:
    return [get_production(r["id"]) for r in q("SELECT id FROM productions ORDER BY updated DESC")]


def save_production(p: dict) -> None:
    data = {k: v for k, v in p.items() if k not in ("id", "title", "created", "updated")}
    q("UPDATE productions SET title=?, updated=?, data=? WHERE id=?", (p.get("title", ""), now(), jdump(data), p["id"]))


def set_stage(pid: str, stage: str, **kw) -> None:
    p = get_production(pid)
    p["stages"].setdefault(stage, {}).update(kw)
    save_production(p)


def read_json(pid: str, rel: str, default: Any = None) -> Any:
    f = pdir(pid) / rel
    if not f.exists():
        return default
    return json.loads(f.read_text(encoding="utf-8"))


def write_json(pid: str, rel: str, obj: Any) -> None:
    f = pdir(pid) / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


# ---- jobs
def add_job(kind: str, production_id: str = "", params: dict | None = None) -> str:
    jid = new_id("j")
    q("INSERT INTO jobs(id,production_id,kind,state,progress,message,created,params,log) VALUES(?,?,?,?,?,?,?,?,?)",
      (jid, production_id, kind, "queued", 0.0, "Queued", now(), jdump(params or {}), ""))
    return jid


def update_job(jid: str, **kw) -> None:
    if not kw:
        return
    cols = ",".join(f"{k}=?" for k in kw)
    q(f"UPDATE jobs SET {cols} WHERE id=?", (*kw.values(), jid))


def job_log(jid: str, line: str) -> None:
    q("UPDATE jobs SET log = log || ? WHERE id=?", (time.strftime("%H:%M:%S ") + line + "\n", jid))


def get_job(jid: str) -> dict | None:
    r = q("SELECT * FROM jobs WHERE id=?", (jid,))
    return r[0] if r else None


def list_jobs(limit: int = 60, production_id: str = "") -> list[dict]:
    if production_id:
        return q("SELECT id,production_id,kind,state,progress,message,created,started,finished,paid FROM jobs WHERE production_id=? ORDER BY created DESC LIMIT ?", (production_id, limit))
    return q("SELECT id,production_id,kind,state,progress,message,created,started,finished,paid FROM jobs ORDER BY created DESC LIMIT ?", (limit,))
