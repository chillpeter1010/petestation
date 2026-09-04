$ErrorActionPreference = "Stop"

$taskName = "Petehub Private Site"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptPath = Join-Path $projectRoot "start-private-site.ps1"
$powerShellPath = (Get-Command powershell.exe -ErrorAction Stop).Source
$action = New-ScheduledTaskAction `
    -Execute $powerShellPath `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`"" `
    -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Days 7) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Start the password-protected Petehub site and its localhost.run SSH tunnel after sign-in." `
    -Force | Out-Null

Get-ScheduledTask -TaskName $taskName | Select-Object TaskName, State
