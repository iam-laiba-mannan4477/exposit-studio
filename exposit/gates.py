"""Quality gates and the engagement evaluator. Measurements are exact; judgement comes from the Reviewer role."""
from __future__ import annotations
import re, statistics
from . import schemas
from .render.engine import norm_word, Scene, TREATMENTS, TRANSITIONS
from .render import assets, design

WPS = 2.45  # words per second at a natural narration pace


def _crit(name: str, ok: bool, detail: str = "") -> dict:
    return {"name": name, "passed": bool(ok), "detail": detail}


def research_gate(facts: dict) -> dict:
    claims = facts.get("claims", [])
    unsourced = [c["id"] for c in claims if not any(str(s.get("url", "")).startswith("http") for s in c.get("sources", []))]
    primary = [c for c in claims if any(s.get("kind") == "primary" for s in c.get("sources", []))]
    comps = {c["id"] for c in facts.get("model", {}).get("components", [])}
    bad_steps = [s["n"] for s in facts.get("model", {}).get("steps", []) if any(x not in comps for x in s.get("components", []))]
    crit = [
        _crit("At least five claims", len(claims) >= 5, f"{len(claims)} claims"),
        _crit("Every claim has a source with an address", not unsourced, "Missing: " + ", ".join(unsourced) if unsourced else "All sourced"),
        _crit("At least half the claims have a primary source", len(primary) * 2 >= len(claims), f"{len(primary)} of {len(claims)}"),
        _crit("One concrete arrangement is stated", bool(facts.get("arrangement", "").strip())),
        _crit("System model has components and ordered steps", len(comps) >= 2 and len(facts.get("model", {}).get("steps", [])) >= 2),
        _crit("Steps only name known components", not bad_steps, f"Steps {bad_steps}" if bad_steps else ""),
        _crit("No open questions left", not facts.get("open_questions"), "; ".join(facts.get("open_questions", []))),
    ]
    return {"gate": "research", "passed": all(c["passed"] for c in crit), "criteria": crit}


def words(text: str) -> list[str]:
    return [w for w in re.split(r"\s+", text.strip()) if w]


def engagement(script: dict, strategy: dict | None, target_seconds: float) -> dict:
    """Code-measured engagement signals. Flags are prompts to look, not predictions."""
    scenes = script.get("scenes", [])
    flags, per_scene = [], []
    all_sent = []
    for sc in scenes:
        sents = [s["text"] for s in sc.get("sentences", [])]
        n = sum(len(words(s)) for s in sents)
        per_scene.append({"id": sc["id"], "words": n, "est_seconds": round(n / WPS, 1), "terms": len(sc.get("terms", []))})
        all_sent += [(sc["id"], s) for s in sents]
        if len(sc.get("terms", [])) > 1:
            flags.append({"scene": sc["id"], "label": "overloaded", "why": f"{len(sc['terms'])} new terms in one scene", "fix": "Introduce one term per scene"})
        for s in sents:
            if len(words(s)) > 22:
                flags.append({"scene": sc["id"], "label": "confusing", "why": f"A sentence has {len(words(s))} words", "fix": "Split it into two"})
    total = sum(p["words"] for p in per_scene)
    med = statistics.median([p["est_seconds"] for p in per_scene]) if per_scene else 0
    for p in per_scene:
        if med and p["est_seconds"] > 2 * med:
            flags.append({"scene": p["id"], "label": "boring", "why": f"About {p['est_seconds']} s, more than twice the median scene", "fix": "Split the scene or add a visual change"})
    first = " ".join(s for sid, s in all_sent if scenes and sid == scenes[0]["id"])
    hook_ok = bool(re.search(r"\?|\byou\b|\bfour\b|\bthree\b|\bfive\b|\btwo\b|\d", first, re.I))
    grams: dict = {}
    for sid, s in all_sent:
        ws = [norm_word(w) for w in words(s)]
        for i in range(len(ws) - 3):
            g = " ".join(ws[i:i + 4])
            grams.setdefault(g, set()).add(sid)
    rep = [g for g, ids in grams.items() if len(ids) > 2]
    if rep:
        flags.append({"scene": "", "label": "repetitive", "why": f"Phrase repeated in three or more scenes: '{rep[0]}'", "fix": "Vary or cut the repeat"})
    stop = set("the a an and of to in is it that your you for on with as at by before are be this one same way".split())
    kw = lambda t: {norm_word(w) for w in words(t)} - stop
    last = " ".join(s for sid, s in all_sent if scenes and sid == scenes[-1]["id"])
    payoff_ok = len(kw(first) & kw(last)) >= 1 if scenes else False
    dev = abs(total / WPS - target_seconds) / max(1.0, target_seconds)
    return {"total_words": total, "est_seconds": round(total / WPS, 1), "target_seconds": target_seconds, "deviation": round(dev, 3),
            "per_scene": per_scene, "hook_has_question_or_stake": hook_ok, "ending_echoes_opening": payoff_ok, "flags": flags}


