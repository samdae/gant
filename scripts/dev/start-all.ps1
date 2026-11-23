$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Magenta
Write-Host " G-ANT Dev Environment" -ForegroundColor Magenta
Write-Host " DB: 5433 | BE: 8011 | FE: 5174" -ForegroundColor Magenta
Write-Host "============================================" -ForegroundColor Magenta
Write-Host ""

# 1. DB
& "$PSScriptRoot\start-db.ps1"

# 2. Init schema
& "$PSScriptRoot\init-db.ps1"

# 3. BE (background job)
Write-Host ""
Write-Host "[dev] Starting Backend (background)..." -ForegroundColor Cyan
$devDirectory = $PSScriptRoot
$beJob = Start-Job -ScriptBlock {
    & (Join-Path $using:devDirectory start-be.ps1)
}

Start-Sleep -Seconds 3

# 4. FE (foreground)
Write-Host ""
Write-Host "[dev] Starting Frontend..." -ForegroundColor Cyan
try {
    & "$PSScriptRoot\start-fe.ps1"
} finally {
    Write-Host "[dev] Stopping backend..." -ForegroundColor Yellow
    Stop-Job $beJob -ErrorAction SilentlyContinue
    Remove-Job $beJob -ErrorAction SilentlyContinue
}
