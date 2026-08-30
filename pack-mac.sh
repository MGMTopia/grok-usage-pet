#!/bin/bash
# Run this on a Mac. Windows cannot cross-compile a .app.
set -euo pipefail
cd "$(dirname "$0")"
python3 -m pip install -q pillow pyinstaller
python3 -m PyInstaller --noconfirm --clean --windowed --onedir \
  --name GrokUsagePet \
  --icon skins/original/app.png \
  --add-data "skins:skins" \
  --hidden-import fetch_usage \
  --hidden-import watch_apps \
  --hidden-import skin_catalog \
  --hidden-import PIL._tkinter_finder \
  --exclude-module numpy \
  --exclude-module pandas \
  --exclude-module scipy \
  pet.py
rm -rf release/GrokUsagePet-mac
mkdir -p release
cp -R dist/GrokUsagePet release/GrokUsagePet-mac
cp "使用说明.txt" release/GrokUsagePet-mac/
echo "packed release/GrokUsagePet-mac"
