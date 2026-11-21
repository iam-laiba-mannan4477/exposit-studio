"""End to end: brief -> roles answered over the agent bridge -> narration -> render -> export -> edits.
Slow (a few minutes): it really narrates and renders, at 540p to keep it short.  Skip with:  pytest -m "not slow" """
import json, zipfile
import pytest
from conftest import wait_job
from exposit import tts

pytestmark = [pytest.mark.slow, pytest.mark.skipif(not tts.engines()[0]["available"], reason="Kokoro model files are not installed")]
state = {}


def get(client):
    return client.get(f"/api/productions/{state['pid']}").json()


def test_full_pipeline_through_the_bridge(client, fake_agent):
    r = client.post("/api/productions", json={"topic": "How an HTTP request travels through DNS, an AWS load balancer, NGINX and a Kubernetes application.",
                                              "duration": 60, "quality": "540p", "review_mode": "final_only", "voice_speed": 1.06})
    assert r.status_code == 200, r.text
    state["pid"] = r.json()["id"]
    j = wait_job(client, r.json()["job"])
    assert j["state"] == "done", j["message"] + "\n" + j["log"]
    assert {role for _, role in fake_agent} >= {"researcher", "creative_director", "storyteller", "visual_planner"}
    p = get(client)
    assert all(p["stages"][s]["state"] == "passed" for s in ("research", "strategy", "script", "storyboard", "produce", "export"))
    assert p["final"] == "awaiting_approval", "final approval stays with the user"
    assert p["gates"]["script"]["decided"] == "automatically"
    g = p["gates"]["final"]
    assert g["passed"], [c for c in g["criteria"] if not c["passed"]]
    m = p["manifest"]
    assert (m["settings"]["w"], m["settings"]["h"]) == (960, 540) and len(m["scenes"]) == 6
    assert 57 <= m["duration"] <= 65
    assert j["paid"] == 0


def test_exports_are_real_files(client):
    pid = state["pid"]
    v = client.get(f"/api/productions/{pid}/media/video")
    assert v.status_code == 200 and v.content[4:8] == b"ftyp" and len(v.content) > 300_000
    srt = client.get(f"/api/productions/{pid}/file/subtitles.srt").text
    assert "-->" in srt and "Enter" in srt
    z = client.get(f"/api/productions/{pid}/file/project.zip").content
    import io
    names = zipfile.ZipFile(io.BytesIO(z)).namelist()
    for need in ("brief.json", "research/facts.json", "strategy/strategy.json", "script/script.json", "storyboard/board.json"):
        assert any(n.endswith(need) for n in names), need
    assert client.get(f"/api/productions/{pid}/media/still/s3").headers["content-type"].startswith("image/")
    assert client.get(f"/api/productions/{pid}/file/../../exposit.db").status_code in (400, 404)


def store_settings():
    from exposit import store
    return store.get_settings()


def transition_dependents(board_scenes: list[dict], order: list[str], changed: set[str]) -> set[str]:
    """Scenes whose clip changes when `changed` scenes change, through transitions: a scene that enters from its
    predecessor depends on that scene's picture, and a scene does not fade out when its successor transitions from it."""
    from exposit.render import engine
    by = {s["id"]: s for s in board_scenes}
    out = set(changed)
    for i, sid in enumerate(order):
        if i > 0 and order[i - 1] in changed and engine.needs_prev(by[sid]):
            out.add(sid)
    return out


def reorder_dependents(board_scenes: list[dict], before: list[str], after: list[str]) -> set[str]:
    from exposit.render import engine
    by = {s["id"]: s for s in board_scenes}

    def deps(order):
        d = {}
        for i, sid in enumerate(order):
            prev = order[i - 1] if i > 0 and engine.needs_prev(by[sid]) else None
            nofade = i + 1 < len(order) and engine.needs_prev(by[order[i + 1]])
            d[sid] = (prev, nofade)
        return d
    a, b = deps(before), deps(after)
    return {sid for sid in after if a.get(sid) != b.get(sid)}


def test_scene_edit_rebuilds_only_that_scene(client):
    pid = state["pid"]
    before = {s["id"]: s["clip_hash"] for s in get(client)["manifest"]["scenes"]}
    board = get(client)["board"]["scenes"]
    expect = transition_dependents(board, [s["id"] for s in board], {"s2"})     # s2, and a scene entering from it
    plan = client.put(f"/api/productions/{pid}/scenes/s2", json={"patch": {"pad_end": 1.2}, "label": "Longer hold"}).json()
    assert plan["renders"] == len(expect) and plan["narrations"] == 0 and {s["scene"] for s in plan["scenes"]} == expect
    assert client.put(f"/api/productions/{pid}/scenes/s2", json={"patch": {"treatment": "hologram"}}).status_code == 400
    r = client.post(f"/api/productions/{pid}/rebuild").json()
    assert wait_job(client, r["job"])["state"] == "done"
    p = get(client)
    after = {s["id"]: s["clip_hash"] for s in p["manifest"]["scenes"]}
    assert {k for k in before if before[k] != after[k]} == expect
    assert p["plan"]["rejoin"] is False
    assert p["final"] == "awaiting_approval"
    state["edited_hash"] = after["s2"]; state["orig_hash"] = before["s2"]


