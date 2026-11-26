# Exposit Studio

A local studio that turns a technical topic into a narrated, captioned, animated explainer video, and lets you edit it scene by scene.

It runs on your laptop at **http://127.0.0.1:8600**. No paid service is needed: narration (Kokoro), animation (a Skia scene renderer) and encoding (FFmpeg) all run on your processor. The AI roles that research, plan and write each video are answered by a model **you** choose: by default a coding agent you already use (for example Claude Code) through the "agent bridge", at no API cost.

The included 60-second sample, *How an HTTP request reaches a Kubernetes app*, is in `examples/http-request-journey/output/`: `video.mp4` (16:9, YouTube) and `video-vertical-9x16.mp4` (9:16, Instagram Reels and YouTube Shorts).

**Formats:** 16:9 landscape and 9:16 vertical. Choose one when you create a production, or switch an existing production on its **Export** tab: only the pictures are re-rendered; the narration and the AI's work are reused, and switching back is instant because the other shape's clips are kept.

---

## 1. Install (Windows PowerShell)

You need **Python 3.12 or 3.13** (64-bit) and about **1.5 GB** of disk. Node.js is *not* needed (the web interface comes prebuilt). These commands work in both Windows PowerShell and PowerShell 7.

1. **Python.** Check with `py --version` or `python --version`. If neither prints 3.12 or 3.13, download the **Windows installer (64-bit)** for Python 3.12 from https://www.python.org/downloads/windows/, tick **"Add python.exe to PATH"** on the first screen, and open a **new** PowerShell window afterwards.
2. **Go to the folder that contains `install.ps1`.** After unzipping it is the inner `exposit-studio` folder; `ls install.ps1` should find the file.
3. **Install:**

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # allows scripts in this window only
.\install.ps1
```

The installer creates `.venv`, installs the packages, downloads the 120 MB narration model and runs a self-check. It finishes with `All checks passed.` If it reports a problem, see [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md). The most likely one on Windows is a missing Visual C++ runtime: install it from https://aka.ms/vs/17/release/vc_redist.x64.exe (Microsoft's official link) and run `.\install.ps1` again.

## 2. Start

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # needed once per new PowerShell window
.\start-exposit.ps1
```

It waits until the studio answers, prints the address, and opens your browser at **http://127.0.0.1:8600** (`http://localhost:8600` also works). Stop it with **Ctrl+C** in that window. Options: `-Port 8700`, `-NoBrowser`.

There is no sign-in: the studio only listens on your own computer.

## 3. First run: check that production works

On **Home**, click **Create from example**. This builds the 60-second sample from prepared role outputs (written by Claude during development and checked by the same schemas and quality gates as a live run). Narration, animation, mixing, encoding and the automated checks all run on your machine. It takes about 4 minutes on 2 cores; the progress shows at the top right and on the **Scenes** tab.

When it finishes, open **Export**: watch the video, read the checks, download the MP4, subtitles and `project.zip`, and click **Approve final video**. Nothing is ever published for you.

## 4. Make your own video

1. **Choose an AI provider** in **Settings** (see section 5). The default, *Agent bridge*, costs nothing.
2. **Home → New production.** Enter the topic. Leave the audience on *Let it decide* and the review mode on *Final only*, or change them.
3. The roles run in order: **Researcher → Creative Director → Storyteller → Visual Planner**, then the **Audio Producer** narrates and the **Animation Producer** renders each scene, and the **Quality Reviewer** checks every stage and the final file.
   - In *Final only* mode, research, script and storyboard pass by themselves when their gates pass, and the production stops at the finished video for your approval.
   - In *Every gate* mode it also stops at the script and the storyboard.
4. Review the **Strategy**: the three treatments compared, the one chosen, and every decision with its reason. **Override** any decision; your choice is kept in the library as a preference.
5. Edit in **Script** (re-narrates only that scene) or **Edit** (timing, transitions, theme, labels, raw specification, reorder, or describe a change in words and accept or discard the proposal). Before anything renders, the studio shows which scenes and files will be rebuilt. **Undo**, **Redo** and **Versions** are at the bottom of the editor.
6. **Export**, check, approve.

## 5. AI providers and cost

| Provider (Settings) | Cost | How it works |
|---|---|---|
| **Agent bridge** (default) | $0 | Each role writes a task to `data\bridge\tasks\`. A coding agent answers it, or you paste an answer under **Renders → Agent tasks**. The production pauses until then. Not unattended. |
| **Claude Code command line** | Your Claude plan | Runs `claude -p` once per role. It uses your plan's usage limits, which are **not** unlimited; if a limit is hit, the stage fails with the message and you run it again later. |
| **OpenAI-compatible** | $0 locally | For Ollama or LM Studio, set the address to `http://127.0.0.1:11434/v1` and a model name. Local addresses count as free. Small local models will produce weaker research and scripts; an 8 GB laptop can only run small ones. |
| **Anthropic API** | Paid, per token | Needs `EXPOSIT_LLM_API_KEY` in `.env` **and** a paid budget above $0 in Settings. At $0 it is refused. |

