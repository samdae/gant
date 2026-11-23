$ErrorActionPreference = "Stop"
Push-Location "$PSScriptRoot\..\.."

. "$PSScriptRoot/environment.ps1"

Write-Host "[dev] Resetting DB (PostgreSQL + ChromaDB)..." -ForegroundColor Yellow
uv run python scripts/reset_db.py --confirm
if ($LASTEXITCODE) { throw "Development database command failed" }

Write-Host "[dev] Reset complete" -ForegroundColor Green
Pop-Location
