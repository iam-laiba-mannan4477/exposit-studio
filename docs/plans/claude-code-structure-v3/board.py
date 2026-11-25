"""TechHub Reel v3, "What happens when you type claude?": one story in clean diagrams (claude-orange-dark, no editor
UI), with the channel's mascot. Script fact-checked 2026-11-25 (two small wording fixes). Writes script.json,
board.json, research.json and strategy.json next to this file."""
import json, sys
from pathlib import Path

H = Path(__file__).parent
V2 = H.parent / "claude-code-structure-v2"
sys.path.insert(0, str(H.parents[2]))
from exposit.render import tree as TR, design as DS, styles  # noqa: E402,F401

THEME = "claude-orange-dark"
D = "https://code.claude.com/docs/en/"
S = lambda text, *claims: {"text": text, "claims": list(claims)}
LINES = [
 ("s1", "Type claude", [S("What actually happens when you type claude in your terminal?", "c20"),
                        S("Before you write a single prompt, it reads a stack of files.", "c20")]),
 ("s2", "CLAUDE.md", [S("First, CLAUDE.md.", "c1"), S("Your project brief: commands, stack, conventions.", "c1"),
                      S("It's loaded into every session.", "c1")]),
 ("s3", "CLAUDE.local.md", [S("Next to it, CLAUDE.local.md: your personal notes, kept out of git via .gitignore.", "c2")]),
 ("s4", "settings.json", [S("Then .claude settings.json.", "c4"),
                          S("This one isn't advice, it's enforced: what Claude may run, and what it never can.", "c4", "c14")]),
 ("s5", ".mcp.json", [S(".mcp.json connects your team's tools, like GitHub or a database.", "c3")]),
 ("s6", "skills and agents", [S("Skills and agents get registered.", "c21"),
                              S("A skill loads in full only when it's needed; an agent works in its own context.", "c21", "c17")]),
 ("s7", "rules", [S("Path-scoped rules wait until Claude reads a matching file.", "c22")]),
 ("s8", "hooks", [S("And hooks fire on events, like before every tool call, where they can block it.", "c10", "c18")]),
 ("s9", "payoff", [S("So: CLAUDE.md guides.", "c12"), S("Settings and hooks enforce.", "c12"), S("Know which file you're writing in.", "c12"),
                   S("Here's the full Claude Code project structure.", "c13"), S("Save it for your next project.", "c13")]),
]
script = {"scenes": [{"id": i, "title": t, "sentences": s, "terms": []} for i, t, s in LINES]}

v2_board = json.loads((V2 / "board.json").read_text(encoding="utf-8"))["scenes"]
DIAGRAM = next(s for s in v2_board if s.get("diagram"))["diagram"]       # the approved dark diagram
DS.set_active(DS.TEMPLATES[THEME])
TR.set_palette(THEME)
problems = TR.check_layout(DIAGRAM)
PERCH = [930.0, TR.layout(DIAGRAM)["cards"]["claude_md"]["y"] - 1]

