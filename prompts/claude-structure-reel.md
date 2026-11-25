Make a new 60-second 9:16 Reel for TechHub: "Claude Code project structure, explained".
Studio at http://127.0.0.1:8600 (start it only if not running). Answer all agent tasks yourself.
Audience: senior engineers. Precise, calm, no hype, no emojis. Burned-in captions off.
Standard TechHub end slide (like/share/follow) at the end. Cover on export.

0. FACTS FIRST
Verify every line against the official docs fetched today:
code.claude.com/docs/en/claude-directory, /memory, /settings, /hooks, /skills, /sub-agents, /mcp.
Cite them in sources.md. If a line is unsupported, change the fewest words and tell me.

1. COLOUR: new template "claude-orange" (orange is the dominant colour)
- Background: warm cream #F4F1EA with subtle paper grain.
- Primary: terracotta #D97757 for the title band, arrows, connector lines, card headers and the active row.
- Deep rust #B85C3C for highlights. Soft peach #F6DCCB for card fills.
- Text: charcoal #1F1E1D. Inactive rows: warm grey #9A938B.
- Transitions: a full-screen terracotta wipe, used twice at most.
- Fonts: JetBrains Mono for file names, Inter for cards, a heavy OFL sans for titles (verify licences).
- Contrast at least 4.5:1. Every label at least 30 px.
- Optional logo: if assets/brand/claude-logo.(svg|png) exists, show it small (about 90 px) top-right on a
  cream badge, unmodified. If it is missing, skip it. Never redraw it.

2. MASCOT: animate my pixel sprite assets/brand/clawd-sunglasses.png (48x48)
- If the file is missing, stop and tell me. Do not download or redraw a different character.
- Pixel-art rules:
  - Scale only by integer factors with nearest-neighbour (4x = 192 px; 3x = 144 px for small perches).
  - No smoothing or blur. Keep the original colours.
- Split the sprite into 2 layers using its own pixels:
  - BODY: everything except the sunglasses. Where the glasses were, fill with the sampled body colour
    plus two small dark square eyes in the same pixel style.
  - GLASSES: the sunglasses pixels.
- Signature move "glasses drop" (0.8 s):
  - Glasses are pushed up on the head.
  - The mascot does a tiny blink.
  - The glasses slide down onto the eyes in 2-pixel steps with a small 1-pixel bounce.
  - A tiny white pixel "shine" sweeps across the lenses.
- Idle: a 2-frame bob (1 px up/down every 0.5 s).
- Hop: squash (1 frame) -> arc jump (8-10 frames, ease-out) -> stretch -> squash on landing,
  plus 3-4 pixel dust specks.
- Walk: a 2-frame waddle with a slight tilt when moving sideways.
- Timeline (synced to the script lines below):
  - line 1: drops in from the top, lands bottom-right, glasses drop.
  - line 2: hops onto the top edge of the CLAUDE.md card and sits there.
  - line 3: glasses lift and it peeks left and right ("private"), then the glasses drop again.
  - line 4: waddles along the bottom margin.
  - line 5: jumps beside settings.json and taps it once (the row pulses).
  - line 7: hops into the skills/ folder; the folder opens; it pops back out.
  - line 9: stands next to the hook flow; on "block" it does a quick head-shake and the red block lights.
  - line 10: hops to the centre bottom, final glasses drop with shine.
  - final 3 s: sits calmly beside the full diagram.
  - Hidden during the end slide.
- Safe zones: it must never cover the title, the tree, card text or arrows. Use margins and card tops only.
  At most one big hop every 4-5 s, so it supports the lesson instead of distracting from it.

3. LAYOUT (a project-structure diagram that builds step by step)
- Pinned terracotta title band at top: "Claude Code" (large, cream), "Project Structure" below.
- Left half: a file tree with Lucide icons (ISC) and thin terracotta connector lines.
- Right half: one card per entry, joined to its own row by an arrow. Check that every arrow points to
  the right card.
- Final frame (hold 3 s before the end slide): the full diagram, readable, made to be screenshotted
  and saved.

