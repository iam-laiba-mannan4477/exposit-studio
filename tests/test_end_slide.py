"""End slide (outro): appended at export from Settings, outside the AI script."""
import copy

from conftest import example
from exposit import store, director, compose, cli
from exposit.render import engine


def _prod(fmt="9:16"):
    pid = cli.create_from_example(fmt=fmt)
    b = store.read_json(pid, "brief.json", {})
    b["theme"] = "noir-network"
    store.write_json(pid, "brief.json", b)
    return pid


def _set(**kw):
    store.set_settings(kw)


def test_defaults_say_tech_hub_as_two_words_with_long_pauses():
    s = store.DEFAULT_SETTINGS
    assert s["end_slide"] is True
    assert s["end_slide_spoken"] == ["If you want tech to make sense to you,", "Like.", "Share.", "And follow Tech Hub."]
    assert [l["text"] for l in s["end_slide_lines"]] == ["If you want tech", "to make sense to you", "Like", "Share", "& Follow", "TechHub"]
    assert [l["accent"] for l in s["end_slide_lines"]] == [False, False, True, True, True, False]
    assert director.END_GAP == 0.55


def test_each_line_appears_on_its_spoken_word():
    s = store.DEFAULT_SETTINGS
    spec = director.end_slide_spec(s["end_slide_lines"], s["end_slide_spoken"], "push")
    assert spec["treatment"] == "kinetic" and spec["locked"] and spec["transition"] == "push" and spec["pad_end"] >= 1.8
    assert [l["at"] for l in spec["lines"]] == [{"word": w} for w in ("If", "make", "Like", "Share", "follow", "Hub")]
    assert spec["lines"][-1]["brand"] and spec["lines"][-1]["size"] > spec["lines"][2]["size"] > spec["lines"][0]["size"]
    # a cue word that is not spoken falls back to a timed reveal instead of firing at 0
    odd = director.end_slide_spec([{"text": "Hello", "at": "nonsense"}], ["Like."])
    assert isinstance(odd["lines"][0]["at"], float)
    # the timing resolves to the right words
    tm = {"duration": 4.0, "sentences": [], "words": [{"w": w, "s": i * 0.4, "e": i * 0.4 + 0.3, "si": 0} for i, w in
                                                      enumerate("If you want tech to make sense to you Like Share And follow Tech Hub".split())]}
    sc = engine.Scene(spec, tm)
    times = [sc.cue_time(l["at"]) for l in spec["lines"]]
    assert times == sorted(times) and all(t is not None for t in times)


def test_end_slide_is_appended_and_only_its_clip_changes_with_its_settings(client):
    pid = _prod()
    try:
        _set(end_slide=True)
        cur = director.scene_hashes(pid)
        board = example("board.json")["scenes"]
        assert [s["id"] for s in cur] == [s["id"] for s in board] + ["end"]
        end = cur[-1]
        assert end["end_slide"] and end["gap"] == 0.55 and end["spec"]["transition"] == board[-1].get("transition", "crossfade")
        before = {s["id"]: s["clip_hash"] for s in cur}
        lines = copy.deepcopy(store.DEFAULT_SETTINGS["end_slide_lines"])
        lines[-1]["text"] = "Tech Hub"
        _set(end_slide_lines=lines)
        after = {s["id"]: s["clip_hash"] for s in director.scene_hashes(pid)}
        assert [k for k in before if before[k] != after[k]] == ["end"], "only the end slide re-renders"
        _set(end_slide_spoken=["Like.", "Share."])
        again = director.scene_hashes(pid)
        assert again[-1]["audio_hash"] != end["audio_hash"] and all(a["audio_hash"] == b["audio_hash"] for a, b in zip(again[:-1], cur[:-1]))
        _set(end_slide=False)
        assert "end" not in [s["id"] for s in director.scene_hashes(pid)]
        # the script never contains it
        assert all(s["id"] != "end" for s in store.read_json(pid, "script/script.json")["scenes"])
    finally:
        store.set_settings({k: store.DEFAULT_SETTINGS[k] for k in ("end_slide", "end_slide_lines", "end_slide_spoken")})


def test_duration_check_counts_the_main_content_only(monkeypatch):
    monkeypatch.setattr(compose, "probe", lambda p: {"width": 1080, "height": 1920, "fps": 30.0, "duration": 70.0,
                                                    "vcodec": "h264", "acodec": "aac"})
    monkeypatch.setattr(compose, "_run", lambda args: "")
    expect = {"width": 1080, "height": 1920, "fps": 30, "duration": 60, "tolerance": 3}
    dur = lambda r: next(c for c in r if c["name"] == "Duration")
    assert not dur(compose.checks("x.mp4", expect))["passed"], "70 s fails a 60 s target"
    d = dur(compose.checks("x.mp4", dict(expect, exclude_tail=9.5)))
    assert d["passed"] and "end slide 9.5 s not counted" in d["detail"]


