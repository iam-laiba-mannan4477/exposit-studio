"""Claude Code project structure Reel, v2: a multi-scene edit in claude-orange-dark (one dev_scene per script line,
varied transitions, generic editor UI, the channel's mascot) ending on the full dark diagram. Script and facts from v1
(fact-checked 2026-11-25), line 1 as a question. Writes script.json, board.json, research.json and strategy.json."""
import json, sys
from pathlib import Path

H = Path(__file__).parent
V1 = H.parent / "claude-code-structure"
sys.path.insert(0, str(H.parents[2]))
from exposit.render import tree as TR, design as DS, styles  # noqa: E402,F401

THEME = "claude-orange-dark"
v1_script = json.loads((V1 / "script.json").read_text(encoding="utf-8"))
script = json.loads(json.dumps(v1_script))
script["scenes"][0]["sentences"] = [{"text": "Which files does Claude Code actually read?", "claims": ["c13"]},
                                    {"text": "Here are the key ones.", "claims": ["c13"]}]

# the final diagram: v1's tree with two-line cards so it fits between y 300 and 1530 (Instagram safe zones)
CARDS = {"claude_md": "Project brief, read every session. Supports @imports.",
         "local_md": "Your personal notes, read after CLAUDE.md. Add it to .gitignore.",
         "mcp": "Team-shared MCP servers, committed with the repo.",
         "settings": "Permissions, hooks, env, model. Enforced, not advisory.",
         "settings_local": "Personal overrides. Git-ignored once Claude Code writes it.",
         "rules": "Instructions by topic. Can be scoped to file paths.",
         "skills": "One folder per skill. Run with /name, or used when relevant.",
         "commands": "Older single-file form of skills. Same /name.",
         "agents": "Subagents with their own prompt, tools and model.",
         "hooks": "Scripts around tool calls. Pre-tool hooks can block."}
v1_board = json.loads((V1 / "board.json").read_text(encoding="utf-8"))["scenes"]
TREE = [dict(r, card=CARDS[r["id"]]) if r["id"] in CARDS else dict(r) for r in v1_board[0]["tree"]]
for r in TREE:
    r.pop("space_after", None)
    if r.get("note"):
        r["note"] = "wired in settings.json"
FOOT = "Has AGENTS.md? Claude Code reads it if there is no CLAUDE.md."
DIAGRAM = {"tree": TREE, "footnote": FOOT, "band": [330, 1530], "foot_inset": 0, "keep": ["claude_md", "settings"]}
DS.set_active(DS.TEMPLATES[THEME])
TR.set_palette(THEME)
problems = TR.check_layout(DIAGRAM)
PERCH = [930.0, TR.layout(DIAGRAM)["cards"]["claude_md"]["y"] - 1]      # on the CLAUDE.md card's top edge, under the heading row

