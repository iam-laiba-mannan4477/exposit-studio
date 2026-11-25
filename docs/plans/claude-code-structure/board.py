"""Claude Code project structure Reel (prompts/claude-structure-reel.md): the user's 10-line script, fact-checked
against the docs on 2026-11-25 and trimmed to about 60 s; one project_tree scene per line in claude-orange, with the
channel owner's pixel mascot. Writes script.json, board.json and research.json next to this file."""
import json, sys
from pathlib import Path

H = Path(__file__).parent
sys.path.insert(0, str(H.parents[2]))
from exposit.render import tree as TR, design as DS, styles  # noqa: E402,F401

D = "https://code.claude.com/docs/en/"
THEME = "claude-orange"

TREE = [
    {"id": "root", "name": "my-project/", "depth": 0, "dir": True, "icon": "folder-open", "term": ["."]},
    {"id": "claude_md", "name": "CLAUDE.md", "depth": 1, "icon": "file-text",
     "card": "Project brief loaded at session start. Stack, commands, conventions. Supports @imports."},
    {"id": "local_md", "name": "CLAUDE.local.md", "depth": 1, "icon": "file-text",
     "card": "Your personal notes. Read after CLAUDE.md. Add it to .gitignore."},
    {"id": "mcp", "name": ".mcp.json", "depth": 1, "icon": "file-json",
     "card": "Team-shared MCP servers: GitHub, Jira, databases. Committed with the repo."},
    {"id": "dot_claude", "name": ".claude/", "depth": 1, "dir": True, "icon": "folder-open"},
    {"id": "settings", "name": "settings.json", "depth": 2, "icon": "file-cog",
     "card": "Permissions, hooks, env vars, model defaults. Enforced, not advisory.", "space_after": 16},
    {"id": "settings_local", "name": "settings.local.json", "depth": 2, "icon": "file-cog",
     "card": "Personal overrides. Git-ignored once Claude Code writes it."},
    {"id": "rules", "name": "rules/", "depth": 2, "dir": True, "icon": "folder",
     "card": "Instructions split by topic. Can be scoped to file paths."},
    {"id": "code_style", "name": "code-style.md", "depth": 3, "icon": "file-text"},
    {"id": "testing", "name": "testing.md", "depth": 3, "icon": "file-text"},
    {"id": "skills", "name": "skills/", "depth": 2, "dir": True, "icon": "folder",
     "card": "One folder per skill with SKILL.md. Run with /name, or used automatically when relevant."},
    {"id": "review", "name": "review/SKILL.md", "depth": 3, "icon": "file-text", "term": ["review", "SKILL.md"]},
    {"id": "fix_issue", "name": "fix-issue/SKILL.md", "depth": 3, "icon": "file-text", "term": ["fix-issue", "SKILL.md"]},
    {"id": "commands", "name": "commands/", "depth": 2, "dir": True, "icon": "folder", "tag": "legacy",
     "card": "Single-file prompts. Older form of skills; same /name mechanism."},
    {"id": "deploy", "name": "deploy.md", "depth": 3, "icon": "file-text"},
    {"id": "agents", "name": "agents/", "depth": 2, "dir": True, "icon": "folder",
     "card": "Subagents with their own prompt, tools and model."},
    {"id": "code_reviewer", "name": "code-reviewer.md", "depth": 3, "icon": "file-text"},
    {"id": "security_auditor", "name": "security-auditor.md", "depth": 3, "icon": "file-text"},
    {"id": "hooks", "name": "hooks/", "depth": 2, "dir": True, "icon": "folder",
     "card": "Scripts run before or after tool calls. Pre-tool hooks can block unsafe actions."},
    {"id": "validate", "name": "validate-bash.sh", "depth": 3, "icon": "file-terminal",
     "note": "script, wired up in settings.json"},
]
FOOT = "Repo already has AGENTS.md? Claude Code can read it in place of CLAUDE.md, when there is no CLAUDE.md."

