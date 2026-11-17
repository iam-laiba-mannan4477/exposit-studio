<#
  Registers a daily Windows scheduled task that runs one Scout collection, even when the studio is closed.
  The task starts a short Python process (no AI model, no server) and exits; it runs as you, only while you are signed in.

      powershell -ExecutionPolicy Bypass -File .\scripts\register-scout-task.ps1            # daily at 09:10
      powershell -ExecutionPolicy Bypass -File .\scripts\register-scout-task.ps1 -At 21:40
      powershell -ExecutionPolicy Bypass -File .\scripts\register-scout-task.ps1 -Remove

  The Scout reads public sources only (GitHub search, release feeds, YouTube channel feeds, Hacker News search).
  It records what it finds; it never installs or runs anything it discovers.
#>
[CmdletBinding()]
param(
    [string]$At = '09:10',
    [switch]$Remove
)
$ErrorActionPreference = 'Stop'
$name = 'Exposit Studio Scout'
$root = Split-Path -Parent $PSScriptRoot

if ($Remove) {
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false
        Write-Host "Removed the scheduled task '$name'."
    } else {
        Write-Host "There is no scheduled task named '$name'."
    }
    exit 0
}

$py = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $py)) { Write-Host 'Run install.ps1 first.' -ForegroundColor Red; exit 1 }

$action = New-ScheduledTaskAction -Execute $py -Argument '-m exposit.cli scout' -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Force `
    -Description 'Exposit Studio: daily collection of public tool and trend signals. Records only; never installs anything.' | Out-Null
Write-Host "Registered '$name': every day at $At. Results appear on the Scout page of the studio."
Write-Host "Run it once now with:  Start-ScheduledTask -TaskName '$name'"
