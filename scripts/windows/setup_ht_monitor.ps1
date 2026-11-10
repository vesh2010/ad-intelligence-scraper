[CmdletBinding()]
param([switch]$InstallSchedule)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$State = Join-Path $Root ".ht-monitor"
$Python = Join-Path $State "venv\Scripts\python.exe"

if ($InstallSchedule -and (Get-TimeZone).Id -ne "India Standard Time") {
    throw "Set Windows time zone to India Standard Time before installing the 08:00/14:00 IST schedule."
}
New-Item -ItemType Directory -Force -Path $State | Out-Null
if (-not (Test-Path $Python)) {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        throw "Install Python 3.12 from python.org (including the Python launcher), then run setup again."
    }
    & py -3.12 -m venv (Join-Path $State "venv")
    if ($LASTEXITCODE -ne 0) { throw "Python 3.12 is required. Install it, then run setup again." }
}
& $Python -m pip install -r (Join-Path $PSScriptRoot "requirements-ht-monitor.txt")
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
& $Python -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw "Chromium installation failed." }

# Verify the actual browser exit before installing any scheduled capture task.
& $Python (Join-Path $Root "scripts\run_hindustan_times_local.py") --check-proxy
if ($LASTEXITCODE -ne 0) {
    throw "Delhi/NCR exit could not be verified. No schedule was installed. Check your connection or VPN."
}

if ($InstallSchedule) {
    $TaskName = "Hindustan Times NCR Screenshot Monitor"
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        throw "A monitor task already exists. Remove it explicitly before replacing its configuration."
    }
    $Runner = Join-Path $PSScriptRoot "run_ht_monitor.ps1"
    $Action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument ('-NoProfile -ExecutionPolicy Bypass -File "' + $Runner + '"') `
        -WorkingDirectory $Root
    $Triggers = @(
        (New-ScheduledTaskTrigger -Daily -At "08:00"),
        (New-ScheduledTaskTrigger -Daily -At "14:00")
    )
    $Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 45) -WakeToRun `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    $User = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $Principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Triggers `
        -Settings $Settings -Principal $Principal | Out-Null
    Write-Host "Scheduled for 08:00 and 14:00 IST. Stay signed in; keep this computer online."
}
Write-Host 'Ready. Run a sample: powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\run_ht_monitor.ps1'
Write-Host "Reports: $Root\screenshots. This does not configure a GitHub-hosted proxy or enable email."
