param(
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not $PythonExe) {
    $venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    $localPython = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
    if (Test-Path $venvPython) {
        $PythonExe = $venvPython
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 -m unittest discover -s tests -v
        exit $LASTEXITCODE
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $PythonExe = (Get-Command python).Source
    } elseif (Test-Path $localPython) {
        $PythonExe = $localPython
    } else {
        throw "Python 3.12 not found. Pass -PythonExe or create .venv."
    }
}

& $PythonExe -m unittest discover -s tests -v
exit $LASTEXITCODE
