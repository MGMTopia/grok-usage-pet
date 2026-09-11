"""Local clock information module: current time and a stopwatch."""

from __future__ import annotations

from datetime import datetime

from info_modules import ModulePermission, ModuleRefreshResult, ModuleSpec
from pet_settings import CLOCK_MODULE_ID, CLOCK_SOURCE_IDS, clock_module_enabled

CLOCK_SPEC = ModuleSpec(
    id=CLOCK_MODULE_ID,
    title="时钟",
    refresh_ms=None,
    permissions=(
        ModulePermission("本机", "只读系统时间，不上网，不读取任何账号"),
    ),
)

CLOCK_ROW_IDS = ("clk", "tmr")
CLOCK_ROW_BY_SOURCE = {"time": "clk", "timer": "tmr"}
WEEKDAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
PANEL_TAB_H = 30
CLOCK_TIME_H = 90
CLOCK_TIMER_H = 156
COUNTDOWN_PRESETS = (1, 5, 10, 25)
DEFAULT_COUNTDOWN_MS = 5 * 60 * 1000
MAX_COUNTDOWN_MS = 99 * 60 * 1000


def normalize_clock_state(raw: object) -> dict:
    data = dict(raw) if isinstance(raw, dict) else {}
    enabled = data.get("enabled") if isinstance(data.get("enabled"), dict) else {}
    mode = str(data.get("timer_mode") or "countdown")
    if mode not in ("stopwatch", "countdown"):
        mode = "countdown"
    try:
        countdown_ms = int(float(data.get("countdown_ms") or DEFAULT_COUNTDOWN_MS))
    except (TypeError, ValueError):
        countdown_ms = DEFAULT_COUNTDOWN_MS
    countdown_ms = max(60_000, min(MAX_COUNTDOWN_MS, countdown_ms))
    out = {
        "enabled": {
            "time": bool(enabled["time"]) if "time" in enabled else True,
            "timer": bool(enabled["timer"]) if "timer" in enabled else True,
        },
        "timer_mode": mode,
        "countdown_ms": countdown_ms,
        "timer_running": bool(data.get("timer_running", False)),
        "timer_accumulated_ms": max(0.0, float(data.get("timer_accumulated_ms") or 0)),
        "timer_started_at": data.get("timer_started_at"),
        "timer_ringing": bool(data.get("timer_ringing", False)),
    }
    started = out["timer_started_at"]
    if started is not None:
        try:
            out["timer_started_at"] = float(started)
        except (TypeError, ValueError):
            out["timer_running"] = False
            out["timer_started_at"] = None
    return out


def format_clock_time(moment: datetime) -> str:
    return moment.strftime("%H:%M:%S")


