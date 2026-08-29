# Grok 额度宠物

Current version: **0.2.0** (`v0.2.0`). Previous GitHub snapshot: **0.1.0** (unnumbered at the time).

Unofficial desktop pet for SuperGrok weekly, Grok Bot weekly, and Cursor’s two monthly pools. Not an xAI or Cursor product. Character art is unofficial Kato Megumi fan work — personal, non-commercial use only. See [NOTICE.md](NOTICE.md).

This folder is **not** a git repo. Dual GitHub backup: [GITHUB备份说明.txt](GITHUB备份说明.txt). Do not `git init` or `git checkout` here.

End-user instructions: [使用说明.txt](使用说明.txt)

## Run from source

```text
pythonw pet.py
```

Data is stored in `%LOCALAPPDATA%\GrokUsagePet` for the source build and `%LOCALAPPDATA%\GrokUsagePetKawaii` for the kawaii executable.

Fetching does not require Grok Build or Cursor to be running. SuperGrok silently refreshes the OIDC token in `~/.grok/auth.json`.

## Test

Tests do not open Tk, use the network, or read real Grok/Cursor credentials.

```powershell
powershell -File .\run-tests.ps1
```

## Build the kawaii release

The verified toolchain is Python 3.12, Pillow 11.0.0, PyInstaller 6.22.2, and pyinstaller-hooks-contrib 2026.7.

```powershell
python -m pip install -r requirements-build.txt
powershell -File .\pack-kawaii.ps1
```

`GrokUsagePetKawaii.spec` is the single source of truth for PyInstaller resources. The packaging script runs tests, builds the executable, runs `--smoke-test`, checks required skins, rejects user-data files, and then creates the ZIP.
It also writes `GrokUsagePet-kawaii.zip.sha256` for integrity verification.

For a deterministic GUI lifecycle check without credentials or network access:

```powershell
.\dist\GrokUsagePetKawaii\GrokUsagePetKawaii.exe --visual-smoke-test
```

The preview renders fixed sample quotas and exits after three seconds without saving state.

## Packs in `release/`

| Zip | What |
|-----|------|
| `GrokUsagePet-kawaii.zip` | Current cute build (`GrokUsagePetKawaii.exe`). Rebuild with `pack-kawaii.ps1`. |
| `GrokUsagePet.zip` | Older plush build. Leave in place unless asked to replace. |

Do not copy `auth.json`, Cursor `state.vscdb`, or `pet_state.json` into a zip.

## Snapshot contract

- `complete`: Grok and Cursor both returned usable quota data.
- `partial`: one source returned usable data; this is normal when only one service is logged in.
- `failed`: neither source returned usable data. The previous usable snapshot is retained.
- CLI exit codes: `0` for complete/partial, `1` for failed, and `2` for an internal error.

## Layout

- `pet.py` — Tk controller, animation, and quota bubble
- `fetch_usage.py` — Grok/Cursor fetching and aggregation
- `usage_model.py` — pure snapshot status and text formatting
- `snapshot_store.py` — atomic public snapshot persistence
- `cursor_hooks.py` — safe shared Cursor hook management
- `skin_catalog.py` — skin discovery and manifest defaults
- `pet_view_model.py` — pure UI quota mapping
- `tests/` — offline unit and smoke tests
- `assets/` — default Kato sheet (legacy fallback)
- `skins/megumi-kato/` — complete example skin
- `skins/original/` — drop `spritesheet.webp` here; see `素材说明.txt`
- `pack-kawaii/` — portable `start_pet.bat` + `register_watch.ps1` for the exe

Version changes are recorded in [CHANGELOG.md](CHANGELOG.md). Source-code licensing is intentionally unresolved; do not publish or accept outside contributions until a license and artwork redistribution policy are chosen.
