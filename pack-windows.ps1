param(
    [string]$PythonExe = "",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$version = (Get-Content (Join-Path $PSScriptRoot "VERSION") -Raw).Trim()
$name = "GrokUsagePet"
$artifactName = "$name-v$version-Windows-x64"
$dist = Join-Path $PSScriptRoot "dist\$name"
$out = Join-Path $PSScriptRoot "release\$artifactName"
$zip = Join-Path $PSScriptRoot "release\$artifactName.zip"
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
    if ($LASTEXITCODE -ne 0) { throw "Tests failed" }
}

& $PythonExe -m PyInstaller --noconfirm --clean "GrokUsagePet.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
if (-not (Test-Path $dist)) { throw "PyInstaller did not produce $dist" }

$builtExe = Join-Path $dist "$name.exe"
& $builtExe --smoke-test
if ($LASTEXITCODE -ne 0) { throw "Frozen executable smoke test failed" }
& $builtExe --visual-smoke-test
if ($LASTEXITCODE -ne 0) { throw "Frozen executable visual smoke test failed" }

if (Test-Path $out) { Remove-Item -LiteralPath $out -Recurse -Force }
New-Item -ItemType Directory -Path (Split-Path $out) -Force | Out-Null
Copy-Item -LiteralPath $dist -Destination $out -Recurse
foreach ($file in @("使用说明.txt", "CHANGELOG.md", "LICENSE", "NOTICE.md", "ASSETS_NOTICE.md", "SECURITY.md", "THIRD_PARTY_NOTICES.md")) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination (Join-Path $out $file) -Force
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "packaging\windows\start_pet.bat") -Destination (Join-Path $out "start_pet.bat") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "packaging\windows\register_watch.ps1") -Destination (Join-Path $out "register_watch.ps1") -Force

$thirdPartyDir = Join-Path $out "THIRD_PARTY_LICENSES"
New-Item -ItemType Directory -Path $thirdPartyDir -Force | Out-Null
$pythonRoot = (& $PythonExe -c "import sys; print(sys.base_prefix)").Trim()
if ($LASTEXITCODE -ne 0 -or -not $pythonRoot) { throw "could not locate Python base prefix" }
$pythonLicense = Join-Path $pythonRoot "LICENSE.txt"
$packageLicenseCode = @'
import importlib.metadata as metadata
import sys

dist = metadata.distribution(sys.argv[1])
candidates = [
    item for item in (dist.files or [])
    if item.name.lower() in {"license", "license.txt", "copying", "copying.txt"}
    and "licenses" in str(item).lower()
]
if not candidates:
    raise SystemExit(f"license file not found for {sys.argv[1]}")
print(dist.locate_file(candidates[0]))
'@
$pillowLicense = (& $PythonExe -c $packageLicenseCode "Pillow").Trim()
if ($LASTEXITCODE -ne 0 -or -not $pillowLicense) { throw "could not locate Pillow license" }
$pyInstallerLicense = (& $PythonExe -c $packageLicenseCode "PyInstaller").Trim()
if ($LASTEXITCODE -ne 0 -or -not $pyInstallerLicense) { throw "could not locate PyInstaller license" }
$tclTkLicense = Get-ChildItem -LiteralPath (Join-Path $pythonRoot "tcl") -Filter "license.terms" -Recurse -File | Select-Object -First 1
if (-not (Test-Path $pythonLicense)) { throw "could not locate Python license" }
if (-not $tclTkLicense) { throw "could not locate Tcl/Tk license" }
Copy-Item -LiteralPath $pythonLicense -Destination (Join-Path $thirdPartyDir "PYTHON_LICENSE.txt") -Force
Copy-Item -LiteralPath $pillowLicense -Destination (Join-Path $thirdPartyDir "PILLOW_LICENSE.txt") -Force
Copy-Item -LiteralPath $pyInstallerLicense -Destination (Join-Path $thirdPartyDir "PYINSTALLER_COPYING.txt") -Force
Copy-Item -LiteralPath $tclTkLicense.FullName -Destination (Join-Path $thirdPartyDir "TCL_TK_LICENSE.txt") -Force

$skinRoot = Join-Path $out "_internal\skins"
foreach ($need in @(
    "original\pet.json",
    "original\spritesheet.webp",
    "original\app.ico",
    "original\app.png",
    "megumi-kato\pet.json",
    "megumi-kato\spritesheet.webp"
)) {
    if (-not (Test-Path (Join-Path $skinRoot $need))) { throw "pack missing skins\$need" }
}

$forbidden = @("auth.json", "state.vscdb", "pet_state.json", "usage.json", "usage.txt", "pet.log", "watch.log")
$leaks = Get-ChildItem -LiteralPath $out -Recurse -File | Where-Object { $forbidden -contains $_.Name.ToLowerInvariant() }
if ($leaks) { throw "pack contains forbidden user data: $($leaks.FullName -join ', ')" }

$secretPatterns = @(
    'C:\\Users\\[A-Za-z0-9._-]+\\',
    'sk-[A-Za-z0-9_-]{20,}',
    'gh[pousr]_[A-Za-z0-9_]{20,}',
    'AKIA[0-9A-Z]{16}',
    '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----'
)
$textFiles = Get-ChildItem -LiteralPath $out -Recurse -File | Where-Object { $_.Extension -in @('.txt', '.md', '.json', '.py', '.ps1', '.bat', '.xml', '.yml', '.yaml') }
foreach ($file in $textFiles) {
    $content = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction Stop
    foreach ($pattern in $secretPatterns) {
        if ($content -match $pattern) { throw "pack content check failed: $($file.FullName) matched $pattern" }
    }
}

if (Test-Path $zip) { Remove-Item -LiteralPath $zip -Force }
if (Test-Path $checksum) { Remove-Item -LiteralPath $checksum -Force }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($out, $zip, [System.IO.Compression.CompressionLevel]::Optimal, $true)
$zipHash = Get-FileHash -LiteralPath $zip -Algorithm SHA256
"$($zipHash.Hash) *$([IO.Path]::GetFileName($zip))" | Set-Content -LiteralPath $checksum -Encoding ascii

Write-Host "packed $out"
Write-Host "zip $zip"
$zipHash | Format-Table Path, Hash
Get-Item -LiteralPath $checksum, $zip | Format-Table Name, Length, LastWriteTime
