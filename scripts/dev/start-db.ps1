$ErrorActionPreference = "Stop"
Push-Location "$PSScriptRoot\..\.."

Write-Host "[dev] Starting PostgreSQL on port 5433..." -ForegroundColor Cyan
docker compose -f infra/docker-compose.dev.yml up -d

Write-Host "[dev] Waiting for PostgreSQL..."
do {
    Start-Sleep -Seconds 1
    $ready = docker exec tradingagents-postgres-dev pg_isready -U trading -d tradingagents_dev 2>$null
} while ($LASTEXITCODE -ne 0)

Write-Host "[dev] PostgreSQL ready (localhost:5433)" -ForegroundColor Green
Pop-Location
