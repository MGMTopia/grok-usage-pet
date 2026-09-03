#!/usr/bin/env python3
"""Fetch remaining Grok usage and map it to local files.

Reads (leave these where the apps put them):
  ~/.grok/auth.json                                  SuperGrok / Grok Build login
  %APPDATA%/Cursor/User/globalStorage/state.vscdb    Cursor login (Grok Bot)
  ~/.codex/auth.json                                 Codex / ChatGPT login

Writes snapshots to the OS app-data folder (%%LOCALAPPDATA%%/GrokUsagePet on
Windows, ~/Library/Application Support/GrokUsagePet on macOS).

Two independent weekly meters:
  SuperGrok  — Chat / Build / Imagine / Voice (CLI-proxy billing)
  Grok Bot   — metered on the Cursor account (DashboardService/GetSandUsageStatus)
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from snapshot_store import write_snapshot_files
from usage_model import (
    SOURCE_ERROR,
    SOURCE_OK,
    SOURCE_UNAVAILABLE,
    STATUS_COMPLETE,
    STATUS_FAILED,
    STATUS_PARTIAL,
    as_float,
    exit_code_for_snapshot,
    ms_to_iso,
    one_line,
    seconds_until,
    snapshot_is_usable,
)

APP_NAME = "GrokUsagePet"
BILLING_URL = "https://cli-chat-proxy.grok.com/v1/billing?format=credits"
SETTINGS_URL = "https://cli-chat-proxy.grok.com/v1/settings"
CURSOR_RPC = "https://api2.cursor.sh/aiserver.v1.DashboardService"
CODEX_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
CODEX_TOKEN_URL = "https://auth.openai.com/oauth/token"
GROK_OIDC_ISSUER = "https://auth.x.ai"
GROK_OIDC_HOST = "auth.x.ai"
CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
WATCH_SECS = 60
REFRESH_SKEW_SECS = 300
_AUTH_REVISION_UNSET = object()
_SENSITIVE_TEXT_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(
        r"(?i)\b(?:access_token|refresh_token|id_token|authorization|api[_-]?key)"
        r"\b\s*[:=]\s*['\"]?[^'\"\s,;]{8,}"
    ),
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,})\b", re.IGNORECASE),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
)


def redact_sensitive_text(value: object, *, limit: int = 500) -> str:
    """Bound diagnostic text and remove common credential and URL-query shapes."""
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = re.sub(r"(https://[^\s?]+)\?[^\s]+", r"\1?[redacted]", text, flags=re.IGNORECASE)
    for pattern in _SENSITIVE_TEXT_PATTERNS:
        text = pattern.sub("[redacted]", text)
    if len(text) > limit:
        text = text[: max(0, limit - 1)] + "…"
    return text


def bounded_service_text(value: object, *, limit: int = 240) -> str | None:
    """Return one bounded, redacted service label or None for non-text values."""
    if not isinstance(value, str):
        return None
    return redact_sensitive_text(value, limit=limit)


class AuthFileChangedError(RuntimeError):
    """Raised when another process updates an auth file during refresh."""


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def pack_id() -> str:
    return "windows" if is_frozen() else "source"


def app_data_name() -> str:
    return APP_NAME


def _migrate_legacy_data(base: Path, destination: Path) -> None:
    legacy = base / "GrokUsagePetKawaii"
    if not legacy.is_dir():
        return
    for name in ("pet_state.json", "usage.json", "usage.txt"):
        source = legacy / name
        target = destination / name
        if source.is_file() and not target.exists():
            try:
                shutil.copy2(source, target)
            except OSError:
                pass


def resource_dir() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def install_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def data_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    path = base / app_data_name()
    path.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_data(base, path)
    return path


def grok_home() -> Path:
    env = os.environ.get("GROK_HOME")
    return Path(env) if env else Path.home() / ".grok"


def grok_auth_file() -> Path:
    return grok_home() / "auth.json"


def codex_home() -> Path:
    env = os.environ.get("CODEX_HOME")
    return Path(env) if env else Path.home() / ".codex"


def codex_auth_file() -> Path:
    return codex_home() / "auth.json"


def find_cursor_db() -> Path | None:
    home = Path.home()
    if sys.platform == "darwin":
        roots = [home / "Library" / "Application Support"]
    elif os.name == "nt":
        roots = [home / "AppData" / "Roaming"]
    else:
        roots = [home / ".config"]
    for root in roots:
        for name in ("Cursor", "Cursor Nightly", "Cursor Dev"):
            path = root / name / "User" / "globalStorage" / "state.vscdb"
            if path.exists():
                return path
    return None


def _parse_expires(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


def _token_expired(entry: dict, skew_secs: int = 0) -> bool:
    exp = _parse_expires(entry.get("expires_at"))
    if exp is None:
        return False
    return exp <= datetime.now(timezone.utc) + timedelta(seconds=skew_secs)


def _grok_https_url(url: str) -> str:
    parsed = urllib.parse.urlparse(str(url or "").strip())
    if (
        parsed.scheme != "https"
        or parsed.hostname != GROK_OIDC_HOST
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError("Grok 登录刷新地址无效")
    return urllib.parse.urlunparse(parsed)


def _oidc_token_url(issuer: str) -> str:
    base = _grok_https_url(issuer or GROK_OIDC_ISSUER).rstrip("/")
    url = f"{base}/.well-known/openid-configuration"
    req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    with urllib.request.urlopen(req, timeout=20) as resp:
        cfg = json.loads(resp.read().decode("utf-8"))
    token_url = cfg.get("token_endpoint")
    if not token_url:
        raise RuntimeError("无法发现 Grok 登录刷新地址")
    return _grok_https_url(str(token_url))


def _auth_revision(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    return hashlib.sha256(raw).hexdigest()


def _read_auth_json(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("登录文件顶层必须是对象")
    return payload, hashlib.sha256(raw).hexdigest()


def _windows_replace_file(replaced: Path, replacement: Path) -> None:
    import ctypes
    from ctypes import wintypes

    replace_file = ctypes.WinDLL("kernel32", use_last_error=True).ReplaceFileW
    replace_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.LPVOID,
    ]
    replace_file.restype = wintypes.BOOL
    if not replace_file(str(replaced), str(replacement), None, 0, None, None):
        error = ctypes.get_last_error()
        raise OSError(error, ctypes.FormatError(error), str(replaced))


def _replace_auth_file(tmp: Path, path: Path) -> None:
    if os.name == "nt" and path.exists():
        # ReplaceFileW preserves the replaced file's DACL, encryption, and streams.
        _windows_replace_file(path, tmp)
    else:
        os.replace(tmp, path)


def _write_auth(
    path: Path,
    data: dict,
    *,
    expected_revision: str | None | object = _AUTH_REVISION_UNSET,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if expected_revision is not _AUTH_REVISION_UNSET and _auth_revision(path) != expected_revision:
        raise AuthFileChangedError("登录文件已被其他进程更新，已保留较新内容")
    original_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    # Auth files must never become group/world-readable after token refresh.
    secure_mode = original_mode & 0o700
    if not secure_mode:
        secure_mode = 0o600
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        if os.name != "nt":
            os.chmod(tmp, secure_mode)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        if expected_revision is not _AUTH_REVISION_UNSET and _auth_revision(path) != expected_revision:
            raise AuthFileChangedError("登录文件已被其他进程更新，已保留较新内容")
        _replace_auth_file(tmp, path)
        if os.name != "nt":
            os.chmod(path, secure_mode)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def refresh_grok_auth(
    data: dict,
    account_id: str,
    entry: dict,
    *,
    expected_revision: str | None | object = _AUTH_REVISION_UNSET,
) -> dict:
    refresh = entry.get("refresh_token")
    client_id = entry.get("oidc_client_id")
    issuer = entry.get("oidc_issuer") or GROK_OIDC_ISSUER
    if not refresh or not client_id:
        raise RuntimeError("Grok 登录已过期，请先运行 grok login")
    body = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": client_id,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        _oidc_token_url(str(issuer)),
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError("Grok 登录已过期，请先运行 grok login") from exc
    access = payload.get("access_token")
    if not access:
        raise RuntimeError("Grok 登录刷新失败，请先运行 grok login")
    entry["key"] = access
    if payload.get("refresh_token"):
        entry["refresh_token"] = payload["refresh_token"]
    expires_in = payload.get("expires_in")
    if expires_in:
        end = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        entry["expires_at"] = end.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    data[account_id] = entry
    _write_auth(grok_auth_file(), data, expected_revision=expected_revision)
    return entry


def load_token(*, force_refresh: bool = False, _allow_revision_retry: bool = True) -> tuple[str, dict]:
    auth_file = grok_auth_file()
    if not auth_file.exists():
        raise RuntimeError("未找到 Grok 登录，请先运行 grok login")
    data, revision = _read_auth_json(auth_file)
    if not data:
        raise RuntimeError("Grok 登录文件为空，请先运行 grok login")
    account_id, entry = next(iter(data.items()))
    if not isinstance(entry, dict):
        raise RuntimeError("Grok 登录文件损坏，请先运行 grok login")
    stale = force_refresh or _token_expired(entry, REFRESH_SKEW_SECS)
    if stale:
        try:
            entry = refresh_grok_auth(
                data,
                str(account_id),
                entry,
                expected_revision=revision,
            )
        except AuthFileChangedError:
            if _allow_revision_retry:
                return load_token(force_refresh=False, _allow_revision_retry=False)
            raise
        except RuntimeError:
            if force_refresh or _token_expired(entry, 0) or not entry.get("key"):
                raise
    token = entry.get("key")
    if not token:
        raise RuntimeError("Grok 登录无 token，请先运行 grok login")
    if _token_expired(entry, 0):
        raise RuntimeError("Grok 登录已过期，请先运行 grok login")
    return token, entry


def cursor_rpc(token: str, method: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"{CURSOR_RPC}/{method}",
        data=json.dumps(body or {}).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Connect-Protocol-Version": "1",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_cursor_token() -> dict | None:
    db = find_cursor_db()
    if db is None or not db.exists():
        return None
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cur = con.cursor()

        def get(key: str) -> str | None:
            cur.execute("SELECT value FROM ItemTable WHERE key=?", (key,))
            row = cur.fetchone()
            if not row:
                return None
            val = row[0]
            return val.decode("utf-8") if isinstance(val, bytes) else val

        token = get("cursorAuth/accessToken")
        if not token:
            return None
        return {
            "token": token,
            "email": get("cursorAuth/cachedEmail"),
            "plan": get("cursorAuth/stripeMembershipType"),
            "status": get("cursorAuth/stripeSubscriptionStatus"),
        }
    finally:
        con.close()


def fetch_cursor() -> dict | None:
    creds = load_cursor_token()
    if not creds:
        return None
    token = creds["token"]
    bot = {}
    period = {}
    plan = {}
    hard = {}
    errors = {}
    try:
        bot = cursor_rpc(token, "GetSandUsageStatus")
    except Exception as exc:
        errors["grok_bot"] = redact_sensitive_text(exc)
    try:
        period = cursor_rpc(token, "GetCurrentPeriodUsage")
    except Exception as exc:
        errors["cursor_period"] = redact_sensitive_text(exc)
    try:
        plan = cursor_rpc(token, "GetPlanInfo")
    except Exception as exc:
        errors["cursor_plan"] = redact_sensitive_text(exc)
    try:
        hard = cursor_rpc(token, "GetHardLimit")
    except Exception as exc:
        errors["cursor_hard_limit"] = redact_sensitive_text(exc)

    used = as_float(bot.get("usagePercent"))
    reset = bot.get("nextResetTimestampUtc") if bot else None
    plan_info = plan.get("planInfo") or {}
    plan_usage = period.get("planUsage") or {}
    limit_cents = plan_usage.get("limit")
    included_cents = plan_usage.get("includedSpend")
    models_used = plan_usage.get("autoPercentUsed")
    other_used = plan_usage.get("apiPercentUsed")

    def remain(used_pct) -> float | None:
        value = as_float(used_pct)
        if value is None:
            return None
        return max(0.0, 100.0 - value)

    bot_remaining = max(0.0, 100.0 - used) if used is not None else None
    cursor_remaining = remain(models_used)
    other_remaining = remain(other_used)
    usable = any(value is not None for value in (bot_remaining, cursor_remaining, other_remaining))

    return {
        "source_status": SOURCE_OK if usable else SOURCE_ERROR,
        "cursor_plan": bounded_service_text(plan_info.get("planName") or creds.get("plan"), limit=120),
        "grok_bot": {
            "used_percent": used,
            "remaining_percent": bot_remaining,
            "resets_at": reset,
        },
        "cursor_monthly": {
            "billing_cycle_end": ms_to_iso(period.get("billingCycleEnd")),
            "included_limit_cents": limit_cents,
            "included_used_cents": included_cents,
            "display_message": bounded_service_text(period.get("displayMessage")),
            "on_demand_allowed": not bool(hard.get("noUsageBasedAllowed")),
            "cursor_models": {
                "hint": "Composer / Cursor Grok 等自有模型",
                "used_percent": models_used,
                "remaining_percent": cursor_remaining,
                "display_message": bounded_service_text(period.get("autoModelSelectedDisplayMessage")),
            },
            "other_models": {
                "hint": "GPT / Claude 等第三方模型",
                "used_percent": other_used,
                "remaining_percent": other_remaining,
                "display_message": bounded_service_text(period.get("namedModelSelectedDisplayMessage")),
            },
        },
        "errors": errors or None,
    }


def _b64url_json(segment: str) -> dict | None:
    try:
        padded = segment + "=" * (-len(segment) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _jwt_expiry(token: str) -> datetime | None:
    parts = token.split(".")
    if len(parts) < 2:
        return None
    payload = _b64url_json(parts[1]) or {}
    try:
        return datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
    except (KeyError, TypeError, ValueError, OSError, OverflowError):
        return None


def _epoch_to_iso(value) -> str | None:
    number = as_float(value)
    if number is None:
        return None
    if number > 1e12:
        number /= 1000.0
    try:
        return datetime.fromtimestamp(number, tz=timezone.utc).isoformat()
    except (OSError, OverflowError, ValueError):
        return None


def _codex_window(raw: dict | None) -> dict:
    data = raw if isinstance(raw, dict) else {}
    used = as_float(data.get("used_percent"))
    remaining = max(0.0, 100.0 - used) if used is not None else None
    seconds = as_float(data.get("limit_window_seconds"))
    hint = ""
    if seconds is not None:
        hours = int(seconds) // 3600
        if hours >= 24:
            hint = f"{hours // 24} 天窗口"
        elif hours:
            hint = f"{hours} 小时窗口"
    resets_at = _epoch_to_iso(data.get("reset_at"))
    if resets_at is None and data.get("reset_after_seconds") is not None:
        try:
            resets_at = _epoch_to_iso(time.time() + float(data["reset_after_seconds"]))
        except (TypeError, ValueError):
            resets_at = None
    return {
        "used_percent": used,
        "remaining_percent": remaining,
        "resets_at": resets_at,
        "window_seconds": int(seconds) if seconds is not None else None,
        "hint": hint,
    }


def refresh_codex_auth(
    data: dict,
    *,
    expected_revision: str | None | object = _AUTH_REVISION_UNSET,
) -> dict:
    tokens = data.get("tokens")
    if not isinstance(tokens, dict):
        raise RuntimeError("Codex 登录已过期，请先运行 codex login")
    refresh = tokens.get("refresh_token")
    if not refresh:
        raise RuntimeError("Codex 登录已过期，请先运行 codex login")
    body = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": CODEX_CLIENT_ID,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        CODEX_TOKEN_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError("Codex 登录已过期，请先运行 codex login") from exc
    access = payload.get("access_token")
    if not access:
        raise RuntimeError("Codex 登录刷新失败，请先运行 codex login")
    tokens["access_token"] = access
    if payload.get("refresh_token"):
        tokens["refresh_token"] = payload["refresh_token"]
    if payload.get("id_token"):
        tokens["id_token"] = payload["id_token"]
    data["tokens"] = tokens
    data["last_refresh"] = datetime.now(timezone.utc).isoformat()
    _write_auth(codex_auth_file(), data, expected_revision=expected_revision)
    return data


def load_codex_auth(*, force_refresh: bool = False, _allow_revision_retry: bool = True) -> dict | None:
    path = codex_auth_file()
    if not path.exists():
        return None
    try:
        data, revision = _read_auth_json(path)
    except (OSError, json.JSONDecodeError):
        raise RuntimeError("Codex 登录文件损坏，请先运行 codex login")
    if not isinstance(data, dict):
        raise RuntimeError("Codex 登录文件损坏，请先运行 codex login")
    mode = str(data.get("auth_mode") or "").lower()
    if mode in {"apikey", "api_key", "api"} or (data.get("OPENAI_API_KEY") and not (data.get("tokens") or {}).get("access_token")):
        return {"mode": "apikey"}
    tokens = data.get("tokens")
    if not isinstance(tokens, dict) or not tokens.get("access_token"):
        return None
    access = str(tokens.get("access_token"))
    exp = _jwt_expiry(access)
    stale = force_refresh or (exp is not None and exp <= datetime.now(timezone.utc) + timedelta(seconds=REFRESH_SKEW_SECS))
    if stale:
        try:
            data = refresh_codex_auth(data, expected_revision=revision)
            tokens = data.get("tokens") or {}
            access = str(tokens.get("access_token") or "")
        except AuthFileChangedError:
            if _allow_revision_retry:
                return load_codex_auth(force_refresh=False, _allow_revision_retry=False)
            raise
        except RuntimeError:
            if force_refresh or not access:
                raise
            if exp is not None and exp <= datetime.now(timezone.utc):
                raise
    if not access:
        raise RuntimeError("Codex 登录无 token，请先运行 codex login")
    return {
        "mode": "chatgpt",
        "access_token": access,
        "account_id": tokens.get("account_id") or None,
    }


def _codex_get(url: str, access: str, account_id: str | None) -> dict:
    headers = {
        "Authorization": f"Bearer {access}",
        "Accept": "application/json",
        "User-Agent": "codex-cli",
    }
    if account_id:
        headers["ChatGPT-Account-Id"] = str(account_id)
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Codex 额度接口返回异常")
    return payload


def fetch_codex() -> dict | None:
    try:
        creds = load_codex_auth()
    except RuntimeError as exc:
        return {"source_status": SOURCE_ERROR, "errors": {"codex": redact_sensitive_text(exc)}}
    if creds is None:
        return None
    if creds.get("mode") == "apikey":
        return {
            "source_status": SOURCE_UNAVAILABLE,
            "plan_type": "api",
            "primary": {"remaining_percent": None, "used_percent": None, "resets_at": None, "hint": "API Key 按量计费，没有套餐剩余百分比"},
            "secondary": {"remaining_percent": None, "used_percent": None, "resets_at": None, "hint": ""},
            "errors": {"codex": "Codex 当前为 API Key 计费，没有套餐剩余百分比。请用 ChatGPT 登录 Codex。"},
        }
    access = str(creds.get("access_token") or "")
    account_id = creds.get("account_id")
    try:
        try:
            payload = _codex_get(CODEX_USAGE_URL, access, account_id)
        except urllib.error.HTTPError as exc:
            if exc.code not in (401, 403):
                raise
            creds = load_codex_auth(force_refresh=True) or {}
            access = str(creds.get("access_token") or "")
            account_id = creds.get("account_id")
            payload = _codex_get(CODEX_USAGE_URL, access, account_id)
    except Exception as exc:
        return {"source_status": SOURCE_ERROR, "errors": {"codex": redact_sensitive_text(exc)}}
    rate = payload.get("rate_limit") if isinstance(payload.get("rate_limit"), dict) else {}
    primary = _codex_window(rate.get("primary_window"))
    secondary = _codex_window(rate.get("secondary_window"))
    credits = payload.get("credits") if isinstance(payload.get("credits"), dict) else {}
    extras: list[str] = []
    plan = payload.get("plan_type")
    if plan:
        extras.append(f"ChatGPT {plan}")
    balance = credits.get("balance")
    if balance not in (None, ""):
        extras.append(f"额外 credits {balance}")
    usable = primary.get("remaining_percent") is not None or secondary.get("remaining_percent") is not None
    if not primary.get("hint"):
        primary["hint"] = "5 小时窗口"
    if not secondary.get("hint"):
        secondary["hint"] = "7 天窗口"
    primary["extra"] = extras
    secondary["extra"] = extras
    return {
        "source_status": SOURCE_OK if usable else SOURCE_ERROR,
        "plan_type": plan,
        "primary": primary,
        "secondary": secondary,
        "errors": None if usable else {"codex": "Codex 接口未返回有效额度数据"},
    }


def get_json(url: str, token: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "x-xai-token-auth": "xai-grok-cli",
            "Accept": "application/json",
            "User-Agent": "grok-cli",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def snapshot() -> dict:
    now = datetime.now(timezone.utc)
    errors: dict[str, str] = {}
    grok_status = SOURCE_UNAVAILABLE if not grok_auth_file().exists() else SOURCE_ERROR
    cursor_status = SOURCE_UNAVAILABLE
    codex_status = SOURCE_UNAVAILABLE
    entry: dict = {}
    cfg: dict = {}
    tier = None
    try:
        token, entry = load_token()
        try:
            billing = get_json(BILLING_URL, token)
        except urllib.error.HTTPError as exc:
            if exc.code not in (401, 403):
                raise
            token, entry = load_token(force_refresh=True)
            billing = get_json(BILLING_URL, token)
        if not isinstance(billing.get("config"), dict):
            raise RuntimeError("Grok billing response missing config")
        grok_status = SOURCE_OK
        try:
            settings = get_json(SETTINGS_URL, token)
            tier = settings.get("subscription_tier_display")
        except Exception as exc:
            errors["grok_settings"] = redact_sensitive_text(exc)
        cfg = billing.get("config") or {}
    except Exception as exc:
        errors["grok"] = redact_sensitive_text(exc)

    period = cfg.get("currentPeriod") or {}
    used_pct = float(cfg.get("creditUsagePercent") or 0) if cfg else None
    remaining_pct = max(0.0, 100.0 - used_pct) if used_pct is not None else None
    products = {}
    for item in cfg.get("productUsage") or []:
        name = item.get("product") or "Unknown"
        products[name] = float(item.get("usagePercent") or 0)

    reset_iso = period.get("end") or cfg.get("billingPeriodEnd")

    cursor = None
    try:
        cursor = fetch_cursor()
        if cursor is None:
            errors["cursor"] = "未找到 Cursor 登录，请先打开 Cursor 并登录"
            cursor_status = SOURCE_UNAVAILABLE
        else:
            cursor_status = str(cursor.get("source_status") or SOURCE_ERROR)
            cursor_errors = cursor.get("errors") or {}
            if isinstance(cursor_errors, dict):
                for key, value in cursor_errors.items():
                    name = key if str(key).startswith("cursor_") else f"cursor_{key}"
                    errors[name] = str(value)
            if cursor_status == SOURCE_ERROR and not cursor_errors:
                errors["cursor"] = "Cursor 接口未返回有效额度数据"
    except Exception as exc:
        cursor = {"error": redact_sensitive_text(exc)}
        errors["cursor"] = redact_sensitive_text(exc)
        cursor_status = SOURCE_ERROR

    codex = None
    try:
        codex = fetch_codex()
        if codex is None:
            errors["codex"] = "未找到 Codex 登录，请先运行 codex login"
            codex_status = SOURCE_UNAVAILABLE
        else:
            codex_status = str(codex.get("source_status") or SOURCE_ERROR)
            codex_errors = codex.get("errors") or {}
            if isinstance(codex_errors, dict):
                for key, value in codex_errors.items():
                    errors[str(key)] = str(value)
            if codex_status == SOURCE_ERROR and "codex" not in errors:
                errors["codex"] = "Codex 接口未返回有效额度数据"
    except Exception as exc:
        codex = {"error": redact_sensitive_text(exc)}
        errors["codex"] = redact_sensitive_text(exc)
        codex_status = SOURCE_ERROR

    source_states = (grok_status, cursor_status, codex_status)
    active = [state for state in source_states if state != SOURCE_UNAVAILABLE]
    if not active:
        status = STATUS_FAILED
    elif all(state == SOURCE_OK for state in active):
        status = STATUS_COMPLETE
    elif any(state == SOURCE_OK for state in active):
        status = STATUS_PARTIAL
    else:
        status = STATUS_FAILED

    sources = {
        "grok": {"status": grok_status},
        "cursor": {"status": cursor_status},
        "codex": {"status": codex_status},
    }
    if errors.get("grok"):
        sources["grok"]["error"] = errors["grok"]
    if errors.get("cursor"):
        sources["cursor"]["error"] = errors["cursor"]
    if errors.get("codex"):
        sources["codex"]["error"] = errors["codex"]

    return {
        "status": status,
        "sources": sources,
        "fetched_at": now.isoformat(),
        "plan": tier,
        "period": {"end": reset_iso},
        "used_percent": used_pct,
        "remaining_percent": remaining_pct,
        "products_used_percent": products,
        "cursor": cursor,
        "codex": codex,
        "errors": errors or None,
    }


def write_snapshot(snap: dict) -> bool:
    if not snapshot_is_usable(snap):
        return False
    out_dir = data_dir()
    write_snapshot_files(out_dir, snap, one_line(snap))
    return True


def fetch_once(quiet: bool = False) -> dict:
    snap = snapshot()
    written = write_snapshot(snap)
    if not quiet:
        if written:
            print("updated local usage snapshot")
        else:
            print("usage unavailable; kept previous local snapshot", file=sys.stderr)
    return snap


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Map Grok remaining usage to a local snapshot"
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help=f"poll every {WATCH_SECS}s (Grok's own subscription watch interval)",
    )
    parser.add_argument("--interval", type=int, default=WATCH_SECS, help="watch interval seconds")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    try:
        snap = fetch_once(quiet=args.quiet)
        if args.watch:
            while True:
                time.sleep(max(15, args.interval))
                try:
                    fetch_once(quiet=args.quiet)
                except Exception as exc:
                    print(f"refresh failed: {redact_sensitive_text(exc)}", file=sys.stderr)
        return exit_code_for_snapshot(snap)
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {redact_sensitive_text(exc.reason)}", file=sys.stderr)
        if exc.code in (401, 403):
            print("token rejected; run `grok login`", file=sys.stderr)
        return 1
    except SystemExit as exc:
        print(redact_sensitive_text(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"fatal: {redact_sensitive_text(exc)}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
