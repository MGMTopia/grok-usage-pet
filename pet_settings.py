"""Compatible settings layout for the pet core and information modules."""

from __future__ import annotations

SETTINGS_SCHEMA = 2
SESSION_LAYOUT_KEYS = ("pinned", "expanded")
QUOTA_MODULE_ID = "quota"
QUOTA_SOURCE_IDS = ("sg", "bot", "cm", "om", "cx")
DEFAULT_QUOTA_ENABLED = {key: True for key in QUOTA_SOURCE_IDS}
CLOCK_MODULE_ID = "clock"
CLOCK_SOURCE_IDS = ("time", "timer")
DEFAULT_CLOCK_ENABLED = {key: True for key in CLOCK_SOURCE_IDS}
INFO_PANELS = ("quota", "clock")
LAYERS = ("pet", "interaction", "modules", "system")


def _as_dict(value: object) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def normalize_enabled(raw: object) -> dict[str, bool]:
    enabled = dict(DEFAULT_QUOTA_ENABLED)
    if not isinstance(raw, dict):
        return enabled
    for key in QUOTA_SOURCE_IDS:
        if key in raw:
            enabled[key] = bool(raw[key])
    if "cx" not in raw and ("cx5" in raw or "cxw" in raw):
        enabled["cx"] = bool(raw.get("cx5", True)) or bool(raw.get("cxw", True))
    return enabled


def quota_module_enabled(state: dict | None) -> bool:
    values = (state or {}).get("enabled") or {}
    return any(bool(values.get(key, False)) for key in QUOTA_SOURCE_IDS)


def normalize_clock_enabled(raw: object) -> dict[str, bool]:
    enabled = dict(DEFAULT_CLOCK_ENABLED)
    if not isinstance(raw, dict):
        return enabled
    for key in CLOCK_SOURCE_IDS:
        if key in raw:
            enabled[key] = bool(raw[key])
    return enabled


def clock_module_enabled(state: dict | None) -> bool:
    clock = _as_dict(_as_dict((state or {}).get("modules")).get(CLOCK_MODULE_ID))
    enabled = normalize_clock_enabled(clock.get("enabled"))
    return any(bool(enabled.get(key, False)) for key in CLOCK_SOURCE_IDS)


def normalize_info_panel(value: object) -> str:
    text = str(value or "").strip()
    return text if text in INFO_PANELS else "quota"


def clamp_info_panel(panel: str, available: tuple[str, ...]) -> str:
    if panel in available:
        return panel
    return available[0] if available else "quota"


def _quota_enabled_from(data: dict, modules: dict) -> dict[str, bool]:
    if isinstance(data.get("enabled"), dict):
        return normalize_enabled(data["enabled"])
    quota = _as_dict(modules.get(QUOTA_MODULE_ID))
    return normalize_enabled(quota.get("enabled"))


def normalize_state(raw: object) -> dict:
    """Classify v0.3 flat keys into pet / interaction / modules / system.

    Flat aliases stay in the result so current callers and older installs keep
    working. A broken quota blob must not drop pet-core fields.
    Autostart lives in hooks and scheduled tasks, not this file.
    """
    data = _as_dict(raw)
    for key in SESSION_LAYOUT_KEYS:
        data.pop(key, None)

    pet = _as_dict(data.get("pet"))
    interaction = _as_dict(data.get("interaction"))
    modules = _as_dict(data.get("modules"))
    system = _as_dict(data.get("system"))

    if "skin" in data:
        pet["skin"] = data["skin"]
    if "x" in data:
        pet["x"] = data["x"]
    if "y" in data:
        pet["y"] = data["y"]
    if "check_updates" in data:
        system["check_updates"] = data["check_updates"]
    if "last_update_check" in data:
        system["last_update_check"] = data["last_update_check"]
    panel = data.get("info_panel")
    if panel is None:
        panel = interaction.get("info_panel")
    interaction["info_panel"] = normalize_info_panel(panel)

    enabled = _quota_enabled_from(data, modules)
    quota = _as_dict(modules.get(QUOTA_MODULE_ID))
    quota["enabled"] = enabled
    modules[QUOTA_MODULE_ID] = quota

    clock = _as_dict(modules.get(CLOCK_MODULE_ID))
    clock["enabled"] = normalize_clock_enabled(clock.get("enabled"))
    if "timer_running" in clock:
        clock["timer_running"] = bool(clock.get("timer_running"))
    if "timer_accumulated_ms" in clock:
        try:
            clock["timer_accumulated_ms"] = max(0.0, float(clock.get("timer_accumulated_ms") or 0))
        except (TypeError, ValueError):
            clock["timer_accumulated_ms"] = 0.0
    modules[CLOCK_MODULE_ID] = clock

    out = dict(data)
    out["schema"] = SETTINGS_SCHEMA
    out["pet"] = pet
    out["interaction"] = interaction
    out["modules"] = modules
    out["system"] = system
    out["enabled"] = enabled
    if "skin" in pet:
        out["skin"] = pet["skin"]
    if "x" in pet:
        out["x"] = pet["x"]
    if "y" in pet:
        out["y"] = pet["y"]
    if "check_updates" in system:
        out["check_updates"] = system["check_updates"]
    if "last_update_check" in system:
        out["last_update_check"] = system["last_update_check"]
    out["info_panel"] = interaction["info_panel"]
    return out
