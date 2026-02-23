$ErrorActionPreference = "Stop"
Push-Location "$PSScriptRoot\..\.."

$env:POSTGRES_USER = "trading"
$env:POSTGRES_PASSWORD = "tradingpass"
$env:POSTGRES_DB = "tradingagents_dev"
$env:POSTGRES_HOST = "localhost"
$env:POSTGRES_PORT = "5433"
$env:TRADINGAGENTS_CORS_ORIGINS = "http://localhost:5174"
$env:TRADINGAGENTS_LOG_LEVEL = if ($env:TRADINGAGENTS_LOG_LEVEL) { $env:TRADINGAGENTS_LOG_LEVEL } else { "INFO" }

Write-Host "[dev] Starting FastAPI on port 8001..." -ForegroundColor Cyan
uv run uvicorn tradingagents.api.app:app --host 0.0.0.0 --port 8001 --reload

Pop-Location
