$ErrorActionPreference = "Stop"
Push-Location "$PSScriptRoot\..\..\apps\web"

$env:VITE_API_BASE_URL = "http://localhost:8001"

Write-Host "[dev] Starting Vite on port 5174 (API -> localhost:8001)..." -ForegroundColor Cyan
npm run dev -- --port 5174

Pop-Location
