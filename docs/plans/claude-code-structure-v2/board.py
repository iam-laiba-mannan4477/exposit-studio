"""Claude Code project structure Reel, v2 update (production p5c0e8dbb85): the problem-first script (2026-11-25),
a generic IDE for S1-S3, S5, S7 and S9, full-screen diagrams for S4, S6 and S8, and three takeaway cards. Line 10 is
four scenes (intro + one per takeaway) so the scene pads give the ~0.35 s pauses between the points.
Writes script.json, board.json, research.json and strategy.json next to this file."""
import json, sys
from pathlib import Path

H = Path(__file__).parent
V1 = H.parent / "claude-code-structure"
sys.path.insert(0, str(H.parents[2]))
from exposit.render import tree as TR, design as DS, styles  # noqa: E402,F401

THEME = "claude-orange-dark"
S = lambda text, *claims: {"text": text, "claims": list(claims)}
LINES = [
    ("s1", "Hook: ignored rule", [S("Claude Code ignored your rule?", "c12"), S("It's probably in the wrong file.", "c12")]),
    ("s2", "CLAUDE.md", [S("CLAUDE.md is the project brief, loaded every session.", "c1")]),
    ("s3", "CLAUDE.local.md", [S("CLAUDE.local.md is the same idea, but personal.", "c2"), S("Add it to .gitignore.", "c2")]),
    ("s4", ".mcp.json", [S(".mcp.json connects tools like GitHub or a database for the whole team.", "c3")]),
    ("s5", "settings", [S("Inside .claude: settings.json is enforced: permissions, hooks, environment, model.", "c4"),
                        S("settings.local.json is your private override.", "c5")]),
    ("s6", "rules", [S("Rules split instructions by topic, and can target specific file paths.", "c6", "c16")]),
    ("s7", "skills and commands", [S("Skills are reusable workflows, called with a slash or picked up automatically.", "c7", "c19"),
                                   S("Commands are the older form.", "c8")]),
    ("s8", "agents", [S("Agents are subagents with their own context and tools.", "c9", "c17")]),
    ("s9", "hooks", [S("Hooks run scripts around tool calls, and can block unsafe ones before they run.", "c10", "c18")]),
    ("s10", "Three things", [S("Three things to remember.", "c12")]),
    ("s11", "Takeaway one", [S("CLAUDE.md is guidance, not a guarantee.", "c12")]),
    ("s12", "Takeaway two", [S("If it must never happen, enforce it with a deny rule or a hook.", "c14", "c18")]),
    ("s13", "Takeaway three", [S("Start with CLAUDE.md and settings.json.", "c12")]),
]
script = {"scenes": [{"id": i, "title": t, "sentences": s, "terms": []} for i, t, s in LINES]}

# the final diagram, as approved for v2
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
PERCH = [930.0, TR.layout(DIAGRAM)["cards"]["claude_md"]["y"] - 1]

