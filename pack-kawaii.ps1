$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$name = "GrokUsagePetKawaii"
$dist = Join-Path $PSScriptRoot "dist\$name"
$out = Join-Path $PSScriptRoot "release\GrokUsagePet-kawaii"
$zip = Join-Path $PSScriptRoot "release\GrokUsagePet-kawaii.zip"

python -m PyInstaller --noconfirm --clean --windowed --onedir `
  --name $name `
  --icon "assets\app.ico" `
  --add-data "assets;assets" `
  --add-data "skins;skins" `
  --hidden-import fetch_usage `
  --hidden-import watch_apps `
  --hidden-import PIL._tkinter_finder `
  --exclude-module numpy `
  --exclude-module numpy.core `
  --exclude-module pandas `
  --exclude-module scipy `
  --exclude-module charset_normalizer `
  --exclude-module psutil `
  --exclude-module multiprocessing `
  pet.py

if (-not (Test-Path $dist)) {
    throw "PyInstaller did not produce $dist"
}

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Path (Split-Path $out) -Force | Out-Null
Copy-Item $dist $out -Recurse
Copy-Item (Join-Path $PSScriptRoot "使用说明.txt") (Join-Path $out "使用说明.txt") -Force
Copy-Item (Join-Path $PSScriptRoot "pack-kawaii\start_pet.bat") (Join-Path $out "start_pet.bat") -Force
Copy-Item (Join-Path $PSScriptRoot "pack-kawaii\register_watch.ps1") (Join-Path $out "register_watch.ps1") -Force

$assets = Join-Path $out "_internal\assets"
foreach ($need in @("spritesheet.webp", "app.ico", "app.png")) {
    if (-not (Test-Path (Join-Path $assets $need))) {
        throw "pack missing $need"
    }
}

if (Test-Path $zip) { Remove-Item $zip -Force }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($out, $zip, [System.IO.Compression.CompressionLevel]::Optimal, $true)

Write-Host "packed $out"
Write-Host "zip $zip"
Get-ChildItem $out | Format-Table Name, Length
Get-Item $zip | Format-Table Name, Length, LastWriteTime
