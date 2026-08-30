param(
    [string]$PythonExe = "",
    [switch]$SkipTests
)

Write-Warning "pack.ps1 is a compatibility wrapper; use pack-windows.ps1."
& (Join-Path $PSScriptRoot "pack-windows.ps1") -PythonExe $PythonExe -SkipTests:$SkipTests
exit $LASTEXITCODE
