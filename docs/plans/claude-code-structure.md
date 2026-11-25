# Claude Code project structure Reel (2026-11-25)

Brief: `prompts/claude-structure-reel.md`. Produced in the studio as **pc5e7848729** (claude-orange, 9:16, 1080p,
am_michael at 1.1, captions off, standard TechHub end slide).

- Facts: every line checked against code.claude.com/docs (claude-directory, memory, settings, hooks, skills, sub-agents,
  mcp) on 2026-11-25; sources in `research.json` and the production's sources.md. Wording narrowed where the docs are
  narrower (.gitignore for CLAUDE.local.md; settings.local.json ignored once Claude Code writes it; pre-tool hooks block;
  "enforced" not "guarantees"; AGENTS.md read when there is no CLAUDE.md). `.claude/hooks/` is the docs' example path.
- Script trimmed 145 -> 126 words (user-approved line 9: "Hooks run scripts around tool calls, and can block unsafe ones
  before they run."). Content 62.5 s + 8.2 s end slide; all final checks pass, including No empty frames.
- New code: `render/tree.py` (project_tree effect, layout check: every arrow ends on its own row's card), `render/mascot.py`
  (the channel's 48x48 sprite split into body and glasses layers, integer scale, nearest-neighbour), claude-orange and
  claude-warm-dark style packs, Archivo Black (OFL), Lucide folder-open/file-json/file-terminal/file-cog/square-terminal.
- Colours adjusted for 4.5:1 on cream: grey #635C55, accent text #9E4528, title band #A44A2C with a #D97757 stripe.
- Gates: the strategy and script gates were held by rules the user's design overrides (no more than two scenes in a row with
  the same treatment: the video is one continuous diagram; the opening is a statement, not a question). The script gate was
  approved through the API; the strategy stage stays "needs you" because the API cannot approve it.
- Files: `board.py` (writes board/script/research), `strategy.py`, `answer_tasks.py`, `preview.py`, `stills.py`,
  `mascot_test.py`, `caption.txt`, `review-stills.png`, `final-frames.png`.