w = lambda x, off=0.0, occ=1: {"word": x, "offset": off, "occurrence": occ}
M = lambda pos, *acts: {"scale": 3, "pos": list(pos), "acts": list(acts)}
TOPR = [960.0, 352.0]
SC = {
 "s1": dict(kind="st_hook", pops=[{"text": "What happens next?", "at": 1.25, "y": 1250, "size": 76, "hold": 2.9}],
            mascot=M((930, 1500), {"type": "drop_in", "at": 1.6, "to": [930, 1500]}, {"type": "glasses", "at": 2.3}),
            cues=[{"at": 0.3, "action": "keys"}, {"at": 1.0, "action": "highlight"}, {"at": 1.25, "action": "highlight"},
                  {"at": w("stack"), "action": "whoosh_soft"}, {"at": w("files."), "action": "packet"}],
            objective="$ claude types in the centre; Enter ripples; 'What happens next?'; file cards fall into a Context stack"),
 "s2": dict(kind="st_claude_md", tout="push",
            pops=[{"text": "every session", "at": w("every"), "y": 310, "size": 64}],
            mascot=M((930, 1500), {"type": "hop", "at": 0.8, "to": TOPR}),
            cues=[{"at": 0.0, "action": "whoosh_soft"}, {"at": 0.8, "action": "keys"}, {"at": w("brief:"), "action": "highlight"},
                  {"at": w("every"), "action": "highlight"}],
            objective="Match cut: the top card grows into CLAUDE.md, three headings type in; sessions 1-3 load the same card"),
 "s3": dict(kind="st_local", tin="push", wipe_out=True,
            pops=[{"text": "private", "at": w("personal"), "y": 310, "size": 64}],
            mascot=M(TOPR, {"type": "peek", "at": w("personal"), "dur": 2.2}),
            cues=[{"at": 0.0, "action": "whoosh_soft"}, {"at": w("personal"), "action": "highlight"}, {"at": w("git", -0.2), "action": "packet"},
                  {"at": w(".gitignore."), "action": "highlight"}],
            objective="CLAUDE.local.md slides out from behind; git bounces off a 'gitignored' shield"),
 "s4": dict(kind="st_gate", wipe_in=True, tout="whip", shake_at=w("run,", 0.4),
            pops=[{"text": "ENFORCED", "at": w("enforced:"), "y": 520, "size": 88}],
            mascot=M(TOPR, {"type": "hop", "at": w("enforced:", 0.5), "to": [700, 678]}, {"type": "tap", "at": w("enforced:", 1.1), "dir": -1}),
            cues=[{"at": 0.0, "action": "transition"}, {"at": w("enforced:"), "action": "thud"}, {"at": w("run,"), "action": "highlight"},
                  {"at": w("run,", 0.4), "action": "thud"}],
            objective="A gate: npm test and git push pass green; rm -rf build is denied with a shake; ENFORCED stamps"),
 "s5": dict(kind="mcp", hub_only=True, tin="whip", tout="zoom", focus_out=[540, 860],
            mascot=M((930, 420)),
            cues=[{"at": 0.0, "action": "whoosh_soft"}, {"at": w("connects"), "action": "highlight"}, {"at": w("GitHub"), "action": "packet"},
                  {"at": w("database."), "action": "packet"}],
            objective="Hub and spoke: Claude Code to GitHub, Postgres and Jira; data pulses; 'shared with team'"),
 "s6": dict(kind="st_skills_agents", tin="zoom", focus_in=[540, 860], tout="mask",
            pops=[{"text": "only when needed", "at": w("only"), "y": 300, "size": 64}],
            mascot=M((980, 360)),
            cues=[{"at": 0.0, "action": "whoosh_soft"}, {"at": w("registered."), "action": "highlight"}, {"at": w("only"), "action": "highlight"},
                  {"at": w("agent"), "action": "packet"}, {"at": w("context."), "action": "highlight"}],
            objective="Two shelves: skill tiles show name + description, /review opens to its full SKILL.md; agents in their own context"),
 "s7": dict(kind="st_rules", tin="mask", focus_in=[300, 700], tout="push",
            mascot=M((960, 1500)),
            cues=[{"at": 0.0, "action": "whoosh_soft"}, {"at": 0.5, "action": "highlight"}, {"at": w("matching"), "action": "highlight"},
                  {"at": w("file."), "action": "packet"}],
            objective="A rule with paths: src/api/** sleeps on Button.tsx and wakes on users.ts, sliding into Context"),
 "s8": dict(kind="hooks", tin="push", tout="mask", pad_end=0.6,
            mascot=M((960, 760), {"type": "shake", "at": w("block")}),
            push=[{"at": w("block"), "x": 300, "y": 700, "z": 1.06, "hold": 0.9}],
            cues=[{"at": 0.0, "action": "whoosh_soft"}, {"at": 0.9, "action": "keys"}, {"at": w("block"), "action": "thud"},
                  {"at": w("it."), "action": "highlight"}],
            objective="PreToolUse -> tool runs -> PostToolUse; the script runs; BLOCK slams; a safe call passes"),
 "s9": dict(kind="st_payoff", rev=3, tin="mask", focus_in=[540, 800], pad_end=1.6, diagram=DIAGRAM,
            diagram_at=w("in.", 0.3), wipe_out=w("in.", 0.3),
            mascot=M((930, 430), {"type": "hop", "at": w("in.", 0.4), "to": PERCH}, {"type": "glasses", "at": w("project.", 0.3, 2)}),
            cues=[{"at": 0.0, "action": "whoosh_soft"}, {"at": w("guides."), "action": "highlight"}, {"at": w("enforce."), "action": "thud"},
                  {"at": w("in.", 0.3), "action": "whoosh_soft"}, {"at": w("in.", 1.05), "action": "soft"},
                  {"at": w("project.", 0.5, 2), "action": "soft"}, {"at": w("project.", 1.15, 2), "action": "whoosh_soft"}],   # no silent hold
            objective="GUIDES vs ENFORCES, then a wipe into the full dark diagram; CLAUDE.md and settings.json glow; hold 3 s"),
}
scenes = []
for s in script["scenes"]:
    sp = {"id": s["id"], "title": s["title"], "treatment": "motion", "effect": "dev_scene", "transition": "cut",
          "pad_start": 0.1, "pad_end": 0.15, "tier": "hypothesis", "recipes": [], "reason": "One diagram type per step of the story."}
    sp.update(SC[s["id"]])
    if s["id"] == "s1":
        sp["transition"] = "fade"
        sp.update(cover=True, cover_crop=[340, 1300], cover_mascot={"x": 930, "y": 1690, "scale": 4, "glasses_dy": -6})
    scenes.append(sp)

