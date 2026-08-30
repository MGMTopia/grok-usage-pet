#!/usr/bin/env python3
"""Fetch remaining Grok usage and map it to local files.

Reads (leave these where the apps put them):
  ~/.grok/auth.json                                  SuperGrok / Grok Build login
  %APPDATA%/Cursor/User/globalStorage/state.vscdb    Cursor login (Grok Bot)

Writes snapshots to the OS app-data folder (%%LOCALAPPDATA%%/GrokUsagePet on
Windows, ~/Library/Application Support/GrokUsagePet on macOS).

Two independent weekly meters:
  SuperGrok  — Chat / Build / Imagine / Voice (CLI-proxy billing)
  Grok Bot   — metered on the Cursor account (DashboardService/GetSandUsageStatus)
"""

from __future__ import annotations

import argparse
import json
import os
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
WATCH_SECS = 60
REFRESH_SKEW_SECS = 300


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


def _oidc_token_url(issuer: str) -> str:
    base = (issuer or "https://auth.x.ai").rstrip("/")
    url = f"{base}/.well-known/openid-configuration"
    req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    with urllib.request.urlopen(req, timeout=20) as resp:
        cfg = json.loads(resp.read().decode("utf-8"))
    token_url = cfg.get("token_endpoint")
    if not token_url:
        raise RuntimeError("无法发现 Grok 登录刷新地址")
    return str(token_url)


def _write_auth(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
        os.replace(tmp, path)
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


def refresh_grok_auth(data: dict, account_id: str, entry: dict) -> dict:
    refresh = entry.get("refresh_token")
    client_id = entry.get("oidc_client_id")
    issuer = entry.get("oidc_issuer") or "https://auth.x.ai"
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
    _write_auth(grok_auth_file(), data)
    return entry


def load_token(*, force_refresh: bool = False) -> tuple[str, dict]:
    auth_file = grok_auth_file()
    if not auth_file.exists():
        raise RuntimeError("未找到 Grok 登录，请先运行 grok login")
    data = json.loads(auth_file.read_text(encoding="utf-8"))
    if not data:
        raise RuntimeError("Grok 登录文件为空，请先运行 grok login")
    account_id, entry = next(iter(data.items()))
    if not isinstance(entry, dict):
        raise RuntimeError("Grok 登录文件损坏，请先运行 grok login")
    stale = force_refresh or _token_expired(entry, REFRESH_SKEW_SECS)
    if stale:
        try:
            entry = refresh_grok_auth(data, str(account_id), entry)
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
        errors["grok_bot"] = str(exc)
    try:
        period = cursor_rpc(token, "GetCurrentPeriodUsage")
    except Exception as exc:
        errors["cursor_period"] = str(exc)
    try:
        plan = cursor_rpc(token, "GetPlanInfo")
    except Exception as exc:
        errors["cursor_plan"] = str(exc)
    try:
        hard = cursor_rpc(token, "GetHardLimit")
    except Exception as exc:
        errors["cursor_hard_limit"] = str(exc)

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
        "cursor_plan": plan_info.get("planName") or creds.get("plan"),
        "grok_bot": {
            "used_percent": used,
            "remaining_percent": bot_remaining,
            "resets_at": reset,
        },
        "cursor_monthly": {
            "billing_cycle_end": ms_to_iso(period.get("billingCycleEnd")),
            "included_limit_cents": limit_cents,
            "included_used_cents": included_cents,
            "display_message": period.get("displayMessage"),
            "on_demand_allowed": not bool(hard.get("noUsageBasedAllowed")),
            "cursor_models": {
                "hint": "Composer / Cursor Grok 等自有模型",
                "used_percent": models_used,
                "remaining_percent": cursor_remaining,
                "display_message": period.get("autoModelSelectedDisplayMessage"),
            },
            "other_models": {
                "hint": "GPT / Claude 等第三方模型",
                "used_percent": other_used,
                "remaining_percent": other_remaining,
                "display_message": period.get("namedModelSelectedDisplayMessage"),
            },
        },
        "errors": errors or None,
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
            errors["grok_settings"] = str(exc)
        cfg = billing.get("config") or {}
    except Exception as exc:
        errors["grok"] = str(exc)

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
        cursor = {"error": str(exc)}
        errors["cursor"] = str(exc)
        cursor_status = SOURCE_ERROR

    source_states = (grok_status, cursor_status)
    if all(state == SOURCE_OK for state in source_states):
        status = STATUS_COMPLETE
    elif any(state == SOURCE_OK for state in source_states):
        status = STATUS_PARTIAL
    else:
        status = STATUS_FAILED

    sources = {
        "grok": {"status": grok_status},
        "cursor": {"status": cursor_status},
    }
    if errors.get("grok"):
        sources["grok"]["error"] = errors["grok"]
    if errors.get("cursor"):
        sources["cursor"]["error"] = errors["cursor"]

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
        print(one_line(snap))
        if written:
            out_dir = data_dir()
            print(f"wrote {out_dir / 'usage.json'}")
            print(f"wrote {out_dir / 'usage.txt'}")
        else:
            print("kept previous snapshot", file=sys.stderr)
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
                    print(f"refresh failed: {exc}", file=sys.stderr)
        return exit_code_for_snapshot(snap)
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.reason}", file=sys.stderr)
        if exc.code in (401, 403):
            print("token rejected; run `grok login`", file=sys.stderr)
        return 1
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"fatal: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
