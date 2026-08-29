param(
    [string]$PythonExe = "",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$name = "GrokUsagePetKawaii"
$dist = Join-Path $PSScriptRoot "dist\$name"
$out = Join-Path $PSScriptRoot "release\GrokUsagePet-kawaii"
$zip = Join-Path $PSScriptRoot "release\GrokUsagePet-kawaii.zip"
$checksum = "$zip.sha256"

if (-not $PythonExe) {
    $venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    $localPython = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
    if (Test-Path $venvPython) {
        $PythonExe = $venvPython
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $PythonExe = (Get-Command python).Source
    } elseif (Test-Path $localPython) {
        $PythonExe = $localPython
    } else {
        throw "Python 3.12 not found. Pass -PythonExe or create .venv."
    }
}

& $PythonExe -c "import PIL, PyInstaller; print('Pillow', PIL.__version__, 'PyInstaller', PyInstaller.__version__)"
if ($LASTEXITCODE -ne 0) {
    throw "Build dependencies missing. Run: $PythonExe -m pip install -r requirements-build.txt"
}

if (-not $SkipTests) {
    & (Join-Path $PSScriptRoot "run-tests.ps1") -PythonExe $PythonExe
    if ($LASTEXITCODE -ne 0) {
        throw "Tests failed"
    }
}

& $PythonExe -m PyInstaller --noconfirm --clean "GrokUsagePetKawaii.spec"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed"
}

if (-not (Test-Path $dist)) {
    throw "PyInstaller did not produce $dist"
}

$builtExe = Join-Path $dist "$name.exe"
& $builtExe --smoke-test
if ($LASTEXITCODE -ne 0) {
    throw "Frozen executable smoke test failed"
}
& $builtExe --visual-smoke-test
if ($LASTEXITCODE -ne 0) {
    throw "Frozen executable visual smoke test failed"
}

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Path (Split-Path $out) -Force | Out-Null
Copy-Item $dist $out -Recurse
Copy-Item (Join-Path $PSScriptRoot "使用说明.txt") (Join-Path $out "使用说明.txt") -Force
Copy-Item (Join-Path $PSScriptRoot "CHANGELOG.md") (Join-Path $out "CHANGELOG.md") -Force
Copy-Item (Join-Path $PSScriptRoot "NOTICE.md") (Join-Path $out "NOTICE.md") -Force
Copy-Item (Join-Path $PSScriptRoot "pack-kawaii\start_pet.bat") (Join-Path $out "start_pet.bat") -Force
Copy-Item (Join-Path $PSScriptRoot "pack-kawaii\register_watch.ps1") (Join-Path $out "register_watch.ps1") -Force

$assets = Join-Path $out "_internal\assets"
foreach ($need in @("spritesheet.webp", "app.ico", "app.png")) {
    if (-not (Test-Path (Join-Path $assets $need))) {
        throw "pack missing $need"
    }
}
$skinRoot = Join-Path $out "_internal\skins"
foreach ($need in @(
    "megumi-kato\pet.json",
    "megumi-kato\spritesheet.webp",
    "original\pet.json",
    "original\素材说明.txt"
)) {
    if (-not (Test-Path (Join-Path $skinRoot $need))) {
        throw "pack missing skins\$need"
    }
}

$forbidden = @("auth.json", "state.vscdb", "pet_state.json", "usage.json", "usage.txt", "pet.log", "watch.log")
$leaks = Get-ChildItem $out -Recurse -File | Where-Object { $forbidden -contains $_.Name.ToLowerInvariant() }
if ($leaks) {
    throw "pack contains forbidden user data: $($leaks.FullName -join ', ')"
}

if (Test-Path $zip) { Remove-Item $zip -Force }
if (Test-Path $checksum) { Remove-Item $checksum -Force }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($out, $zip, [System.IO.Compression.CompressionLevel]::Optimal, $true)
$zipHash = Get-FileHash $zip -Algorithm SHA256
"$($zipHash.Hash) *$([IO.Path]::GetFileName($zip))" | Set-Content $checksum -Encoding ascii

Write-Host "packed $out"
Write-Host "zip $zip"
$zipHash | Format-Table Path, Hash
Get-Item $checksum | Format-Table Name, Length, LastWriteTime
Get-ChildItem $out | Format-Table Name, Length
Get-Item $zip | Format-Table Name, Length, LastWriteTime
