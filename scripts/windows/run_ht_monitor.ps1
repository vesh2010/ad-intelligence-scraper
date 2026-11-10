[CmdletBinding()]
param([switch]$CheckProxy)

$ErrorActionPreference = "Continue"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Python = Join-Path $Root ".ht-monitor\venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "Run scripts\windows\setup_ht_monitor.ps1 first."
    exit 1
}
$LogDir = Join-Path $Root ".ht-monitor\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir ("run-" + (Get-Date -Format "yyyy-MM-dd-HH-mm-ss") + ".log")
$Arguments = @((Join-Path $Root "scripts\run_hindustan_times_local.py"))
if ($CheckProxy) { $Arguments += "--check-proxy" }
& $Python @Arguments *> $Log
$Code = $LASTEXITCODE
Get-Content $Log
Write-Host "Log saved to $Log"
exit $Code
