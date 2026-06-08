<#
.SYNOPSIS
  Start ClearPort locally — backend API (:8080) and the web dashboard (:3000).

.DESCRIPTION
  Launches each service in its own PowerShell window so you can watch the logs,
  then opens the dashboard in your browser. Everything runs offline (no keys).

.EXAMPLE
  .\tools\start.ps1
#>
#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

# Pick the backend runner: uv > venv console-script > module.
if (Get-Command uv -ErrorAction SilentlyContinue) {
    $backend = "uv run clearport-api"
} elseif (Test-Path ".\.venv\Scripts\clearport-api.exe") {
    $backend = ".\.venv\Scripts\clearport-api.exe"
} elseif (Test-Path ".\.venv\Scripts\python.exe") {
    $backend = ".\.venv\Scripts\python.exe -m clearport.api.main"
} else {
    throw "No backend environment found. Run .\tools\setup.ps1 first."
}

Write-Host "Starting ClearPort backend → http://localhost:8080  (API docs at /docs)" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root'; $backend"

if (Get-Command npm -ErrorAction SilentlyContinue) {
    if (-not (Test-Path ".\dashboard\node_modules")) {
        Write-Warning "dashboard\node_modules missing — run .\tools\setup.ps1 (or 'cd dashboard; npm install')."
    }
    Write-Host "Starting dashboard → http://localhost:3000" -ForegroundColor Cyan
    $dash = Join-Path $root "dashboard"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$dash'; npm run dev"
    Start-Sleep -Seconds 3
    Start-Process "http://localhost:3000"
} else {
    Write-Warning "npm not found — backend only. Open http://localhost:8080/docs"
}

Write-Host "`nTip: in the dashboard, click '▶ Play full demo' to run the whole storyboard." -ForegroundColor Green