w = lambda x, off=0.0, occ=1: {"word": x, "offset": off, "occurrence": occ}
M = lambda pos, *acts: {"scale": 3, "pos": list(pos), "acts": list(acts)}
TABS = [900.0, 352.0]                                    # on the IDE's tab row, right side
SC = {
 "s1": dict(kind="ide_hook", file="CLAUDE.md", tout="whip",
            pops=[{"text": "Ignored your rule?", "at": 0.45, "y": 760, "size": 84, "hold": 2.2}],
            mascot=M((960, 900), {"type": "peek", "at": 0.7, "dur": 2.3}),
            cues=[{"at": 0.3, "action": "thud"}, {"at": 0.45, "action": "highlight"}, {"at": w("wrong"), "action": "whoosh_soft"},
                  {"at": w("file."), "action": "highlight"}],
            expand_at=w("wrong", -0.1),
            objective="Frame 0: CLAUDE.md says 'Never delete build/' while the terminal shows rm -rf build/ (illustrative); the rule flashes red; 'Ignored your rule?'; pull back as the explorer expands"),
 "s2": dict(kind="ide_claude_md", file="CLAUDE.md", tin="whip", tout="push",
            pops=[{"text": "CLAUDE.md", "at": w("CLAUDE.md"), "y": 1440}],
            mascot=M(TABS),
            cues=[{"at": 0.4, "action": "keys"}, {"at": 1.4, "action": "keys"}, {"at": w("loaded"), "action": "highlight"},
                  {"at": w("session."), "action": "highlight"}],
            objective="CLAUDE.md types in the editor; on 'loaded every session' it fills the context window"),
 "s3": dict(kind="ide_local", file="CLAUDE.local.md", tin="push", tout="zoom", focus_out=[700, 1300],
            pops=[{"text": "personal", "at": w("personal."), "y": 1000}],
            mascot=M(TABS, {"type": "peek", "at": w("personal."), "dur": 2.2}),
            cues=[{"at": w("Add", 0.1), "action": "keys"}, {"at": w(".gitignore."), "action": "highlight"}],
            objective="Explorer marks CLAUDE.local.md untracked (U); Add-Content .gitignore; the file dims as ignored"),
 "s4": dict(kind="mcp", hub_only=True, file=".mcp.json", tin="zoom", focus_in=[540, 860], wipe_out=True,
            mascot=M((930, 420)),
            cues=[{"at": w("connects"), "action": "highlight"}, {"at": w("GitHub"), "action": "packet"},
                  {"at": w("team."), "action": "highlight"}],
            objective="Full-screen hub: Claude Code connected to GitHub, Postgres and Jira; 'shared with team'"),
 "s5": dict(kind="ide_settings", file=".claude/settings.json", wipe_in=True, tout="push",
            pops=[{"text": "enforced", "at": w("enforced:"), "y": 1000}],
            mascot=M((930, 420), {"type": "hop", "at": w("settings.json", 0.2), "to": TABS},
                     {"type": "tap", "at": w("settings.json", 0.8), "dir": -1}),
            cues=[{"at": 0.4, "action": "keys"}, {"at": w("enforced:"), "action": "keys"}, {"at": w("permissions,"), "action": "highlight"},
                  {"at": w("settings.local.json"), "action": "whoosh_soft"}, {"at": w("override."), "action": "highlight"}],
            objective="IDE: a deny rule; the terminal's rm -rf build/ is denied (illustrative); then the precedence stack"),
 "s6": dict(kind="rules", file=".claude/rules/", tin="push", lit_at=w("paths."),
            mascot=M((930, 930)),
            cues=[{"at": w("topic,"), "action": "highlight"}, {"at": w("paths."), "action": "highlight"}],
            objective="Full-screen isometric rule cards; a paths glob lights the matching files"),
 "s7": dict(kind="ide_skills", file=".claude/skills/", tin="mask", focus_in=[540, 900], tout="whip",
            pick_at=w("slash", 0.1), push_at=w("automatically.", -0.3), flip_at=w("Commands", -0.1),
            pops=[{"text": "/review", "at": w("slash", 0.1), "y": 1400}],
            mascot=M(TABS, {"type": "into_folder", "at": w("automatically.", 0.1), "to": [100, 446], "hold": 99},
                     {"type": "out_of_folder", "at": w("Commands", -0.6), "to": [900, 650]}),
            cues=[{"at": 0.6, "action": "keys"}, {"at": w("slash", 0.1), "action": "highlight"}, {"at": w("automatically."), "action": "keys"},
                  {"at": w("Commands"), "action": "whoosh_soft"}, {"at": w("older"), "action": "highlight"}],
            objective="IDE terminal: '/' opens the menu, /review; SKILL.md frontmatter in the editor; commands/ card flips to legacy"),
 "s8": dict(kind="agents", file=".claude/agents/", tin="whip", tout="push",
            mascot=M((900, 650)),
            cues=[{"at": w("subagents"), "action": "highlight"}, {"at": w("tools."), "action": "highlight"}],
            objective="Full-screen node graph: two subagents with their own tools report back"),
 "s9": dict(kind="ide_hooks", file=".claude/hooks/", tin="push", pad_end=0.6,
            mascot=M(TABS, {"type": "shake", "at": w("block")}),
            cues=[{"at": 0.2, "action": "keys"}, {"at": w("block"), "action": "thud"}, {"at": w("block"), "action": "highlight"},
                  {"at": w("run."), "action": "highlight"}],
            objective="IDE: validate-bash.sh, the lifecycle strip, BLOCK on rm -rf (illustrative), npm test allowed"),
 "s10": dict(kind="takeaway_step", step=0, file="my-project/", tin="mask", focus_in=[540, 700], pad_end=0.2,
             mascot=M((930, 450)), cues=[{"at": w("three"), "action": "highlight"}],
             objective="'3 things to remember'"),
 "s11": dict(kind="takeaway_step", step=1, file="my-project/", pad_start=0.15, pad_end=0.2, mascot=M((930, 450)),
             cues=[{"at": w("guidance,"), "action": "highlight"}], objective="Card 1: CLAUDE.md = guidance (book)"),
 "s12": dict(kind="takeaway_step", step=2, file="my-project/", pad_start=0.15, pad_end=0.2, mascot=M((930, 450)),
             cues=[{"at": w("deny"), "action": "highlight"}, {"at": w("hook."), "action": "highlight"}],
             objective="Card 2: Must never happen? deny rule or hook (lock); the opening rm -rf build/ is now denied (illustrative)"),
 "s13": dict(kind="takeaway_step", step=3, file="my-project/", pad_start=0.15, pad_end=3.7, diagram=DIAGRAM,
             diagram_at=w("settings.json.", 0.5), wipe_out=w("settings.json.", 0.5),
             mascot=M((930, 450), {"type": "hop", "at": w("settings.json.", 0.6), "to": PERCH}, {"type": "glasses", "at": w("settings.json.", 1.9)}),
             cues=[{"at": w("CLAUDE.md"), "action": "highlight"}, {"at": w("settings.json.", 0.5), "action": "whoosh_soft"},
                   {"at": w("settings.json.", 1.05), "action": "soft"},
                   {"at": w("settings.json.", 3.1), "action": "soft"}],   # the landing and the shine: no silent 3 s in the hold
             objective="Card 3: Start with CLAUDE.md + settings.json (rocket); wipe into the full diagram; hold 3 s"),
}
scenes = []
for s in script["scenes"]:
    sp = {"id": s["id"], "title": s["title"], "treatment": "motion", "effect": "dev_scene", "transition": "cut",
          "pad_start": 0.1, "pad_end": 0.15, "tier": "hypothesis", "recipes": [], "reason": "A different layout and camera move per line."}
    sp.update(SC[s["id"]])
    if s["id"] == "s1":
        sp["transition"] = "fade"
        sp["pad_end"] = 0.6                              # the explorer finishes expanding before the cut
        sp.update(cover=True, cover_crop=[236, 1524], cover_mascot={"x": 930, "y": 1700, "scale": 4, "glasses_dy": -6})
    scenes.append(sp)

research = json.loads((H / "research.json").read_text(encoding="utf-8"))
for c_ in research["claims"]:
    if c_["id"] == "c14" and "editorial" not in c_["text"]:
        c_["text"] += " Card 2's 'hooks are the strongest' is an editorial judgement: deny rules match command text, while a hook sees the full tool input."
strategy = json.loads((H / "strategy.json").read_text(encoding="utf-8"))
strategy.update(hook="Frame 0: CLAUDE.md says 'Never delete build/' and the terminal shows rm -rf build/; 'Ignored your rule?'",
                narrative_structure="A familiar failure; where each file goes; three takeaways; the full diagram to save.",
                scene_breakdown=[{"title": sp["title"], "treatment": "motion",
                                  "effect": "dev_scene:" + sp["kind"] + (str(sp.get("step", "")) if sp["kind"] == "takeaway_step" else ""),
                                  "seconds": 5.0, "purpose": sp["objective"]} for sp in scenes])

for name, obj in (("script", script), ("board", {"scenes": scenes}), ("research", research), ("strategy", strategy)):
    (H / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(scenes), "scenes;", sum(len(x["text"].split()) for sc in script["scenes"] for x in sc["sentences"]), "words; diagram:", problems or "ok")