S = lambda text, *claims: {"text": text, "claims": list(claims)}
LINES = [
    ("s1", "Hook", [S("Here are the key files in a Claude Code project, and what each does.", "c13")]),
    ("s2", "CLAUDE.md", [S("CLAUDE.md is the project brief, loaded every session.", "c1")]),
    ("s3", "CLAUDE.local.md", [S("CLAUDE.local.md holds your personal notes; add it to .gitignore.", "c2")]),
    ("s4", ".mcp.json", [S(".mcp.json connects tools like GitHub or a database for the whole team.", "c3")]),
    ("s5", "settings", [S("Inside .claude: settings.json is enforced: permissions, hooks, environment, model.", "c4"),
                        S("settings.local.json is your private override.", "c5")]),
    ("s6", "rules", [S("Rules split instructions by topic, even by file path.", "c6")]),
    ("s7", "skills and commands", [S("Skills are reusable workflows, one folder each.", "c7"),
                                   S("Run them as slash commands, or Claude uses them when the task fits.", "c7"),
                                   S("Commands are the older, single-file version.", "c8")]),
    ("s8", "agents", [S("Agents are subagents with their own tools.", "c9")]),
    ("s9", "hooks", [S("Hooks run scripts around tool calls, and can block unsafe ones before they run.", "c10")]),
    ("s10", "Guidance vs enforced", [S("CLAUDE.md is guidance.", "c12"), S("Settings and hooks are enforced.", "c12"),
                                     S("Start with those two files.", "c12")]),
]
script = {"scenes": [{"id": i, "title": t, "sentences": s, "terms": []} for i, t, s in LINES]}

w = lambda x, occ=1, off=0.0: {"word": x, "occurrence": occ, "offset": off}
BUILD = {
    "s1": [{"rows": ["root"], "at": {"t": 3.1}}],
    "s2": [{"rows": ["claude_md"], "at": w("CLAUDE.md")}],
    "s3": [{"rows": ["local_md"], "at": w("CLAUDE.local.md")}],
    "s4": [{"rows": ["mcp"], "at": w(".mcp.json")}],
    "s5": [{"rows": ["dot_claude", "settings"], "at": w("Inside")}, {"rows": ["settings_local"], "at": w("settings.local.json")}],
    "s6": [{"rows": ["rules", "code_style", "testing"], "at": w("Rules")}],
    "s7": [{"rows": ["skills", "review", "fix_issue"], "at": w("Skills")}, {"rows": ["commands", "deploy"], "at": w("Commands")}],
    "s8": [{"rows": ["agents", "code_reviewer", "security_auditor"], "at": w("Agents")}],
    "s9": [{"rows": ["hooks", "validate"], "at": w("Hooks")}],
    "s10": [],
}

# ---- mascot perches, from the diagram's own layout (world coordinates: the point under the feet)
DS.set_active(DS.TEMPLATES[THEME])
L = TR.layout({"tree": TREE, "footnote": FOOT, "pill": "Project Structure", "lane": True})
R = {r["id"]: r for r in L["rows"]}
C = L["cards"]
LANE_Y = 1878.0
BR = [930.0, LANE_Y]                                       # bottom right, beside the footnote
CARD_TOP = [930.0, C["claude_md"]["y"] - 1]                # on the CLAUDE.md card's top edge
SET_GAP = [445.0, R["settings_local"]["y"] - 26]       # right of settings.json, under its arrow, above settings.local.json
FOLDER = [R["skills"]["x"] + TR.ICON / 2, R["skills"]["y"] + 8]
PANEL_TOP = [965.0, R["hooks"]["y"] - 50 - 14]            # inside the hook-flow panel, bottom right (free space)
MID = [540.0, LANE_Y]
print("settings perch: clear of the arrow by", SET_GAP[1] - 93 - R["settings"]["y"], "px; right of the row text by", 445 - 72 - R["settings"]["end"], "px")
MASCOT = {
    "s1": {"pos": BR, "acts": [{"type": "drop_in", "at": 0.5, "to": BR}, {"type": "glasses", "at": 1.25}]},
    "s2": {"acts": [{"type": "hop", "at": w("brief,", off=0.1), "to": CARD_TOP}]},
    "s3": {"acts": [{"type": "peek", "at": w("personal"), "dur": 2.6}]},
    "s4": {"acts": [{"type": "hop", "at": 0.3, "to": [930.0, LANE_Y]}, {"type": "walk", "at": 1.2, "to": [330.0, LANE_Y], "speed": 170}]},
    "s5": {"acts": [{"type": "hop", "at": w("settings.json", off=0.3), "to": SET_GAP},
                    {"type": "tap", "at": w("settings.json", off=0.95), "row": "settings", "dir": -1}]},
    "s6": {"acts": []},
    "s7": {"acts": [{"type": "into_folder", "at": w("Skills", off=0.25), "to": FOLDER, "row": "skills", "hold": 99},
                    {"type": "out_of_folder", "at": w("Commands", off=-0.5), "to": [330.0, LANE_Y]}]},
    "s8": {"acts": []},
    "s9": {"acts": [{"type": "hop", "at": w("scripts", off=0.6), "to": PANEL_TOP}, {"type": "shake", "at": w("block")}]},
    "s10": {"pos": BR, "acts": [{"type": "hop", "at": 0.7, "to": MID}, {"type": "glasses", "at": 1.15},
                                {"type": "hop", "at": w("files.", off=0.9), "to": BR}]},
}

