<#
.SYNOPSIS
  Offline verification: byte-compile everything and run the full test suite.

.DESCRIPTION
  Mirrors the CI gate. Needs no API keys, no network, no Docker.

.EXAMPLE
  .\tools\verify.ps1
#>
#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

Write-Host "1/2  Byte-compiling backend + tests…" -ForegroundColor Cyan
python -m compileall -q clearport tests
if ($LASTEXITCODE -ne 0) { throw "compile failed" }
Write-Host "     COMPILE_OK" -ForegroundColor Green

Write-Host "2/2  Running the test suite (offline, deterministic)…" -ForegroundColor Cyan
if (Get-Command uv -ErrorAction SilentlyContinue) {
    uv run pytest -ra
} elseif (Test-Path ".\.venv\Scripts\python.exe") {
    & .\.venv\Scripts\python.exe -m pytest -ra
} else {
    throw "No environment found. Run .\tools\setup.ps1 first."
}
Write-Host "`nVerification complete." -ForegroundColor Green
