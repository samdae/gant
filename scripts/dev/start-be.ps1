$ErrorActionPreference = "Stop"
Push-Location "$PSScriptRoot\..\.."

. "$PSScriptRoot/environment.ps1"
$env:TRADINGAGENTS_CORS_ORIGINS = "http://localhost:5174"

Write-Host "[dev] Starting FastAPI on port 8011..." -ForegroundColor Cyan
uv run uvicorn tradingagents.api.app:app --host 127.0.0.1 --port 8011

Pop-Location