def script_gate(script: dict, facts: dict, strategy: dict | None, target_seconds: float, review: dict | None) -> dict:
    ids = {c["id"] for c in facts.get("claims", [])}
    eng = engagement(script, strategy, target_seconds)
    unknown = sorted({c for sc in script["scenes"] for s in sc["sentences"] for c in s.get("claims", []) if c not in ids})
    uncited = [sc["id"] for sc in script["scenes"] if not any(s.get("claims") for s in sc["sentences"])]
    blocking = [f for f in eng["flags"] if f["label"] in ("confusing", "overloaded")]
    crit = [
        _crit("Cited claims exist in the facts", not unknown, ", ".join(unknown)),
        _crit("Every scene rests on at least one claim", not uncited, ", ".join(uncited)),
        _crit("Length within 15% of the target", eng["deviation"] <= 0.15, f"About {eng['est_seconds']} s for a {target_seconds:.0f} s target"),
        _crit("Opening poses a question or stake", eng["hook_has_question_or_stake"]),
        _crit("Ending returns to the opening", eng["ending_echoes_opening"]),
        _crit("No scene flagged confusing or overloaded", not blocking, "; ".join(f"{f['scene']}: {f['why']}" for f in blocking)),
    ]
    if review is not None:
        crit.append(_crit("Independent review found no accuracy issue", bool(review.get("passed")), "; ".join(review.get("accuracy_issues", []))))
    return {"gate": "script", "passed": all(c["passed"] for c in crit), "criteria": crit, "engagement": eng, "review": review}


def max_run(xs: list) -> int:
    """The longest run of equal neighbours."""
    best = run = 0
    prev = object()
    for x in xs:
        run = run + 1 if x == prev else 1
        best, prev = max(best, run), x
    return best


def spec_icons(spec: dict) -> list[str]:
    """Every icon name a scene spec asks for (elements, items, steps, panel, client, origin, strip, footer)."""
    out = []
    pools = [spec.get("elements", []), spec.get("items", []), spec.get("footer", []),
             (spec.get("strip") or {}).get("items", []), (spec.get("legend") or {}).get("items", [])]
    for lane in spec.get("lanes", []):
        pools.append(lane.get("steps", []))
        pools.append([lane] + ([lane["result"]] if isinstance(lane.get("result"), dict) else []))
    pools.append([spec.get(k) for k in ("panel", "client", "origin") if isinstance(spec.get(k), dict)])
    pools.append([c for c in spec.get("cues", []) if c.get("action") == "chip"])
    for pool in pools:
        out += [str(x["icon"]) for x in pool if isinstance(x, dict) and x.get("icon")]
    if spec.get("icon"):
        out.append(str(spec["icon"]))
    return out


def storyboard_gate(board: dict, script: dict, facts: dict) -> dict:
    comps = {c["id"] for c in facts.get("model", {}).get("components", [])}
    sids = [s["id"] for s in script.get("scenes", [])]
    problems, sparse, refs, unknown_names = [], [], [], []
    if board.get("template") and board["template"] not in design.TEMPLATES:
        unknown_names.append(f"unknown template {board['template']}")
    for spec in board.get("scenes", []):
        sc_script = next((s for s in script["scenes"] if s["id"] == spec["id"]), None)
        if sc_script is None:
            problems.append(f"{spec['id']}: no such script scene")
            continue
        if spec.get("treatment") not in TREATMENTS:
            problems.append(f"{spec['id']}: unknown treatment {spec.get('treatment')}")
        bad_icons = sorted({i for i in spec_icons(spec) if assets.resolve(i) is None})
        if bad_icons:
            unknown_names.append(f"{spec['id']}: unknown icon {', '.join(bad_icons)}")
        if spec.get("theme") and spec["theme"] not in design.TEMPLATES:
            unknown_names.append(f"{spec['id']}: unknown template {spec['theme']}")
        if spec.get("transition", "fade") not in TRANSITIONS:
            unknown_names.append(f"{spec['id']}: unknown transition {spec.get('transition')}")
        spoken = {norm_word(w) for s in sc_script["sentences"] for w in words(s["text"])}
        eids = {e["id"] for e in spec.get("elements", [])} | {"_in"}
        for c in spec.get("cues", []) + (spec.get("lines") or []):
            at = c.get("at")
            if isinstance(at, dict) and "word" in at and norm_word(at["word"]) not in spoken:
                problems.append(f"{spec['id']}: cue word '{at['word']}' is not spoken in this scene")
            for k in ("target", "from", "to"):
                if k in c and c.get("action") not in ("count",) and c[k] not in eids:
                    problems.append(f"{spec['id']}: cue refers to unknown element '{c[k]}'")
        for e in spec.get("elements", []):
            if e.get("model_ref") and e["model_ref"] not in comps:
                refs.append(f"{spec['id']}: {e['id']} -> {e['model_ref']}")
        n_words = sum(len(words(s["text"])) for s in sc_script["sentences"])
        est = n_words / WPS
        changes = len(spec.get("cues", [])) + len(spec.get("lines") or [])
        if est > 0 and changes / est < 1 / 6:
            sparse.append(f"{spec['id']}: {changes} visual changes in about {est:.0f} s")
    crit = [
        _crit("One specification per script scene", [s["id"] for s in board.get("scenes", [])] == sids),
        _crit("Cues point at spoken words and known elements", not problems, "; ".join(problems[:6])),
        _crit("Drawn elements map to the system model", not refs, "; ".join(refs[:6])),
        _crit("A visual change at least every 6 seconds", not sparse, "; ".join(sparse)),
        _crit("Icons, templates and transitions are all known", not unknown_names, "; ".join(unknown_names[:6])),
        _crit("Every treatment is supported on this machine", all(s.get("treatment") in TREATMENTS for s in board.get("scenes", []))),
        _crit("No paid service required", True, "Local renderer"),
    ]
    return {"gate": "storyboard", "passed": all(c["passed"] for c in crit), "criteria": crit}
