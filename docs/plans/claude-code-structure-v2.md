# Claude Code project structure Reel, v2 (2026-11-25)

Produced in the studio as **p5c0e8dbb85** (claude-orange-dark, 9:16, 1080p, am_michael 1.1, captions off, music off,
standard end slide). v1 is pc5e7848729, untouched. Plan and files: `claude-code-structure-v2/`.

- One `dev_scene` per line (render/devscenes.py): hook terminal and 3D cards, editor + context window, editor/terminal
  split with .gitignore, .mcp.json then hub, deny rule + precedence stack, isometric rules with a paths glob, skill
  menu + SKILL.md + legacy flip, subagent graph, hook timeline with BLOCK, guidance vs enforced, then the full diagram.
- Final checks: all pass (63.5 s + 8.2 s end slide). Gates: script approved through the API (its word-count estimate,
  50.6 s, ignores the spelled-out file names and the 3 s hold); the others passed on their own.
- Sound: generated only (sound.py). The new effect names (keys, thud, whoosh_soft, soft, transition) were missing from
  director.SFX_FOR, so this export plays only the "highlight" blips, including the one that breaks the silent final hold.
  The fix is committed; it takes effect after a studio restart and a re-export (export stage only).
