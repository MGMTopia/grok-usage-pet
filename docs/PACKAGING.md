# Packaging and releases

The verified Windows toolchain is Python 3.12, Pillow 11.0.0, PyInstaller
6.22.2, and pyinstaller-hooks-contrib 2026.7.

## Build locally

```powershell
python -m pip install -r requirements-build.txt
powershell -File .\pack-windows.ps1
```

The current script:

1. verifies dependency versions;
2. runs the offline unit tests;
3. runs the source smoke test;
4. builds the PyInstaller spec;
5. runs frozen non-GUI and three-second Tk visual smoke tests;
6. verifies required themes and rejects user-data files;
7. creates a Windows x64 ZIP and matching SHA256 file.

`pack-kawaii.ps1` remains only as a temporary compatibility wrapper. Public
artifacts, executable names, scheduled tasks, and data paths use
`GrokUsagePet`.

## Release contract

Release artifacts must be built on Windows from a version tag and include:

```text
GrokUsagePet-v<version>-Windows-x64.zip
GrokUsagePet-v<version>-Windows-x64.zip.sha256
```

Do not publish `auth.json`, `state.vscdb`, quota snapshots, state files, logs,
or a locally populated data directory. The CI release workflow is the preferred
source of public binaries.
