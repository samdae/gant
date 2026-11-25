[CmdletBinding()]
param([Parameter(Mandatory)][ValidateSet('core','edge')][string]$Role)

$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime = Join-Path $env:LOCALAPPDATA 'TradingAgentsV3'
$port = if ($Role -eq 'core') { 8024 } else { 8025 }
$packages = [regex]::Escape((Join-Path $project 'packages'))
$expected = "tradingagents\.forecast_lab\.shared_view:build_shared_${Role}\s+--factory\s+--host\s+127\.0\.0\.1\s+--port\s+${port}\s+--no-access-log\s+--no-proxy-headers\s+--app-dir\s+`"?" + $packages + '"?\s*$'

function Test-SharedListener {
    $listeners = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
    foreach ($listener in $listeners) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
        if ($listener.LocalAddress -ne '127.0.0.1' -or $proc.Name -ne 'python.exe' -or $proc.CommandLine -notmatch $expected) {
            throw "Port $port belongs to a different listener. Verify and retire the prior service before shared cutover."
        }
    }
    return $listeners.Count -gt 0
}

function Start-ArchiveIfNeeded {
    # The V3 database holds optional time-bounded news, never the shared forecasting schedule.
    $data = Join-Path $runtime 'pgdata'
    $ctl = Join-Path $env:LOCALAPPDATA 'TradingAgentsDeploy/pgsql/bin/pg_ctl.exe'
    if (-not (Test-Path -LiteralPath (Join-Path $data 'PG_VERSION') -PathType Leaf)) {
        throw 'V3 archive cluster is missing.'
    }
    & $ctl status -D $data *> $null
    if ($LASTEXITCODE -eq 0) {
        $info = @(Get-Content -LiteralPath (Join-Path $data 'postmaster.pid') -TotalCount 6)
        if ($info.Count -ne 6 -or $info[3] -ne '55436' -or $info[5] -ne '127.0.0.1') {
            throw 'V3 archive data is running with an unexpected address or port.'
        }
        return
    }
    if (Get-NetTCPConnection -LocalPort 55436 -State Listen -ErrorAction SilentlyContinue) {
        throw 'Archive port is occupied by a different cluster.'
    }
    & $ctl start -w -t 12 -D $data -l (Join-Path $runtime 'logs/postgres.log') -o '-h 127.0.0.1 -p 55436'
    if ($LASTEXITCODE -ne 0) { throw 'Could not start the optional archive.' }
}

$mutex = [Threading.Mutex]::new($false, "Local\TradingAgentsV3Shared$Role")
$locked = $false
try {
    try { $locked = $mutex.WaitOne(30000) } catch [Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { throw 'Another viewer launch is in progress.' }
    if ($Role -eq 'core') {
        try { Start-ArchiveIfNeeded } catch { Write-Warning $_.Exception.Message }
    }
    if (-not (Test-SharedListener)) {
        $python = Join-Path $project '.venv/Scripts/python.exe'
        & $python -I (Join-Path $PSScriptRoot 'spawn-v3-shared-view.py') $Role $runtime
        if ($LASTEXITCODE -ne 0) { throw "Could not spawn shared viewer on $port." }
    }
    for ($i=0; $i -lt 20; $i++) {
        if (Test-SharedListener) {
            try {
                $health = Invoke-RestMethod "http://127.0.0.1:$port/healthz" -TimeoutSec 2
                if ($health.ok -and $health.source -ceq 'v2' -and $health.role -ceq $Role) {
                    Write-Output "Shared $Role viewer ready on $port."
                    return
                }
            } catch {}
        }
        Start-Sleep -Seconds 1
    }
    throw "Shared viewer readiness timed out on $port."
} finally {
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
