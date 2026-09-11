"""Pure presentation mapping for the desktop pet UI."""

from __future__ import annotations

from datetime import datetime

POOL_META = {
    "sg": {"title": "SuperGrok", "tag": "周", "period": "周额度", "cover": "Chat / Build / Imagine 共用"},
    "bot": {"title": "Grok Bot", "tag": "周", "period": "周额度", "cover": "Cursor 账号独立池"},
    "cm": {"title": "Cursor 模型", "tag": "月", "period": "月额度", "cover": "Composer / Cursor 内置"},
    "om": {"title": "其他模型", "tag": "月", "period": "月额度", "cover": "GPT / Claude 等"},
    "cx": {"title": "Codex", "tag": "5h+周", "period": "5小时 + 周额度", "cover": "5小时同其它条 · 周额度略深"},
}


def format_reset(iso: str | None, *, language: str = "zh-CN") -> tuple[str, str]:
    english = str(language).lower().startswith("en")
    if not iso:
        return ("Reset time unavailable" if english else "到期时间未知"), ""
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
        left = f"{days}d {hours}h remaining" if english else f"还剩 {days} 天 {hours} 小时"
    elif hours:
        left = f"{hours}h {minutes}m remaining" if english else f"还剩 {hours} 小时 {minutes} 分"
    else:
        left = f"{minutes}m remaining" if english else f"还剩 {minutes} 分钟"
    stamp = local.strftime("%b %d %H:%M") if english else local.strftime("%m月%d日 %H:%M")
    return (f"Resets {stamp}" if english else f"重置 {stamp}"), left


def cursor_extra(monthly: dict, key: str, *, language: str = "zh-CN") -> list[str]:
    english = str(language).lower().startswith("en")
    lines: list[str] = []
    limit = monthly.get("included_limit_cents")
    used = monthly.get("included_used_cents")
    if key == "other_models" and limit is not None:
        try:
            used_value = float(used or 0) / 100
            limit_value = float(limit) / 100
            lines.append((f"Included ${used_value:.2f} / ${limit_value:.2f}") if english else f"套餐内 ${used_value:.2f} / ${limit_value:.2f}")
        except (TypeError, ValueError):
            pass
    lines.append(("On-demand enabled" if monthly.get("on_demand_allowed") else "On-demand disabled") if english else ("按量付费 开" if monthly.get("on_demand_allowed") else "按量付费 关"))
    return [line for line in lines if line]


def remaining_bar_level(value) -> str:
    """Map remaining percent to bar color band.

    Matches the fetch animation: remaining < 20 is low, 20–50 is mid, >= 50 is ok.
    """
    pct = max(0.0, min(100.0, float(value)))
    if pct < 20:
        return "low"
    if pct < 50:
        return "mid"
    return "ok"


def format_remaining_pct(value) -> str:
    if value is None:
        return "…"
    return f"{max(0.0, min(100.0, float(value))):.0f}%"


def format_pool_pct(pool: dict) -> str:
    if pool.get("value_text") is not None:
        return str(pool.get("value_text") or "")
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


def pool_tip_lines(pool: dict, *, fetching: bool = False, language: str = "zh-CN") -> list[str]:
    english = str(language).lower().startswith("en")
    lines = [str(pool.get("title") or "")]
    if pool.get("period"):
        lines.append(str(pool["period"]))
    layers = pool.get("layers") or []
    empty = ("Fetching…" if fetching else "Unavailable; retrying") if english else ("正在获取…" if fetching else "暂时没拿到，正在重试")
    if pool.get("value_text") is not None:
        lines.append(str(pool.get("value_text") or ""))
        for extra in pool.get("extra") or []:
            lines.append(str(extra))
        return [line for line in lines if line]
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
                when, left = format_reset(layer.get("reset"), language=language)
                lines.append(when)
                if left:
                    lines.append(left)
    elif pool.get("remaining") is None:
        lines.append(empty)
    else:
        lines.append(format_remaining_pct(pool.get("remaining")))
        when, left = format_reset(pool.get("reset"), language=language)
        lines.append(when)
        if left:
            lines.append(left)
    for extra in pool.get("extra") or []:
        lines.append(str(extra))
    return [line for line in lines if line]


def build_pools(snap: dict | None, *, language: str = "zh-CN") -> dict:
    english = str(language).lower().startswith("en")
    meta = POOL_META if not english else {
        "sg": {"title": "SuperGrok", "tag": "Weekly", "period": "Weekly allowance", "cover": "Shared by Chat / Build / Imagine"},
        "bot": {"title": "Grok Bot", "tag": "Weekly", "period": "Weekly allowance", "cover": "Separate pool for the Cursor account"},
        "cm": {"title": "Cursor models", "tag": "Monthly", "period": "Monthly allowance", "cover": "Composer / built-in Cursor models"},
        "om": {"title": "Other models", "tag": "Monthly", "period": "Monthly allowance", "cover": "GPT / Claude and others"},
        "cx": {"title": "Codex", "tag": "5h + weekly", "period": "5-hour + weekly allowance", "cover": "5-hour window plus weekly allowance"},
    }
    data = snap or {}
    cursor = data.get("cursor") or {}
    monthly = cursor.get("cursor_monthly") or {}
    codex = data.get("codex") or {}
    pools = {
        "sg": {
            "title": meta["sg"]["title"],
            "tag": meta["sg"]["tag"],
            "period": meta["sg"]["period"],
            "remaining": data.get("remaining_percent"),
            "reset": (data.get("period") or {}).get("end"),
            "extra": [meta["sg"]["cover"]],
        },
        "bot": {
            "title": meta["bot"]["title"],
            "tag": meta["bot"]["tag"],
            "period": meta["bot"]["period"],
            "remaining": (cursor.get("grok_bot") or {}).get("remaining_percent"),
            "reset": (cursor.get("grok_bot") or {}).get("resets_at"),
            "extra": [meta["bot"]["cover"]],
        },
        "cm": {
            "title": meta["cm"]["title"],
            "tag": meta["cm"]["tag"],
            "period": meta["cm"]["period"],
            "remaining": (monthly.get("cursor_models") or {}).get("remaining_percent"),
            "reset": monthly.get("billing_cycle_end"),
            "extra": [line for line in (meta["cm"]["cover"], *cursor_extra(monthly, "cursor_models", language=language)) if line],
        },
        "om": {
            "title": meta["om"]["title"],
            "tag": meta["om"]["tag"],
            "period": meta["om"]["period"],
            "remaining": (monthly.get("other_models") or {}).get("remaining_percent"),
            "reset": monthly.get("billing_cycle_end"),
            "extra": [line for line in (meta["om"]["cover"], *cursor_extra(monthly, "other_models", language=language)) if line],
        },
        "cx": {
            "title": meta["cx"]["title"],
            "tag": meta["cx"]["tag"],
            "period": meta["cx"]["period"],
            "remaining": None,
            "reset": None,
            "layers": [
                _codex_window_layer(codex, "primary", label="5 hours" if english else "5小时", tone="light"),
                _codex_window_layer(codex, "secondary", label="Weekly" if english else "周额度", tone="dark"),
            ],
            "extra": ([meta["cx"]["cover"], "Read-only local ChatGPT plan session"] if english else _codex_pool_extra(codex)),
        },
    }
    cx_vals = pool_remainings(pools["cx"])
    pools["cx"]["remaining"] = min(cx_vals) if cx_vals else None
    return pools
