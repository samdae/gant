[CmdletBinding()]
param(
    [string]$EnvFile = (Join-Path $env:LOCALAPPDATA 'TradingAgentsV3/lab.env')
)

$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime = Join-Path $env:LOCALAPPDATA 'TradingAgentsV3'
$pgData = Join-Path $runtime 'pgdata'
$pgCtl = Join-Path $env:LOCALAPPDATA 'TradingAgentsDeploy/pgsql/bin/pg_ctl.exe'
$pgReady = Join-Path $env:LOCALAPPDATA 'TradingAgentsDeploy/pgsql/bin/pg_isready.exe'
$python = Join-Path $project '.venv/Scripts/python.exe'
$logDir = Join-Path $runtime 'logs'
foreach ($file in @($EnvFile, (Join-Path $runtime 'console.env'), (Join-Path $project 'apps/web/dist/index.html'), $pgCtl, $pgReady, $python, (Join-Path $pgData 'PG_VERSION'))) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Required lab file is missing: $file" }
}
$EnvFile = (Resolve-Path -LiteralPath $EnvFile).Path
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$mutex = [Threading.Mutex]::new($false, 'Local\TradingAgentsV3Start')
$locked = $false
try {
    try { $locked = $mutex.WaitOne(30000) } catch [Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { throw 'Another lab launch is in progress.' }
    & $pgCtl status -D $pgData *> $null
    if ($LASTEXITCODE -ne 0) {
        if (Get-NetTCPConnection -State Listen -LocalPort 55436 -ErrorAction SilentlyContinue) {
            throw 'Port 55436 belongs to another server.'
        }
        & $pgCtl start -w -t 45 -D $pgData -l (Join-Path $logDir 'postgres.log') -o '-h 127.0.0.1 -p 55436'
        if ($LASTEXITCODE -ne 0) { throw 'Research PostgreSQL startup failed.' }
    }
    $pidLines = Get-Content -LiteralPath (Join-Path $pgData 'postmaster.pid')
    if ($pidLines.Count -lt 6 -or $pidLines[3] -ne '55436' -or $pidLines[5] -ne '127.0.0.1') {
        throw 'Research PostgreSQL is not bound to its expected loopback address and port.'
    }
    & $pgReady -h 127.0.0.1 -p 55436 -d forecast_lab_research -t 3 *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Research PostgreSQL is not ready.' }

    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort 8024 -ErrorAction SilentlyContinue)
    if ($listeners.Count) {
        foreach ($listener in $listeners) {
            $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
            if ($listener.LocalAddress -ne '127.0.0.1' -or $proc.CommandLine -notmatch 'tradingagents\.forecast_lab\.app' -or
                 $proc.CommandLine -notmatch 'serve\s+--console' -or
                $proc.CommandLine.IndexOf($EnvFile,[StringComparison]::OrdinalIgnoreCase) -lt 0) {
                throw 'Port 8024 is occupied by another process or the prior standalone lab. Stop the verified lab process before upgrading.'
            }
        }
    } else {
        $env:PYTHONPATH = Join-Path $project 'packages'
        $env:PYTHONUTF8 = '1'
        $arguments = "-m tradingagents.forecast_lab.app --env-file `"$EnvFile`" serve --console"
        Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $runtime -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $logDir 'app.out.log') `
            -RedirectStandardError (Join-Path $logDir 'app.err.log') | Out-Null
    }
    for ($i = 0; $i -lt 40; $i++) {
        try {
            $health = Invoke-RestMethod 'http://127.0.0.1:8024/health' -TimeoutSec 2
            $ready = Invoke-RestMethod 'http://127.0.0.1:8024/ready' -TimeoutSec 2
            if ($health.service -eq 'forecast-lab' -and $ready.ready -and $ready.console) {
                Write-Output 'Forecast Lab ready at http://127.0.0.1:8024/'
                return
            }
        } catch {}
        Start-Sleep -Seconds 1
    }
    throw "Forecast Lab readiness timed out. Check $logDir."
} finally {
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
