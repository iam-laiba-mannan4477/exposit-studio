# Feature-status register

Last updated 17 November 2026 (9:16 vertical added). Every line says what was actually checked.

**Status key.**
- **Tested**: implemented, and an automated test or a recorded manual check exercised it.
- **Not fully tested**: implemented, but some path could not be exercised in the development environment.
- **Partial**: some of the capability exists; the rest is named.
- **Planned**: designed, not built. The interface labels it "Planned".
- **Blocked**: needs access or a service that does not exist or was not available.

"Development environment" means a Linux sandbox with 2 CPUs and 8 GB RAM, Python 3.13, and no outbound access except package registries and GitHub downloads. It was **not** a Windows laptop. See "What was not tested on Windows" at the end.

## Screens (all 13 requested)

| # | Screen | Where | Status | Checked by |
|---|---|---|---|---|
| 1 | Production dashboard | Home | Tested | Screenshot; data from live API |
| 2 | New production | /new | Tested | Screenshot; `POST /api/productions` in tests |
| 3 | Research workspace | Production → Research | Tested | Screenshot; facts, sources, system model, gate; text-document upload |
| 4 | Script editor | Production → Script | Tested | Screenshot; sentence editing re-narrates one scene (test) |
| 5 | Storyboard workspace | Production → Storyboard | Tested | Screenshot; stills per scene, reasons, tier |
| 6 | Creative Strategy workspace | Production → Strategy | Tested | Screenshot; override recorded as preference (test) |
| 7 | Scene production | Production → Scenes | Tested | Screenshot; per-scene clip and narration players |
| 8 | Scene editor | Production → Edit | Tested | Screenshot; edits, undo/redo, versions, reorder, proposals (tests) |
| 9 | Creative intelligence library | Creative library | Tested | Screenshot; add / edit / retire / delete (test) |
| 10 | Reference analysis | Reference analysis | Tested | Transcript, link and video paths (tests; the video test uses the sample MP4) |
| 11 | Tools, skills, plugins, MCP servers | Tools and skills | Tested | Status changes recorded; never installs (test) |
| 12 | Rendering and export | Production → Export, and Renders | Tested | Downloads, checks, approval (tests) |
| 13 | Settings | Settings | Tested | Paid provider refused at $0 budget (test) |

## Seven-role workflow

| Capability | Status | Notes |
|---|---|---|
| Roles as written skills plus a JSON schema each (`exposit/skills/`, `exposit/schemas.py`) | Tested | Output that does not fit the schema is rejected, with one repair attempt (test) |
| Sequential orchestration, one model call at a time | Tested | Single worker thread runs one job at a time |
| Audio Producer as plain code (no model) | Tested | Kokoro narration, generated music bed and effects, loudness normalisation |
| Quality Reviewer: code checks on every gate and on the final video | Tested | Independent model review is optional (Settings) |
| Repair rounds before a failing stage stops for you (0 to 3, Settings) | Tested | Default 1. If the same agent writes and reviews, the review is not truly independent |
| Provider: **Agent bridge** (default, $0) | Tested | Full production driven through it in the end-to-end test, with a stand-in agent answering |
| Provider: **Claude Code command line** (`claude -p`) | Not fully tested | Code written; not run here because the sandbox has no signed-in Claude Code. Uses your plan's limits; not unlimited |
| Provider: **OpenAI-compatible** (Ollama, LM Studio, hosted) | Not fully tested | Code written; no endpoint available here. Local addresses count as free |
| Provider: **Anthropic API** | Not fully tested | Code written; blocked unless the paid budget is above $0 (that refusal is tested) |
| Live AI quality of role answers | Not fully tested | The sample production's role answers were written by Claude during development and checked by the same schemas and gates. A live run's quality depends on the model you connect |

## Creative Director and gates

