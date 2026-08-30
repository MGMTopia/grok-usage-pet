param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Enable", "Disable")]
    [string]$Action
)

$ErrorActionPreference = "Stop"
$watchTask = "GrokUsagePetWatch"
$launchTask = "GrokUsagePetLaunch"
$exe = Join-Path $PSScriptRoot "GrokUsagePet.exe"
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew

if (-not (Test-Path $exe)) { throw "missing $exe" }

function Register-LaunchTask {
    $launchAction = New-ScheduledTaskAction -Execute $exe -WorkingDirectory $PSScriptRoot
    Register-ScheduledTask -TaskName $launchTask -Action $launchAction -Principal $principal -Settings $settings -Force | Out-Null
}

Register-LaunchTask

if ($Action -eq "Disable") {
    if (Get-ScheduledTask -TaskName $watchTask -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $watchTask -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $watchTask -Confirm:$false
    }
    Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq "GrokUsagePet.exe" -and $_.CommandLine -match "--watch"
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    return
}

$actionObj = New-ScheduledTaskAction -Execute $exe -Argument "--watch" -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
Register-ScheduledTask -TaskName $watchTask -Action $actionObj -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $watchTask
