import json
from pathlib import Path
H = Path(__file__).parent
board = json.loads((H / "board.json").read_text(encoding="utf-8"))["scenes"]
secs = {"s1": 4.1, "s2": 4.2, "s3": 5.4, "s4": 6.4, "s5": 10.5, "s6": 3.9, "s7": 10.9, "s8": 2.6, "s9": 5.4, "s10": 9.3}
s = {
 "audience_profile": "Senior engineers who use Claude Code or are evaluating it, and want to know which file in a repository does what, and which ones are enforced.",
 "learning_objective": "Name each project file and folder Claude Code reads (CLAUDE.md, CLAUDE.local.md, .mcp.json, .claude/settings*.json, rules, skills, commands, agents, hook scripts) and tell guidance from enforced configuration.",
 "creative_concept": "One project-structure diagram that builds row by row while each line is spoken, ending on a complete, screenshot-worthy reference card; the channel's pixel mascot guides the eye from the margins.",
 "treatments": [
  {"name": "A. One diagram that builds row by row", "shape": "terminal tree -a morphing into a styled tree; one row, arrow and card per line; recap and a full final frame",
   "engagement": "steady build with a payoff frame worth saving", "teaching_fit": "strong: position in the tree is the lesson", "accuracy_risk": "low: every card is a sourced claim",
   "feasibility": "new project_tree effect", "verdict": "Chosen: the user's layout, and the final frame doubles as a saved reference."},
  {"name": "B. One file per scene, full screen", "shape": "ten separate cards with icons", "engagement": "varied but repetitive", "teaching_fit": "weak: loses where each file lives",
   "accuracy_risk": "low", "feasibility": "existing cards treatment", "verdict": "Rejected: no overview to save."},
  {"name": "C. Live terminal walkthrough", "shape": "scrolling terminal with cat of each file", "engagement": "authentic", "teaching_fit": "medium", "accuracy_risk": "medium: invented file contents",
   "feasibility": "scroll_demo", "verdict": "Rejected: text-heavy on a phone, invents contents."}],
 "chosen": "A. One diagram that builds row by row",
 "hook": "A terminal types tree -a; the real output prints and morphs into the styled tree.",
 "narrative_structure": "Overview; root files (CLAUDE.md, CLAUDE.local.md, .mcp.json); inside .claude (settings, rules, skills, commands, agents, hooks); guidance vs enforced; full diagram held 3 s.",
 "visual_direction": "claude-orange: cream page, terracotta band, arrows and connectors, peach cards, JetBrains Mono file names; the channel's own pixel mascot at integer scale in safe zones.",
 "narration_approach": "Calm, one line per row; file names spoken as written (Claude dot M D, dot M C P dot jay-son).",
 "scene_breakdown": [{"title": sc["title"], "treatment": "motion", "effect": "project_tree", "seconds": secs[sc["id"]], "purpose": sc["objective"]} for sc in board],
 "tools": ["Exposit renderer", "Kokoro voice", "Lucide icons", "Archivo Black, Inter, JetBrains Mono (OFL)", "Channel owner's pixel sprite"],
 "decisions": [
  {"key": "template", "choice": "claude-orange", "reason": "User's explicit choice; grey, accent text and band darkened to reach 4.5:1.", "tier": "preference"},
  {"key": "structure", "choice": "one continuous diagram across 10 scenes joined by cuts", "reason": "User's layout: each line builds its own row and card.", "tier": "preference"},
  {"key": "hook", "choice": "tree -a in a terminal morphing into the diagram", "reason": "Starts from a command engineers know.", "tier": "hypothesis"},
  {"key": "length", "choice": "about 63 s", "reason": "User approved after trimming 145 to 126 words.", "tier": "preference"},
  {"key": "transitions", "choice": "two terracotta wipes (into .claude/ and into the takeaway)", "reason": "User asked for at most two.", "tier": "preference"},
  {"key": "mascot", "choice": "channel's own 48x48 sprite at 3x/4x, nearest-neighbour", "reason": "User's asset; never covers title, tree rows, card text or arrows.", "tier": "preference"}],
 "dropoff": [{"where": "s5 settings (10 s)", "why": "Two files and four terms in one line", "countermeasure": "Wipe into .claude/, mascot taps the row, git badge on the .local file"},
             {"where": "s7 skills (11 s)", "why": "Longest line", "countermeasure": "Camera push into skills/ with the SKILL.md frontmatter, then the legacy tag"}],
 "experiment": "Does a save-worthy final frame lift saves compared with earlier videos?",
 "recipes_used": [],
 "template": "claude-orange",
 "template_reason": "User's explicit choice for this video.",
 "effects": ["project_tree", "focus_frame"],
 "effects_reason": "project_tree builds the diagram; its focus frame walks to each new card."}
(H / "strategy.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok")
