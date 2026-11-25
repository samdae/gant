[CmdletBinding()]
param([switch]$CheckOnly)

$ErrorActionPreference = 'Stop'
$deploy = Join-Path $env:LOCALAPPDATA 'TradingAgentsDeploy'
$exe = Join-Path $deploy 'cloudflared.exe'
$config = Join-Path $deploy 'tunnel.yml'

function Get-ArgumentPattern([string]$Value) {
    $literal = [regex]::Escape($Value)
    if ($Value -match '\s') { return '"' + $literal + '"' }
    return '(?:"' + $literal + '"|' + $literal + ')'
}

function Get-Connector {
    $pattern = '^\s*' + (Get-ArgumentPattern $exe) + '\s+tunnel\s+--config\s+' +
        (Get-ArgumentPattern $config) + '\s+run\s*$'
    $instances = @(Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe'" -ErrorAction Stop)
    $exact = @($instances | Where-Object { $_.ExecutablePath -eq $exe -and $_.CommandLine -match $pattern })
    if ($exact.Count -gt 1) { throw 'Multiple exact connectors found. Inspect the existing processes.' }
    foreach ($instance in $instances) {
        if ($exact.Count -and $instance.ProcessId -eq $exact[0].ProcessId) { continue }
        # Fail closed if another process might be using this named tunnel.
        if (-not $instance.CommandLine -or $instance.CommandLine -match [regex]::Escape($config) -or
            $instance.CommandLine -match [regex]::Escape($tunnelId) -or $instance.ExecutablePath -eq $exe) {
            throw 'Another cloudflared invocation needs inspection before starting a connector.'
        }
    }
    if ($exact.Count) { return $exact[0] }
}

function Wait-Registration([int]$ConnectorId) {
    $deadline = [datetime]::UtcNow.AddSeconds(45)
    do {
        if (-not (Get-Process -Id $ConnectorId -ErrorAction SilentlyContinue)) {
            throw 'The connector exited before registering. Inspect its startup logs.'
        }
        $listeners = @(Get-NetTCPConnection -OwningProcess $ConnectorId -State Listen -ErrorAction SilentlyContinue)
        foreach ($listener in $listeners) {
            if ($listener.LocalAddress -eq '127.0.0.1') { $address = '127.0.0.1' }
            elseif ($listener.LocalAddress -eq '::1') { $address = '[::1]' }
            else { continue }
            try {
                $request = [Net.HttpWebRequest]::Create("http://${address}:$($listener.LocalPort)/ready")
                $request.Proxy = $null
                $request.AllowAutoRedirect = $false
                $request.Timeout = 1500
                $response = $request.GetResponse()
                try { if ([int]$response.StatusCode -eq 200) { return } }
                finally { $response.Dispose() }
            } catch [Net.WebException] {
                if ($_.Exception.Response) { $_.Exception.Response.Dispose() }
            }
        }
        Start-Sleep -Milliseconds 750
    } while ([datetime]::UtcNow -lt $deadline)
    throw 'No registered connection confirmed by the connector readiness endpoint.'
}

$mutex = [Threading.Mutex]::new($false, 'Global\TradingAgentsPublicTunnelStarter')
$held = $false
try {
    try { $held = $mutex.WaitOne([TimeSpan]::FromSeconds(90)) }
    catch [Threading.AbandonedMutexException] { $held = $true }
    if (-not $held) { throw 'Timed out waiting for the tunnel starter.' }
    foreach ($file in $exe, $config) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Missing $file" }
    }
    $yaml = Get-Content -LiteralPath $config -Raw
    if ($yaml -notmatch '(?m)^tunnel:\s*([0-9a-fA-F-]{36})\s*$') { throw 'Expected a named tunnel UUID.' }
    $tunnelId = ([guid]$Matches[1]).ToString()
    if ($yaml -notmatch '(?m)^credentials-file:[ \t]*([^\r\n]+)') { throw 'Missing credentials-file setting.' }
    $credential = $Matches[1].Trim().Trim('"').Trim("'")
    if (-not [IO.Path]::IsPathRooted($credential) -or
        -not (Test-Path -LiteralPath $credential -PathType Leaf)) { throw 'Missing tunnel credentials file.' }
    & $exe tunnel --config $config ingress validate
    if ($LASTEXITCODE -ne 0) { throw 'Cloudflare ingress validation failed.' }

    $connector = Get-Connector
    if ($connector) {
        $connectorId = $connector.ProcessId
    } elseif ($CheckOnly) {
        throw 'No exact connector is running. CheckOnly did not start one.'
    } else {
        $logDir = Join-Path $deploy 'public-tunnel-logs'
        [void][IO.Directory]::CreateDirectory($logDir)
        $prefix = Join-Path $logDir ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N'))
        $started = Start-Process -FilePath $exe -ArgumentList ('tunnel --config "' + $config + '" run') `
            -WorkingDirectory $deploy -WindowStyle Hidden -RedirectStandardError "$prefix.err" `
            -RedirectStandardOutput "$prefix.out" -PassThru
        $connectorId = $started.Id
    }
    Wait-Registration $connectorId
    Write-Output "Public tunnel registered (PID $connectorId)."
} finally {
    if ($held) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
