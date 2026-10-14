$ErrorActionPreference = "Stop"
$taskName = "Petehub Daily Data Update"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$commandPath = Join-Path $projectRoot "daily-update.cmd"
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/d /c `"$commandPath`"" -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -Daily -At "03:00"
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -WakeToRun -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 6)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Run the complete Petehub data pipeline every day at 03:00 Asia/Taipei local time." -Force | Out-Null
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName, State
