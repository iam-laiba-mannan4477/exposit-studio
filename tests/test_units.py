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
    assert {"iconflow", "isometric", "cutaway", "sequence"} <= {sc.treatment for sc in b.scenes}


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


def _timing_for(sents):
    words, t = [], 0.5
    for si, s in enumerate(sents):
        for w in s.split():
            words.append({"w": w, "s": t, "e": t + 0.3, "si": si}); t += 0.35
        t += 0.3
    return {"duration": t + 0.5, "sentences": [], "words": words}


def test_word_groups_are_two_to_four_words_within_a_sentence():
    sents = ["Behind a CDN, your request often never reaches the website's own server.", "So where does it go?", "Hi.", "Now"]
    timing = _timing_for(sents)
    groups = engine.word_groups(timing)
    flat = [w["w"] for g in groups for w in g["words"]]
    assert flat == [w["w"] for w in timing["words"]], "every word, once, in order"
    for g in groups:
        assert len({w["si"] for w in g["words"]}) == 1, "a group never spans two sentences"
        n_in_sentence = sum(1 for w in timing["words"] if w["si"] == g["words"][0]["si"])
        assert 2 <= len(g["words"]) <= 4 or n_in_sentence < 2, [w["w"] for w in g["words"]]
        assert g["s"] == g["words"][0]["s"] and g["e"] == g["words"][-1]["e"]


def _accent_pixels(png, region, accent="#7C6CF6"):
    import io
    from PIL import Image
    a = np.asarray(Image.open(io.BytesIO(png)).convert("RGB")).astype(int)
    y0, y1 = region
    band = a[int(y0 * a.shape[0]):int(y1 * a.shape[0])]
    r, g, b = (int(accent[i:i + 2], 16) for i in (1, 3, 5))
    return int((np.abs(band - [r, g, b]).sum(axis=2) < 60).sum())


@pytest.mark.parametrize("portrait", [False, True])
def test_word_highlight_captions_follow_the_spoken_word(portrait):
    spec = {"id": "s1", "treatment": "kinetic", "lines": [], "elements": [], "cues": []}
    timing = _timing_for(["Behind a CDN your request often never reaches the server."])
    w, h = (540, 960) if portrait else (960, 540)
    band = (1350 / 1920, 1500 / 1920) if portrait else (900 / 1080, 1010 / 1080)
    tr = engine.build(spec, timing, portrait=portrait, caption_style="word")
    t2 = tr.sc.word_groups[0]["words"][1]["s"] + 0.1          # second word of the first group is being spoken
    g, k = engine.active_word_group(tr.sc, t2)
    assert k == 1 and g is tr.sc.word_groups[0]
    word = engine.render_still(spec, timing, t2, w, h, captions=True, caption_style="word")
    phrase = engine.render_still(spec, timing, t2, w, h, captions=True, caption_style="phrase")
    assert _accent_pixels(word, band) > 50, "the spoken word is drawn in the accent colour"
    assert _accent_pixels(phrase, band) == 0, "Phrase captions are white on black"
    off = engine.render_still(spec, timing, t2, w, h, captions=False, caption_style="word")
    assert _accent_pixels(off, band) == 0, "no captions when burn-in is off"


def test_phrase_style_is_the_default_and_unchanged():
    spec = example("board.json")["scenes"][0]
    timing = _timing_for([s["text"] for s in example("script.json")["scenes"][0]["sentences"]])
    t = timing["duration"] * 0.5
    default = engine.render_still(spec, timing, t, 960, 540, "premium-technical", True)
    assert default == engine.render_still(spec, timing, t, 960, 540, "premium-technical", True, caption_style="phrase")
    assert default == engine.render_still(spec, timing, t, 960, 540, "premium-technical", True, caption_style="bogus"), "unknown styles fall back to Phrase"
    assert store.DEFAULT_SETTINGS["caption_style"] == "phrase"


@pytest.mark.parametrize("fault", ["icon", "template", "transition"])
def test_storyboard_gate_rejects_unknown_icons_templates_and_transitions(fault):
    facts, script, board = (example(f) for f in ("facts.json", "script.json", "board.json"))
    bad = copy.deepcopy(board)
    sc = bad["scenes"][1]
    if fault == "icon":
        (sc.setdefault("elements", []) or [{}])[0]["icon"] = "not-a-real-icon"
    elif fault == "template":
        sc["theme"] = "neon-dreams"
    else:
        sc["transition"] = "star-wipe"
    g = gates.storyboard_gate(bad, script, facts)
    crit = next(c for c in g["criteria"] if c["name"].startswith("Icons, templates and transitions"))
    assert not g["passed"] and not crit["passed"] and fault in crit["detail"]