| Capability | Status |
|---|---|
| Strategy with audience profile, objective, concept, hook, narrative, visual direction, scene breakdown, narration approach, tools, decisions with reasons and evidence tier | Tested |
| At least three treatments compared, one chosen with a verdict | Tested (gate requires three) |
| Override any decision; kept as a "preference" in the library; later stages marked stale | Tested |
| Research, script and storyboard pass automatically when their gates pass ("final only" mode) | Tested |
| "Every gate" mode stops at script and storyboard for approval | Tested |
| Final video always waits for your approval | Tested |
| Engagement evaluation of the script (hook, ending, boring/overloaded/repetitive flags) | Tested (code rules; flags are prompts, not predictions) |
| Library items feed the roles' inputs | Tested (passed in payloads); whether a given model uses them well depends on the model |
| Learning from your own channel's retention | Planned (needs YouTube Analytics sign-in) |

## Video production engine

| Capability | Status | Notes |
|---|---|---|
| Templates as design systems: noir-network, paper, blueprint, sketch, premium-technical (plus midnight-blue, minimal-mono) | Tested | noir-network and paper are polished and reviewed on the style gallery; blueprint and sketch render every treatment and pass the same tests but had no further polish. One template per video, chosen by the Creative Director with a reason, or by you (New production, Export: re-renders pictures only) |
| Phone-first size system: headings 72-88 px, labels 44, body 36, nothing under 30 px; icons 150 px (9:16) / 120 px (16:9); 6-8 px connectors | Tested | Enforced in the font code; tests check every string of every gallery tile for size and for 4.5:1 contrast against the pixels it sits on, and that text never leaves its card |
| Icon flow (badges, connectors with arrowheads, label chips, dashed returns, packets on the real path) | Tested | |
| World map (real lat/lon, great-circle arcs, glowing halftone land on noir-network and blueprint, light-points, legend, stat strip) | Tested | Places are examples unless the facts say otherwise. The stat strip shows a number only when it names the fact behind it |
| Sequence diagram (lifelines, messages, self-loops, activation bars) | Tested | |
| Title and benefit cards | Tested | |
| Hit versus miss (framed middle tier, check and x chips, dashed returns, benefits footer) | Tested | The footer is dropped in 9:16 when the band is too short |
| Stat (one sourced number that counts up) | Tested | |
| Motion effects (10): parallax, pinned heading, 3D card zoom, line-by-line reveal, sideways text, card arc carousel, low-poly 3D models (server rack, cube, globe with Natural Earth land, database), stacking cards, focus frame, terminal scroll demo | Tested | Own software 3D (projected quads and triangles, flat shading, depth sort). Cards on the arc use an affine fit of the projected quad (no true foreshortening) because projective image draws are slow on this CPU renderer. All under 80 ms per frame at 1080p |
| Animation styles, Tier 1 (12): whiteboard, sketchnote, minimal counter story, limited animation (12 fps feel), low-poly neon, dark pixel grunge, pixel art, engraving print, silent film (18 fps feel), paper craft, coloured shadow puppetry, cardboard diorama | Tested | Style packs: palette, fonts, procedural background and card texture, badge style, frame-rate feel, jitter, default effects and a post-process chain. Every ready style passes the 30 px and 4.5:1 text checks on all gallery scenes; all under 55 ms per frame at 1080p. Textures are procedural; fonts are OFL (IM FELL English and Press Start 2P added) |
| Animation styles, Tier 2: stop-motion clay, HD pixel sprite 3D | Tested | Simplified versions: clay is rounded shapes, 12 fps holds, frame jitter and a fingerprint texture; pixel sprite 3D is a pixelated, posterised render |
| Animation styles, Tier 2: stick figure story, paper cut-out puppet, hand puppet theatre | Planned | They need posed, rigged characters; a palette and texture alone would not be honest. Not offered to the AI roles |
| Kinetic typography | Tested | |
| 2D network flow (nodes, arrows, travelling packets, highlights) | Tested | |
| Isometric architecture scene | Tested | Generic: any front component (load balancer, CDN cache, gateway, primary database) sending to members grouped in zones, with topic-specific state labels |
| Technical cutaway (containers inside containers, code panel, strike-through misconception) | Tested | Generic: inside any component (panel, router, row of workers); Kubernetes kinds still work |
| Charts | Tested | Bar chart; unit test only, not used in the sample |
| UI demonstrations | Partial | Browser address bar with typing, code/config panels. No general UI-screen mock-up component |
| 3D scenes | Planned | Optional. Blender is in the tool register as "watching"; nothing 3D is rendered |
| Word-level cue sync: visuals fire on a spoken word | Tested | Sentence timing is exact (per-sentence synthesis); word timing within a sentence is estimated |
| Captions burned in + SRT and VTT files | Tested | |
| Caption style: Phrase (default) or Word highlight (2 to 4 words, large bold, spoken word in the accent colour), 16:9 and 9:16 | Tested | Unit tests on stills; Phrase frames checked byte-identical to the previous engine. Not watched in a full rendered video by a person. Word timing within a sentence is estimated, so the highlight can lead or lag a word slightly. In the Mono theme (white accent) the other words are drawn grey instead |
| Sound design: generated ambient bed, ducking, blips/whooshes on cues | Tested | Not listened to by a person (see limitations) |
| Transitions: fade, crossfade, slide, push, match cut (chosen per scene); camera pull-back in, push-in out | Tested | Rendered inside the incoming scene's opening pause from the previous scene's last frame, so narration timing is unchanged. The match cut carries the whole scene so that the shared element starts where it was (it does not morph one element alone) |
| Motion: draw-on connectors and arcs, spring icons, staggered cards, popping chips, counting numbers, focus (others dim to 35%, active one glows) | Tested | Text is never dimmed |
| Frame time under 80 ms at 1080p | Tested | Every treatment x template x format, after the cache build (slow test and scripts/bench_frames.py) |
| Storyboard gate: unknown icons, templates or transitions fail | Tested | |
| Cover image (cover.png) with every export: brand kicker, production title, first iconflow or cards scene as the visual, small brand badge; 1080x1920 (content within y 240-1680) or 1920x1080 | Tested | Drawn in the video's animation style (textures and pixel steps), with the scene's effects, highlights and step markers left out |
| Creative Director picks one animation style and 2-4 motion effects per video, with the variety rule | Tested | Strategy gate: style known and available, effects known, requirements met, not the previous video's combination. Storyboard gate: unknown effects, planned styles, hd-pixel-sprite-3d without a 3D model scene fail |
| Pronunciation of CI/CD, LLMOps, DevSecOps, AI and IaC | Tested | Spoken forms applied before synthesis; changing the table re-records narration that contains those words |
| End slide (outro) on every video: on/off, spoken lines and on-screen lines in Settings | Tested | Appended at export, not part of the AI script; rendered in the production's template, format, voice and speed with its music, a soft sound per line and the production's transition; held about 1.8 s. Excluded from the script length gate and the duration check, included in the subtitle files. Cached by its own hash, so changing it re-renders only the end slide. Shown locked in the Edit timeline |
| Automated final checks: size, frame rate, duration, black, frozen, silence, clipping, codec, no paid service | Tested | |
| Regenerate only changed scenes; clips cached by content hash | Tested | Undo restores from cache without rendering |
| Show what will be rebuilt before running | Tested | |
| 720p and 540p output | Tested (540p in tests) | |
| 9:16 vertical (Instagram Reels, YouTube Shorts, TikTok) | Tested | Every treatment has its own tall layout (flows top to bottom, zig-zag isometric column, stacked cutaway); content fills y 260-1500, or stops at y 1340 when burned-in captions are on (tested). Full 1080x1920 sample rendered and checked; switching an existing production between 16:9 and 9:16 re-renders pictures only (test). 16:9 output is byte-identical to before |
| 1:1 square | Planned | Refused with a clear message |
| 4K | Not offered | Impractical on the target hardware |
| Cloud rendering | Planned | Optional, paid; off |

