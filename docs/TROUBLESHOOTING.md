# Troubleshooting

Start with the self-check. It names the failing part:

```powershell
.\.venv\Scripts\python -m exposit.cli doctor
```

## Installing

**"running scripts is disabled on this system"**
Run the scripts with `powershell -ExecutionPolicy Bypass -File .\install.ps1`. This applies to that run only and changes no setting.

**"Python 3.12 or 3.13 was not found"**
`winget install -e --id Python.Python.3.12`, then **open a new PowerShell window** so PATH updates, and run the installer again. If you have several Pythons, pass one: `.\install.ps1 -Python C:\Path\To\python.exe`.
Python 3.14 is not supported yet, because some packages have no 3.14 build. Python 3.11 is untested.

**pip fails with "No matching distribution" or tries to compile something**
The installer only accepts prebuilt packages (`--only-binary`). This error means the Python is the wrong version or 32-bit. Check with `python -c "import struct,sys;print(sys.version, struct.calcsize('P')*8)"`: it must be 3.12 or 3.13, and 64.

**doctor: `package onnxruntime` or `package skia` PROBLEM, "DLL load failed"**
The Microsoft Visual C++ runtime is missing. Install it and run `doctor` again:
`winget install -e --id Microsoft.VCRedist.2015+.x64`

**Model download fails or "checksum does not match"**
Run `.\.venv\Scripts\python -m exposit.cli models` again; it resumes cleanly. Behind a company proxy, set `HTTPS_PROXY` first. To download by hand, put these two files in `models\`, then run the command again to verify them:
- https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx
- https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin

**Antivirus quarantines `ffmpeg-win64-*.exe`**
It is the FFmpeg build shipped inside the `imageio-ffmpeg` package. Allow it, or install FFmpeg yourself and set `EXPOSIT_FFMPEG=C:\path\to\ffmpeg.exe` in `.env`.

## Starting

**"port 8600 in use"**
Either the studio is already running (`start-exposit.ps1` detects this and just opens the browser), or another program uses the port. Use `.\start-exposit.ps1 -Port 8700` or set `EXPOSIT_PORT` in `.env`.
To find the program using the port: `Get-NetTCPConnection -LocalPort 8600 | Select OwningProcess`.

**The browser shows "can't reach this page" at localhost**
Use `http://127.0.0.1:8600`. Some systems resolve `localhost` to the IPv6 address first, and the studio listens on IPv4.

**The page is blank, or "The web interface has not been built"**
The `web\dist` folder is missing. Run `.\install.ps1 -BuildWeb` (needs Node.js 20+: `winget install -e --id OpenJS.NodeJS.LTS`).

## Producing

**A production sits at "Waiting for the agent"**
With the *Agent bridge* provider that is expected: each role waits for an answer. Open **Renders → Agent tasks** and paste an answer, or have a coding agent answer it (see README section 5). The wait ends after `EXPOSIT_LLM_TIMEOUT` seconds (default one hour), and the stage is marked failed. Run it again from the stage's tab.

**"The Researcher returned output that does not match its schema"**
The model's answer did not fit the required shape twice. Small local models do this most. Try again, or use a stronger model.

**"Natural-language edits need an AI provider"**
Settings → AI provider shows the reason (for example, no model name set). Scene edits by controls and the raw specification need no AI.

**Claude Code provider: "the 'claude' command was not found"**
Install Claude Code and sign in, or set `EXPOSIT_CLAUDE_BIN` to its full path in `.env`. Usage counts against your plan's limits.

**A paid provider is refused**
By design: your budget for paid services is $0. Raise it in Settings only if you accept the provider's per-token charges.

**Narration sounds wrong on a term**
Kokoro reads some acronyms and names unusually. Write the term the way it should sound in the script editor (for example "N-G-I-N-X" or "engine-x"). The captions show the script text.

**Rendering is slow, or the laptop gets hot**
Create productions at 720p or 540p for drafts, and plug in the laptop. Only one job runs at a time; the rest wait in the queue (top-right indicator, or **Renders**).

**A job was interrupted (the studio was closed while rendering)**
At the next start it is marked failed. Run the stage again: finished narration and clips are reused, not redone.

**Final checks failed**
**Export** lists the failing check. "Duration" means the narration is too long or short for the target; shorten or lengthen the script. The other checks point to the renderer or audio; send the job log (Renders → Log) with a bug report.

## Scout

**Every source shows an error**
The Scout needs internet access to `api.github.com`, `hn.algolia.com`, `www.youtube.com` and the feed addresses you list. A firewall or proxy may block them. GitHub allows 60 searches an hour without a token; set `EXPOSIT_GITHUB_TOKEN` for more.

**The scheduled task does not run**
Open Task Scheduler and find **Exposit Studio Scout**. It runs only while you are signed in and online. `Start-ScheduledTask -TaskName 'Exposit Studio Scout'` runs it now.

## Reference analysis

**"No transcript"**
Paste a transcript, or install the optional recogniser: `.\.venv\Scripts\python -m pip install -r requirements-optional.txt`. The first use downloads its model from Hugging Face (about 150 MB).

**A continuous animation shows as one long shot**
Shots are split at hard cuts and fades through a dark or flat frame. Dissolves and continuous camera moves are not split.

## Resetting

Your work lives in `data\`. To start completely fresh, stop the studio and rename `data` to `data-old`; a new one is created at the next start. To reinstall packages only, delete `.venv` and run `install.ps1`.
