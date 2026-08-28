param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Enable", "Disable")]
    [string]$Action
)

$ErrorActionPreference = "Stop"
$watchTask = "GrokUsagePetWatch"
$launchTask = "GrokUsagePetLaunch"
$pythonw = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\pythonw.exe"
$script = Join-Path $PSScriptRoot "watch_apps.py"
$pet = Join-Path $PSScriptRoot "pet.py"
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew

function Register-LaunchTask {
    $launchAction = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$pet`"" -WorkingDirectory $PSScriptRoot
    Register-ScheduledTask -TaskName $launchTask -Action $launchAction -Principal $principal -Settings $settings -Force | Out-Null
}

Register-LaunchTask

if ($Action -eq "Disable") {
    if (Get-ScheduledTask -TaskName $watchTask -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $watchTask -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $watchTask -Confirm:$false
    }
    Get-CimInstance Win32_Process | Where-Object { $_.Name -eq "pythonw.exe" -and $_.CommandLine -match "watch_apps.py" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    return
}

$actionObj = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`"" -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
Register-ScheduledTask -TaskName $watchTask -Action $actionObj -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $watchTask
