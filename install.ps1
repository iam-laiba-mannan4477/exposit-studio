<#
  Exposit Studio — installer for Windows PowerShell 5.1 and PowerShell 7.

  Run from the project folder (works in Windows PowerShell 5.1 and PowerShell 7):
      Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
      .\install.ps1

  What it does, in order (each step can be re-run safely):
    1. Finds Python 3.12 or 3.13.
    2. Creates a private Python environment in .venv (nothing is installed system-wide).
    3. Installs the pinned Python packages.
    4. Creates .env from .env.example if you do not have one.
    5. Downloads the Kokoro narration model (about 120 MB) and verifies its checksums.
    6. Rebuilds the web interface only if it is missing or you pass -BuildWeb (needs Node.js 20+).
    7. Runs the self-check.

  Options:
    -SkipModels   do not download the narration model
    -BuildWeb     rebuild the web interface from web\src
    -Python PATH  use this python.exe
#>
[CmdletBinding()]
param(
    [switch]$SkipModels,
    [switch]$BuildWeb,
    [string]$Python = ''
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$onWindows = ($PSVersionTable.PSEdition -eq 'Desktop') -or $IsWindows

function Step([string]$text) { Write-Host ''; Write-Host "==> $text" -ForegroundColor Cyan }
function Fail([string]$text) { Write-Host ''; Write-Host "INSTALL STOPPED: $text" -ForegroundColor Red; exit 1 }
function Check([string]$what) { if ($LASTEXITCODE -ne 0) { Fail "$what failed (exit code $LASTEXITCODE). See docs\TROUBLESHOOTING.md." } }

function Get-PyVersion([string]$exe, [string[]]$pre) {
    try {
        $v = & $exe @pre -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0) { return ($v | Select-Object -First 1).Trim() }
    } catch { }
    return $null
}

# ---------------------------------------------------------------- 1. Python
Step 'Looking for Python 3.12 or 3.13'
$pyExe = $null; $pyPre = @()
$supported = @('3.12', '3.13')
if ($Python) {
    $v = Get-PyVersion $Python @()
    if ($supported -notcontains $v) { Fail "$Python is Python $v. Exposit needs 3.12 or 3.13." }
    $pyExe = $Python
} else {
    $tries = @()
    if (Get-Command py -ErrorAction SilentlyContinue) { $tries += , @('py', @('-3.13')); $tries += , @('py', @('-3.12')) }
    foreach ($n in @('python', 'python3')) { if (Get-Command $n -ErrorAction SilentlyContinue) { $tries += , @($n, @()) } }
    foreach ($t in $tries) {
        $v = Get-PyVersion $t[0] $t[1]
        if ($supported -contains $v) { $pyExe = $t[0]; $pyPre = $t[1]; break }
    }
}
if (-not $pyExe) {
    Fail ("Python 3.12 or 3.13 was not found.`n" +
          "  Download the 'Windows installer (64-bit)' for Python 3.12 from https://www.python.org/downloads/windows/`n" +
          "  and tick 'Add python.exe to PATH' on its first screen. Then open a NEW PowerShell window and run install.ps1 again.")
}
Write-Host "    Using: $pyExe $($pyPre -join ' ') (Python $(Get-PyVersion $pyExe $pyPre))"

# ---------------------------------------------------------------- 2. virtual environment
Step 'Creating the private Python environment (.venv)'
if ($onWindows) { $venvPy = Join-Path $PSScriptRoot '.venv\Scripts\python.exe' } else { $venvPy = Join-Path $PSScriptRoot '.venv/bin/python' }
if (-not (Test-Path -LiteralPath $venvPy)) {
    & $pyExe @pyPre -m venv .venv
    Check 'Creating .venv'
} else {
    Write-Host '    .venv already exists; reusing it.'
}

# ---------------------------------------------------------------- 3. packages
Step 'Installing Python packages (first run: a few minutes, about 250 MB)'
& $venvPy -m pip install --disable-pip-version-check --upgrade pip
Check 'Upgrading pip'
if ($onWindows) { $req = 'requirements.lock' } else { $req = 'requirements.txt' }
& $venvPy -m pip install --disable-pip-version-check --only-binary=:all: -r $req
Check "Installing $req"

# ---------------------------------------------------------------- 4. .env
Step 'Configuration'
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
    Write-Host '    Created .env from .env.example. Nothing in it is required.'
} else {
    Write-Host '    .env already exists; left unchanged.'
}

# ---------------------------------------------------------------- 5. narration model
if ($SkipModels) {
    Step 'Skipping the narration model download (-SkipModels). Narration will not work until you run:  .\.venv\Scripts\python -m exposit.cli models'
} else {
    Step 'Downloading the narration model (Kokoro, about 120 MB)'
    & $venvPy -m exposit.cli models
    Check 'Downloading the narration model'
}

# ---------------------------------------------------------------- 6. web interface
$dist = Join-Path $PSScriptRoot 'web\dist\index.html'
if ($BuildWeb -or -not (Test-Path -LiteralPath $dist)) {
    Step 'Building the web interface'
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        Fail "The web interface needs building and Node.js was not found. Install the LTS version from https://nodejs.org/ and run install.ps1 again."
    }
    Push-Location web
    try {
        & npm ci --no-audit --no-fund
        Check 'npm ci'
        & npm run build
        Check 'npm run build'
    } finally { Pop-Location }
} else {
    Step 'Web interface is already built (pass -BuildWeb to rebuild it)'
}

# ---------------------------------------------------------------- 7. self-check
Step 'Self-check'
& $venvPy -m exposit.cli doctor
if ($LASTEXITCODE -ne 0) {
    Write-Host ''
    Write-Host 'Installed, but the self-check found a problem (listed above). See docs\TROUBLESHOOTING.md.' -ForegroundColor Yellow
    exit 1
}
Write-Host ''
Write-Host 'Exposit Studio is installed. Start it with:' -ForegroundColor Green
Write-Host '    .\start-exposit.ps1   (in a new window, first run:  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass)'
