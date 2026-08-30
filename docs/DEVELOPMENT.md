# Development

## Requirements

- Windows 10 or 11 for the packaged application
- Python 3.12
- Dependencies from `requirements.txt`
- Build dependencies from `requirements-build.txt`

## Run from source

```powershell
pythonw pet.py
```

Source runs store data under `%LOCALAPPDATA%\GrokUsagePet`.

## Test

```powershell
powershell -File .\run-tests.ps1
```

Tests are offline. They do not open the production Tk window, access the
network, or read real Grok/Cursor credentials.

## Modules

- `pet.py`: Tk controller, animation, settings, and quota bubble
- `fetch_usage.py`: Grok/Cursor adapters and snapshot aggregation
- `usage_model.py`: pure status and text formatting
- `snapshot_store.py`: atomic last-known-good snapshot persistence
- `cursor_hooks.py`: safe shared Cursor hook management
- `skin_catalog.py`: theme discovery and validation
- `pet_view_model.py`: pure UI quota mapping
- `tests/`: offline unit and smoke tests

Keep credential access inside the provider layer. New tests must use temporary
fixtures and mocks rather than real local sessions.
