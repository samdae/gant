$ErrorActionPreference = "Stop"
Push-Location "$PSScriptRoot\..\..\apps\web"

# node_modules 없으면 자동 설치
if (-not (Test-Path "node_modules")) {
    Write-Host "[dev] node_modules not found, running npm install..." -ForegroundColor Yellow
    npm install
}

$env:VITE_API_BASE_URL = "http://localhost:8001"

Write-Host "[dev] Starting Vite on port 5174 (API -> localhost:8001)..." -ForegroundColor Cyan
npm run dev -- --port 5174

Pop-Location
