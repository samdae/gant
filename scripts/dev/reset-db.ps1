$ErrorActionPreference = "Stop"
Push-Location "$PSScriptRoot\..\.."

$env:POSTGRES_USER = "trading"
$env:POSTGRES_PASSWORD = "tradingpass"
$env:POSTGRES_DB = "tradingagents_dev"
$env:POSTGRES_HOST = "localhost"
$env:POSTGRES_PORT = "5433"

Write-Host "[dev] Resetting DB (PostgreSQL + ChromaDB)..." -ForegroundColor Yellow
uv run python scripts/reset_db.py --confirm

Write-Host "[dev] Reset complete" -ForegroundColor Green
Pop-Location