def test_end_slide_renders_in_both_formats_and_templates():
    s = store.DEFAULT_SETTINGS
    spec = director.end_slide_spec(s["end_slide_lines"], s["end_slide_spoken"])
    tm = {"duration": 4.0, "sentences": [], "words": []}
    for tp in ("noir-network", "paper"):
        for w, h in ((540, 960), (960, 540)):
            png = engine.render_still(spec, tm, 5.0, w, h, tp)
            assert png[:4] == b"\x89PNG"


def test_insert_scene_renders_only_the_new_scene_and_its_transition_neighbour(client):
    pid = _prod()
    try:
        _set(end_slide=False)
        before = {s["id"]: s for s in director.scene_hashes(pid)}
        board = example("board.json")["scenes"]
        after_id = board[1]["id"]
        plan = director.insert_scene(pid, after_id,
            {"id": "s2b", "title": "More", "terms": [], "sentences": [{"text": "And beyond that: Linux and databases.", "claims": []}]},
            {"treatment": "motion", "effect": "card_carousel", "transition": board[2].get("transition", "fade"),
             "items": [{"icon": "terminal", "title": "Linux", "at": {"word": "Linux"}}, {"icon": "database", "title": "Databases", "at": {"word": "databases"}}]})
        now = {s["id"]: s for s in director.scene_hashes(pid)}
        changed = {k for k in now if k not in before or now[k]["clip_hash"] != before[k]["clip_hash"]}
        nxt = board[2]["id"]
        expect = {"s2b"} | ({nxt} if engine.needs_prev(board[2]) else set())
        assert changed == expect, changed
        assert [k for k in now if k not in before or now[k]["audio_hash"] != before[k]["audio_hash"]] == ["s2b"]
        import pytest
        with pytest.raises(ValueError):
            director.insert_scene(pid, after_id, {"id": "s2b", "title": "dup", "sentences": [{"text": "x"}]}, {"treatment": "kinetic"})
    finally:
        store.set_settings({"end_slide": True})


def test_narration_hash_counts_only_pronunciations_that_apply():
    from exposit import tts
    assert tts.applied(["Linux and databases."]) == {}
    assert set(tts.applied(["AI agents and CI/CD."])) == {"AI", "CI/CD"}


def test_ai_and_iac_are_spelled_out_as_letters():
    import pytest
    from exposit import tts
    assert tts.spoken("AI agents and AI infrastructure") == "eh eye agents and eh eye infrastructure"
    assert tts.spoken("IaC") == "eye eh see"
    try:
        tok = tts.kokoro().tokenizer
    except Exception:
        pytest.skip("voice model not installed")
    assert tok.phonemize(tts.spoken("AI agents"), "en-us").startswith("ˈeɪ ˈaɪ")
    assert tok.phonemize(tts.spoken("IaC"), "en-us").startswith("ˈaɪ ˈeɪ")


def test_synthesis_cache_follows_the_spoken_form(monkeypatch):
    from exposit import tts
    keys = []
    monkeypatch.setattr(tts.store, "sha", lambda *a: keys.append(a) or "k")
    monkeypatch.setattr(tts, "kokoro", lambda: (_ for _ in ()).throw(RuntimeError("stop")))
    for text in ("AI agents",):
        try:
            tts.synth_sentence(text, "am_michael", 1.0)
        except RuntimeError:
            pass
    assert keys and keys[0][1] == "eh eye agents", "the cache key is the spoken text, so table changes take effect"


def test_cards_heading_leaves_room_for_the_step_pill():
    from exposit.render import design
    spec = {"id": "x", "treatment": "cards", "variant": "benefits", "title": "What you'll get",
            "items": [{"icon": "cpu", "title": "AI infrastructure", "text": "GPUs", "at": 0.2}],
            "cues": [{"action": "count", "at": 0.3, "n": 4, "total": 4, "label": "Real architectures"}]}
    tm = {"duration": 3.0, "sentences": [], "words": []}
    design.TEXT_LOG = []
    try:
        engine.render_still(spec, tm, 2.0, 1080, 1920, "noir-network", False)
        log = design.TEXT_LOG
    finally:
        design.TEXT_LOG = None
    head = [t for t in log if "What" in t["text"] or "get" in t["text"]]
    pill = [t for t in log if "Real architectures" in t["text"]]
    assert head and pill and all(h["size"] >= 72 for h in head)
    assert max(h["rect"][2] for h in head) < min(p["rect"][0] for p in pill), "the heading ends before the pill begins"
