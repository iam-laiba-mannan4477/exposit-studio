"""API tests that need no rendering."""
import io
from conftest import wait_job


def test_health_and_settings(client):
    h = client.get("/api/health").json()
    assert h["ok"] and h["ffmpeg"] and h["provider"]["provider"] == "bridge" and h["provider"]["paid"] is False
    s = client.get("/api/settings").json()
    assert s["settings"]["budget_paid_usd"] == 0 and s["settings"]["default_review_mode"] == "final_only"
    assert set(s["env"]) == {"EXPOSIT_LLM_API_KEY", "EXPOSIT_GITHUB_TOKEN", "EXPOSIT_YOUTUBE_API_KEY"}
    assert all(isinstance(v, bool) for v in s["env"].values()), "key values are never returned, only whether they are set"


def test_paid_provider_cannot_be_selected_at_zero_budget(client):
    r = client.put("/api/settings", json={"llm_provider": "anthropic", "llm_model": "any"})
    assert r.status_code == 400 and "budget" in r.json()["detail"]
    assert client.get("/api/settings").json()["settings"]["llm_provider"] == "bridge"


def test_library_crud_and_evidence_rule(client):
    k = client.get("/api/knowledge").json()
    assert len(k["items"]) >= 30 and len(k["categories"]) >= 10
    r = client.post("/api/knowledge", json={"title": "T", "body": "B", "tier": "verified", "category": "Opening hooks"})
    assert r.status_code == 400, "a verified item needs a source"
    it = client.post("/api/knowledge", json={"title": "My rule", "body": "Open on the failure.", "tier": "preference", "category": "Opening hooks"}).json()
    assert client.put(f"/api/knowledge/{it['id']}", json={"status": "retired"}).json()["status"] == "retired"
    assert client.delete(f"/api/knowledge/{it['id']}").json()["ok"]
    assert it["id"] not in [i["id"] for i in client.get("/api/knowledge").json()["items"]]


def test_registry_status_change_records_only(client):
    reg = client.get("/api/registry").json()
    assert len(reg["tools"]) >= 10
    t = next(x for x in reg["tools"] if x["status"] == "watching")
    r = client.post(f"/api/registry/{t['id']}/status", json={"status": "evaluated"}).json()
    assert "never installs" in r["note"]
    assert next(x for x in client.get("/api/registry").json()["tools"] if x["id"] == t["id"])["status"] == "evaluated"
    assert client.post(f"/api/registry/{t['id']}/status", json={"status": "installed"}).status_code == 400


def test_reference_transcript_analysis_and_library(client):
    text = "Why does the page load? First the name is resolved. Then a balancer picks a node. That is the path."
    r = client.post("/api/references", data={"title": "Transcript sample", "transcript": text}).json()
    assert wait_job(client, r["job"], 60)["state"] == "done"
    ref = client.get(f"/api/references/{r['id']}").json()
    n = ref["analysis"]["narration"]
    assert n["sentences"] == 4 and n["opens_with_question"] and n["questions"] == 1
    assert len(ref["analysis"]["unsupported"]) >= 3, "unsupported capabilities are listed, not hidden"
    made = client.post(f"/api/references/{r['id']}/to-library").json()["created"]
    assert made and all(m["tier"] == "observation" for m in made)
    assert all(text[:20] not in m["body"] for m in made), "the wording itself is not copied into the library"
    assert client.delete(f"/api/references/{r['id']}").json()["ok"]


def test_reference_rejects_unknown_file_and_url_is_not_fetched(client):
    r = client.post("/api/references", files={"file": ("x.exe", io.BytesIO(b"MZ"), "application/octet-stream")})
    assert r.status_code == 400
    r = client.post("/api/references", data={"title": "Link", "url": "https://www.youtube.com/watch?v=abc"}).json()
    assert wait_job(client, r["job"], 60)["state"] == "done"
    ref = client.get(f"/api/references/{r['id']}").json()
    assert any("did not fetch" in n for n in ref["analysis"]["notes"])


def test_formats(client):
    r = client.post("/api/productions", json={"topic": "Vertical test", "format": "9:16", "start": False})
    assert r.status_code == 200
    pid = r.json()["id"]
    assert client.get(f"/api/productions/{pid}").json()["brief"]["format"] == "9:16"
    assert client.put(f"/api/productions/{pid}/brief", json={"format": "1:1"}).status_code == 400
    assert client.put(f"/api/productions/{pid}/brief", json={"format": "16:9"}).json()["brief"]["format"] == "16:9"
    assert client.post("/api/productions", json={"topic": "Square", "format": "1:1", "start": False}).status_code == 400
    client.delete(f"/api/productions/{pid}")


def test_unknown_routes(client):
    assert client.get("/api/productions/nope").status_code == 404
    assert client.get("/api/nothing").status_code == 404
    assert client.post("/api/productions", json={"topic": ""}).status_code == 400


import pytest
from pathlib import Path
SAMPLE = Path(__file__).resolve().parent.parent / "examples" / "http-request-journey" / "output" / "video.mp4"


@pytest.mark.slow
@pytest.mark.skipif(not SAMPLE.exists(), reason="sample video not present")
def test_reference_video_analysis_on_the_sample(client):
    with open(SAMPLE, "rb") as f:
        r = client.post("/api/references", data={"title": "Sample"}, files={"file": ("sample.mp4", f, "video/mp4")}).json()
    j = wait_job(client, r["job"], 300)
    assert j["state"] == "done", j["log"]
    a = client.get(f"/api/references/{r['id']}").json()["analysis"]
    assert a["metadata"]["width"] == 1920 and 55 < a["metadata"]["duration"] < 66
    starts = [s["start"] for s in a["shots"] if s["begins_with"] == "fade"]
    import json as _j
    truth = [s["start"] for s in _j.loads((SAMPLE.parent / "manifest.json").read_text())["scenes"]][1:]
    assert len(starts) == len(truth) and all(abs(x - y) < 0.4 for x, y in zip(starts, truth)), (starts, truth)
    assert all(s.get("frame") and s.get("palette") for s in a["shots"])
    assert client.get(f"/api/references/{r['id']}/frames/{a['shots'][0]['frame']}").headers["content-type"].startswith("image/")
    assert a["audio"]["has_audio"] and a["audio"]["mean_volume_db"] < -10
    made = client.post(f"/api/references/{r['id']}/to-library").json()["created"]
    assert {m["title"].split(" of ")[0] for m in made} >= {"Editing rhythm", "Audio pattern"}
    client.delete(f"/api/references/{r['id']}")