research = json.loads((V2 / "research.json").read_text(encoding="utf-8"))
research["claims"] = [c for c in research["claims"] if c["id"] not in ("c20", "c21", "c22")] + [
 {"id": "c20", "text": "At session start Claude Code loads CLAUDE.md (and CLAUDE.local.md), settings, project MCP servers and the descriptions of skills and subagents.",
  "sources": [{"title": "Memory (read 2026-11-25)", "url": D + "memory", "kind": "primary"}, {"title": "Explore the .claude directory (read 2026-11-25)", "url": D + "claude-directory", "kind": "primary"}], "confidence": "high"},
 {"id": "c21", "text": "Skill descriptions are available from the start; a skill's full content loads only when it is used. Subagents are defined up front and each runs in its own context window.",
  "sources": [{"title": "Extend Claude with skills (read 2026-11-25)", "url": D + "skills", "kind": "primary"}, {"title": "Create custom subagents (read 2026-11-25)", "url": D + "sub-agents", "kind": "primary"}], "confidence": "high"},
 {"id": "c22", "text": "Rules with a paths: field load when Claude reads, writes or edits a matching file.",
  "sources": [{"title": "Explore the .claude directory (read 2026-11-25)", "url": D + "claude-directory", "kind": "primary"}], "confidence": "high"}]
research["open_questions"] = []
research["arrangement"] = "A repository using Claude Code: what Claude Code reads when a session starts, and what loads later (skills in full, path-scoped rules), plus enforced settings and hooks."

strategy = json.loads((V2 / "strategy.json").read_text(encoding="utf-8"))
strategy.update(
    creative_concept="One story: what Claude Code does when it starts, step by step, in clean diagrams; ending on the save-worthy file diagram.",
    hook="Pure black, `$ claude` typed in the centre: what happens next?",
    narrative_structure="Start command; the context stack; each file's job in load order; what loads later; enforcement; the payoff and the diagram.",
    visual_direction="claude-orange-dark diagrams only: file cards, a context stack, a gate, a hub, shelves, a rule that wakes, a hook timeline, guides vs enforces; no editor UI.",
    treatments=[dict(strategy["treatments"][0], name="A. One story in clean diagrams", verdict="Chosen: the user's v3 plan; v2's IDE screens were too busy.")]
               + strategy["treatments"][1:],
    chosen="A. One story in clean diagrams",
    scene_breakdown=[{"title": sp["title"], "treatment": "motion", "effect": "dev_scene:" + sp["kind"], "seconds": 7.0, "purpose": sp["objective"]} for sp in scenes])

for name, obj in (("script", script), ("board", {"scenes": scenes}), ("research", research), ("strategy", strategy)):
    (H / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(scenes), "scenes;", sum(len(x["text"].split()) for sc in script["scenes"] for x in sc["sentences"]), "words; diagram:", problems or "ok")