w = lambda x, off=0.0, occ=1: {"word": x, "offset": off, "occurrence": occ}
M = lambda pos, *acts: {"scale": 3, "pos": list(pos), "acts": list(acts)}
SC = {
 "s1": dict(kind="hook", file="~/my-project", focus_out=[540, 900],
            mascot=M((940, 1500), {"type": "drop_in", "at": w("Here", 0.5), "to": [940, 1500]}, {"type": "glasses", "at": w("Here", 1.2)}),
            cues=[{"at": 0.35, "action": "keys"}, {"at": 1.1, "action": "keys"}, {"at": w("Here"), "action": "transition"}],
            objective="Black screen, `claude` typed, tree -a cascades, the camera dollies through as the tree flies apart into 3D file cards"),
 "s2": dict(kind="claude_md", file="CLAUDE.md", tin="match", tout="whip",
            mascot=M((940, 1500), {"type": "hop", "at": w("brief,", 0.2), "to": [900, 330]}),
            pops=[{"text": "CLAUDE.md", "at": w("CLAUDE.md"), "y": 1470}],
            push=[{"at": w("loaded"), "x": 540, "y": 1300, "z": 1.06, "hold": 1.2}],
            cues=[{"at": 0.75, "action": "keys"}, {"at": 1.6, "action": "keys"}, {"at": w("loaded"), "action": "whoosh_soft"}],
            objective="Cards fly into the editor; CLAUDE.md types in; on 'loaded' it pours into the context-window bar"),
 "s3": dict(kind="local_md", file="CLAUDE.local.md", tin="whip", tout="zoom", focus_out=[700, 1240],
            mascot=M((900, 320), {"type": "peek", "at": w("personal"), "dur": 2.4}),
            pops=[{"text": "private", "at": w("personal"), "y": 1470}],
            cues=[{"at": 0.0, "action": "transition"}, {"at": w("add", 0.2), "action": "keys"}, {"at": w(".gitignore."), "action": "highlight"}],
            objective="Editor above, terminal below: git status, echo >> .gitignore, the file greys out with an 'ignored' tag"),
 "s4": dict(kind="mcp", file=".mcp.json", tin="zoom", focus_in=[540, 600], wipe_out=True,
            mascot=M((960, 330)),
            cues=[{"at": 0.0, "action": "transition"}, {"at": w("connects"), "action": "highlight"}, {"at": w("GitHub"), "action": "whoosh_soft"},
                  {"at": w("team."), "action": "highlight"}],
            objective=".mcp.json keys highlight one by one; mask reveal into a hub with GitHub, Postgres and Jira; 'shared with team'"),
 "s5": dict(kind="settings", file=".claude/settings.json", wipe_in=True, tout="push",
            mascot=M((960, 320), {"type": "hop", "at": w("settings.json", 0.2), "to": [760, 372]},
                     {"type": "tap", "at": w("settings.json", 0.8), "dir": -1}),
            pops=[{"text": "enforced", "at": w("enforced:"), "y": 1450}],
            push=[{"at": w("enforced:"), "x": 540, "y": 1150, "z": 1.07, "hold": 1.6}],
            cues=[{"at": 0.0, "action": "transition"}, {"at": 0.5, "action": "keys"}, {"at": w("enforced:", 0.0), "action": "keys"},
                  {"at": w("permissions,"), "action": "highlight"}, {"at": w("settings.local.json"), "action": "whoosh_soft"},
                  {"at": w("override."), "action": "highlight"}],
            objective="Wipe into .claude/: a deny rule, a blocked command, then the settings precedence as stacking cards"),
 "s6": dict(kind="rules", file=".claude/rules/", tin="push",
            mascot=M((930, 930)),
            cues=[{"at": 0.0, "action": "transition"}, {"at": w("topic,"), "action": "highlight"}, {"at": w("path."), "action": "highlight"}],
            objective="Isometric rule cards fan out; a paths glob lights the matching files"),
 "s7": dict(kind="skills", file=".claude/skills/", tin="mask", focus_in=[540, 900], tout="whip",
            pick_at=w("Run", 0.1), push_at=w("Claude", -0.2), flip_at=w("Commands", -0.1, 2),
            mascot=M((960, 330), {"type": "into_folder", "at": w("Claude", 0.5), "to": [58, 470], "hold": 99},
                     {"type": "out_of_folder", "at": w("Commands", -0.6, 2), "to": [900, 650]}),
            pops=[{"text": "/review", "at": w("Run", 0.1), "y": 1420}],
            push=[{"at": w("Claude"), "x": 540, "y": 700, "z": 1.06, "hold": 2.0}],
            cues=[{"at": 0.35, "action": "keys"}, {"at": w("Run", 0.1), "action": "highlight"}, {"at": w("Claude", 0.2), "action": "keys"},
                  {"at": w("Commands", 0, 2), "action": "whoosh_soft"}, {"at": w("older,"), "action": "highlight"}],
            objective="'/' opens the skill menu; /review; push into SKILL.md frontmatter; card flip to commands/ (legacy)"),
 "s8": dict(kind="agents", file=".claude/agents/", tin="whip", tout="push",
            mascot=M((900, 650)),
            cues=[{"at": 0.0, "action": "transition"}, {"at": w("subagents"), "action": "highlight"}, {"at": w("tools."), "action": "highlight"}],
            objective="The main session spawns two subagents with their own tool chips; they work in parallel and send summaries back"),
 "s9": dict(kind="hooks", file=".claude/hooks/", tin="push",
            mascot=M((960, 760), {"type": "shake", "at": w("block")}),
            push=[{"at": w("block"), "x": 300, "y": 700, "z": 1.06, "hold": 0.9}],
            cues=[{"at": 0.0, "action": "transition"}, {"at": 0.9, "action": "keys"}, {"at": w("block"), "action": "thud"},
                  {"at": w("run."), "action": "highlight"}],
            objective="PreToolUse -> tool runs -> PostToolUse; validate-bash.sh; BLOCK stamp with a shake; a safe call passes"),
 "s10": dict(kind="takeaway", file="my-project/", tin="mask", focus_in=[540, 900], wipe_out=w("Start", -0.35), diagram=DIAGRAM,
             mascot=M((930, 420), {"type": "hop", "at": w("Start", -0.25), "to": PERCH}, {"type": "glasses", "at": w("files.", 1.6)}),
             cues=[{"at": 0.0, "action": "transition"}, {"at": w("guidance."), "action": "highlight"}, {"at": w("enforced."), "action": "highlight"},
                   {"at": w("Start", -0.35), "action": "transition"}, {"at": w("files."), "action": "highlight"},
                   {"at": w("files.", 2.15), "action": "highlight"}],   # the shine: breaks the silent 3 s hold
             pad_end=3.7, objective="Guidance vs enforced, then a wipe into the full diagram; CLAUDE.md and settings.json glow; hold 3 s"),
}
scenes = []
for s in script["scenes"]:
    sp = {"id": s["id"], "title": s["title"], "treatment": "motion", "effect": "dev_scene", "transition": "cut",
          "pad_start": 0.1, "pad_end": 0.15, "tier": "hypothesis", "recipes": [], "reason": "A different layout and camera move per line."}
    sp.update(SC[s["id"]])
    if s["id"] == "s1":
        sp["transition"] = "fade"
    if s["id"] == "s9":
        sp["pad_end"] = 0.6
    if s["id"] == "s10":
        sp.update(cover=True, cover_crop=[280, 1560], cover_mascot={"x": 930, "y": 1690, "scale": 4, "glasses_dy": -6})
    scenes.append(sp)