## Scene editor

| Capability | Status |
|---|---|
| Preview (whole video / this scene), scene list, timeline with visual, narration, caption, cue and music lanes, playhead, click to seek | Tested (screenshot) |
| Pause before / hold after, animation speed, transitions, theme, heading, labels, raw specification JSON | Tested |
| Reorder scenes | Tested |
| Undo / redo; named versions and restore | Tested |
| Natural-language change: proposal shown, applied only when accepted | Tested (stand-in agent) |
| Split / merge scenes | Planned |
| Colour grading, masking, motion tracking | Not applicable (no filmed footage) |

## Scout

| Capability | Status | Notes |
|---|---|---|
| Collectors: GitHub search, Atom/RSS feeds, YouTube channel feeds, Hacker News | Tested with recorded responses | Live collection **blocked in the sandbox** (GitHub API and HN returned 403 through its proxy); each failure is shown, nothing is invented |
| Licence, maintenance, hardware, cost and security notes for found repositories | Tested | From public metadata only, and labelled so |
| Found tools go to the register as "discovered"; never installed or run | Tested (and a test checks the module has no install/exec path) |
| On-demand run; daily run while the studio is open | Tested (on demand); daily timer not waited for |
| Daily run when the studio is closed (Windows Task Scheduler) | Not fully tested | `scripts/register-scout-task.ps1` parses; not run on Windows |
| Weekly summary (counts and links) | Tested |
| Scout signals passed to the Creative Director (videos from the last 14 days, 10 most-discussed items; titles, counts, URLs) | Tested | Payload and skill rules tested; whether a model uses them well depends on the model. Channel names only for items collected after this change |
| Written trend interpretation | Planned |
| YouTube view counts | Needs your free API key |
| Instagram Reels trends | Blocked: no legitimate automated access for an individual account |
| Other creators' retention | Blocked: private on every platform |

