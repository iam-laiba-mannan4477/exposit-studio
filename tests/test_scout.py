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
