# Run under the same Windows account used for Codex login.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path "$PSScriptRoot\..").Path
$deploy = Join-Path $env:LOCALAPPDATA TradingAgentsDeploy
$nginx = Join-Path $deploy nginx-1.30.7
Set-Location $root
& "$deploy\pgsql\bin\pg_ctl.exe" status -D "$deploy\pgdata" | Out-Null
if ($LASTEXITCODE -ne 0) {
    & "$deploy\pgsql\bin\pg_ctl.exe" start -D "$deploy\pgdata" -l "$deploy\postgres.log" -w
    if ($LASTEXITCODE) { throw 'PostgreSQL startup failed' }
}
function Get-ListenerProcess([int]$Port) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener) {
        Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
    }
}

function Assert-ApiProcess($process) {
    $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($process.ParentProcessId)"
    $venv = "$root\.venv\Scripts\python.exe"
    if (($process.ExecutablePath -ne $venv -and $parent.ExecutablePath -ne $venv) -or
        $process.CommandLine -notmatch 'uvicorn apps\.api\.app:app(?:\s|$)') {
        throw "Port 8001 belongs to another application (PID $($process.ProcessId))."
    }
}

$api = Get-ListenerProcess 8001
if ($api) { Assert-ApiProcess $api } else {
    Start-Process "$root\.venv\Scripts\python.exe" -ArgumentList '-m uvicorn apps.api.app:app --env-file .env --host 127.0.0.1 --port 8001' -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardError "$root\logs\windows-api.err" -RedirectStandardOutput "$root\logs\windows-api.out"
}
$deadline = (Get-Date).AddMinutes(2)
do {
    try { $null = Invoke-RestMethod http://127.0.0.1:8001/health -TimeoutSec 3; break }
    catch { if ((Get-Date) -gt $deadline) { throw }; Start-Sleep -Seconds 3 }
} while ($true)
Assert-ApiProcess (Get-ListenerProcess 8001)
$proxy = Get-ListenerProcess 18080
if ($proxy) {
    if ($proxy.ExecutablePath -ne "$nginx\nginx.exe" -or $proxy.CommandLine -notlike "*conf/tradingagents.conf*") {
        throw "Port 18080 belongs to another proxy (PID $($proxy.ProcessId))."
    }
} else {
    Start-Process "$nginx\nginx.exe" -ArgumentList '-c conf/tradingagents.conf' -WorkingDirectory $nginx -WindowStyle Hidden
}
$deadline = (Get-Date).AddSeconds(20)
do {
    try { $null = Invoke-RestMethod http://127.0.0.1:18080/api/health -TimeoutSec 3; break }
    catch { if ((Get-Date) -gt $deadline) { throw }; Start-Sleep -Seconds 1 }
} while ($true)
$connector = Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe'" | Where-Object { $_.ExecutablePath -eq "$deploy\cloudflared.exe" -and $_.CommandLine -like '*tunnel.yml*' }
if (!$connector) {
    Start-Process "$deploy\cloudflared.exe" -ArgumentList "tunnel --config `"$deploy\tunnel.yml`" run" -WorkingDirectory $deploy -WindowStyle Hidden -RedirectStandardError "$deploy\tunnel.err" -RedirectStandardOutput "$deploy\tunnel.out"
}