4. THE CORRECT TREE
  my-project/
    CLAUDE.md
    CLAUDE.local.md
    .mcp.json
    .claude/
      settings.json
      settings.local.json
      rules/       code-style.md, testing.md
      skills/      review/SKILL.md, fix-issue/SKILL.md
      commands/    deploy.md            (tag: "legacy")
      agents/      code-reviewer.md, security-auditor.md
      hooks/       validate-bash.sh     (note: "script, wired up in settings.json")

5. CARDS (2-3 short lines each)
- CLAUDE.md: Project brief loaded at session start. Stack, commands, conventions. Supports @imports.
- CLAUDE.local.md: Your personal notes. Read after CLAUDE.md. Kept out of git.
- .mcp.json: Team-shared MCP servers: GitHub, Jira, databases. Committed with the repo.
- settings.json: Permissions, hooks, env vars, model defaults. Enforced, not advisory.
- settings.local.json: Personal overrides. Git-ignored automatically.
- rules/: Instructions split by topic. Can be scoped to file paths.
- skills/: One folder per skill with SKILL.md. Run with /name, or used automatically when relevant.
- commands/: Single-file prompts. Older form of skills; same /name mechanism.
- agents/: Subagents with their own prompt, tools and model.
- hooks/: Scripts run before or after tool calls. Can block unsafe actions.
Footnote card: "Repo already has AGENTS.md? Claude Code can read it in place of CLAUDE.md."

6. SCRIPT (voice am_michael, speed 1.1). Each line is spoken while its row builds and its card appears.
 1 "Here's every file in a Claude Code project, and what each one actually does."
 2 "CLAUDE.md is the project brief, loaded at the start of every session."
 3 "CLAUDE.local.md holds your personal notes, kept out of git."
 4 "Dot-mcp.json connects outside tools, like GitHub or a database, for the whole team."
 5 "Inside dot-claude: settings.json is enforced: permissions, hooks, environment, model.
    settings.local.json is your private override."
 6 "Rules split instructions by topic, even by file path."
 7 "Skills are reusable workflows, one folder each. Run them with a slash command, or Claude picks
    them up when the task fits. Commands are the older, single-file version."
 8 "Agents are specialised subagents with their own tools."
 9 "Hooks run your scripts before or after a tool call, and can block unsafe actions."
 10 "Remember: CLAUDE.md is guidance. Settings and hooks are guarantees. Most projects only need
    those two files: CLAUDE.md and settings.json."
Pronunciation: "CLAUDE.md" = "Claude dot M D", ".mcp.json" = "dot M C P dot JSON",
".claude" = "dot Claude", "JSON" = "jay-son".

7. MOTION (never static for more than 2 s, no floating decorative shapes)
- Line 1: hook. A terminal types "tree -a", the output prints, then morphs into the styled tree.
- Each row: connector line reveal, icon pops in, row glows orange, arrow draws, card slides in.
  Earlier rows dim.
- Lines 3 and 5: a "git" badge with a strike-through on the .local files.
- Line 7: push into skills/, review/ expands to show SKILL.md frontmatter (name, description),
  pull back. commands/ gets the "legacy" tag.
- Line 9: mini flow: tool call -> validate-bash.sh -> allow (green) / block (red).
- Line 10: everything dims except CLAUDE.md and settings.json, which glow. Then the full diagram
  lights up.
- Parallax, focus frame, stacking cards. Run the empty-frame check.

8. QUALITY GATE
- First render a 4-second mascot test clip on cream: idle -> hop -> glasses drop with shine.
- Render a still of each script line plus the final frame.
- Render a 540x960 preview of lines 1-5.
- Show me all of it and WAIT for my OK.
- Then render 1080p and run all final checks.
- Generate the cover in claude-orange: headline "Claude Code project structure", the tree diagram,
  the mascot at 4x mid glasses-drop, the TechHub badge.
- Draft the post caption with credits at the end:
  "Sprite: Icons8 (icons8.com). Not affiliated with Anthropic."
- Give me the MP4, cover and caption paths. Commit and push.