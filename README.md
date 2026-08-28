# Grok 额度宠物

Unofficial desktop pet for SuperGrok weekly, Grok Bot weekly, and Cursor’s two monthly pools. Not an xAI or Cursor product. Character art is unofficial Kato Megumi fan work — personal use only.

End-user instructions: [使用说明.txt](使用说明.txt)

## Run (this machine)

```text
pythonw D:\ai\pet.py
```

Or the scheduled task `GrokUsagePetLaunch`. Data: `%LOCALAPPDATA%\GrokUsagePet`.

Fetching does not require Grok Build or Cursor to be running. SuperGrok silently refreshes the OIDC token in `~/.grok/auth.json`.

## Packs in `release/`

| Zip | What |
|-----|------|
| `GrokUsagePet-kawaii.zip` | Current cute build (`GrokUsagePetKawaii.exe`). Rebuild with `pack-kawaii.ps1`. |
| `GrokUsagePet.zip` | Older plush build. Leave in place unless asked to replace. |

```powershell
powershell -File D:\ai\pack-kawaii.ps1
```

Do not copy `auth.json`, Cursor `state.vscdb`, or `pet_state.json` into a zip.

## Layout

- `pet.py` — window, animations, kawaii quota bubble
- `fetch_usage.py` — billing snapshot
- `assets/` — `spritesheet.webp`, Kato `app.ico` / `app.png`
- `pack-kawaii/` — portable `start_pet.bat` + `register_watch.ps1` for the exe
