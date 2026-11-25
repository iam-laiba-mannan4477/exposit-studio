# "What happens when you type claude?" (v3, 2026-11-26)

Produced as **pbcc5ac6862** (claude-orange-dark, 9:16, 1080p, am_michael 1.1, captions off, music off, standard end slide).
v1 (pc5e7848729) and v2 (p5c0e8dbb85) are untouched. Plan and files: `claude-code-structure-v3/`.

- One story in clean diagrams (render/story.py, dev_scene kinds st_*): $ claude and the context stack, CLAUDE.md and
  sessions, CLAUDE.local.md and the gitignored shield, a permissions gate, the MCP hub, skills and agents shelves, a
  path-scoped rule that wakes, the hook timeline, guides vs enforces, then the dark file diagram held 3 s.
- Fact fixes: line 3 "kept out of git via .gitignore"; line 7 "reads" instead of "opens".
- Length: 53.6 s narration, 59.8 s before the end slide; target 60 s. All final checks pass.
- Gates: strategy held by "not the same style and effects as the previous video" (the user chose claude-orange-dark;
  the template override is recorded); script gate approved through the API ("ending returns to the opening").
- The running studio had loaded its scene code before the st_* kinds existed and was not to be restarted, so the
  produce and export stages ran through director.run_pipeline in a separate one-off process (one scene at a time).

## Update 2026-11-26
- S9: the line "Here's the full Claude Code project structure. Save it for your next project." is spoken over the
  diagram, then about 1.5 s of hold with a soft blip and whoosh. Length 62.4 s; target set to 62 s.
- End slide: this production's end slide was already narrated (measured -17 to -21 dB at 60-66 s before the change).
  The code now falls back to the standard narration if the spoken lines are ever empty, and a new final check,
  "End slide is narrated", fails when the end-slide window has no voice-level audio (needs a studio restart to apply
  to renders done by the studio itself).
