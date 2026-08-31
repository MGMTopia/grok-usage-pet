"""Pure usage snapshot conversions and presentation helpers."""

from __future__ import annotations

from datetime import datetime, timezone


STATUS_COMPLETE = "complete"
STATUS_PARTIAL = "partial"
STATUS_FAILED = "failed"
SOURCE_OK = "ok"
SOURCE_UNAVAILABLE = "unavailable"
SOURCE_ERROR = "error"


def as_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def ms_to_iso(ms) -> str | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def seconds_until(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        end = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return max(0, int((end - datetime.now(timezone.utc)).total_seconds()))
    except ValueError:
        return None


def one_line(snap: dict) -> str:
    if snap.get("status") == STATUS_FAILED:
        errors = snap.get("errors") or {}
        detail = " · ".join(str(value) for value in errors.values())
        suffix = f" | {detail}" if detail else ""
        return f"usage unavailable{suffix}"
    products = snap.get("products_used_percent") or {}
    bits = [f"{key.replace('Grok', '')} {value:.0f}%" for key, value in sorted(products.items())]
    product_part = " · ".join(bits) if bits else "no product split"
    reset = snap.get("period", {}).get("end") or "?"
    plan = snap.get("plan") or "Grok"
    remaining = snap.get("remaining_percent")
    line = ""
    if remaining is not None:
        used = snap.get("used_percent")
        used_txt = f"{used:.0f}%" if used is not None else "—"
        line = f"{plan} remaining {remaining:.0f}% (used {used_txt}) | {product_part} | resets {reset}"
    bot = ((snap.get("cursor") or {}).get("grok_bot") or {})
    if bot.get("remaining_percent") is not None:
        bot_reset = bot.get("resets_at") or "?"
        separator = " || " if line else ""
        line += (
            f"{separator}Grok Bot remaining {bot['remaining_percent']:.1f}% "
            f"(used {bot.get('used_percent', 0):.1f}%) | resets {bot_reset}"
        )
    monthly = ((snap.get("cursor") or {}).get("cursor_monthly") or {})
    for key, label in (("cursor_models", "Cursor模型"), ("other_models", "其他模型")):
        pool = monthly.get(key) or {}
        if pool.get("remaining_percent") is not None:
            separator = " || " if line else ""
            line += f"{separator}{label} remaining {pool['remaining_percent']:.1f}%"
    codex = snap.get("codex") or {}
    for key, label in (("primary", "Codex 5小时"), ("secondary", "Codex 周额度")):
        pool = codex.get(key) or {}
        if pool.get("remaining_percent") is not None:
            separator = " || " if line else ""
            line += f"{separator}{label} remaining {pool['remaining_percent']:.1f}%"
    return line or "usage unavailable"


def snapshot_is_usable(snap: dict) -> bool:
    return snap.get("status") in (STATUS_COMPLETE, STATUS_PARTIAL)


def exit_code_for_snapshot(snap: dict) -> int:
    return 0 if snapshot_is_usable(snap) else 1
