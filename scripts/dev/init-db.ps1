$ErrorActionPreference = "Stop"
Push-Location "$PSScriptRoot\..\.."

$env:POSTGRES_USER = "trading"
$env:POSTGRES_PASSWORD = "tradingpass"
$env:POSTGRES_DB = "tradingagents_dev"
$env:POSTGRES_HOST = "localhost"
$env:POSTGRES_PORT = "5433"

Write-Host "[dev] Initializing DB schema..." -ForegroundColor Cyan
uv run python scripts/init_db.py

Write-Host "[dev] Schema initialization complete" -ForegroundColor Green
Pop-Location
