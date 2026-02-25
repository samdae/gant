$ErrorActionPreference = "Stop"
Push-Location "$PSScriptRoot\..\.."

# .env.dev 로드
if (Test-Path ".env.dev") {
    Get-Content ".env.dev" | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
    Write-Host "[dev] Loaded .env.dev" -ForegroundColor DarkGray
}

# Dev 포트/DB 오버라이드
$env:POSTGRES_DB = "tradingagents_dev"
$env:POSTGRES_PORT = "5433"
$env:TRADINGAGENTS_CORS_ORIGINS = "http://localhost:5174"

Write-Host "[dev] Starting FastAPI on port 8001..." -ForegroundColor Cyan
uv run uvicorn tradingagents.api.app:app --host 0.0.0.0 --port 8001

Pop-Location