EXTRA_CUES = {"s1": ["Claude", "files", "does."], "s2": ["brief,", "session."], "s4": ["GitHub", "team."], "s6": ["topic,", "path."],
              "s8": ["tools."], "s10": ["guidance.", "enforced."]}
base = {"treatment": "motion", "effect": "project_tree", "transition": "cut", "tree": TREE, "footnote": FOOT, "lane": True,
        "tree_title": "Claude Code", "pill": "Project Structure", "pad_start": 0.1, "pad_end": 0.05, "tier": "hypothesis", "recipes": []}
scenes, done, pos = [], [], None
for sid, title, _ in LINES:
    sp = dict(base, id=sid, title=title, done=list(done), build=BUILD[sid], phase="build")
    m = dict(MASCOT[sid], scale=3)
    if not m.get("pos"):
        m["pos"] = pos
    sp["mascot"] = m
    moves = [a for a in m["acts"] if "to" in a]
    pos = moves[-1]["to"] if moves else m["pos"]
    if sid == "s1":
        sp.update(phase="hook", pad_start=0.1, transition="fade",
                  hook={"command": "tree -a", "prompt": "~/my-project $", "summary": "8 directories, 13 files", "morph_at": {"t": 2.55}},
                  objective="A terminal runs tree -a; the output morphs into the styled tree", reason="Starts from what engineers already type.")
    sp["_git_done"] = {"s1": [], "s2": [], "s3": [], "s4": ["local_md"], "s5": ["local_md"]}.get(sid, ["local_md", "settings_local"])
    if sid == "s3":
        sp["git_strike"] = [{"row": "local_md", "at": w(".gitignore.")}]
    if sid == "s5":
        sp["git_strike"] = [{"row": "settings_local", "at": w("override.")}]
    if sid == "s4":
        sp["wipe_out"] = True                                # wipe 1 of 2: into .claude/
    if sid == "s5":
        sp["wipe_in"] = True
    if sid == "s7":
        sp["frontmatter"] = {"row": "review", "push": "skills", "at": w("one"), "until": w("Commands"), "file": "review/SKILL.md",
                             "lines": ["---", "name: review", "description: Reviews the diff for bugs and style", "---"]}
        sp["legacy"] = {"row": "commands", "at": w("older,")}
    if sid == "s9":
        sp["hook_flow"] = {"row": "hooks", "at": w("scripts"), "until": 999, "block_at": w("block")}
        sp["pad_end"] = 0.5
        sp["wipe_out"] = True                                # wipe 2 of 2: into the takeaway
    if sid == "s10":
        sp.update(phase="recap", wipe_in=True, recap={"keep": ["claude_md", "settings"], "dim_at": w("CLAUDE.md"),
                                                      "all_at": w("files.", off=0.6)},
                  pad_end=3.7, objective="Everything dims but CLAUDE.md and settings.json; then the full diagram lights up and holds 3 s",
                  reason="The takeaway, then a frame worth saving.",
                  cover=True, cover_crop=[300, 1890], cover_mascot={"x": 935, "y": 1560, "scale": 4, "glasses_dy": -6})
    # every timed change of the diagram and the mascot, as cues (the storyboard gate counts them)
    words = []
    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("at"), dict) and "word" in o["at"]:
                words.append(o["at"]["word"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk([sp.get(k) for k in ("build", "mascot", "frontmatter", "legacy", "git_strike", "hook_flow", "recap", "hook")])
    words += EXTRA_CUES.get(sid, [])
    sp["cues"] = [{"at": {"word": x}, "action": "pulse"} for x in dict.fromkeys(words)]
    sp.setdefault("objective", f"Build the {title} row and its card while the line is spoken")
    sp.setdefault("reason", "One focal action per line: connector, icon, glow, arrow, card.")
    scenes.append(sp)
    for b in BUILD[sid]:
        done += b["rows"]

claims = [
 ("c1", "CLAUDE.md is read at the start of every session; it holds commands, conventions and architecture notes and can import files with @path/to/import.", "memory", "Memory (CLAUDE.md files)"),
 ("c2", "CLAUDE.local.md holds private per-project preferences, is appended after CLAUDE.md, and should be added to .gitignore.", "memory", "Memory (CLAUDE.md files)"),
 ("c3", "A project-scoped .mcp.json is checked into version control so the team shares the same MCP servers (e.g. GitHub, databases; Jira appears as a use case).", "mcp", "Connect Claude Code to tools via MCP"),
 ("c4", ".claude/settings.json holds permissions, hooks, env vars and model defaults; unlike CLAUDE.md these are enforced.", "claude-directory", "Explore the .claude directory"),
 ("c5", ".claude/settings.local.json holds personal overrides and is gitignored when Claude Code saves a setting to it.", "settings", "Claude Code settings"),
 ("c6", ".claude/rules/*.md split instructions by topic and can be scoped to file paths with a `paths` frontmatter field.", "memory", "Memory (rules)"),
 ("c7", "Skills live in .claude/skills/<name>/SKILL.md, are invoked with /skill-name, or used by Claude when it matches the task.", "skills", "Extend Claude with skills"),
 ("c8", "Custom commands (.claude/commands/*.md) have been merged into skills: single-file prompts, same mechanism.", "skills", "Extend Claude with skills"),
 ("c9", "Subagents in .claude/agents/*.md each have their own system prompt, tool access and optionally their own model.", "sub-agents", "Create custom subagents"),
 ("c10", "Hooks run commands before (PreToolUse) or after (PostToolUse) tool calls; a PreToolUse hook can block the call. Hooks are defined in settings files; .claude/hooks/ is the path used in the docs' examples, not a required folder.", "hooks", "Hooks reference"),
 ("c11", "If a repository already has an AGENTS.md, Claude Code can read it in place of a CLAUDE.md (by default only when there is no CLAUDE.md).", "claude-directory", "Explore the .claude directory"),
 ("c12", "Claude treats CLAUDE.md as context, not enforced configuration; settings rules are enforced by the client.", "memory", "Memory"),
 ("c13", "The .claude directory page lists CLAUDE.md, .mcp.json, .claude/settings.json, settings.local.json, rules/, skills/, commands/ and agents/ for a project, among other files.", "claude-directory", "Explore the .claude directory"),
]
research = {"arrangement": "A typical repository using Claude Code: project memory files at the root, team MCP config, and a .claude/ folder with settings, rules, skills, legacy commands, subagents and a hook script.",
            "claims": [{"id": i, "text": t, "sources": [{"title": f"{ti} (read 2026-11-25)", "url": D + pg, "kind": "primary"}], "confidence": "high"}
                       for i, t, pg, ti in claims],
            "model": "", "open_questions": []}
for c in research["claims"]:
    if c["id"] in ("c4", "c10", "c12"):
        c["sources"].append({"title": "Claude Code settings (read 2026-11-25)", "url": D + "settings", "kind": "primary"})

research["model"] = {"components": [{"id": "repo", "kind": "zone", "label": "my-project/"}, {"id": "memory", "kind": "service", "label": "CLAUDE.md, CLAUDE.local.md"},
    {"id": "mcp", "kind": "service", "label": ".mcp.json"}, {"id": "dotclaude", "kind": "zone", "label": ".claude/"},
    {"id": "settings", "kind": "service", "label": "settings.json, settings.local.json"}, {"id": "ext", "kind": "service", "label": "rules, skills, commands, agents, hook scripts"}],
    "links": [["repo", "memory"], ["repo", "mcp"], ["repo", "dotclaude"], ["dotclaude", "settings"], ["dotclaude", "ext"]],
    "steps": [{"n": 1, "text": "At session start Claude reads CLAUDE.md, then CLAUDE.local.md.", "components": ["repo", "memory"]},
              {"n": 2, "text": "Project MCP servers from .mcp.json connect outside tools.", "components": ["mcp"]},
              {"n": 3, "text": "The client enforces settings.json: permissions, hooks, env, model.", "components": ["dotclaude", "settings"]},
              {"n": 4, "text": "Rules, skills, commands, agents and hook scripts extend Claude.", "components": ["ext"]}]}
(H / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1), encoding="utf-8")
(H / "board.json").write_text(json.dumps({"scenes": scenes}, ensure_ascii=False, indent=1), encoding="utf-8")
(H / "research.json").write_text(json.dumps(research, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(scenes), "scenes;", sum(len(x["text"].split()) for sc in script["scenes"] for x in sc["sentences"]), "words;",
      "layout:", TR.check_layout(scenes[-1]) or "ok")
