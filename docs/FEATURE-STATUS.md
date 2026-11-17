# Feature-status register

Last updated 17 November 2026. Every line says what was actually checked.

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
| Kinetic typography | Tested | |
| 2D network flow (nodes, arrows, travelling packets, highlights) | Tested | |
| Isometric architecture scene | Tested | |
| Technical cutaway (containers inside containers, code panel, strike-through misconception) | Tested | |
| Charts | Tested | Bar chart; unit test only, not used in the sample |
| UI demonstrations | Partial | Browser address bar with typing, code/config panels. No general UI-screen mock-up component |
| 3D scenes | Planned | Optional. Blender is in the tool register as "watching"; nothing 3D is rendered |
| Word-level cue sync: visuals fire on a spoken word | Tested | Sentence timing is exact (per-sentence synthesis); word timing within a sentence is estimated |
| Captions burned in + SRT and VTT files | Tested | |
| Sound design: generated ambient bed, ducking, blips/whooshes on cues | Tested | Not listened to by a person (see limitations) |
| Transitions: fade, pull-back in, push-in out | Tested | |
| Automated final checks: size, frame rate, duration, black, frozen, silence, clipping, codec, no paid service | Tested | |
| Regenerate only changed scenes; clips cached by content hash | Tested | Undo restores from cache without rendering |
| Show what will be rebuilt before running | Tested | |
| 720p and 540p output | Tested (540p in tests) | |
| 9:16 and 1:1 formats | Planned | Refused with a clear message |
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
