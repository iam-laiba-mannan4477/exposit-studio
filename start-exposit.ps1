<#
  Exposit Studio — start the studio and open it in your browser.

      Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass; .\start-exposit.ps1

  Options:
    -Port 8700     listen on another port (default 8600, or EXPOSIT_PORT in .env)
    -NoBrowser     do not open the browser
  Stop the studio with Ctrl+C in this window. Rendering jobs that were running are marked as interrupted
  and can be started again; finished work is kept.
#>
[CmdletBinding()]
param(
    [int]$Port = 0,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$onWindows = ($PSVersionTable.PSEdition -eq 'Desktop') -or $IsWindows
if ($onWindows) { $venvPy = Join-Path $PSScriptRoot '.venv\Scripts\python.exe' } else { $venvPy = Join-Path $PSScriptRoot '.venv/bin/python' }
if (-not (Test-Path -LiteralPath $venvPy)) {
    Write-Host 'Exposit is not installed yet. Run:  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass; .\install.ps1' -ForegroundColor Red
    exit 1
}

# Port: -Port, then EXPOSIT_PORT in the environment or .env, then 8600.
if ($Port -gt 0) {
    $env:EXPOSIT_PORT = "$Port"
} elseif (-not $env:EXPOSIT_PORT -and (Test-Path -LiteralPath '.env')) {
    $m = Select-String -LiteralPath '.env' -Pattern '^\s*EXPOSIT_PORT\s*=\s*(\d+)' | Select-Object -First 1
    if ($m) { $Port = [int]$m.Matches[0].Groups[1].Value }
}
if ($Port -le 0) { if ($env:EXPOSIT_PORT) { $Port = [int]$env:EXPOSIT_PORT } else { $Port = 8600 } }
$url = "http://127.0.0.1:$Port"

function Test-Studio {
    try { $h = Invoke-RestMethod -Uri "$url/api/health" -TimeoutSec 2; return [bool]$h.ok } catch { return $false }
}

if (Test-Studio) {
    Write-Host "Exposit Studio is already running at $url"
    if (-not $NoBrowser) { Start-Process $url }
    exit 0
}

Write-Host "Starting Exposit Studio on port $Port ..."
$server = Start-Process -FilePath $venvPy -ArgumentList @('-m', 'exposit.cli', 'serve') -NoNewWindow -PassThru
try {
    $ready = $false
    for ($i = 0; $i -lt 90; $i++) {
        Start-Sleep -Milliseconds 700
        if ($server.HasExited) { break }
        if (Test-Studio) { $ready = $true; break }
    }
    if (-not $ready) {
        if ($server.HasExited) {
            Write-Host "The studio stopped while starting (exit code $($server.ExitCode)). The error is shown above." -ForegroundColor Red
        } else {
            Write-Host "The studio did not answer at $url within 60 seconds." -ForegroundColor Red
        }
        Write-Host 'Run  .\.venv\Scripts\python -m exposit.cli doctor  and see docs\TROUBLESHOOTING.md.'
        exit 1
    }
    Write-Host ''
    Write-Host "  Exposit Studio is running:  $url" -ForegroundColor Green
    Write-Host "  (http://localhost:$Port works too.)  Press Ctrl+C here to stop it."
    Write-Host ''
    if (-not $NoBrowser) { Start-Process $url }
    Wait-Process -Id $server.Id
} finally {
    if (-not $server.HasExited) {
        Write-Host 'Stopping Exposit Studio ...'
        Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
    }
}
