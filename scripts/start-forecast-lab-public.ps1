[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime = Join-Path $env:LOCALAPPDATA 'TradingAgentsForecastLab'
$logs = Join-Path $runtime 'logs'
$packages = Join-Path $project 'packages'
$expected = '-m\s+uvicorn\s+tradingagents\.forecast_lab\.public_app:app\s+--host\s+127\.0\.0\.1\s+--port\s+8015\s+--no-access-log\s+--no-proxy-headers\s+--app-dir\s+"?' + [regex]::Escape($packages) + '"?\s*$'

function Test-PublicListener {
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort 8015 -ErrorAction SilentlyContinue)
    foreach ($listener in $listeners) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
        if ($listener.LocalAddress -ne '127.0.0.1' -or $proc.Name -ne 'python.exe' -or $proc.CommandLine -notmatch $expected) {
            throw 'Port 8015 is occupied by a different listener. Verify its identity before taking action.'
        }
    }
    return $listeners.Count -gt 0
}

$mutex = [Threading.Mutex]::new($false, 'Local\TradingAgentsForecastLabPublicStart')
$locked = $false
try {
    try { $locked = $mutex.WaitOne(30000) } catch [Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { throw 'Another public service launch is in progress.' }
    if (-not (Test-PublicListener)) {
        New-Item -ItemType Directory -Force -Path $logs | Out-Null
        $python = Join-Path $project '.venv/Scripts/python.exe'
        & $python -I (Join-Path $PSScriptRoot 'spawn-forecast-lab-public.py') $runtime
        if ($LASTEXITCODE -ne 0) { throw "Public viewer startup failed. Check $logs." }
    }
    for ($i = 0; $i -lt 20; $i++) {
        if (Test-PublicListener) {
            try {
                $health = Invoke-RestMethod 'http://127.0.0.1:8015/healthz' -TimeoutSec 2
                if ($health.service -ceq 'forecast-lab-public' -and $health.ok -eq $true) {
                    Write-Output 'Forecast Lab public viewer ready at http://127.0.0.1:8015/'
                    return
                }
            } catch {}
        }
        Start-Sleep -Seconds 1
    }
    throw "Public viewer readiness timed out. Check $logs/public.err.log."
} finally {
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