def format_elapsed(ms: float) -> str:
    total = int(max(0.0, float(ms)) // 1000)
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def timer_elapsed_ms(clock: dict, now: float) -> float:
    acc = max(0.0, float(clock.get("timer_accumulated_ms") or 0))
    if not clock.get("timer_running"):
        return acc
    started = clock.get("timer_started_at")
    if started is None:
        return acc
    try:
        started_at = float(started)
    except (TypeError, ValueError):
        return acc
    return acc + max(0.0, (float(now) - started_at) * 1000.0)


def countdown_remaining_ms(clock: dict, now: float) -> float:
    state = normalize_clock_state(clock)
    return max(0.0, float(state["countdown_ms"]) - timer_elapsed_ms(state, now))


def advance_timer(clock: dict, now: float) -> dict:
    state = normalize_clock_state(clock)
    if state["timer_mode"] != "countdown" or not state["timer_running"]:
        return state
    if countdown_remaining_ms(state, now) > 0:
        return state
    state["timer_running"] = False
    state["timer_accumulated_ms"] = float(state["countdown_ms"])
    state["timer_started_at"] = None
    state["timer_ringing"] = True
    return state


def toggle_timer(clock: dict, now: float) -> dict:
    state = normalize_clock_state(clock)
    now_ts = float(now)
    if state["timer_ringing"]:
        state["timer_ringing"] = False
        state["timer_accumulated_ms"] = 0.0
        state["timer_running"] = False
        state["timer_started_at"] = None
        return state
    if state["timer_running"]:
        state["timer_accumulated_ms"] = timer_elapsed_ms(state, now_ts)
        state["timer_running"] = False
        state["timer_started_at"] = None
        return state
    if state["timer_mode"] == "countdown" and state["timer_accumulated_ms"] >= float(state["countdown_ms"]):
        state["timer_accumulated_ms"] = 0.0
    state["timer_running"] = True
    state["timer_started_at"] = now_ts
    state["timer_ringing"] = False
    return state


def reset_timer(clock: dict) -> dict:
    state = normalize_clock_state(clock)
    state["timer_running"] = False
    state["timer_accumulated_ms"] = 0.0
    state["timer_started_at"] = None
    state["timer_ringing"] = False
    return state


def set_timer_mode(clock: dict, mode: str) -> dict:
    state = reset_timer(clock)
    state["timer_mode"] = "stopwatch" if mode == "stopwatch" else "countdown"
    return state


def set_countdown_minutes(clock: dict, minutes: int) -> dict:
    state = reset_timer(clock)
    state["timer_mode"] = "countdown"
    state["countdown_ms"] = max(60_000, min(MAX_COUNTDOWN_MS, int(minutes) * 60_000))
    return state


def alarm_hand_angles(elapsed_ms: float, remaining_ms: float, *, countdown: bool) -> tuple[float, float, float]:
    seconds = (remaining_ms if countdown else elapsed_ms) / 1000.0
    sec = seconds % 60.0
    minute = (seconds / 60.0) % 60.0
    hour = (seconds / 3600.0) % 12.0
    return hour * 30.0, minute * 6.0, sec * 6.0


def clock_panel_available(enabled: dict[str, bool] | None) -> bool:
    values = enabled or {}
    return any(bool(values.get(key)) for key in CLOCK_SOURCE_IDS)


def clock_panel_height(enabled: dict[str, bool] | None, *, tabs: bool) -> int:
    body = 0
    values = enabled or {}
    if values.get("time"):
        body += CLOCK_TIME_H
    if values.get("timer"):
        body += CLOCK_TIMER_H
    if not body:
        body = 48
    return (PANEL_TAB_H if tabs else 0) + body


def clock_panel_view(
    enabled: dict[str, bool] | None,
    clock: dict,
    *,
    now: float,
    moment: datetime | None = None,
    language: str = "zh-CN",
) -> dict:
    english = str(language).lower().startswith("en")
    when = moment or datetime.fromtimestamp(now)
    state = normalize_clock_state(clock)
    elapsed = timer_elapsed_ms(state, now)
    running = bool(state["timer_running"])
    ringing = bool(state["timer_ringing"])
    countdown = state["timer_mode"] == "countdown"
    remaining = countdown_remaining_ms(state, now) if countdown else 0.0
    duration = float(state["countdown_ms"])
    if ringing:
        status = "Time's up" if english else "时间到"
        display_ms = 0.0 if countdown else elapsed
        toggle = "Stop" if english else "关掉"
    elif running:
        status = ("Counting down" if countdown else "Timing") if english else ("倒计时中" if countdown else "计时中")
        display_ms = remaining if countdown else elapsed
        toggle = "Pause" if english else "暂停"
    elif (countdown and remaining < duration) or (not countdown and elapsed > 0):
        status = "Paused" if english else "已暂停"
        display_ms = remaining if countdown else elapsed
        toggle = "Resume" if english else "继续"
    else:
        status = "Ready" if english else "待开始"
        display_ms = remaining if countdown else elapsed
        toggle = "Start" if english else "开始"
    hour_deg, minute_deg, second_deg = alarm_hand_angles(elapsed, remaining, countdown=countdown)
    values = enabled or {}
    return {
        "show_time": bool(values.get("time")),
        "show_timer": bool(values.get("timer")),
        "weekday": when.strftime("%a") if english else WEEKDAYS[when.weekday()],
        "date": when.strftime("%b %d") if english else f"{when.month}月{when.day}日",
        "hours": f"{when.hour:02d}",
        "minutes": f"{when.minute:02d}",
        "seconds": f"{when.second:02d}",
        "colon_on": int(now) % 2 == 0,
        "caption": "Local time" if english else "本地时间",
        "timer_mode": state["timer_mode"],
        "timer_caption": ("Countdown" if countdown else "Stopwatch") if english else ("倒计时" if countdown else "秒表"),
        "timer_status": status,
        "timer_text": format_elapsed(display_ms),
        "timer_running": running,
        "timer_ringing": ringing,
        "elapsed_ms": elapsed,
        "remaining_ms": remaining,
        "duration_ms": duration,
        "progress": (remaining / duration) if countdown and duration else 0.0,
        "hour_deg": hour_deg,
        "minute_deg": minute_deg,
        "second_deg": second_deg,
        "presets": tuple(
            {"minutes": mins, "label": f"{mins}m" if english else f"{mins}分", "selected": int(duration) == mins * 60_000}
            for mins in COUNTDOWN_PRESETS
        ),
        "toggle_label": toggle,
        "reset_label": "Reset" if english else "归零",
    }


def visible_clock_rows(enabled: dict[str, bool] | None) -> tuple[str, ...]:
    values = enabled or {}
    return tuple(
        CLOCK_ROW_BY_SOURCE[source]
        for source in CLOCK_SOURCE_IDS
        if values.get(source)
    )


def clock_rows(
    enabled: dict[str, bool] | None,
    clock: dict,
    *,
    now: float,
    moment: datetime | None = None,
) -> dict[str, dict]:
    state = normalize_clock_state(clock)
    when = moment or datetime.fromtimestamp(now)
    rows: dict[str, dict] = {}
    if (enabled or {}).get("time"):
        rows["clk"] = {
            "title": "时间",
            "tag": "本地",
            "period": "现在",
            "remaining": None,
            "show_bar": False,
            "value_text": format_clock_time(when),
            "extra": ["本机系统时间"],
        }
    if (enabled or {}).get("timer"):
        elapsed = timer_elapsed_ms(state, now)
        running = bool(state["timer_running"])
        rows["tmr"] = {
            "title": "计时",
            "tag": "秒表",
            "period": "计时",
            "remaining": None,
            "show_bar": False,
            "value_text": format_elapsed(elapsed),
            "extra": [
                "运行中，单击暂停" if running else "单击开始，右键可归零",
            ],
        }
    return rows


class ClockModule:
    spec = CLOCK_SPEC

    def wants_refresh(self, enabled: dict[str, bool] | None) -> bool:
        return False

    def visible_rows(self, enabled: dict[str, bool] | None) -> tuple[str, ...]:
        return visible_clock_rows(enabled)

    def rows(self, enabled: dict[str, bool] | None, clock: dict, now: float) -> dict[str, dict]:
        return clock_rows(enabled, clock, now=now)

    def refresh(self) -> ModuleRefreshResult:
        return ModuleRefreshResult(ok=True)

    def is_enabled(self, clock_enabled: dict[str, bool] | None) -> bool:
        return clock_module_enabled({"modules": {CLOCK_MODULE_ID: {"enabled": clock_enabled or {}}}})
