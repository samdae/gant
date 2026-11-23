$ErrorActionPreference = "Stop"
Push-Location "$PSScriptRoot\..\.."

Write-Host "[dev] Starting PostgreSQL on port 5433..." -ForegroundColor Cyan
. "$PSScriptRoot/environment.ps1"
docker compose --env-file .env.dev -f infra/docker-compose.dev.yml up -d
if ($LASTEXITCODE) { throw "Docker Compose startup failed" }

Write-Host "[dev] Waiting for PostgreSQL..."
$deadline = (Get-Date).AddSeconds(90)
do {
    if ((Get-Date) -gt $deadline) { throw "Development PostgreSQL readiness timed out" }
    Start-Sleep -Seconds 1
    $ready = docker exec tradingagents-postgres-dev pg_isready -U trading -d tradingagents_dev 2>$null
} while ($LASTEXITCODE -ne 0)

Write-Host "[dev] PostgreSQL ready (localhost:5433)" -ForegroundColor Green
Pop-Location
