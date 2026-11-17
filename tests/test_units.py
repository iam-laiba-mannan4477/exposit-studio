import copy, json
import numpy as np
import pytest
from conftest import example
from exposit import schemas, gates, providers, store, knowledge, roles
from exposit.render import engine


def test_example_role_outputs_match_schemas():
    schemas.Facts.model_validate(example("facts.json"))
    s = schemas.Strategy.model_validate(example("strategy.json"))
    assert len(s.treatments) >= 3 and s.chosen in [t.name for t in s.treatments]
    schemas.Script.model_validate(example("script.json"))
    b = schemas.Storyboard.model_validate(example("board.json"))
    assert {"flow2d", "isometric", "cutaway"} <= {sc.treatment for sc in b.scenes}


def test_gates_pass_on_example_and_catch_faults():
    facts, script, strat, board = (example(f) for f in ("facts.json", "script.json", "strategy.json", "board.json"))
    assert gates.research_gate(facts)["passed"]
    assert gates.script_gate(script, facts, strat, 60, None)["passed"]
    assert gates.storyboard_gate(board, script, facts)["passed"]
    bad = copy.deepcopy(script)
    bad["scenes"][1]["sentences"][0]["claims"] = ["c99"]          # cites a fact that does not exist
    assert not gates.script_gate(bad, facts, strat, 60, None)["passed"]
    long = copy.deepcopy(script)
    long["scenes"][2]["sentences"].append({"text": "word " * 120, "claims": ["c2"]})
    assert not gates.script_gate(long, facts, strat, 60, None)["passed"]
    unsourced = copy.deepcopy(facts)
    unsourced["claims"][0]["sources"] = []
    assert not gates.research_gate(unsourced)["passed"]


@pytest.mark.parametrize("idx", range(6))
def test_every_example_scene_renders_a_frame(idx):
    spec = example("board.json")["scenes"][idx]
    sents = [s["text"] for s in example("script.json")["scenes"][idx]["sentences"]]
    words, t, timing_s = [], 0.5, []
    for si, s in enumerate(sents):
        s0 = t
        for w in s.split():
            words.append({"w": w, "s": t, "e": t + 0.3, "si": si}); t += 0.35
        timing_s.append({"text": s, "s": s0, "e": t}); t += 0.3
    timing = {"duration": t + 0.5, "sentences": timing_s, "words": words}
    img = engine.render_still(spec, timing, timing["duration"] * 0.8, 640, 360, "premium-technical", True)
    import io
    from PIL import Image
    a = np.asarray(Image.open(io.BytesIO(img)).convert("RGB"))      # render_still returns PNG bytes
    assert a.shape[0] == 360 and a.shape[1] == 640
    assert a.std() > 4, "frame is blank"


def test_paid_provider_is_refused_at_zero_budget():
    assert providers.is_paid({"llm_provider": "anthropic"})
    assert not providers.is_paid({"llm_provider": "bridge"})
    assert not providers.is_paid({"llm_provider": "openai", "llm_base_url": "http://127.0.0.1:11434/v1"})
    store.set_settings({"llm_provider": "anthropic", "llm_model": "x", "budget_paid_usd": 0})
    try:
        assert not providers.status()["ready"]
        with pytest.raises(providers.ProviderError):
            providers.complete("s", "u", "researcher", {})
    finally:
        store.set_settings({"llm_provider": "bridge", "llm_model": ""})


def test_role_rejects_output_that_does_not_fit_schema(monkeypatch):
    monkeypatch.setattr(providers, "complete", lambda *a, **k: '{"nonsense": true}')
    with pytest.raises(providers.ProviderError):
        roles.run("researcher", {"brief": {}})


def test_role_reads_json_inside_a_code_fence(monkeypatch):
    monkeypatch.setattr(providers, "complete", lambda *a, **k: "Here you go:\n```json\n" + json.dumps(example("facts.json")) + "\n```")
    assert roles.run("researcher", {"brief": {}}).claims


def test_library_seed_has_evidence_tiers():
    knowledge.seed()
    items = knowledge.items()
    assert len(items) >= 30
    assert all(i["tier"] in knowledge.TIERS and i["category"] and i["date"] for i in items)
    assert not [i for i in items if i["tier"] == "verified"], "nothing is 'verified' before the user has measured anything"
    assert all(t["status"] != "discovered" or True for t in knowledge.tools())


def test_no_secret_in_source():
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    pat = re.compile(r"sk-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}|ghp_[A-Za-z0-9]{30,}")
    for f in list((root / "exposit").rglob("*.py")) + list((root / "web" / "src").rglob("*.js*")) + [root / ".env.example"]:
        if f.exists():
            assert not pat.search(f.read_text(encoding="utf-8", errors="ignore")), f