**Answering the bridge with Claude Code:** open a terminal in the project folder, run `claude`, and say *"Answer the open Exposit tasks."* The repository's `AGENTS.md` (read via `CLAUDE.md`) tells it exactly how: read each task, do the role's work, write one JSON answer to the path in the task, touch nothing else. Any other coding agent can follow the same file.

API keys are only read from `.env`; none is stored in the code, the database or the interface.

## 6. Configuration (`.env`)

Every setting is optional. `install.ps1` creates `.env` from `.env.example`, which documents each one:

| Variable | Default | Purpose |
|---|---|---|
| `EXPOSIT_HOST` / `EXPOSIT_PORT` | `127.0.0.1` / `8600` | Where the studio listens |
| `EXPOSIT_DATA` / `EXPOSIT_MODELS` | `.\data` / `.\models` | Storage folders |
| `EXPOSIT_WIDTH`, `EXPOSIT_HEIGHT`, `EXPOSIT_FPS` | 1920, 1080, 30 | Render size (each production can also use 720p or 540p) |
| `EXPOSIT_X264_PRESET`, `EXPOSIT_X264_CRF` | `veryfast`, `19` | Encoder speed and quality |
| `EXPOSIT_FFMPEG` | bundled | Use your own FFmpeg |
| `EXPOSIT_LLM_API_KEY` | empty | Key for a hosted model provider |
| `EXPOSIT_LLM_TIMEOUT` | 3600 bridge / 600 other | Seconds a role waits for an answer |
| `EXPOSIT_CLAUDE_BIN` | `claude` | Path to Claude Code if not on PATH |
| `EXPOSIT_GITHUB_TOKEN` | empty | Raises the Scout's GitHub limit from 60 searches an hour |
| `EXPOSIT_YOUTUBE_API_KEY` | empty | Free key, only for public view counts in the Scout |
| `EXPOSIT_WHISPER_MODEL` | `base.en` | Speech recognition model for reference videos (optional package) |

## 7. Scout, library, references

- **Scout** collects public signals: GitHub repositories and releases, feeds, YouTube channel uploads and Hacker News. Run it from the Scout page, let it run daily while the studio is open, or register a Windows task that runs it daily even when the studio is closed:
  `.\scripts\register-scout-task.ps1` (add `-Remove` to undo).
  It uses no AI model. Every tool it finds is recorded as *discovered*, with licence, maintenance, hardware, cost and security notes from public metadata. **It never installs or runs anything.**
- **Creative library**: 35 starting items in 11 categories, each with source, date, evidence level (verified / preference / observation / hypothesis / experiment), applicability and confidence.
- **Reference analysis**: upload a video you may use, an image or a transcript. It measures shots (hard cuts and fades), motion, palettes, pauses, loudness and narration pace, and can add those numbers to the library. It does not download from platforms or keep anyone's wording. Transcribing a video's speech is optional: `.\.venv\Scripts\python -m pip install -r requirements-optional.txt`.

## 8. Command line

```powershell
.\.venv\Scripts\python -m exposit.cli doctor        # self-check
.\.venv\Scripts\python -m exposit.cli sample        # build the 60-second sample without the web interface
.\.venv\Scripts\python -m exposit.cli scout         # one Scout run
.\.venv\Scripts\python -m exposit.cli bridge        # list open agent tasks
.\.venv\Scripts\python -m exposit.cli bridge answer <task-id> answer.json
.\.venv\Scripts\python -m exposit.cli check video.mp4   # run the final checks on any MP4
.\.venv\Scripts\python -m exposit.cli models        # (re)download the narration model, checksum-verified
```

## 8a. Templates, treatments and licences

- **Templates** (one per video): `noir-network` (dark, glowing; the default for 9:16 Reels and Shorts), `paper` (light;
  the default for 16:9), `blueprint`, `sketch`, `premium-technical`. Choose one in New production (or let the Creative
  Director choose and say why) and change it later in Export: that re-renders pictures only.
- **Treatments**: iconflow, map, sequence, cards (title or benefits), compare (hit versus miss), stat, kinetic, flow2d,
  isometric, cutaway, chart. `exposit/skills/visual_planner.md` documents each with an example specification.
- **Transitions** per scene: fade, crossfade, slide, push, match cut.
- **Animation styles** (one per video, chosen by the Creative Director with a reason): 14 ready style packs on top of
  the templates: whiteboard, sketchnote, minimal-counter, limited-animation, low-poly-neon, dark-pixel-grunge,
  pixel-art, engraving-print, silent-film, paper-craft, shadow-puppetry, cardboard-diorama, stop-motion-clay and
  hd-pixel-sprite-3d (only with a 3D model scene). Stick figure, paper cut-out puppet and hand puppet theatre are
  planned. Gallery: `python scripts/render_style_gallery.py [--bench]` into `docs/style-packs/`.
- **Motion effects** (2-4 per video): parallax, pinned heading, 3D card zoom, line reveal, marquee, card carousel,
  low-poly 3D models, stacking cards, focus frame and a terminal scroll demo. Gallery and 3 s clips:
  `python scripts/render_motion_gallery.py` into `docs/motion-gallery/`.
