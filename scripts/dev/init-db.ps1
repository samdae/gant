$ErrorActionPreference = "Stop"
Push-Location "$PSScriptRoot\..\.."

. "$PSScriptRoot/environment.ps1"

Write-Host "[dev] Initializing DB schema..." -ForegroundColor Cyan
uv run python scripts/init_db.py
if ($LASTEXITCODE) { throw "Development database command failed" }

Write-Host "[dev] Schema initialization complete" -ForegroundColor Green
Pop-Location
