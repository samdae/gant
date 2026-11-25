[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$EnvFile = (Join-Path $env:LOCALAPPDATA 'TradingAgentsV3/lab.env')
)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = (Resolve-Path (Join-Path $project '.venv/Scripts/python.exe')).Path
$settingsFile = (Resolve-Path -LiteralPath $EnvFile).Path
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$name = 'TradingAgents V3 Issue Collection'
$action = New-ScheduledTaskAction -Execute $python -WorkingDirectory $project -Argument (
    '-m tradingagents.forecast_lab.issue_collector --env-file "{0}"' -f $settingsFile
)
$triggers = @(
    (New-ScheduledTaskTrigger -AtLogOn -User $user),
    (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Hours 4))
)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
if ($PSCmdlet.ShouldProcess($name, 'Register or update current-user issue collection task')) {
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Force | Out-Null
}