## Reference analysis

| Capability | Status |
|---|---|
| Upload video / image / transcript; record a link without downloading it | Tested |
| Metadata, shot boundaries (hard cuts and fades), representative frames, palettes, motion level per shot, editing rhythm | Tested: on the sample MP4 all five scene changes are found within 0.4 s of the true times |
| Audio pauses and loudness; narration pace from a transcript | Tested |
| Transcription with timestamps (faster-whisper, optional) | Not fully tested: its model download from Hugging Face was blocked in the sandbox |
| Turn measurements into library observations (numbers only, no wording copied) | Tested |
| Animation-style naming, camera-move classification, dissolve and wipe detection | Planned (listed as unsupported in the screen) |

## Installation and operations

| Capability | Status |
|---|---|
| `install.ps1` | Ran end to end under PowerShell 7.5 **on Linux** in a clean copy, including the web build; parses cleanly. Not run on Windows |
| `start-exposit.ps1` | Ran under PowerShell 7.5 on Linux: waits for the health check, prints the address, detects an already running studio. Not run on Windows |
| All Python dependencies available as Windows wheels | Checked: all 39 packages resolve as `win_amd64` wheels for Python 3.12 and 3.13 (no compiler needed) |
| Bundled FFmpeg (imageio-ffmpeg) has every encoder and filter used | Checked; full test suite passed using it |
| `python -m exposit.cli doctor` self-check | Tested |
| Model download with SHA-256 verification | Tested from scratch |
| Docker image and Compose file with HTTPS and a password | Not fully tested: written, not built (Docker Hub blocked in the sandbox) |
| Sign-in to the studio | Not implemented. It listens on 127.0.0.1 only; on a server it must sit behind the password-protected proxy in `deploy/` |

## What was not tested on Windows

Nothing was run on Windows. The risks, and what the scripts do about them:
- **Visual C++ runtime** needed by onnxruntime and Skia. If missing, `doctor` shows the failed import; the fix is in TROUBLESHOOTING.md.
- **Execution policy** blocking scripts: the commands use `-ExecutionPolicy Bypass` for that one run.
- **Fonts and paths**: the renderer loads its own bundled fonts by file path, not from the system.
- **Speed on the i5-1235U**: not measured. See the performance notes in the README.

## Optional 3D shots (Blender)
- Status: **works when Blender is installed by the user**; otherwise every 3D shot renders as its 2D fallback
  (stacking cards built from its labels, or the spec's own "fallback"), with a note in the production log.
- Shot types: layers3d, path3d, stack3d, network3d, device3d, globe3d. EEVEE, 8 samples, 2 threads, capped textures and shadows, no raytracing or volumetrics, the 3D layer at
  720x1280 upscaled under full-resolution labels, a 2.5 GB memory watchdog, one process at a time, a timeout per shot, transparent PNG frames cached by spec hash; labels are drawn in 2D on top.
- External tool, not bundled: Blender (GPL), installed from blender.org. `python -m exposit.cli doctor` checks it.
