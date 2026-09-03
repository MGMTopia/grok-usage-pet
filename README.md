# Grok 额度宠物

Current release: **0.3.7** (`v0.3.7`).

Unofficial desktop pet for SuperGrok weekly, Grok Bot weekly, Cursor monthly pools, and locally signed-in Codex quota windows. Not an xAI, Cursor, or OpenAI product. Program code is MIT licensed; character assets have separate terms in [ASSETS_NOTICE.md](ASSETS_NOTICE.md).

End-user instructions: [使用说明.txt](使用说明.txt)

## Run from source

```text
pythonw pet.py
```

Data is stored in `%LOCALAPPDATA%\GrokUsagePet`. A first run can copy missing state from the legacy `%LOCALAPPDATA%\GrokUsagePetKawaii` directory without deleting it. Settings → 卸载, or `--uninstall`, stops pet/watcher instances and removes local integration residue without touching Grok, Cursor, or Codex logins.

Fetching does not require Grok Build, Cursor, or Codex to be running. SuperGrok and ChatGPT-login Codex sessions can refresh their local OAuth credentials when needed; API-key Codex mode has no subscription quota percentage.

## Test

Tests do not open Tk, use the network, or read real Grok/Cursor credentials.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run-tests.ps1
```

## Build the Windows release

The verified toolchain is Python 3.12, Pillow 12.3.0, PyInstaller 6.22.2, and pyinstaller-hooks-contrib 2026.7.

```powershell
python -m pip install --require-hashes -r requirements-build.lock
powershell -NoProfile -ExecutionPolicy Bypass -File .\pack-windows.ps1
```

`GrokUsagePet.spec` is the single source of truth for PyInstaller resources. The packaging script runs tests, builds the executable, runs smoke tests, checks required skins and sensitive content, includes exact third-party license files, and creates a versioned ZIP with SHA256 verification. GitHub release builds also publish a verifiable provenance attestation.

For a deterministic GUI lifecycle check without credentials or network access:

```powershell
.\dist\GrokUsagePet\GrokUsagePet.exe --visual-smoke-test
```

The preview renders fixed sample quotas and exits after three seconds without saving state.

## Packs in `release/`

| Zip | What |
|-----|------|
| `GrokUsagePet-v0.3.7-Windows-x64.zip` | Current release (`GrokUsagePet.exe`). Rebuild with `pack-windows.ps1`. |
| `GrokUsagePet-kawaii.zip` | Legacy v0.2.0 compatibility archive; not the current release. |

Do not copy `auth.json`, Cursor `state.vscdb`, or `pet_state.json` into a zip.

## Snapshot contract

- `complete`: at least one configured source returned usable quota data.
- `partial`: retained for compatibility with older snapshots.
- `failed`: neither source returned usable data. The previous usable snapshot is retained.
- CLI exit codes: `0` for complete/partial, `1` for failed, and `2` for an internal error.

## Layout

- `pet.py` — Tk controller, animation, and quota bubble
- `fetch_usage.py` — Grok/Cursor/Codex fetching and aggregation
- `usage_model.py` — pure snapshot status and text formatting
- `snapshot_store.py` — atomic public snapshot persistence
- `cursor_hooks.py` — safe shared Cursor hook management
- `skin_catalog.py` — skin discovery and manifest defaults
- `pet_view_model.py` — pure UI quota mapping
- `tests/` — offline unit and smoke tests
- `skins/megumi-kato/` — complete example skin
- `skins/original/` — complete default Original/Pip skin
- `packaging/windows/` — portable launcher and watcher registration files

Version changes are recorded in [CHANGELOG.md](CHANGELOG.md). Code licensing is in [LICENSE](LICENSE), packaged dependency terms are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), and artwork redistribution boundaries are documented separately.

## Feedback and contributions

- [Report a bug or request a feature](https://github.com/liruilong0805/grok-usage-pet/issues/new/choose)
- [Ask questions, suggest themes, or vote on ideas](https://github.com/liruilong0805/grok-usage-pet/discussions)
- [Report a security vulnerability privately](https://github.com/liruilong0805/grok-usage-pet/security/advisories/new)

Before posting, remove email addresses, tokens, `auth.json`, `state.vscdb`, quota snapshots, and full logs. See [CONTRIBUTING.md](CONTRIBUTING.md) for the project scope and test requirements.
