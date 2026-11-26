[CmdletBinding()]
param([switch]$RegisterAtLogon, [switch]$RunServer)

$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$server = (Resolve-Path (Join-Path $PSScriptRoot 'v4-preview.mjs')).Path
$node = (Get-Command node.exe -CommandType Application | Select-Object -First 1).Source
$name = 'TradingAgents V4 Preview'
$port = 8035
$pointer = Join-Path $env:LOCALAPPDATA 'TradingAgentsV4/web/current'
if (-not (Test-Path -LiteralPath $pointer -PathType Leaf)) { throw 'Publish a v4 build before starting the preview.' }
if ($RunServer) {
    & $node $server serve
    exit $LASTEXITCODE
}

function Test-V4Listener {
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
    if (-not $listeners.Count) { return $false }
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($listeners[0].OwningProcess)"
    $expected = '(?:^|\s)"?' + [regex]::Escape($server) + '"?\s+serve\s*$'
    if ($listeners.Count -ne 1 -or $listeners[0].LocalAddress -ne '127.0.0.1' -or
        $owner.Name -ine 'node.exe' -or $owner.CommandLine -notmatch $expected) {
        throw 'Port 8035 belongs to another process. No changes were made to it.'
    }
    return $true
}

$mutex = [Threading.Mutex]::new($false, 'Local\TradingAgentsV4PreviewStart')
$locked = $false
try {
    try { $locked = $mutex.WaitOne(30000) } catch [Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { throw 'Another v4 launch is in progress.' }
    $listening = Test-V4Listener
    $shell = Join-Path $env:WINDIR 'System32/WindowsPowerShell/v1.0/powershell.exe'
    $argsLine = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -RunServer' -f $PSCommandPath
    $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($task -and ($task.Actions.Count -ne 1 -or $task.Actions[0].Execute -ine $shell -or $task.Actions[0].Arguments -ine $argsLine)) {
        throw 'A task with this name belongs to another launcher. Verify its owner.'
    }
    if ($RegisterAtLogon -and -not $task) {
        $user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        $action = New-ScheduledTaskAction -Execute $shell -Argument $argsLine -WorkingDirectory $project
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
        $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
        $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        $task = Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Principal $principal -Settings $settings
    }
    if (-not $task) { throw 'Use -RegisterAtLogon for the first installation.' }
    if (-not $listening) { Start-ScheduledTask -TaskName $name }
    for ($i = 0; $i -lt 20; $i++) {
        if (Test-V4Listener) {
            try {
                $indexResponse = Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8035/v4/' -TimeoutSec 3
                if ($indexResponse.StatusCode -eq 200 -and $indexResponse.Content.Contains('name="forecast-console-access" content="public-readonly"')) {
                    Write-Output 'GANT v4 public viewer ready at http://127.0.0.1:8035/v4/'
                    return
                }
            } catch {}
        }
        Start-Sleep -Seconds 1
    }
    throw 'The v4 task did not serve its public index on 8035. Check the task result and published release.'
} finally {
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
