"""The Scout: lightweight collection of public trend and tool signals. No model runs here.

Every item carries a signal class so that a public count is never mistaken for proof:
  observed data | public engagement signal | estimate | hypothesis
Nothing discovered is ever installed or executed. Tools enter the registry as 'discovered' and wait for you.
"""
from __future__ import annotations
import json, statistics, threading, time
import xml.etree.ElementTree as ET
import httpx
from . import config, store, knowledge

UA = {"User-Agent": "ExpositStudio-Scout/1.0 (local research tool)"}
PERMISSIVE = ("mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "isc", "mpl-2.0", "unlicense", "0bsd")
COPYLEFT = ("gpl-2.0", "gpl-3.0", "agpl-3.0", "lgpl-2.1", "lgpl-3.0")

ACCESS = [
    {"source": "GitHub repositories and releases", "status": "available", "note": "Public API; 60 requests an hour without a token. Set EXPOSIT_GITHUB_TOKEN to raise the limit."},
    {"source": "Release and blog feeds (Atom/RSS)", "status": "available", "note": "Any feed address you add in Settings."},
    {"source": "YouTube channel uploads", "status": "available", "note": "Public channel feeds; add channel ids in Settings. Titles and dates only."},
    {"source": "YouTube view counts", "status": "needs key", "note": "Needs a free YouTube Data API key in EXPOSIT_YOUTUBE_API_KEY. Public counts only; no retention."},
    {"source": "Hacker News discussions", "status": "available", "note": "Public search API."},
    {"source": "Instagram Reels trends", "status": "blocked", "note": "No legitimate automated feed. Official hashtag search needs a Business account and Meta app review, and is limited to 30 hashtags a week. Paste links by hand instead."},
    {"source": "Other creators' retention and impressions", "status": "blocked", "note": "Private on every platform. Exposit never claims to know it."},
    {"source": "Your own channel analytics", "status": "planned", "note": "YouTube Analytics with your sign-in is designed but not built."},
]


def fetch(url: str, params: dict | None = None, headers: dict | None = None) -> httpx.Response:
    """Single place for outbound requests, so tests can replace it."""
    return httpx.get(url, params=params, headers={**UA, **(headers or {})}, timeout=20, follow_redirects=True)


def _add(item: dict) -> bool:
    iid = store.sha(item["url"])
    if store.q("SELECT id FROM scout_items WHERE id=?", (iid,)):
        return False
    extra = {k: v for k, v in item.items() if k not in ("source", "kind", "title", "url", "signal_class")}
    store.q("INSERT INTO scout_items VALUES(?,?,?,?,?,?,?,?)", (iid, item["source"], item["kind"], item["title"][:300], item["url"], store.now(),
                                                           item.get("signal_class", "public engagement signal"), store.jdump(extra)))
    return True


def licence_class(spdx: str) -> str:
    s = (spdx or "").lower()
    if not s or s == "noassertion":
        return "none stated: no reuse rights by default"
    if s in PERMISSIVE:
        return "permissive"
    if s in COPYLEFT:
        return "copyleft: obligations if distributed or served"
    return "other: read before use"


def evaluate_repo(r: dict) -> dict:
    """Paper evaluation from public metadata only. No code is fetched or run."""
    pushed = r.get("pushed_at") or ""
    days = None
    try:
        days = (time.time() - time.mktime(time.strptime(pushed[:10], "%Y-%m-%d"))) / 86400
    except Exception:
        pass
    maint = "archived" if r.get("archived") else ("unknown" if days is None else "active" if days < 90 else "slow" if days < 365 else "stale")
    spdx = (r.get("license") or {}).get("spdx_id") or ""
    text = ((r.get("description") or "") + " " + " ".join(r.get("topics") or [])).lower()
    gpu = "likely needs a GPU" if any(k in text for k in ("diffusion", "cuda", "gpu", "comfyui")) else "not stated"
    paid = "may call paid APIs" if any(k in text for k in ("openai", "elevenlabs", "api key", "fal.ai", "replicate")) else "not stated"
    return {"maintenance": f"{maint}; last push {pushed[:10] or 'unknown'}", "licence": spdx or "none", "licence_class": licence_class(spdx),
            "hardware": gpu, "cost": "free software; " + paid, "interface": "MCP server" if "mcp" in text else "not assessed",
            "security": "Not executed or installed. Read the source and any skill text before use; run trials in a sandbox without keys.",
            "stars": r.get("stargazers_count", 0), "evaluated": time.strftime("%Y-%m-%d"),
            "basis": "GitHub metadata only; capabilities are as the project describes them"}


def collect_github(queries: list[str]) -> dict:
    new, seen, errors = 0, 0, []
    headers = {"Accept": "application/vnd.github+json"}
    tok = config.env("EXPOSIT_GITHUB_TOKEN")
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    for q in queries:
        try:
            r = fetch("https://api.github.com/search/repositories", {"q": q, "sort": "updated", "order": "desc", "per_page": 8}, headers)
            if r.status_code != 200:
                errors.append(f"GitHub '{q}': HTTP {r.status_code}")
                continue
            for repo in r.json().get("items", []):
                seen += 1
                ev = evaluate_repo(repo)
                if _add({"source": "github", "kind": "tool", "title": repo["full_name"] + ": " + (repo.get("description") or ""), "url": repo["html_url"],
                         "signal_class": "public engagement signal", "query": q, **ev}):
                    new += 1
                if not store.q("SELECT id FROM registry WHERE url=?", (repo["html_url"],)):
                    knowledge.upsert_tool({"name": repo["full_name"], "url": repo["html_url"], "category": "discovered by Scout", "licence": ev["licence"],
                                           "maintenance": ev["maintenance"], "cost": ev["cost"], "hardware": ev["hardware"], "status": "discovered",
                                           "recommended_use": "Not evaluated beyond metadata", "risks": ev["security"], "evaluation": ev})
        except Exception as e:
            errors.append(f"GitHub '{q}': {type(e).__name__}: {str(e)[:120]}")
    return {"collector": "github", "seen": seen, "new": new, "errors": errors}


def parse_feed(xml_text: str) -> list[dict]:
    out = []
    root = ET.fromstring(xml_text)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for e in root.findall("a:entry", ns):
        link = e.find("a:link", ns)
        out.append({"title": (e.findtext("a:title", "", ns) or "").strip(), "url": link.get("href") if link is not None else "",
                    "date": e.findtext("a:published", "", ns) or e.findtext("a:updated", "", ns),
                    "channel": (e.findtext("a:author/a:name", "", ns) or root.findtext("a:author/a:name", "", ns) or "").strip()})
    for it in root.iter("item"):
        out.append({"title": (it.findtext("title") or "").strip(), "url": (it.findtext("link") or "").strip(), "date": it.findtext("pubDate") or ""})
    return [o for o in out if o["url"]]


def collect_feeds(feeds: list[str], kind: str = "release", source: str = "feed") -> dict:
    new, seen, errors = 0, 0, []
    for f in feeds:
        try:
            r = fetch(f)
            if r.status_code != 200:
                errors.append(f"{f}: HTTP {r.status_code}")
                continue
            for o in parse_feed(r.text)[:10]:
                seen += 1
                new += _add({"source": source, "kind": kind, "title": o["title"], "url": o["url"], "signal_class": "observed data", "date": o["date"], "feed": f,
                             "channel": o.get("channel", "")})
        except Exception as e:
            errors.append(f"{f}: {type(e).__name__}: {str(e)[:120]}")
    return {"collector": source, "seen": seen, "new": new, "errors": errors}


def collect_youtube(channels: list[str]) -> dict:
    res = collect_feeds([f"https://www.youtube.com/feeds/videos.xml?channel_id={c}" for c in channels], "video", "youtube")
    key = config.env("EXPOSIT_YOUTUBE_API_KEY")
    if key and channels:
        try:
            rows = store.q("SELECT id,url,data FROM scout_items WHERE source='youtube' ORDER BY fetched DESC LIMIT 50")
            ids = [r["url"].split("v=")[-1] for r in rows if "v=" in r["url"]]
            if ids:
                r = fetch("https://www.googleapis.com/youtube/v3/videos", {"part": "statistics", "id": ",".join(ids[:50]), "key": key})
                stats = {i["id"]: int(i["statistics"].get("viewCount", 0)) for i in r.json().get("items", [])} if r.status_code == 200 else {}
                med = statistics.median(stats.values()) if stats else 0
                for row in rows:
                    vid = row["url"].split("v=")[-1]
                    if vid in stats:
                        d = json.loads(row["data"] or "{}")
                        d.update(views=stats[vid], views_vs_median=round(stats[vid] / med, 2) if med else None,
                                 note="Views are a public engagement signal. The ratio to the median of fetched videos is an estimate, not proof of quality.")
                        store.q("UPDATE scout_items SET data=? WHERE id=?", (store.jdump(d), row["id"]))
        except Exception as e:
            res["errors"].append(f"YouTube statistics: {type(e).__name__}")
    elif channels:
        res["errors"].append("View counts skipped: no EXPOSIT_YOUTUBE_API_KEY set")
    return res


def collect_hn(queries: list[str]) -> dict:
    new, seen, errors = 0, 0, []
    for q in queries:
        try:
            r = fetch("https://hn.algolia.com/api/v1/search_by_date", {"query": q, "tags": "story", "hitsPerPage": 8})
            if r.status_code != 200:
                errors.append(f"Hacker News '{q}': HTTP {r.status_code}")
                continue
            for h in r.json().get("hits", []):
                seen += 1
                url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
                new += _add({"source": "hackernews", "kind": "discussion", "title": h.get("title") or "", "url": url, "signal_class": "public engagement signal",
                             "points": h.get("points", 0), "comments": h.get("num_comments", 0), "query": q})
        except Exception as e:
            errors.append(f"Hacker News '{q}': {type(e).__name__}: {str(e)[:120]}")
    return {"collector": "hackernews", "seen": seen, "new": new, "errors": errors}


def run(ctx=None) -> dict:
    s = store.get_settings()
    rid = store.new_id("sr")
    started = time.time()
    parts = []
    steps = [("GitHub", lambda: collect_github(s["scout_github_queries"])), ("release feeds", lambda: collect_feeds(s["scout_feeds"])),
             ("YouTube channels", lambda: collect_youtube(s["scout_youtube_channels"])), ("Hacker News", lambda: collect_hn(s["scout_hn_queries"]))]
    for i, (name, fn) in enumerate(steps):
        if ctx:
            ctx.say(f"Scout: checking {name}", i / len(steps))
        parts.append(fn())
    new = sum(p["new"] for p in parts)
    summary = {"new": new, "seen": sum(p["seen"] for p in parts), "collectors": parts, "note": "no change" if new == 0 else f"{new} new items",
               "model_used": False, "cost_usd": 0}
    store.q("INSERT INTO scout_runs VALUES(?,?,?,?)", (rid, started, time.time(), store.jdump(summary)))
    store.set_settings({"scout_last_run": time.time()})
    return summary


def items(limit: int = 200, kind: str = "") -> list[dict]:
    rows = store.q("SELECT * FROM scout_items ORDER BY fetched DESC LIMIT ?", (limit,))
    out = []
    for r in rows:
        d = json.loads(r.pop("data") or "{}")
        r.update(d)
        if not kind or r["kind"] == kind:
            out.append(r)
    return out


def runs(limit: int = 30) -> list[dict]:
    return [dict(r, summary=json.loads(r["summary"])) for r in store.q("SELECT * FROM scout_runs ORDER BY started DESC LIMIT ?", (limit,))]


SIGNALS_CAVEAT = ("Public titles and counts only. They may suggest topics, hooks and title phrasing; they say nothing about animation "
                  "style or whether a technique works. Ideas drawn from them are tier 'observation' or 'hypothesis'.")


def signals(days: int = 14, top_discussions: int = 10) -> list[dict]:
    """Scout items for the Creative Director: videos collected in the last `days`, plus the most-discussed items
    from the same window (by comment count, then points). Titles, counts and URLs only."""
    since = time.time() - days * 86400
    rows = [r for r in items(1000) if r["fetched"] >= since]
    videos = [{"kind": "video", "title": r["title"], "channel": r.get("channel") or None, "date": r.get("date") or None,
               "views": r.get("views"), "url": r["url"]} for r in rows if r["kind"] == "video"]
    disc = sorted((r for r in rows if r["kind"] == "discussion"), key=lambda r: (-(r.get("comments") or 0), -(r.get("points") or 0)))
    discussed = [{"kind": "discussion", "title": r["title"], "comments": r.get("comments"), "points": r.get("points"), "url": r["url"]}
                 for r in disc[:top_discussions]]
    return videos + discussed


def weekly_summary() -> dict:
    """Counts and lists for the last seven days. No interpretation: that needs a model and is labelled as hypothesis when added."""
    since = time.time() - 7 * 86400
    rows = [r for r in items(1000) if r["fetched"] >= since]
    by_kind: dict = {}
    for r in rows:
        by_kind.setdefault(r["kind"], []).append(r)
    tools = sorted(by_kind.get("tool", []), key=lambda r: -(r.get("stars") or 0))[:10]
    disc = sorted(by_kind.get("discussion", []), key=lambda r: -(r.get("points") or 0))[:10]
    return {"since": since, "total": len(rows), "counts": {k: len(v) for k, v in by_kind.items()},
            "top_tools": [{k: t.get(k) for k in ("title", "url", "stars", "licence", "licence_class", "maintenance", "hardware", "cost")} for t in tools],
            "top_discussions": [{k: d.get(k) for k in ("title", "url", "points", "comments")} for d in disc],
            "releases": [{k: r.get(k) for k in ("title", "url", "date")} for r in by_kind.get("release", [])[:15]],
            "videos": [{k: r.get(k) for k in ("title", "url", "date", "views", "views_vs_median")} for r in by_kind.get("video", [])[:15]],
            "runs": len([r for r in runs(60) if r["started"] >= since]),
            "caveat": "Stars, points and views are public engagement signals. They do not show that a technique works. No private analytics are used."}


_started = False


def start_scheduler(enqueue) -> None:
    """Checks every ten minutes whether a daily run is due. Costs nothing while idle."""
    global _started
    if _started:
        return
    _started = True

    def loop():
        while True:
            try:
                s = store.get_settings()
                if s.get("scout_daily_in_app") and time.time() - float(s.get("scout_last_run") or 0) > 86400:
                    if not store.q("SELECT id FROM jobs WHERE kind='scout' AND state IN ('queued','running')"):
                        enqueue()
            except Exception:
                pass
            time.sleep(600)

    threading.Thread(target=loop, daemon=True, name="scout-scheduler").start()