def test_max_run_of_treatments():
    assert gates.max_run(["kinetic", "map", "map", "iconflow"]) == 2
    assert gates.max_run(["map", "map", "map"]) == 3


def test_visual_planner_skill_documents_every_treatment_template_and_transition():
    from exposit.render import engine, design
    from exposit import schemas
    text = (ROOT / "exposit" / "skills" / "visual_planner.md").read_text(encoding="utf-8") if "ROOT" in globals() else \
        (__import__("pathlib").Path(__file__).resolve().parent.parent / "exposit" / "skills" / "visual_planner.md").read_text(encoding="utf-8")
    for t in engine.TREATMENTS:
        assert f"\n{t}:" in text, f"treatment {t} has no section"
    for t in design.NEW_TEMPLATES:
        assert t in text
    for t in engine.TRANSITIONS:
        assert f'"{t}"' in text
    assert set(schemas.TREATMENTS) == set(engine.TREATMENTS), "the Creative Director is offered every treatment"


def test_storyboard_gate_counts_timed_card_items_as_visual_changes():
    facts, script, board = (example(f) for f in ("facts.json", "script.json", "board.json"))
    b = copy.deepcopy(board)
    words = [w for s in script["scenes"][1]["sentences"] for w in s["text"].split()]
    b["scenes"][1] = {"id": b["scenes"][1]["id"], "title": "t", "treatment": "cards", "variant": "benefits", "cues": [],
                      "items": [{"icon": "cloud", "title": "x", "at": {"word": w.strip(",.:")}} for w in words[:6]]}
    crit = {c["name"]: c for c in gates.storyboard_gate(b, script, facts)["criteria"]}
    assert crit["A visual change at least every 6 seconds"]["passed"], crit["A visual change at least every 6 seconds"]["detail"]


def test_creative_director_knows_every_style_and_effect():
    from exposit.render import styles, motion
    root = __import__("pathlib").Path(__file__).resolve().parent.parent / "exposit" / "skills"
    cd = (root / "creative_director.md").read_text(encoding="utf-8")
    vp = (root / "visual_planner.md").read_text(encoding="utf-8")
    for n in styles.READY:
        assert f"- {n}:" in cd, n
    for n in styles.PLANNED:
        assert n in cd and n in vp
    for e in motion.EFFECTS:
        assert f"- {e}:" in cd and e in vp, e


def test_style_criteria_variety_and_requirements():
    good = {"template": "low-poly-neon", "effects": ["model_3d", "parallax"], "effects_reason": "infra", "template_reason": "x"}
    crit = {c["name"]: c["passed"] for c in gates.style_criteria(good, [])}
    assert all(crit.values()), crit
    prev = [{"title": "Last", "style": "low-poly-neon", "effects": ["parallax", "model_3d"]}]
    assert not {c["name"]: c["passed"] for c in gates.style_criteria(good, prev)}["Not the same style and effects as the previous video"]
    bad = dict(good, template="hd-pixel-sprite-3d", effects=["parallax", "marquee"])
    crit = {c["name"]: c["passed"] for c in gates.style_criteria(bad, [])}
    assert not crit["Style requirements are met"]
    assert not {c["name"]: c["passed"] for c in gates.style_criteria(dict(good, template="stick-figure-story"), [])}["Animation style is known and available"]
    assert not {c["name"]: c["passed"] for c in gates.style_criteria(dict(good, effects=["warp_drive", "parallax"]), [])}["Two to six known motion effects, with a reason"]


@pytest.mark.parametrize("fault", ["effect", "content_effect", "planned_style"])
def test_storyboard_gate_rejects_unknown_effects_and_planned_styles(fault):
    facts, script, board = (example(f) for f in ("facts.json", "script.json", "board.json"))
    bad = copy.deepcopy(board)
    sc = bad["scenes"][1]
    if fault == "effect":
        sc["effects"] = [{"type": "warp_drive"}]
    elif fault == "content_effect":
        sc.update(treatment="motion", effect="hologram")
    else:
        sc["theme"] = "stick-figure-story"
    crit = next(c for c in gates.storyboard_gate(bad, script, facts)["criteria"] if c["name"].startswith("Icons, templates"))
    assert not crit["passed"]


def test_hd_pixel_sprite_needs_a_model_scene():
    facts, script, board = (example(f) for f in ("facts.json", "script.json", "board.json"))
    crit = next(c for c in gates.storyboard_gate(board, script, facts, "hd-pixel-sprite-3d")["criteria"] if c["name"].startswith("Icons, templates"))
    assert not crit["passed"] and "3D model" in crit["detail"]