def test_undo_restores_from_cache_without_rendering(client):
    pid = state["pid"]
    plan = client.post(f"/api/productions/{pid}/undo").json()
    assert plan["renders"] == 0 and plan["scenes"] and all(x["clip"] == "restore from cache" for x in plan["scenes"])
    plan = client.post(f"/api/productions/{pid}/redo").json()
    assert plan["rejoin"] is False
    p = get(client)
    assert p["hpos"] == len(p["history"]) - 1


def test_script_edit_renarrates_one_scene(client):
    pid = state["pid"]
    sc = get(client)["script"]["scenes"][5]
    plan = client.put(f"/api/productions/{pid}/script/{sc['id']}", json={"sentences": [s["text"] for s in sc["sentences"]][:-1] + ["Now you can follow it."]}).json()
    assert plan["narrations"] == 1 and [s["scene"] for s in plan["scenes"]] == [sc["id"]]
    client.post(f"/api/productions/{pid}/undo")


def test_instruction_edit_is_a_proposal_until_accepted(client, fake_agent):
    pid = state["pid"]
    board_before = get(client)["board"]
    r = client.post(f"/api/productions/{pid}/scenes/s4/instruct", json={"instruction": "Hold the last moment a little longer"}).json()
    assert wait_job(client, r["job"])["state"] == "done"
    assert ("scene_editor" in [role for _, role in fake_agent])
    prop = client.get(f"/api/productions/{pid}/scenes/s4/proposal").json()
    assert prop["changed"] == ["pad_end"]
    assert get(client)["board"] == board_before, "nothing changes until the proposal is accepted"
    plan = client.post(f"/api/productions/{pid}/scenes/s4/proposal/apply").json()
    board = get(client)["board"]["scenes"]
    assert {s["scene"] for s in plan["scenes"]} == transition_dependents(board, [s["id"] for s in board], {"s4"}) and plan["narrations"] == 0
    client.post(f"/api/productions/{pid}/undo")


def test_switch_to_vertical_reuses_narration(client):
    pid = state["pid"]
    plan = client.put(f"/api/productions/{pid}/brief", json={"format": "9:16"}).json()["plan"]
    n_clips = len(get(client)["board"]["scenes"]) + (1 if store_settings()["end_slide"] else 0)   # + the end slide
    assert plan["renders"] == n_clips and plan["narrations"] == 0, "a new shape re-renders pictures only; voice and AI work are reused"
    r = client.post(f"/api/productions/{pid}/rebuild").json()
    j = wait_job(client, r["job"])
    assert j["state"] == "done", j["log"]
    p = get(client)
    assert (p["manifest"]["settings"]["w"], p["manifest"]["settings"]["h"]) == (540, 960)
    g = p["gates"]["final"]
    assert g["passed"], [c for c in g["criteria"] if not c["passed"]]
    from PIL import Image
    import io
    assert Image.open(io.BytesIO(client.get(f"/api/productions/{pid}/media/still/s2").content)).size == (540, 960)
    # and back: the 16:9 clips are still cached, so nothing renders
    plan = client.put(f"/api/productions/{pid}/brief", json={"format": "16:9"}).json()["plan"]
    assert plan["renders"] == 0 and plan["rejoin"]
    assert wait_job(client, client.post(f"/api/productions/{pid}/rebuild").json()["job"])["state"] == "done"


def test_versions_override_and_final_approval(client):
    pid = state["pid"]
    v = client.post(f"/api/productions/{pid}/versions", json={"label": "Before reorder"}).json()
    board = get(client)["board"]["scenes"]
    ids = [s["id"] for s in board]
    new = ids[:4] + [ids[5], ids[4]]
    moved = reorder_dependents(board, ids, new)        # only scenes whose transition neighbours changed re-render
    plan = client.post(f"/api/productions/{pid}/reorder", json={"ids": new}).json()
    assert plan["renders"] == len([x for x in plan["scenes"] if x["clip"] == "render"]) and plan["rejoin"]
    assert {x["scene"] for x in plan["scenes"] if x["clip"] in ("render", "restore from cache")} == moved
    client.post(f"/api/productions/{pid}/versions/{v['id']}/restore")
    assert [s["id"] for s in get(client)["board"]["scenes"]] == ids
    assert client.post(f"/api/productions/{pid}/reorder", json={"ids": ids[:3]}).status_code == 400
    r = client.post(f"/api/productions/{pid}/strategy/override", json={"key": "Hook", "choice": "Open on a 502 error"})
    assert r.status_code == 200
    p = get(client)
    assert p["overrides"] and p["stages"]["script"].get("stale")
    lib = client.get("/api/knowledge").json()["items"]
    assert any(i["tier"] == "preference" and "502" in i["body"] for i in lib), "an override is kept as a preference"
    assert client.post(f"/api/productions/{pid}/final/approve").json()["ok"]
    assert get(client)["final"] == "approved"


def test_every_gate_mode_stops_for_approval(client, fake_agent):
    r = client.post("/api/productions", json={"topic": "Same topic, every gate", "duration": 60, "quality": "540p", "review_mode": "every_gate"}).json()
    assert wait_job(client, r["job"])["state"] == "done"
    p = client.get(f"/api/productions/{r['id']}").json()
    assert p["stages"]["script"]["state"] == "awaiting_approval" and p["stages"]["storyboard"]["state"] == "pending"
    assert client.post(f"/api/productions/{r['id']}/gates/storyboard/approve").status_code == 400
    assert client.delete(f"/api/productions/{r['id']}").json()["ok"]
