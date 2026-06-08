<#
.SYNOPSIS
  One-time setup for ClearPort — runs fully offline (no API keys, no cloud, no Docker).

.DESCRIPTION
  - Verifies Python 3.12+ and installs backend dependencies (uv if present, else venv+pip).
  - Creates .env (offline defaults; no keys required).
  - Installs the Next.js dashboard dependencies (if Node.js/npm is available).

.EXAMPLE
  .\tools\setup.ps1
#>
#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

Write-Host "ClearPort setup — offline by default (no API keys, no cloud)" -ForegroundColor Cyan
Write-Host "Repo: $root`n"

# 1) Python ------------------------------------------------------------------
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.12+ was not found on PATH. Install it from https://www.python.org/downloads/"
}
$pyVer = (python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))").Trim()
Write-Host "  Python $pyVer detected"
$ok = python -c "import sys; print(1 if sys.version_info[:2] >= (3,12) else 0)"
if ($ok.Trim() -ne "1") { throw "Python 3.12+ is required (found $pyVer)." }

# 2) .env (offline defaults need no keys) ------------------------------------
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  created .env from .env.example (offline defaults)"
} else {
    Write-Host "  .env already exists — left untouched"
}

# 3) Backend dependencies ----------------------------------------------------
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host "`n  Installing backend dependencies via uv…" -ForegroundColor Yellow
    uv sync --extra dev
    Write-Host "  Backend ready (uv). Run tools\start.ps1 to launch." -ForegroundColor Green
} else {
    Write-Host "`n  'uv' not found — using a Python virtual environment + pip…" -ForegroundColor Yellow
    if (-not (Test-Path ".venv")) { python -m venv .venv }
    & .\.venv\Scripts\python.exe -m pip install --upgrade pip
    & .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
    Write-Host "  Backend ready (.venv). Run tools\start.ps1 to launch." -ForegroundColor Green
}

# 4) Dashboard dependencies --------------------------------------------------
if (Get-Command npm -ErrorAction SilentlyContinue) {
    Write-Host "`n  Installing dashboard dependencies via npm…" -ForegroundColor Yellow
    Push-Location dashboard
    if (-not (Test-Path ".env.local")) { Copy-Item ".env.local.example" ".env.local" }
    npm install
    Pop-Location
    Write-Host "  Dashboard ready." -ForegroundColor Green
} else {
    Write-Warning "Node.js/npm not found — the web dashboard will be skipped."
    Write-Warning "Install Node 18+ from https://nodejs.org, then run: cd dashboard; npm install"
    Write-Host "  You can still run the backend API and the console demo (uv run clearport-demo)."
}

Write-Host "`nSetup complete." -ForegroundColor Green
Write-Host "Next steps:"
Write-Host "  .\tools\start.ps1        # start backend (:8080) + dashboard (:3000)"
Write-Host "  .\tools\verify.ps1       # offline compile + full test suite"
Write-Host "  uv run clearport-demo    # narrated console demo (no UI needed)"
