"""Pure presentation mapping for the desktop pet UI."""

from __future__ import annotations

from datetime import datetime


def format_reset(iso: str | None) -> tuple[str, str]:
    if not iso:
        return "到期时间未知", ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return str(iso), ""
    local = dt.astimezone()
    now = datetime.now().astimezone()
    seconds = max(0, int((local - now).total_seconds()))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    if days:
        left = f"还剩 {days} 天 {hours} 小时"
    elif hours:
        left = f"还剩 {hours} 小时 {minutes} 分"
    else:
        left = f"还剩 {minutes} 分钟"
    return f"重置 {local.strftime('%m月%d日 %H:%M')}", left


def cursor_extra(monthly: dict, key: str) -> list[str]:
    pool = monthly.get(key) or {}
    lines = [pool.get("hint") or ""]
    limit = monthly.get("included_limit_cents")
    used = monthly.get("included_used_cents")
    if key == "other_models" and limit is not None:
        try:
            used_value = float(used or 0) / 100
            limit_value = float(limit) / 100
            lines.append(f"套餐内 ${used_value:.2f} / ${limit_value:.2f}")
        except (TypeError, ValueError):
            pass
    lines.append("On-Demand 开" if monthly.get("on_demand_allowed") else "On-Demand 关")
    if monthly.get("display_message") and key == "other_models":
        lines.append(str(monthly["display_message"]))
    hint_message = pool.get("display_message")
    if hint_message:
        lines.append(str(hint_message))
    return [line for line in lines if line]


def build_pools(snap: dict | None) -> dict:
    data = snap or {}
    cursor = data.get("cursor") or {}
    monthly = cursor.get("cursor_monthly") or {}
    return {
        "sg": {
            "title": "SuperGrok",
            "remaining": data.get("remaining_percent"),
            "reset": (data.get("period") or {}).get("end"),
            "extra": ["Chat / Build / Imagine 共用周池"],
        },
        "bot": {
            "title": "Grok Bot",
            "remaining": (cursor.get("grok_bot") or {}).get("remaining_percent"),
            "reset": (cursor.get("grok_bot") or {}).get("resets_at"),
            "extra": ["Cursor 账号上的独立周额度"],
        },
        "cm": {
            "title": "Cursor 模型",
            "remaining": (monthly.get("cursor_models") or {}).get("remaining_percent"),
            "reset": monthly.get("billing_cycle_end"),
            "extra": cursor_extra(monthly, "cursor_models"),
        },
        "om": {
            "title": "其他模型",
            "remaining": (monthly.get("other_models") or {}).get("remaining_percent"),
            "reset": monthly.get("billing_cycle_end"),
            "extra": cursor_extra(monthly, "other_models"),
        },
    }