research = json.loads((V1 / "research.json").read_text(encoding="utf-8"))
D = "https://code.claude.com/docs/en/"
research["claims"] += [
 {"id": "c14", "text": "A Bash deny rule can use a * wildcard that matches any text, e.g. \"deny\": [\"Bash(rm -rf *)\"] under permissions. The docs do not give an exact denial message, so the video's terminal shows generic wording.", "sources": [{"title": "Permissions (read 2026-11-25)", "url": D + "permissions", "kind": "primary"}], "confidence": "high"},
 {"id": "c15", "text": "Settings precedence, highest first: managed settings, command line, project local, shared project, user.", "sources": [{"title": "Claude Code settings (read 2026-11-25)", "url": D + "settings", "kind": "primary"}], "confidence": "high"},
 {"id": "c16", "text": "Rules can be scoped with a paths: list of globs in YAML frontmatter, e.g. \"src/api/**/*.ts\".", "sources": [{"title": "Memory (rules) (read 2026-11-25)", "url": D + "memory", "kind": "primary"}], "confidence": "high"},
 {"id": "c17", "text": "Each subagent runs in its own context window with its own tool access; subagents can run concurrently and return their results to the main conversation.", "sources": [{"title": "Create custom subagents (read 2026-11-25)", "url": D + "sub-agents", "kind": "primary"}], "confidence": "high"},
 {"id": "c18", "text": "A PreToolUse hook receives tool_input.command for Bash and can deny the call (the docs' example greps for 'rm -rf' with jq).", "sources": [{"title": "Hooks reference (read 2026-11-25)", "url": D + "hooks", "kind": "primary"}], "confidence": "high"},
 {"id": "c19", "text": "Skills appear in the / menu; the frontmatter name is the command shown there and description tells Claude when to use it.", "sources": [{"title": "Extend Claude with skills (read 2026-11-25)", "url": D + "skills", "kind": "primary"}], "confidence": "high"},
]
research["open_questions"] = []

