"""Pure presentation mapping for the desktop pet UI."""

from __future__ import annotations

from datetime import datetime

POOL_META = {
    "sg": {"title": "SuperGrok", "tag": "周", "period": "周额度", "cover": "Chat / Build / Imagine 共用"},
    "bot": {"title": "Grok Bot", "tag": "周", "period": "周额度", "cover": "Cursor 账号独立池"},
    "cm": {"title": "Cursor 模型", "tag": "月", "period": "月额度", "cover": "Composer / Cursor 内置"},
    "om": {"title": "其他模型", "tag": "月", "period": "月额度", "cover": "GPT / Claude 等"},
    "cx": {"title": "Codex", "tag": "5h+周", "period": "5小时 + 周额度", "cover": "深色 5小时 · 浅色 周额度"},
}


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
    lines: list[str] = []
    limit = monthly.get("included_limit_cents")
    used = monthly.get("included_used_cents")
    if key == "other_models" and limit is not None:
        try:
            used_value = float(used or 0) / 100
            limit_value = float(limit) / 100
            lines.append(f"套餐内 ${used_value:.2f} / ${limit_value:.2f}")
        except (TypeError, ValueError):
            pass
    lines.append("按量付费 开" if monthly.get("on_demand_allowed") else "按量付费 关")
    return [line for line in lines if line]


def format_remaining_pct(value) -> str:
    if value is None:
        return "…"
    return f"{max(0.0, min(100.0, float(value))):.0f}%"


def format_pool_pct(pool: dict) -> str:
    layers = pool.get("layers") or []
    if layers:
        if all(layer.get("remaining") is None for layer in layers):
            return "…"
        return "  ".join(format_remaining_pct(layer.get("remaining")) for layer in layers)
    return format_remaining_pct(pool.get("remaining"))


def pool_remainings(pool: dict) -> list[float]:
    layers = pool.get("layers") or []
    if layers:
        vals: list[float] = []
        for layer in layers:
            remaining = layer.get("remaining")
            if remaining is not None:
                vals.append(float(remaining))
        return vals
    remaining = pool.get("remaining")
    return [float(remaining)] if remaining is not None else []


def _codex_window_layer(codex: dict, key: str, *, label: str, tone: str) -> dict:
    pool = codex.get(key) or {}
    return {
        "id": key,
        "label": label,
        "tone": tone,
        "remaining": pool.get("remaining_percent"),
        "reset": pool.get("resets_at"),
        "hint": pool.get("hint") or "",
    }


def _codex_pool_extra(codex: dict) -> list[str]:
    primary = codex.get("primary") or {}
    secondary = codex.get("secondary") or {}
    lines = [POOL_META["cx"]["cover"]]
    if primary.get("remaining_percent") is None and secondary.get("remaining_percent") is None:
        lines.append("ChatGPT 套餐内，本机登录只读")
        for pool in (primary, secondary):
            if pool.get("hint"):
                lines.append(str(pool["hint"]))
    return [line for line in lines if line]


def pool_tip_lines(pool: dict, *, fetching: bool = False) -> list[str]:
    lines = [str(pool.get("title") or "")]
    if pool.get("period"):
        lines.append(str(pool["period"]))
    layers = pool.get("layers") or []
    empty = "正在获取…" if fetching else "暂时没拿到，正在重试"
    if layers:
        if not pool_remainings(pool):
            lines.append(empty)
        else:
            lines.append(format_pool_pct(pool))
            for layer in layers:
                rem = layer.get("remaining")
                lines.append(f"{layer['label']}  {format_remaining_pct(rem)}")
                if rem is None:
                    continue
                when, left = format_reset(layer.get("reset"))
                lines.append(when)
                if left:
                    lines.append(left)
    elif pool.get("remaining") is None:
        lines.append(empty)
    else:
        lines.append(format_remaining_pct(pool.get("remaining")))
        when, left = format_reset(pool.get("reset"))
        lines.append(when)
        if left:
            lines.append(left)
    for extra in pool.get("extra") or []:
        lines.append(str(extra))
    return [line for line in lines if line]


def build_pools(snap: dict | None) -> dict:
    data = snap or {}
    cursor = data.get("cursor") or {}
    monthly = cursor.get("cursor_monthly") or {}
    codex = data.get("codex") or {}
    pools = {
        "sg": {
            "title": POOL_META["sg"]["title"],
            "tag": POOL_META["sg"]["tag"],
            "period": POOL_META["sg"]["period"],
            "remaining": data.get("remaining_percent"),
            "reset": (data.get("period") or {}).get("end"),
            "extra": [POOL_META["sg"]["cover"]],
        },
        "bot": {
            "title": POOL_META["bot"]["title"],
            "tag": POOL_META["bot"]["tag"],
            "period": POOL_META["bot"]["period"],
            "remaining": (cursor.get("grok_bot") or {}).get("remaining_percent"),
            "reset": (cursor.get("grok_bot") or {}).get("resets_at"),
            "extra": [POOL_META["bot"]["cover"]],
        },
        "cm": {
            "title": POOL_META["cm"]["title"],
            "tag": POOL_META["cm"]["tag"],
            "period": POOL_META["cm"]["period"],
            "remaining": (monthly.get("cursor_models") or {}).get("remaining_percent"),
            "reset": monthly.get("billing_cycle_end"),
            "extra": [line for line in (POOL_META["cm"]["cover"], *cursor_extra(monthly, "cursor_models")) if line],
        },
        "om": {
            "title": POOL_META["om"]["title"],
            "tag": POOL_META["om"]["tag"],
            "period": POOL_META["om"]["period"],
            "remaining": (monthly.get("other_models") or {}).get("remaining_percent"),
            "reset": monthly.get("billing_cycle_end"),
            "extra": [line for line in (POOL_META["om"]["cover"], *cursor_extra(monthly, "other_models")) if line],
        },
        "cx": {
            "title": POOL_META["cx"]["title"],
            "tag": POOL_META["cx"]["tag"],
            "period": POOL_META["cx"]["period"],
            "remaining": None,
            "reset": None,
            "layers": [
                _codex_window_layer(codex, "primary", label="5小时", tone="dark"),
                _codex_window_layer(codex, "secondary", label="周额度", tone="light"),
            ],
            "extra": _codex_pool_extra(codex),
        },
    }
    cx_vals = pool_remainings(pools["cx"])
    pools["cx"]["remaining"] = min(cx_vals) if cx_vals else None
    return pools
