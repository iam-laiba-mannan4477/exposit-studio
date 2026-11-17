import httpx
from exposit import scout, store, knowledge

ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><title>v9.9.9</title>
<link href="https://example.org/rel/9.9.9"/><updated>2026-11-10T00:00:00Z</updated><id>x1</id></entry></feed>"""


def fake_fetch(url, params=None, headers=None):
    req = httpx.Request("GET", url)
    if "api.github.com/search" in url:
        return httpx.Response(200, request=req, json={"items": [
            {"full_name": "someone/video-skill", "description": "MCP server for video, needs CUDA and an OpenAI api key", "html_url": "https://github.com/someone/video-skill",
             "stargazers_count": 321, "pushed_at": "2026-11-01T00:00:00Z", "archived": False, "license": {"spdx_id": "GPL-3.0"}, "topics": ["mcp"]}]})
    if "hn.algolia.com" in url:
        return httpx.Response(200, request=req, json={"hits": [{"title": "Show HN: explainer tool", "url": "https://example.org/hn", "points": 77, "num_comments": 12, "objectID": "1", "created_at": "2026-11-12T00:00:00Z"}]})
    if "youtube.com/feeds" in url:
        return httpx.Response(404, request=req)
    return httpx.Response(200, request=req, text=ATOM)


def test_scout_collects_and_never_installs(monkeypatch):
    monkeypatch.setattr(scout, "fetch", fake_fetch)
    store.set_settings({"scout_github_queries": ["video skill"], "scout_feeds": ["https://example.org/releases.atom"], "scout_youtube_channels": ["UCxxxx"], "scout_hn_queries": ["explainer"]})
    said = []

    class Ctx:
        def say(self, msg, p=None): said.append(msg)
    res = scout.run(Ctx())
    assert res["new"] >= 3
    kinds = {i["kind"] for i in scout.items()}
    assert {"tool", "discussion"} <= kinds
    tool = next(i for i in scout.items() if i["kind"] == "tool")
    assert tool["licence_class"] and "GPU" in tool["hardware"] and "paid" in tool["cost"]
    reg = [t for t in knowledge.tools() if "video-skill" in t["name"]]
    assert reg and reg[0]["status"] == "discovered", "found tools are only recorded, with status 'discovered'"
    assert "Not executed or installed" in reg[0]["risks"]
    # A failing source is reported, not hidden, and does not stop the run.
    run = scout.runs()[0]
    assert any(c["errors"] for c in run["summary"]["collectors"]), "the 404 from the YouTube feed must be reported"
    assert run["summary"]["model_used"] is False and run["summary"]["cost_usd"] == 0
    # Running again adds nothing new.
    assert scout.run(Ctx())["new"] == 0
    wk = scout.weekly_summary()
    assert wk["total"] >= 3 and "No private analytics" in wk["caveat"]


def test_scout_module_has_no_install_or_exec_path():
    import inspect
    src = inspect.getsource(scout)
    for banned in ("subprocess", "os.system", "pip install", "git clone", "npm install", "exec("):
        assert banned not in src


YT_FEED = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><author><name>Some Channel</name></author>
<entry><title>CDNs explained</title><link href="https://www.youtube.com/watch?v=sig1"/><published>2026-11-15T00:00:00Z</published></entry></feed>"""


def test_scout_signals_for_creative_director(monkeypatch):
    from exposit import director, roles
    # Channel name comes from the feed's author.
    assert scout.parse_feed(YT_FEED)[0]["channel"] == "Some Channel"
    scout._add({"source": "youtube", "kind": "video", "title": "CDNs explained", "url": "https://www.youtube.com/watch?v=sig1",
                "date": "2026-11-15T00:00:00Z", "channel": "Some Channel", "views": 1234})
    scout._add({"source": "youtube", "kind": "video", "title": "Old video", "url": "https://www.youtube.com/watch?v=sigold"})
    for i, (pts, com) in enumerate([(500, 30), (10, 90), (50, 40)]):
        scout._add({"source": "hackernews", "kind": "discussion", "title": f"Thread {i}", "url": f"https://example.org/sig-hn{i}", "points": pts, "comments": com})
    for i in range(12):
        scout._add({"source": "hackernews", "kind": "discussion", "title": f"Quiet {i}", "url": f"https://example.org/sig-quiet{i}", "points": 1, "comments": 0})
    store.q("UPDATE scout_items SET fetched=? WHERE id=?", (store.now() - 20 * 86400, store.sha("https://www.youtube.com/watch?v=sigold")))

    sig = scout.signals()
    vids = [s for s in sig if s["kind"] == "video"]
    disc = [s for s in sig if s["kind"] == "discussion"]
    v = next(s for s in vids if s["url"].endswith("sig1"))
    assert v == {"kind": "video", "title": "CDNs explained", "channel": "Some Channel", "date": "2026-11-15T00:00:00Z", "views": 1234,
                 "url": "https://www.youtube.com/watch?v=sig1"}
    assert not any(s["url"].endswith("sigold") for s in vids), "only the last 14 days"
    assert len(disc) == 10, "the 10 most-discussed only"
    assert [d["title"] for d in disc[:3]] == ["Thread 1", "Thread 2", "Thread 0"], "ordered by comments, then points"
    assert all(s["url"].startswith("https://") for s in sig)

    # run_strategy hands the signals and their caveat to the Creative Director.
    seen = {}

    def fake_run(role, payload, meta):
        seen[role] = payload
        raise RuntimeError("stop after capturing the payload")
    monkeypatch.setattr(roles, "run", fake_run)
    p = store.create_production({"title": "Signals", "topic": "CDN"})
    try:
        director.run_strategy(p["id"], director.Ctx())
    except RuntimeError:
        pass
    pay = seen["creative_director"]
    assert any(s["url"].endswith("sig1") for s in pay["scout_signals"])
    assert "observation" in pay["scout_signals_caveat"] and "hypothesis" in pay["scout_signals_caveat"]
    skill = (director.config.ROOT / "exposit" / "skills" / "creative_director.md").read_text(encoding="utf-8")
    assert "scout_signals" in skill and "Never infer animation styles" in skill