strategy = json.loads((V1 / "strategy.json").read_text(encoding="utf-8"))
strategy.update(
    creative_concept="A premium multi-scene edit: a different layout and camera move per line inside a generic developer UI, ending on one save-worthy dark diagram.",
    treatments=[
        {"name": "A. Multi-scene developer UI edit", "shape": "terminal, editor, split screen, hub diagram, stacking cards, isometric stack, menu, node graph, lifecycle timeline, full diagram",
         "engagement": "high: a new shot every line", "teaching_fit": "strong: each file shown doing its job", "accuracy_risk": "low: every UI detail from the docs",
         "feasibility": "new dev_scene effect", "verdict": "Chosen: the user's v2 plan."},
        {"name": "B. v1's single building diagram", "shape": "one diagram, row by row", "engagement": "steady", "teaching_fit": "strong overview",
         "accuracy_risk": "low", "feasibility": "done", "verdict": "Rejected for v2: one layout for 60 s."},
        {"name": "C. Talking-head style captions over b-roll", "shape": "kinetic text only", "engagement": "medium", "teaching_fit": "weak",
         "accuracy_risk": "low", "feasibility": "easy", "verdict": "Rejected: shows nothing real."}],
    chosen="A. Multi-scene developer UI edit",
    hook="A blinking cursor types claude; tree -a cascades and flies apart into 3D file cards.",
    visual_direction="claude-orange-dark: near-black, terracotta and bright orange accents, generic editor windows, warm syntax theme, light rays, the channel's mascot with a cream rim light.",
    scene_breakdown=[{"title": s["title"], "treatment": "motion", "effect": "dev_scene", "seconds": 0, "purpose": s["objective"]} for s in scenes],
    template="claude-orange-dark", template_reason="User's choice for v2.",
    effects=["dev_scene", "project_tree"], effects_reason="dev_scene for the per-line scenes; project_tree for the final diagram.",
    decisions=[d for d in strategy["decisions"] if d["key"] not in ("template", "structure", "transitions")] + [
        {"key": "template", "choice": "claude-orange-dark", "reason": "User's choice; comment colour lightened to #8F877D for 4.5:1.", "tier": "preference"},
        {"key": "structure", "choice": "a different layout per line", "reason": "User's v2 plan.", "tier": "preference"},
        {"key": "transitions", "choice": "match cut, whip pans, zoom-through, push-through, mask reveals, two wipes", "reason": "Varied, one per change.", "tier": "preference"}])
for i, sc in enumerate(strategy["scene_breakdown"]):
    sc["seconds"] = [4.6, 4.2, 5.4, 6.4, 10.5, 3.9, 10.9, 2.6, 5.4, 9.3][i]
    sc["effect"] = "dev_scene:" + scenes[i]["kind"]          # each kind is its own layout (a different shot)

for name, obj in (("script", script), ("board", {"scenes": scenes}), ("research", research), ("strategy", strategy)):
    (H / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(scenes), "scenes;", sum(len(x["text"].split()) for sc in script["scenes"] for x in sc["sentences"]), "words; diagram:", problems or "ok")