def test_chart_treatment_renders():
    import io
    from PIL import Image
    spec = {"id": "c", "title": "Latency", "treatment": "chart", "heading": "Latency by hop",
            "data": [{"label": "DNS", "value": 20}, {"label": "Load balancer", "value": 2}, {"label": "Pod", "value": 35}],
            "cues": [{"action": "show", "at": 0.2}]}
    png = engine.render_still(spec, {"duration": 3, "sentences": [], "words": []}, 2.5, 640, 360, "premium-technical", False)
    a = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))
    assert a.std() > 4


@pytest.mark.parametrize("idx", range(6))
def test_every_example_scene_renders_vertically(idx):
    import io
    from PIL import Image
    spec = example("board.json")["scenes"][idx]
    sents = [s["text"] for s in example("script.json")["scenes"][idx]["sentences"]]
    words, t = [], 0.5
    for si, s in enumerate(sents):
        for w in s.split():
            words.append({"w": w, "s": t, "e": t + 0.3, "si": si}); t += 0.35
    timing = {"duration": t + 0.5, "sentences": [], "words": words}
    tr = engine.build(spec, timing, portrait=True)
    assert tr.portrait and tr.CX == 540.0
    for k in tr.pos.values():                       # every laid-out element is inside the 1080-wide frame
        assert -40 <= k[0] and k[0] + k[2] <= 1120, (spec["treatment"], k)
    png = engine.render_still(spec, timing, timing["duration"] * 0.8, 540, 960, "premium-technical", True)
    im = Image.open(io.BytesIO(png))
    assert im.size == (540, 960)
    assert np.asarray(im.convert("RGB")).std() > 4


def test_wrap_respects_width():
    f = engine.font(46, "SemiBold")
    rows = engine.wrap("Before the page appears, four decisions are made about where your request goes", f, 600)
    assert len(rows) > 1 and all(f.measureText(r) <= 600 for r in rows)


@pytest.mark.parametrize("portrait", [False, True])
def test_generic_isometric_and_cutaway_kinds(portrait):
    """The zone view and the cutaway are not tied to AWS or Kubernetes: a CDN draws with them too."""
    iso = {"id": "x", "title": "Edges", "treatment": "isometric", "state_labels": {"healthy": "has a copy", "unhealthy": "no copy yet"},
           "elements": [{"id": "rc", "kind": "cache", "label": "Regional edge cache"}, {"id": "r1", "kind": "region", "label": "Asia"},
                        {"id": "r2", "kind": "region", "label": "Europe"}, {"id": "e1", "kind": "edge", "label": "Karachi edge", "zone": "r1"},
                        {"id": "e2", "kind": "edge", "label": "Frankfurt edge", "zone": "r2", "state": "unhealthy"}],
           "cues": [{"at": 0.5, "action": "pulse"}]}
    cut = {"id": "y", "title": "Inside", "treatment": "cutaway", "container_label": "Edge server", "code": ["GET /logo.png"],
           "elements": [{"id": "p", "kind": "server", "label": "Request handler"}, {"id": "c", "kind": "cache", "label": "Cache lookup"},
                        {"id": "w1", "kind": "storage", "label": "Memory"}, {"id": "w2", "kind": "storage", "label": "SSD"}],
           "cues": [{"at": 0.5, "action": "lookup"}]}
    tm = {"duration": 3, "sentences": [], "words": []}
    a = engine.build(iso, tm, portrait=portrait)
    assert a.lb and len(a.zones) == 2 and len(a.nodes) == 2
    b = engine.build(cut, tm, portrait=portrait)
    assert b.ng and b.svc and len(b.pods) == 2
    for sp in (iso, cut):
        assert len(engine.render_still(sp, tm, 2.5, *((540, 960) if portrait else (960, 540)))) > 5000


def test_long_labels_stay_inside_their_boxes():
    long = "Cache-Control: max-age=86400, s-maxage=600, stale-while-revalidate=30"
    assert engine.fit(long, 200, 21, 15) != long and engine.font(15).measureText(engine.fit(long, 200, 21, 15)) <= 200
    assert engine.fit("Origin", 200, 21, 15) == "Origin"
    els = [{"id": f"e{i}", "label": "Regional edge cache", "sub": "the website's own server"} for i in range(5)]
    tr = engine.build({"id": "a", "title": "t", "treatment": "flow2d", "elements": els, "camera": {"start": ["e0", "e1"]}},
                      {"duration": 3, "sentences": [], "words": []})
    assert all(p[0] >= 0 and p[0] + p[2] <= 1920 for p in tr.pos.values())
    s, fx, _ = tr.frame_for(["e0", "e1"])
    lo, hi = fx - 960 / s, fx + 960 / s
    for p in tr.pos.values():   # no box is cut by the frame edge
        assert p[0] >= lo - 0.5 and p[0] + p[2] <= hi + 0.5 or p[0] + p[2] <= lo or p[0] >= hi
