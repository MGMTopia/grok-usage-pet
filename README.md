# Grok 额度桌宠

**Grok usage desktop pet** · [中文](#安装) · [English](#install)

<p align="center">
  <img src="docs/preview.gif" alt="Grok 额度桌宠 / Grok usage desktop pet showing SuperGrok, Grok Bot, Cursor, and Codex remaining quota" />
</p>

Windows 上的非官方额度桌宠，用来看 SuperGrok 周额度、Grok Bot 周额度、Cursor 月额度，以及 Codex 余量。不是 xAI、Cursor 或 OpenAI 官方软件。程序代码是 MIT；角色素材见 [ASSETS_NOTICE.md](ASSETS_NOTICE.md)。

更完整的中文说明：[使用说明.txt](使用说明.txt) · [README.zh-CN.md](README.zh-CN.md)

## 安装

当前版本：**0.3.13**（`v0.3.13`）。

从 [GitHub Release](https://github.com/MGMTopia/grok-usage-pet/releases/latest) 下载 **`GrokUsagePet-v0.3.13-Windows-x64.zip`**。不必装 Python。

1. 解压**整个文件夹**，不要只拷贝 exe。
2. 本机先登录一次（登哪个就显示哪条）：
   - SuperGrok：`grok login`
   - Grok Bot / Cursor：在 Cursor 里登录
   - Codex：ChatGPT 套餐的 `codex login`（不要用纯 API Key）
3. 双击 `GrokUsagePet.exe`。

Windows 10/11。数据在 `%LOCALAPPDATA%\GrokUsagePet`。设置 → 卸载，或 `--uninstall`，只清本机集成，不动 Grok / Cursor / Codex 登录。

### 常见卡住点

| 你会遇到 | 怎么处理 |
|----------|----------|
| 双击没反应，或闪一下就退出 | 必须解压**整个文件夹**（含 `_internal`），不要只拷贝 exe。从网上下载的 zip / exe 先右键 → 属性 → 勾选「解除锁定」。 |
| SmartScreen「Windows 已保护你的电脑」 | 未做代码签名。点「更多信息」→「仍要运行」。 |
| 杀毒隔离 exe，或「创建桌面快捷方式」失败 | 本程序**不会**关闭杀毒或自动加白名单。在 Windows 安全中心允许 `GrokUsagePet.exe`。若受控文件夹访问挡住桌面，把程序目录里的 `.lnk` 拖到桌面，或右键 exe → 发送到 → 桌面快捷方式。 |
| 有的额度条是空的 | 只显示已经登录过的来源。纯 API Key 的 Codex 没有剩余百分比，请用 `codex login`（ChatGPT 套餐）。 |
| SuperGrok 睡醒后空白 | 一般会自行用本机 refresh token 续期。仍提示登录过期就再运行一次 `grok login`。 |
| 右键退出后，Grok / Cursor 还开着，宠物不回来 | 故意的。重新启动 Grok 或 Cursor，或自己再打开宠物。 |
| 这一次所有来源都没抓到 | 会保留上一次成功额度，不会用空数据覆盖。 |
| macOS 打不开这个 zip | 这是 Windows 包，不是 `.app`。请在 Mac 上用源码运行或执行 `pack-mac.sh`。 |

## Install

Unofficial overlay for SuperGrok weekly, Grok Bot weekly, Cursor monthly, and Codex quota. Not an xAI, Cursor, or OpenAI product.

Download **`GrokUsagePet-v0.3.13-Windows-x64.zip`** from the
[latest GitHub Release](https://github.com/MGMTopia/grok-usage-pet/releases/latest).
Python is not required.

1. Unzip the **whole folder**. Do not copy only the exe.
2. Sign in to at least one source (`grok login`, Cursor, or ChatGPT-plan `codex login`).
3. Double-click `GrokUsagePet.exe`.

Windows 10/11.

### If something looks stuck

| What you see | What to do |
|--------------|------------|
| Double-click does nothing, or the window flashes and exits | Unzip the **whole folder** (including `_internal`). Do not copy only the exe. For a download, right-click the zip/exe → Properties → Unblock. |
| SmartScreen: “Windows protected your PC” | The build is unsigned. Choose **More info** → **Run anyway**. |
| Antivirus quarantines the exe, or “create desktop shortcut” fails | This app **does not** turn off antivirus or add exclusions. Allow `GrokUsagePet.exe` in Windows Security. If Controlled Folder Access blocks the desktop, drag the `.lnk` from the program folder onto the desktop, or right-click the exe → Send to → Desktop. |
| Some quota rows are blank | Only signed-in sources appear. API-key Codex has no remaining percentage; use ChatGPT-plan `codex login`. |
| SuperGrok is empty after sleep | It usually refreshes the local token by itself. If it still says the login expired, run `grok login` again. |
| You quit the pet, Grok/Cursor stay open, and it does not come back | Intended. Restart Grok or Cursor, or open the pet yourself. |
| Every source failed this round | The last successful snapshot is kept. Empty data is not written over it. |
| The zip will not open as an app on macOS | This is a Windows build, not a `.app`. On a Mac, run from source or use `pack-mac.sh`. |

## Run from source

```text
pythonw pet.py
```

Fetching does not require Grok Build, Cursor, or Codex to be running. SuperGrok and ChatGPT-login Codex sessions can refresh their local OAuth credentials when needed; API-key Codex mode has no subscription quota percentage. Settings can enable a local clock panel (weekday and time, plus countdown or stopwatch) separately from quota. When a countdown finishes, the pet switches to the clock, shows a topmost “时间到” banner, jumps, and plays a short beep.

## Test

Tests do not open Tk, use the network, or read real Grok/Cursor credentials.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run-tests.ps1
```

## Build the Windows release

The verified toolchain is Python 3.12, Pillow 12.3.0, PyInstaller 6.22.2, and pyinstaller-hooks-contrib 2026.7. Most people should use the Release zip above instead of compiling.

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
| `GrokUsagePet-v0.3.13-Windows-x64.zip` | Current release (`GrokUsagePet.exe`). Rebuild with `pack-windows.ps1`. |
| `GrokUsagePet-kawaii.zip` | Legacy v0.2.0 compatibility archive; not the current release. |

Do not copy `auth.json`, Cursor `state.vscdb`, or `pet_state.json` into a zip.

## Snapshot contract

- `complete`: at least one configured source returned usable quota data.
- `partial`: retained for compatibility with older snapshots.
- `failed`: neither source returned usable data. The previous usable snapshot is retained.
- CLI exit codes: `0` for complete/partial, `1` for failed, and `2` for an internal error.

## Layout

- `pet.py` — Tk controller, animation, and hover panels
- `fetch_usage.py` — Grok/Cursor/Codex fetching and aggregation
- `usage_model.py` — pure snapshot status and text formatting
- `snapshot_store.py` — atomic public snapshot persistence
- `cursor_hooks.py` — safe shared Cursor hook management
- `skin_catalog.py` — skin discovery and manifest defaults
- `pet_view_model.py` — pure UI quota mapping
- `pet_settings.py` — layered `pet_state.json` with v0.3 flat aliases
- `info_modules.py` — optional module host (refresh and permissions)
- `quota_module.py` — quota as an optional information module
- `clock_module.py` — local clock panel and themed alarm
- `app_update.py` — GitHub Release check and verified zip install
- `tests/` — offline unit and smoke tests
- `skins/megumi-kato/` — complete example skin
- `skins/original/` — complete default Original/Pip skin
- `packaging/windows/` — portable launcher and watcher registration files
- `docs/preview.gif` — README animation, regenerated with `docs/make_preview_gif.py`

Version changes are recorded in [CHANGELOG.md](CHANGELOG.md). Code licensing is in [LICENSE](LICENSE), packaged dependency terms are in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), and artwork redistribution boundaries are documented separately.

## Feedback and contributions

Use this GitHub repository's **Issues**, **Discussions**, and **Security advisories** tabs. Do not paste tokens or quota snapshots.

Before posting, remove email addresses, tokens, `auth.json`, `state.vscdb`, quota snapshots, and full logs. See [CONTRIBUTING.md](CONTRIBUTING.md) for the project scope and test requirements.