- **Variety rule**: the Creative Director sees the last three productions and may not repeat the previous video's
  style-and-effects combination; the strategy gate checks it. TechHub's constants stay the same in every video: the
  cover layout, the end slide, the badge and the narrator voice.
- **Style gallery**: `python scripts/render_gallery.py [--thumbs]` renders every treatment in every template, both
  formats, into `docs/style-gallery/`; `python scripts/combine_references.py` puts it beside the reference images;
  `python scripts/bench_frames.py` measures frame times.
- **Licences** of everything vendored are in `exposit/assets/LICENSES.md` with the licence texts in
  `exposit/assets/licenses/`: Lucide icons (ISC), Kubernetes icons (CC-BY-4.0, with attribution), world map data (Natural Earth via
  world-atlas, public domain / ISC), Inter, JetBrains Mono and Caveat fonts (SIL Open Font License). A test fails if
  any icon file lacks a licence entry.

## 9. Tests

```powershell
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest -m "not slow"   # about 10 seconds
.\.venv\Scripts\python -m pytest                 # about 3 minutes: two complete productions at 540p, edits, undo, references
```

Result on the development machine: **41 passed**. The end-to-end tests drive a complete production through the agent bridge, with a stand-in agent answering each role, then really narrate, render, mix and check it.

## 10. Performance on modest hardware

Measured on the development machine (Linux, 2 virtual CPUs, 8 GB RAM, no GPU) building the 61.6-second sample at 1080p:

| Stage | Time |
|---|---|
| Narration (Kokoro, 6 scenes) | 120 s |
| Rendering (1,847 frames) | 106 s (about 17 frames a second) |
| Join, mix, encode, checks | 13 s |
| **Total** | **239 s** |

The same sample in 9:16 at 1080x1920 took **271 s**.

Peak memory: **520 MB** for the studio, **715 MB** including FFmpeg. With the studio idle, about 150–350 MB. Only one job runs at a time, and the narration model is unloaded before rendering starts.

Your i5-1235U has more cores, so it will probably be faster, but this was **not measured**. Laptop power settings matter: plug in and use "Best performance" while rendering. For quick drafts, choose **720p** or **540p** when creating a production.

## 11. Project layout

```
exposit-studio/
  install.ps1, start-exposit.ps1      Windows install and start
  AGENTS.md, CLAUDE.md                instructions for coding agents (bridge answers, code changes)
  .env.example                        configuration template
  requirements.txt / .lock / -dev / -optional   pinned Python dependencies
  exposit/                            backend (Python)
    app.py          web API and the single job worker
    director.py     pipeline, gates, rebuild planning, undo/redo, versions
    roles.py, skills/*.md, schemas.py   the seven roles: instructions + output schemas
    providers.py    AI provider adapters (bridge, Claude Code CLI, OpenAI-compatible, Anthropic) and the budget guard
    gates.py        quality gates and the script engagement evaluation
    render/engine.py  scene renderer: kinetic type, 2D flow, isometric, cutaway, chart
    tts.py, sound.py  narration, music bed, effects, mixing
    compose.py      joining, muxing, subtitles, final checks
    knowledge.py, seeds/   creative library and tool register
    scout.py        trend and tool discovery
    refs.py         reference analysis
    store.py, config.py, cli.py
  web/src/                            interface (React); web/dist is the built copy the studio serves
  examples/http-request-journey/      the sample: role outputs and output/ (MP4, subtitles, narration, stills, project.zip)
  tests/                              test suite
  scripts/register-scout-task.ps1     daily Scout in Windows Task Scheduler
  deploy/, Dockerfile                 optional server deployment (see docs/DEPLOY-AWS.md)
  docs/                               feature-status register, troubleshooting, AWS deployment
  data/                               created at first start: database, productions, renders (not in the zip)
  models/                             narration model, downloaded by install.ps1
```

Each production is a folder under `data\productions\<id>\` holding plain JSON and media: brief, facts, strategy, script, storyboard, narration, clips, gates, history, versions and exports. The database is an index over these folders.

## 12. Changing the interface

```powershell
# install Node.js LTS from https://nodejs.org/ first
cd web; npm ci; npm run dev     # http://127.0.0.1:5173, with the studio running on 8600
npm run build                   # writes web\dist, which the studio serves
```

## 13. What is built and what is not

See **[docs/FEATURE-STATUS.md](docs/FEATURE-STATUS.md)**: every feature with its status and how it was checked. In short, these are not built: the 1:1 square format, 3D scenes, Urdu narration, split/merge of scenes, publishing, learning from your channel analytics, cloud rendering and a written trend interpretation. Each appears in the interface labelled **Planned**.

Deployment to a server: [docs/DEPLOY-AWS.md](docs/DEPLOY-AWS.md).

## Optional 3D (Blender)
If you install Blender (blender.org), the studio can render up to 2-3 short 3D shots per video (layers, paths, stacks,
networks, devices, a globe) and composite them with sharp 2D labels. Set `BLENDER_PATH` in `.env` if it is not
auto-detected, and check with `python -m exposit.cli doctor`. Without Blender, those scenes render in 2D.
