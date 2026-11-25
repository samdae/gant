[CmdletBinding()]
param(
    [string]$EnvFile = (Join-Path $env:LOCALAPPDATA 'TradingAgentsV3/lab.env')
)

$ErrorActionPreference = 'Stop'
$errors = @()
try { & (Join-Path $PSScriptRoot 'start-forecast-lab-public.ps1') }
catch { $errors += "Public viewer: $($_.Exception.Message)" }
try { & (Join-Path $PSScriptRoot 'start-forecast-lab.ps1') -EnvFile $EnvFile }
catch { $errors += "Private console: $($_.Exception.Message)" }
if ($errors.Count) { throw ($errors -join [Environment]::NewLine) }
