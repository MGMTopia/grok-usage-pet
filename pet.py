#!/usr/bin/env python3
"""Desktop pet that shows SuperGrok + Grok Bot remaining usage."""

from __future__ import annotations

import json
import math
import os
import queue
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import Menu
from tkinter import font as tkfont

if getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))))
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import fetch_usage as fu
import cursor_hooks
import skin_catalog
import app_update
import info_modules
import clock_module
from app_version import APP_VERSION, INSTALL_MARKER_NAME, INSTALL_MARKER_VALUE
from snapshot_store import write_text_atomic
from pet_settings import (
    DEFAULT_QUOTA_ENABLED,
    SESSION_LAYOUT_KEYS,
    clamp_info_panel,
    normalize_enabled,
    normalize_info_panel,
    normalize_state,
)
from pet_view_model import (
    POOL_META,
    build_pools,
    format_pool_pct,
    pool_remainings,
    pool_tip_lines,
    remaining_bar_level,
)
from skin_catalog import SkinCatalog

DATA_DIR = fu.data_dir()
LOCK_FILE = DATA_DIR / "pet.lock"
RAISE_FILE = DATA_DIR / "pet.raise"
STATE_FILE = DATA_DIR / "pet_state.json"
SKINS_DIR = fu.resource_dir() / "skins"
LEGACY_ASSETS = fu.resource_dir() / "assets"
DEFAULT_SKIN_ID = "original"
DEFAULT_THEME_PRESET = "soft"
ASSETS = LEGACY_ASSETS
HOOK_FILE = fu.grok_home() / "hooks" / "usage-pet.json"
CURSOR_HOOK_FILE = Path.home() / ".cursor" / "hooks.json"
CURSOR_HOOK_MARKER = cursor_hooks.MARKER
GROK_HOOK_MARKER = "grok-usage-pet"
BG = "#1b1b1f"
CHROMA = "#ff00ff"
CHROMA_RGB = (255, 0, 255)
REFRESH_MS = 60_000
TICK_MS = 40
MAX_ANIM_ELAPSED_MS = 250
LOOK_SECTORS = 16
LOOK_STEP_DEGREES = 360.0 / LOOK_SECTORS
LOOK_TRANSITION_MS = 55
LOOK_SECTOR_HYSTERESIS_DEGREES = 2.5
LOOK_ENTER_DISTANCE = (48, 330)
LOOK_STAY_DISTANCE = (32, 360)
COLLAPSE_MS = 380
IDLE_WAVE_S = 300.0
CELL_W = 192
CELL_H = 208
SPRITE_W = 192
SPRITE_H = 208
# Skin manifests pick a preset via theme.preset. "classic" is compatibility-only.
STYLES = {
    "classic": {
        "row_h": 38,
        "bubble_w": 280,
        "bubble_top": 8,
        "bubble_fill": "#111111",
        "bubble_outline": "#333333",
        "bubble_shadow": "#111111",
        "label": "#9aa0a6",
        "label_hot": "#e8e8e8",
        "bar_track": "#2a2a2a",
        "bar_ok": "#3ddc97",
        "bar_mid": "#f5c542",
        "bar_low": "#ff6b6b",
        "bar_layer_light": "#86e0b8",
        "bar_layer_dark": "#1f9a64",
        "pct": "#ffffff",
        "tip_fill": "#16161c",
        "tip_outline": "#5eead4",
        "tip_title": "#5eead4",
        "tip_text": "#f4f4f5",
        "spinner": "#5eead4",
        "font": ("Microsoft YaHei UI", 8),
        "font_title": ("Microsoft YaHei UI", 8, "bold"),
        "font_ui": ("Microsoft YaHei UI", 10),
        "settings_bg": "#1b1b1f",
        "settings_fg": "#e8e8e8",
        "settings_muted": "#9aa0a6",
        "settings_text": "#f4f4f5",
        "settings_select": "#111111",
        "settings_active": "#ffffff",
        "muted": "#9aa0a6",
        "radius": 0,
        "accent": "#5eead4",
        "inner": "#16161c",
        "decoration": "none",
        "bar_style": "square",
        "bubble_style": "classic",
        "tip_style": "square",
    },
    "kawaii": {
        "row_h": 44,
        "bubble_w": 292,
        "bubble_top": 20,
        "bubble_bottom": 14,
        "bubble_fill": "#fff7f2",
        "bubble_outline": "#e4b6ad",
        "bubble_shadow": "#efd2c8",
        "label": "#7a5348",
        "label_hot": "#c4453c",
        "bar_track": "#f4e0d8",
        "bar_ok": "#e07a7a",
        "bar_mid": "#e0b36a",
        "bar_low": "#c94b4b",
        "bar_layer_light": "#e8a49a",
        "bar_layer_dark": "#c4453c",
        "pct": "#7a5348",
        "tip_fill": "#fffaf6",
        "tip_outline": "#e4b6ad",
        "tip_title": "#c4453c",
        "tip_text": "#6b4a42",
        "spinner": "#c94b4b",
        "font": ("Microsoft YaHei UI", 9),
        "font_title": ("Microsoft YaHei UI", 9, "bold"),
        "font_ui": ("Microsoft YaHei UI", 10),
        "settings_bg": "#fff7f2",
        "settings_fg": "#5a4038",
        "settings_muted": "#a07a72",
        "settings_text": "#5a4038",
        "settings_select": "#f4e0d8",
        "settings_active": "#c4453c",
        "muted": "#a07a72",
        "radius": 18,
        "accent": "#c94b4b",
        "inner": "#ffffff",
        "decoration": "bow",
        "bar_style": "rounded",
        "bubble_style": "rounded",
        "tip_style": "rounded",
    },
}
STYLES["soft"] = dict(STYLES["kawaii"])
STYLES["soft"]["radius"] = 28
STYLES["tech"] = {
    "row_h": 44,
    "bubble_w": 292,
    "bubble_top": 20,
    "bubble_bottom": 14,
    "bubble_fill": "#10243A",
    "bubble_outline": "#2A6B7A",
    "bubble_shadow": "#0A1826",
    "label": "#9ED8E0",
    "label_hot": "#45DFF2",
    "bar_track": "#163044",
    "bar_ok": "#3DDC97",
    "bar_mid": "#E0B36A",
    "bar_low": "#E05A5A",
    "bar_layer_light": "#7BE7C4",
    "bar_layer_dark": "#2BB07A",
    "pct": "#D7F6FA",
    "tip_fill": "#10243A",
    "tip_outline": "#45DFF2",
    "tip_title": "#45DFF2",
    "tip_text": "#D7F6FA",
    "spinner": "#45DFF2",
    "font": ("Microsoft YaHei UI", 9),
    "font_title": ("Microsoft YaHei UI", 9, "bold"),
    "font_ui": ("Microsoft YaHei UI", 10),
    "settings_bg": "#0C1C2A",
    "settings_fg": "#D7F6FA",
    "settings_muted": "#7AA3A8",
    "settings_text": "#D7F6FA",
    "settings_select": "#163044",
    "settings_active": "#45DFF2",
    "muted": "#7AA3A8",
    "radius": 28,
    "accent": "#45DFF2",
    "inner": "#163044",
    "decoration": "circuit",
    "bar_style": "rounded",
    "bubble_style": "rounded",
    "tip_style": "rounded",
}
_THEME_COLOR_KEYS = {
    "bubbleFill": "bubble_fill",
    "bubbleOutline": "bubble_outline",
    "bubbleShadow": "bubble_shadow",
    "label": "label",
    "labelHot": "label_hot",
    "barTrack": "bar_track",
    "barOk": "bar_ok",
    "barMid": "bar_mid",
    "barLow": "bar_low",
    "percentage": "pct",
    "tipFill": "tip_fill",
    "tipOutline": "tip_outline",
    "tipTitle": "tip_title",
    "tipText": "tip_text",
    "spinner": "spinner",
    "accent": "accent",
    "inner": "inner",
    "settingsBackground": "settings_bg",
    "settingsForeground": "settings_fg",
    "settingsMuted": "settings_muted",
    "muted": "muted",
    "barLayerLight": "bar_layer_light",
    "barLayerDark": "bar_layer_dark",
}
_THEME_ENUM_KEYS = {
    "bubbleStyle": ("bubble_style", {"rounded", "classic"}),
    "barStyle": ("bar_style", {"rounded", "square"}),
    "tipStyle": ("tip_style", {"rounded", "square"}),
    "decoration": ("decoration", {"none", "bow", "circuit"}),
}
_SESSION_LAYOUT_KEYS = SESSION_LAYOUT_KEYS
_ACTIVE_STYLE: dict | None = None
_THEME_PRESETS = ("tech", "soft", "classic")
BUBBLE_ROWS = ("sg", "bot", "cm", "om", "cx")
ROW_LABELS = {key: POOL_META[key]["title"] for key in BUBBLE_ROWS}
DEFAULT_ENABLED = dict(DEFAULT_QUOTA_ENABLED)
ATLAS_NAME = "spritesheet.webp"
ATLAS_SIZE = (1536, 2288)
ANIMATIONS = {
    "idle": (0, 6),
    "running-right": (1, 8),
    "running-left": (2, 8),
    "waving": (3, 4),
    "jumping": (4, 5),
    "failed": (5, 8),
    "waiting": (6, 6),
    "running": (7, 6),
    "review": (8, 6),
}
ANIM_MS = {
    "idle": 260,
    "running-right": 110,
    "running-left": 110,
    "waving": 170,
    "jumping": 140,
    "failed": 200,
    "waiting": 200,
    "running": 140,
    "review": 200,
}
ONESHOT_ANIMS = {"jumping", "waving", "failed", "waiting"}
LOOK_ROWS = ((9, 8), (10, 8))

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None


SKIN_CATALOG = SkinCatalog(
    SKINS_DIR,
    DEFAULT_SKIN_ID,
    ANIMATIONS,
    ANIM_MS,
)


def _frame_clock_steps(accumulator_ms: float, elapsed_ms: float, delay_ms: int) -> tuple[int, float]:
    """Return due animation steps while preserving sub-frame timing remainder."""
    delay = max(1, int(delay_ms))
    elapsed = max(0.0, min(float(elapsed_ms), float(MAX_ANIM_ELAPSED_MS)))
    total = max(0.0, float(accumulator_ms)) + elapsed
    steps = int(total // delay)
    return steps, total - steps * delay


def quota_fetch_oneshot(
    remainings: list[float],
    *,
    error: bool = False,
    has_snap: bool = True,
) -> str | None:
    """Pick the one-shot to play after a usable quota fetch."""
    worst = min(remainings) if remainings else None
    if worst is not None and worst < 20:
        return "failed"
    if not remainings and error and has_snap:
        return "failed"
    if worst is not None and worst > 20:
        return "waiting"
    return None


def idle_wave_due(last_activity: float, now: float, idle_s: float = IDLE_WAVE_S) -> bool:
    return (now - last_activity) >= idle_s


def quota_sources_enabled(enabled: dict[str, bool] | None) -> bool:
    """Return whether any optional quota provider is enabled.

    The desktop-pet core must remain usable when every information source is
    disabled.  Keep this check limited to the known provider keys so legacy
    or future settings cannot accidentally enable network work.
    """
    values = enabled or {}
    return any(bool(values.get(key, False)) for key in BUBBLE_ROWS)


def resolve_animation_state(
    *,
    dragging: bool,
    drag_dx: int,
    oneshot: str | None,
    look_target: int | None,
    snapshot_present: bool,
    busy: bool,
    bars_visible: bool,
    animations: dict[str, list] | set[str],
    quota_enabled: bool = True,
    current_animation: str | None = None,
) -> str | None:
    """Resolve the explicit animation priority without touching UI state."""
    available = set(animations)
    if dragging:
        if drag_dx < 0 and "running-left" in available:
            return "running-left"
        if drag_dx > 0 and "running-right" in available:
            return "running-right"
        if current_animation in ("running-left", "running-right") and current_animation in available:
            return current_animation
        if "idle" in available:
            return "idle"
    if oneshot and oneshot in available:
        return oneshot
    # Look frames live in the separate `_looks` collection rather than the
    # ordinary animation map, so the target itself is the availability signal.
    if look_target is not None:
        return "look"
    if not quota_enabled:
        return "idle" if "idle" in available else None
    if not snapshot_present and "waiting" in available:
        return "waiting"
    if busy and "running" in available:
        return "running"
    if bars_visible and "review" in available:
        return "review"
    if "idle" in available:
        return "idle"
    return None


def _angular_distance_degrees(left: float, right: float) -> float:
    """Smallest unsigned distance between two headings."""
    return abs((float(left) - float(right) + 180.0) % 360.0 - 180.0)


def _step_circular_index(current: int, target: int, size: int = LOOK_SECTORS) -> int:
    """Move one slot toward target using the shortest path around a ring."""
    if size <= 0:
        raise ValueError("size must be positive")
    current %= size
    target %= size
    delta = (target - current) % size
    if delta == 0:
        return current
    if delta > size // 2:
        return (current - 1) % size
    return (current + 1) % size


def skin_folder(skin_id: str) -> Path:
    return SKIN_CATALOG.folder(skin_id)


def load_skin_spec(skin_id: str) -> dict:
    return SKIN_CATALOG.load_spec(skin_id)


def skin_atlas_path(skin_id: str) -> Path | None:
    return SKIN_CATALOG.atlas_path(skin_id)


def skin_ready(skin_id: str) -> bool:
    return SKIN_CATALOG.ready(skin_id)


def list_skins() -> list[dict]:
    return SKIN_CATALOG.list_specs()


def activate_skin(skin_id: str) -> str:
    global ASSETS, CELL_W, CELL_H, SPRITE_W, SPRITE_H, ATLAS_SIZE, ATLAS_NAME, ANIMATIONS, ANIM_MS, LOOK_ROWS, _ACTIVE_STYLE
    if not skin_ready(skin_id):
        skin_id = DEFAULT_SKIN_ID
    spec = load_skin_spec(skin_id)
    atlas = spec.get("atlas") or {}
    CELL_W = int(atlas.get("cellWidth") or 192)
    CELL_H = int(atlas.get("cellHeight") or 208)
    SPRITE_W = CELL_W
    SPRITE_H = CELL_H
    ATLAS_SIZE = (int(atlas.get("width") or 1536), int(atlas.get("height") or 2288))
    ATLAS_NAME = str(spec.get("spritesheetPath") or "spritesheet.webp")
    parsed: dict[str, tuple[int, int]] = {}
    ms: dict[str, int] = {}
    for name, cfg in (spec.get("animations") or {}).items():
        if not isinstance(cfg, dict):
            continue
        parsed[name] = (int(cfg["row"]), int(cfg["frames"]))
        if cfg.get("ms") is not None:
            ms[name] = int(cfg["ms"])
    if parsed:
        ANIMATIONS = parsed
    if ms:
        ANIM_MS = {**ANIM_MS, **ms}
    look = spec.get("look") or {}
    rows = look.get("rows") or [9, 10]
    fpr = int(look.get("framesPerRow") or 8)
    LOOK_ROWS = tuple((int(row), fpr) for row in rows)
    folder = skin_folder(skin_id)
    if not (folder / ATLAS_NAME).exists() and skin_id == DEFAULT_SKIN_ID:
        folder = LEGACY_ASSETS
    ASSETS = folder
    _ACTIVE_STYLE = resolve_theme(spec.get("theme"))
    return str(spec.get("id") or skin_id)


def _parse_hex_color(value: object) -> str | None:
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        return None
    body = value[1:]
    if all(ch in "0123456789abcdefABCDEF" for ch in body):
        return value
    return None


def _blend_hex(left: str, right: str, amount: float) -> str:
    src = _parse_hex_color(left)
    dst = _parse_hex_color(right)
    if src is None or dst is None:
        return left
    t = max(0.0, min(1.0, float(amount)))
    mixed = []
    for i in (1, 3, 5):
        a = int(src[i : i + 2], 16)
        b = int(dst[i : i + 2], 16)
        mixed.append(int(a + (b - a) * t))
    return f"#{mixed[0]:02x}{mixed[1]:02x}{mixed[2]:02x}"


def remaining_bar_fill(value, ui: dict, *, tone: str | None = None) -> str:
    level = remaining_bar_level(value)
    fill = ui[{"ok": "bar_ok", "mid": "bar_mid", "low": "bar_low"}[level]]
    if tone == "dark":
        return _blend_hex(fill, "#000000", 0.18)
    return fill


def resolve_theme(theme: object) -> dict:
    payload = theme if isinstance(theme, dict) else {}
    preset_name = payload.get("preset")
    if preset_name not in _THEME_PRESETS:
        preset_name = DEFAULT_THEME_PRESET
    resolved = dict(STYLES[preset_name])
    for json_key, (style_key, allowed) in _THEME_ENUM_KEYS.items():
        raw = payload.get(json_key)
        if isinstance(raw, str) and raw in allowed:
            resolved[style_key] = raw
    for json_key, style_key in _THEME_COLOR_KEYS.items():
        parsed = _parse_hex_color(payload.get(json_key))
        if parsed is not None:
            resolved[style_key] = parsed
    radius = payload.get("radius")
    if radius is not None:
        try:
            resolved["radius"] = max(0, min(28, int(radius)))
        except (TypeError, ValueError):
            pass
    return resolved


def style() -> dict:
    return _ACTIVE_STYLE if _ACTIVE_STYLE is not None else resolve_theme({})


def _apply_ui_fonts(family: str) -> None:
    fonts = {
        "font": (family, 9),
        "font_title": (family, 9, "bold"),
        "font_ui": (family, 10),
    }
    for name in ("kawaii", "soft", "tech"):
        STYLES[name].update(fonts)
    if _ACTIVE_STYLE is not None:
        _ACTIVE_STYLE.update(fonts)


def pick_ui_fonts(root: tk.Tk) -> None:
    families = {name.lower() for name in tkfont.families(root)}
    cute = None
    for name in ("幼圆", "YouYuan", "Yu Gothic", "Microsoft YaHei UI", "Segoe UI"):
        if name.lower() in families:
            cute = name
            break
    if not cute:
        cute = "Microsoft YaHei UI"
    _apply_ui_fonts(cute)


def canvas_round_rect(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float, r: float = 12, **kwargs):
    r = max(0.0, min(float(r), (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + r, y1,
        x1 + r, y1,
        x2 - r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1 + r,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=20, **kwargs)


def pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return False
            try:
                buf = ctypes.create_unicode_buffer(260)
                size = wintypes.DWORD(260)
                ok = ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
                name = buf.value.lower() if ok else ""
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
            return "python" in name or "grokusagepet" in name
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def claim_singleton() -> bool:
    if LOCK_FILE.exists():
        try:
            old = int(LOCK_FILE.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            old = 0
        if old and old != os.getpid() and pid_running(old):
            RAISE_FILE.write_text("1", encoding="utf-8")
            return False
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
    return True


def load_state() -> dict:
    raw: dict = {}
    if STATE_FILE.exists():
        try:
            loaded = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}
        if isinstance(loaded, dict):
            raw = loaded
    return normalize_state(raw)


def save_state(data: dict) -> None:
    current = load_state()
    current.update(data)
    current = normalize_state(current)
    write_text_atomic(STATE_FILE, json.dumps(current, ensure_ascii=False, indent=2) + "\n")


def load_enabled() -> dict[str, bool]:
    if not STATE_FILE.exists():
        return dict(DEFAULT_ENABLED)
    return normalize_enabled(load_state().get("enabled"))


def load_clock_state() -> dict:
    clock = ((load_state().get("modules") or {}).get("clock") or {}) if STATE_FILE.exists() else {}
    return clock_module.normalize_clock_state(clock)


def _to_photo(im):
    im = im.convert("RGBA")
    alpha = im.getchannel("A").point(lambda v: 0 if v < 16 else v)
    im.putalpha(alpha)
    if os.name == "nt":
        bg = Image.new("RGBA", im.size, (*CHROMA_RGB, 255))
        bg.alpha_composite(im)
        return ImageTk.PhotoImage(bg.convert("RGB"))
    return ImageTk.PhotoImage(im)


def _open_skin_image(
    path: Path,
    allowed_formats: set[str],
    *,
    expected_size: tuple[int, int] | None = None,
):
    if Image is None:
        return None
    try:
        with Image.open(path) as source:
            image_format = str(source.format or "").upper()
            width, height = source.size
            if image_format not in allowed_formats:
                return None
            if width <= 0 or height <= 0 or width * height > skin_catalog.MAX_ATLAS_PIXELS:
                return None
            if expected_size is not None and source.size != expected_size:
                return None
            source.load()
            return source.convert("RGBA")
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        return None


def load_sprite(name: str, height: int):
    if Image is None or ImageTk is None:
        return None
    path = ASSETS / name
    if not path.exists():
        return None
    im = _open_skin_image(path, {"ICO", "PNG", "WEBP"})
    if im is None:
        return None
    ratio = height / im.height
    im = im.resize((max(1, int(im.width * ratio)), height), Image.Resampling.NEAREST)
    return _to_photo(im)


def load_atlas_frames() -> dict[str, list]:
    if Image is None or ImageTk is None:
        return {}
    path = ASSETS / ATLAS_NAME
    if not path.exists():
        return {}
    atlas = _open_skin_image(path, {"WEBP"}, expected_size=ATLAS_SIZE)
    if atlas is None:
        return {}
    scale = SPRITE_H / CELL_H
    dw = max(1, int(CELL_W * scale))
    dh = SPRITE_H
    resample = Image.Resampling.NEAREST
    frames: dict[str, list] = {}
    for name, (row, count) in ANIMATIONS.items():
        clip: list = []
        for column in range(count):
            box = (
                column * CELL_W,
                row * CELL_H,
                (column + 1) * CELL_W,
                (row + 1) * CELL_H,
            )
            im = atlas.crop(box)
            if (dw, dh) != (CELL_W, CELL_H):
                im = im.resize((dw, dh), resample)
            clip.append(_to_photo(im))
        frames[name] = clip
    looks: list = []
    for row, count in LOOK_ROWS:
        for column in range(count):
            box = (
                column * CELL_W,
                row * CELL_H,
                (column + 1) * CELL_W,
                (row + 1) * CELL_H,
            )
            im = atlas.crop(box)
            if (dw, dh) != (CELL_W, CELL_H):
                im = im.resize((dw, dh), resample)
            looks.append(_to_photo(im))
    frames["_looks"] = looks
    return frames


CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


def spawn_kwargs() -> dict:
    kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
        "cwd": str(fu.install_dir()),
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            CREATE_NO_WINDOW
            | DETACHED_PROCESS
            | CREATE_NEW_PROCESS_GROUP
            | 0x01000000  # CREATE_BREAKAWAY_FROM_JOB
        )
    else:
        kwargs["start_new_session"] = True
    return kwargs


def gui_command() -> tuple[str, list[str]]:
    if fu.is_frozen():
        exe = str(Path(sys.executable).resolve())
        return exe, [exe]
    python = Path(sys.executable)
    if os.name == "nt":
        pythonw = python.with_name("pythonw.exe")
        if pythonw.exists():
            python = pythonw
    script = str((fu.resource_dir() / "pet.py").resolve())
    return str(python), [str(python), script]


def hook_command() -> str:
    _target, args = gui_command()
    parts = args + ["--hook"]
    if os.name == "nt":
        return " ".join(f'"{part}"' for part in parts)
    return " ".join(shlex.quote(part) for part in parts)


def launch_task_name() -> str:
    return "GrokUsagePetKawaiiLaunch" if fu.pack_id() == "kawaii" else "GrokUsagePetLaunch"


def watch_task_name() -> str:
    return "GrokUsagePetKawaiiWatch" if fu.pack_id() == "kawaii" else "GrokUsagePetWatch"


def launch_detached() -> None:
    import watch_apps

    procs = watch_apps.running_procs()
    if not watch_apps.allow_autostart(procs):
        return
    watch_apps.clear_dismissed()
    if os.name == "nt":
        flags = CREATE_NO_WINDOW
        ran = subprocess.run(
            ["schtasks", "/Run", "/TN", launch_task_name()],
            capture_output=True,
            creationflags=flags,
        )
        if ran.returncode == 0:
            return
    _target, args = gui_command()
    subprocess.Popen(args, **spawn_kwargs())


def launcher_bat() -> Path | None:
    if os.name != "nt":
        return None
    bat = fu.install_dir() / "start_pet.bat"
    return bat if bat.exists() else None


def install_hook() -> Path:
    HOOK_FILE.parent.mkdir(parents=True, exist_ok=True)
    command = str(launcher_bat().resolve()) if launcher_bat() else hook_command()
    payload = _grok_hook_payload(command)
    if HOOK_FILE.exists():
        try:
            existing = json.loads(HOOK_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Grok hook 配置无法读取，未作修改") from exc
        if not _is_our_grok_hook_payload(existing, command):
            raise RuntimeError("Grok hook 路径已被其他配置使用，未作修改")
    write_text_atomic(HOOK_FILE, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return HOOK_FILE


def _grok_hook_payload(command: str) -> dict:
    return {
        "managedBy": GROK_HOOK_MARKER,
        "hooks": {
            "SessionStart": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": command,
                            "timeout": 15,
                        }
                    ],
                }
            ]
        }
    }


def _is_our_grok_hook_payload(payload: object, command: str | None = None) -> bool:
    if not isinstance(payload, dict):
        return False
    if command is None:
        command = str(launcher_bat().resolve()) if launcher_bat() else hook_command()
    expected = _grok_hook_payload(command)
    if payload == expected:
        return True
    legacy = dict(expected)
    legacy.pop("managedBy", None)
    return payload == legacy


def uninstall_hook() -> None:
    if not HOOK_FILE.exists():
        return
    try:
        payload = json.loads(HOOK_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Grok hook 配置无法读取，未作修改") from exc
    if not _is_our_grok_hook_payload(payload):
        raise RuntimeError("Grok hook 不属于本程序，未作修改")
    HOOK_FILE.unlink()


def cursor_hook_command() -> str:
    bat = launcher_bat()
    if bat is not None:
        return str(bat.resolve())
    return hook_command()


def _is_our_cursor_hook(entry: object) -> bool:
    return cursor_hooks.is_managed_entry(entry, cursor_hook_command())


def install_cursor_hook() -> Path:
    return cursor_hooks.install(CURSOR_HOOK_FILE, cursor_hook_command())


def sync_watcher() -> None:
    if os.name != "nt":
        return
    ps1 = fu.install_dir() / "register_watch.ps1"
    if not ps1.exists():
        return
    action = "Enable" if (grok_autostart_on() or cursor_autostart_on()) else "Disable"
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = CREATE_NO_WINDOW
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ps1),
            "-Action",
            action,
        ],
        timeout=45,
        **kwargs,
    )


def grok_autostart_on() -> bool:
    if not HOOK_FILE.exists():
        return False
    try:
        return _is_our_grok_hook_payload(json.loads(HOOK_FILE.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return False


def cursor_autostart_on() -> bool:
    return cursor_hooks.is_enabled(CURSOR_HOOK_FILE, cursor_hook_command())


def uninstall_cursor_hook() -> None:
    cursor_hooks.uninstall(CURSOR_HOOK_FILE, cursor_hook_command())


APP_TASK_NAMES = (
    "GrokUsagePetLaunch",
    "GrokUsagePetWatch",
    "GrokUsagePetKawaiiLaunch",
    "GrokUsagePetKawaiiWatch",
)
WATCH_TASK_NAMES = tuple(name for name in APP_TASK_NAMES if name.endswith("Watch"))
APP_SHORTCUT_NAMES = (
    "Grok额度宠物.lnk",
    "Grok额度宠物-可爱版.lnk",
    "Grok额度宠物.command",
    "Grok额度宠物-可爱版.command",
)
LEGACY_DATA_NAMES = ("GrokUsagePetKawaii",)


def app_data_directories() -> list[Path]:
    dirs = [DATA_DIR]
    parent = DATA_DIR.parent
    for name in LEGACY_DATA_NAMES:
        path = parent / name
        if path != DATA_DIR:
            dirs.append(path)
    return dirs


_REMOVE_OWNED_TASKS_PS = r"""
$ErrorActionPreference = 'Stop'
$installRoot = [IO.Path]::GetFullPath($env:GROK_USAGE_PET_INSTALL_ROOT).TrimEnd('\')
$taskNames = $env:GROK_USAGE_PET_TASK_NAMES -split '\|'
$productNames = @('GrokUsagePet.exe', 'GrokUsagePetKawaii.exe')
$pythonNames = @('python.exe', 'pythonw.exe')
$sourceScripts = @(
    (Join-Path $installRoot 'pet.py'),
    (Join-Path $installRoot 'watch_apps.py')
)

foreach ($name in $taskNames) {
    try {
        $task = Get-ScheduledTask -TaskPath '\' -TaskName $name -ErrorAction SilentlyContinue
        if (-not $task) { continue }
        $owned = $true
        $seenAction = $false
        foreach ($action in $task.Actions) {
            $seenAction = $true
            $actionOwned = $false
            $raw = [Environment]::ExpandEnvironmentVariables([string]$action.Execute).Trim('"')
            $rawArgs = [Environment]::ExpandEnvironmentVariables([string]$action.Arguments).Trim()
            if (-not [IO.Path]::IsPathRooted($raw)) {
                $owned = $false
                break
            }
            $candidate = [IO.Path]::GetFullPath($raw)
            if (($productNames -icontains [IO.Path]::GetFileName($candidate)) -and
                ([IO.Path]::GetDirectoryName($candidate) -ieq $installRoot)) {
                $actionOwned = $true
            }
            if ((-not $actionOwned) -and ($pythonNames -icontains [IO.Path]::GetFileName($candidate))) {
                foreach ($sourceScript in $sourceScripts) {
                    if (($rawArgs -ieq $sourceScript) -or ($rawArgs -ieq ('"' + $sourceScript + '"'))) {
                        $actionOwned = $true
                        break
                    }
                }
            }
            if (-not $actionOwned) {
                $owned = $false
                break
            }
        }
        if (-not $seenAction) { $owned = $false }
        if (-not $owned) { continue }
        if ($name -like '*Watch') {
            Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        }
        Unregister-ScheduledTask -TaskPath '\' -TaskName $name -Confirm:$false -ErrorAction Stop
        Write-Output $name
    } catch {
        Write-Output ('ERROR::' + $name + '::' + $_.Exception.Message)
    }
}
"""


def remove_scheduled_tasks() -> tuple[list[str], list[str]]:
    removed: list[str] = []
    errors: list[str] = []
    if os.name != "nt":
        return removed, errors
    env = os.environ.copy()
    env["GROK_USAGE_PET_INSTALL_ROOT"] = str(fu.install_dir().resolve())
    env["GROK_USAGE_PET_TASK_NAMES"] = "|".join(APP_TASK_NAMES)
    try:
        ran = subprocess.run(
            ["powershell", "-NoProfile", "-Command", _REMOVE_OWNED_TASKS_PS],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=CREATE_NO_WINDOW,
            timeout=30,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return removed, [f"task cleanup: {fu.redact_sensitive_text(exc)}"]
    if ran.returncode != 0:
        errors.append(f"task cleanup: {fu.redact_sensitive_text(ran.stderr or ran.returncode)}")
    for line in ran.stdout.splitlines():
        if line.startswith("ERROR::"):
            errors.append(fu.redact_sensitive_text(line.removeprefix("ERROR::")))
        elif line in APP_TASK_NAMES:
            removed.append(line)
    return removed, errors


_STOP_APP_PROCESSES_PS = r"""
$ErrorActionPreference = 'Stop'
$currentPid = [int]$env:GROK_USAGE_PET_CURRENT_PID
$installRoot = [IO.Path]::GetFullPath($env:GROK_USAGE_PET_INSTALL_ROOT).TrimEnd('\')
$sourcePattern = [regex]::Escape($installRoot + '\')
$productNames = @('GrokUsagePet.exe', 'GrokUsagePetKawaii.exe')
$pythonNames = @('python.exe', 'pythonw.exe')

Get-CimInstance Win32_Process | Where-Object {
    if ($_.ProcessId -eq $currentPid) { return $false }
    $name = [string]$_.Name
    if ($productNames -icontains $name) {
        $rawPath = [string]$_.ExecutablePath
        if (-not $rawPath) { return $false }
        try {
            $candidate = [IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables($rawPath).Trim('"'))
            return [IO.Path]::GetDirectoryName($candidate) -ieq $installRoot
        } catch {
            return $false
        }
    }
    if ($pythonNames -inotcontains $name) { return $false }
    $command = [string]$_.CommandLine
    return $command -match ('(?i)"?' + $sourcePattern + '(?:pet|watch_apps)\.py"?(?:\s|$)')
} | ForEach-Object {
    $processId = [int]$_.ProcessId
    try {
        Stop-Process -Id $processId -Force -ErrorAction Stop
    } catch {
        if (Get-Process -Id $processId -ErrorAction SilentlyContinue) { throw }
    }
    for ($attempt = 0; $attempt -lt 25; $attempt++) {
        if (-not (Get-Process -Id $processId -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Milliseconds 100
    }
    if (Get-Process -Id $processId -ErrorAction SilentlyContinue) {
        throw "Could not stop managed process $processId"
    }
    Write-Output $processId
}
"""


def stop_app_processes() -> list[str]:
    """Stop other pet/watcher instances without touching unrelated processes."""
    if os.name != "nt":
        return []
    env = os.environ.copy()
    env["GROK_USAGE_PET_CURRENT_PID"] = str(os.getpid())
    env["GROK_USAGE_PET_INSTALL_ROOT"] = str(fu.install_dir().resolve())
    ran = subprocess.run(
        ["powershell", "-NoProfile", "-Command", _STOP_APP_PROCESSES_PS],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        creationflags=CREATE_NO_WINDOW,
        timeout=30,
        env=env,
    )
    if ran.returncode != 0:
        detail = (ran.stderr or "").strip()
        raise RuntimeError(detail or f"PowerShell exited with {ran.returncode}")
    stopped = {line.strip() for line in ran.stdout.splitlines() if line.strip().isdigit()}
    stopped.discard(str(os.getpid()))
    return sorted(stopped, key=int)


def remove_desktop_shortcuts(desktop: Path | None = None) -> list[Path]:
    folder = desktop if desktop is not None else desktop_dir()
    gone: list[Path] = []
    for name in APP_SHORTCUT_NAMES:
        path = folder / name
        try:
            if path.is_file() or path.is_symlink():
                path.unlink()
                gone.append(path)
        except OSError:
            continue
    return gone


def purge_local_residue() -> dict[str, list[str]]:
    """Remove autostart, shortcuts, and app data. Never touch product logins."""
    errors: list[str] = []
    try:
        uninstall_hook()
    except Exception as exc:
        errors.append(f"Grok hook: {exc}")
    try:
        uninstall_cursor_hook()
    except Exception as exc:
        errors.append(f"Cursor hook: {exc}")
    tasks: list[str] = []
    try:
        tasks, task_errors = remove_scheduled_tasks()
        errors.extend(f"scheduled tasks: {detail}" for detail in task_errors)
    except Exception as exc:
        errors.append(f"scheduled tasks: {exc}")
    processes: list[str] = []
    try:
        processes = stop_app_processes()
    except Exception as exc:
        errors.append(f"running processes: {exc}")
    shortcuts: list[str] = []
    try:
        shortcuts = [str(path) for path in remove_desktop_shortcuts()]
    except Exception as exc:
        errors.append(f"shortcuts: {exc}")
    data: list[str] = []
    for path in app_data_directories():
        if not path.exists():
            continue
        try:
            shutil.rmtree(path)
            data.append(str(path))
        except OSError as exc:
            errors.append(f"{path}: {exc}")
    return {
        "tasks": tasks,
        "processes": processes,
        "shortcuts": shortcuts,
        "data": data,
        "errors": errors,
    }


def _is_reparse_point(path: Path) -> bool:
    try:
        attrs = getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0)
    except OSError:
        return True
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def validated_self_delete_dir(
    install_dir: Path | None = None,
    executable: Path | None = None,
    *,
    frozen: bool | None = None,
) -> Path | None:
    """Return a narrowly validated portable install tree, never a broad folder."""
    if os.name != "nt":
        return None
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if not frozen:
        return None
    try:
        destination = Path(install_dir or fu.install_dir()).resolve()
        exe = Path(executable or sys.executable).resolve()
        home = Path.home().resolve()
    except OSError:
        return None
    if destination.parent == destination or destination == home or exe.parent != destination:
        return None
    if exe.name.casefold() != "grokusagepet.exe":
        return None
    if not re.fullmatch(r"GrokUsagePet-v\d+\.\d+\.\d+-Windows-x64", destination.name):
        return None
    marker = destination / INSTALL_MARKER_NAME
    runtime = destination / "_internal"
    try:
        marker_value = marker.read_text(encoding="ascii").strip()
    except OSError:
        return None
    if marker_value != INSTALL_MARKER_VALUE or not runtime.is_dir():
        return None
    for path in (destination, exe, marker, runtime):
        if path.is_symlink() or _is_reparse_point(path):
            return None
    try:
        for path in destination.rglob("*"):
            if path.is_symlink() or _is_reparse_point(path):
                return None
    except OSError:
        return None
    return destination


def _build_self_delete_script(destination: Path, wait_pid: int) -> str:
    return f"""
$ErrorActionPreference = 'Stop'
$dst = {_ps_quote(str(destination))}
$waitPid = {int(wait_pid)}
$markerName = {_ps_quote(INSTALL_MARKER_NAME)}
$markerValue = {_ps_quote(INSTALL_MARKER_VALUE)}

try {{
    for ($i = 0; $i -lt 80; $i++) {{
        if (-not (Get-Process -Id $waitPid -ErrorAction SilentlyContinue)) {{ break }}
        Start-Sleep -Milliseconds 250
    }}
    if (Get-Process -Id $waitPid -ErrorAction SilentlyContinue) {{ throw 'application did not exit' }}
    if (-not (Test-Path -LiteralPath $dst -PathType Container)) {{ return }}
    if ((Get-Item -LiteralPath $dst -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {{
        throw 'install directory is a reparse point'
    }}
    $marker = Join-Path $dst $markerName
    $exe = Join-Path $dst 'GrokUsagePet.exe'
    $runtime = Join-Path $dst '_internal'
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {{ throw 'install marker missing' }}
    if ((Get-Content -LiteralPath $marker -Raw).Trim() -ne $markerValue) {{ throw 'install marker invalid' }}
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {{ throw 'application executable missing' }}
    if (-not (Test-Path -LiteralPath $runtime -PathType Container)) {{ throw 'application runtime missing' }}
    $reparse = Get-ChildItem -LiteralPath $dst -Recurse -Force -ErrorAction Stop | Where-Object {{
        $_.Attributes -band [IO.FileAttributes]::ReparsePoint
    }} | Select-Object -First 1
    if ($reparse) {{ throw 'install tree contains a reparse point' }}
    for ($attempt = 0; $attempt -lt 20; $attempt++) {{
        try {{
            Remove-Item -LiteralPath $dst -Recurse -Force -ErrorAction Stop
            break
        }} catch {{
            if ($attempt -eq 19) {{ throw }}
            Start-Sleep -Milliseconds 500
        }}
    }}
    if (Test-Path -LiteralPath $dst) {{ throw 'install directory was not removed' }}
}} finally {{
    Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
}}
"""


def schedule_self_delete(wait_pid: int | None = None) -> bool:
    destination = validated_self_delete_dir()
    if destination is None:
        return False
    pid = os.getpid() if wait_pid is None else int(wait_pid)
    script = _build_self_delete_script(destination, pid)
    handle, name = tempfile.mkstemp(prefix="grok-usage-pet-uninstall-", suffix=".ps1")
    os.close(handle)
    script_path = Path(name)
    try:
        script_path.write_text(script, encoding="utf-8")
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path)],
            close_fds=True,
            creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        script_path.unlink(missing_ok=True)
        raise
    return True


def format_purge_report(result: dict[str, list[str]], *, program_scheduled: bool = False) -> str:
    lines = [
        "不会删除 Grok / Cursor / Codex 登录。",
        f"计划任务：{', '.join(result['tasks']) or '无'}",
        f"后台进程：{len(result['processes'])} 个",
        f"快捷方式：{len(result['shortcuts'])} 个",
        f"数据目录：{len(result['data'])} 个",
        "程序文件夹：退出后自动删除" if program_scheduled else "程序文件夹：源码/未验证目录请手动删除",
    ]
    if result["errors"]:
        lines.append("未完成：" + "；".join(result["errors"]))
    return "\n".join(lines)


def _windows_guid(text: str):
    import ctypes
    import uuid
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    value = uuid.UUID(text)
    return GUID(
        value.time_low,
        value.time_mid,
        value.time_hi_version,
        (ctypes.c_ubyte * 8).from_buffer_copy(value.bytes[8:]),
    )


def _windows_hr_error(hr: int, action: str) -> OSError:
    return OSError(f"{action} failed (0x{hr & 0xFFFFFFFF:08X})")


def _windows_known_folder_desktop() -> Path | None:
    import ctypes
    from ctypes import wintypes

    ole32 = ctypes.WinDLL("ole32", use_last_error=True)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    shell32.SHGetKnownFolderPath.argtypes = [
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_wchar_p),
    ]
    shell32.SHGetKnownFolderPath.restype = ctypes.HRESULT
    folder_id = _windows_guid("B4BFCC3A-DB2C-424C-B029-7FE99A87C641")
    ppath = ctypes.c_wchar_p()
    hr = shell32.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(ppath))
    try:
        if hr < 0 or not ppath.value:
            return None
        path = Path(ppath.value)
    finally:
        ole32.CoTaskMemFree(ppath)
    return path if str(path) else None


def desktop_dir() -> Path:
    if os.name == "nt":
        try:
            known = _windows_known_folder_desktop()
            if known is not None and (known.is_dir() or not known.exists()):
                return known
        except Exception:
            pass
    home = Path.home()
    for candidate in (
        home / "Desktop",
        home / "OneDrive" / "Desktop",
        home / "OneDrive" / "Documents" / "Desktop",
    ):
        if candidate.exists():
            return candidate
    return home / "Desktop"


def _ps_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _shortcut_argument_string(parts: list[str]) -> str:
    bits: list[str] = []
    for part in parts:
        if any(ch.isspace() for ch in part) or any(ch in part for ch in "&()[]{}^=;!'+,`~"):
            bits.append('"' + part.replace('"', '\\"') + '"')
        else:
            bits.append(part)
    return " ".join(bits)


def _shortcut_icon_path() -> Path | None:
    candidates = [
        ASSETS / "app.ico",
        SKINS_DIR / DEFAULT_SKIN_ID / "app.ico",
        fu.resource_dir() / "skins" / DEFAULT_SKIN_ID / "app.ico",
    ]
    if fu.is_frozen():
        candidates.append(Path(sys.executable))
    for path in candidates:
        try:
            if path.is_file():
                return path
        except OSError:
            continue
    return None


def desktop_shortcut_spec(*, desktop: Path | None = None) -> dict[str, object]:
    target, args = gui_command()
    folder = desktop if desktop is not None else desktop_dir()
    if os.name == "nt":
        name = "Grok额度宠物-可爱版.lnk" if fu.pack_id() == "kawaii" else "Grok额度宠物.lnk"
    else:
        name = "Grok额度宠物-可爱版.command" if fu.pack_id() == "kawaii" else "Grok额度宠物.command"
    icon = _shortcut_icon_path()
    return {
        "path": folder / name,
        "target": target,
        "arguments": _shortcut_argument_string(args[1:]),
        "working_directory": str(fu.install_dir()),
        "icon": str(icon.resolve()) if icon is not None else "",
        "description": "Grok remaining usage pet",
    }


def _windows_com_fn(interface, index, restype, *argtypes):
    import ctypes

    vtbl_ptr = ctypes.cast(interface, ctypes.POINTER(ctypes.c_void_p))[0]
    vtbl = ctypes.cast(vtbl_ptr, ctypes.POINTER(ctypes.c_void_p))
    prototype = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    return prototype(vtbl[index])


def _write_windows_lnk_com(spec: dict[str, object]) -> None:
    import ctypes
    from ctypes import wintypes

    ole32 = ctypes.WinDLL("ole32", use_last_error=True)
    ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    ole32.CoInitializeEx.restype = ctypes.HRESULT
    ole32.CoCreateInstance.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    ole32.CoCreateInstance.restype = ctypes.HRESULT
    ole32.CoUninitialize.argtypes = []

    clsid = _windows_guid("00021401-0000-0000-C000-000000000046")
    iid_link = _windows_guid("000214F9-0000-0000-C000-000000000046")
    iid_file = _windows_guid("0000010b-0000-0000-C000-000000000046")
    link = ctypes.c_void_p()
    persist = ctypes.c_void_p()
    initialized = False
    hr = ole32.CoInitializeEx(None, 0x2)
    if hr == 0:
        initialized = True
    elif hr not in (1, -2147417850):
        raise _windows_hr_error(hr, "CoInitializeEx")
    try:
        hr = ole32.CoCreateInstance(
            ctypes.byref(clsid),
            None,
            1,
            ctypes.byref(iid_link),
            ctypes.byref(link),
        )
        if hr < 0 or not link.value:
            raise _windows_hr_error(hr, "CoCreateInstance(ShellLink)")
        set_path = _windows_com_fn(link, 20, ctypes.HRESULT, wintypes.LPCWSTR)
        set_description = _windows_com_fn(link, 7, ctypes.HRESULT, wintypes.LPCWSTR)
        set_working_directory = _windows_com_fn(link, 9, ctypes.HRESULT, wintypes.LPCWSTR)
        set_arguments = _windows_com_fn(link, 11, ctypes.HRESULT, wintypes.LPCWSTR)
        set_show_cmd = _windows_com_fn(link, 15, ctypes.HRESULT, ctypes.c_int)
        set_icon_location = _windows_com_fn(link, 17, ctypes.HRESULT, wintypes.LPCWSTR, ctypes.c_int)
        query_interface = _windows_com_fn(
            link,
            0,
            ctypes.HRESULT,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        )
        release_link = _windows_com_fn(link, 2, wintypes.ULONG)
        hr = set_path(link, str(spec["target"]))
        if hr < 0:
            raise _windows_hr_error(hr, "SetPath")
        hr = set_arguments(link, str(spec["arguments"]))
        if hr < 0:
            raise _windows_hr_error(hr, "SetArguments")
        hr = set_working_directory(link, str(spec["working_directory"]))
        if hr < 0:
            raise _windows_hr_error(hr, "SetWorkingDirectory")
        hr = set_description(link, str(spec["description"]))
        if hr < 0:
            raise _windows_hr_error(hr, "SetDescription")
        hr = set_show_cmd(link, 1)
        if hr < 0:
            raise _windows_hr_error(hr, "SetShowCmd")
        icon = str(spec.get("icon") or "")
        if icon:
            hr = set_icon_location(link, icon, 0)
            if hr < 0:
                raise _windows_hr_error(hr, "SetIconLocation")
        hr = query_interface(link, ctypes.byref(iid_file), ctypes.byref(persist))
        if hr < 0 or not persist.value:
            raise _windows_hr_error(hr, "QueryInterface(IPersistFile)")
        save = _windows_com_fn(persist, 6, ctypes.HRESULT, wintypes.LPCWSTR, wintypes.BOOL)
        release_file = _windows_com_fn(persist, 2, wintypes.ULONG)
        hr = save(persist, str(spec["path"]), True)
        release_file(persist)
        persist.value = None
        if hr < 0:
            raise _windows_hr_error(hr, "IPersistFile.Save")
        release_link(link)
        link.value = None
    finally:
        if persist.value:
            _windows_com_fn(persist, 2, wintypes.ULONG)(persist)
        if link.value:
            _windows_com_fn(link, 2, wintypes.ULONG)(link)
        if initialized:
            ole32.CoUninitialize()


def _shortcut_blocked_by_system(detail: str) -> bool:
    text = detail.casefold()
    return any(
        token in text
        for token in (
            "0x80070005",
            "access is denied",
            "拒绝访问",
            "0x800704ec",
        )
    )


def _shortcut_block_message(errors: list[str]) -> str:
    detail = "；".join(item for item in errors if item)
    if _shortcut_blocked_by_system(detail):
        return (
            "无法写入桌面快捷方式：Windows 可能拦截了桌面写入"
            "（SmartScreen 或受控文件夹访问）。"
            "可在 Windows 安全中心把本程序加入允许应用，"
            "或右键 GrokUsagePet.exe → 发送到 → 桌面快捷方式。"
            "本程序不会关闭杀毒或自动添加排除项。"
        )
    return "无法写入桌面快捷方式：" + (detail or "文件没有出现")


def create_desktop_shortcut() -> Path:
    spec = desktop_shortcut_spec()
    name = Path(spec["path"])
    name.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        errors: list[str] = []
        try:
            _write_windows_lnk_com(spec)
        except Exception as exc:
            errors.append(str(exc))
        if name.is_file():
            return name
        fallback = fu.install_dir() / name.name
        if fallback.resolve() != name.resolve():
            fallback_spec = dict(spec)
            fallback_spec["path"] = fallback
            try:
                fallback.parent.mkdir(parents=True, exist_ok=True)
                _write_windows_lnk_com(fallback_spec)
            except Exception as exc:
                errors.append(str(exc))
            if fallback.is_file():
                return fallback
        raise RuntimeError(_shortcut_block_message(errors))
    quoted = " ".join(shlex.quote(part) for part in gui_command()[1])
    name.write_text(
        "#!/bin/bash\n"
        f"cd {shlex.quote(str(fu.install_dir()))}\n"
        f"exec {quoted}\n",
        encoding="utf-8",
    )
    name.chmod(name.stat().st_mode | 0o111)
    return name


class UsagePet:
    def __init__(self, *, preview_snapshot: dict | None = None, auto_close_ms: int | None = None) -> None:
        self._preview_mode = preview_snapshot is not None
        self.snap: dict | None = preview_snapshot
        self.error: str | None = None
        self.pinned = True if self._preview_mode else False
        self.skin_id = activate_skin(str(load_state().get("skin") or DEFAULT_SKIN_ID))
        self.enabled = load_enabled()
        self.clock_state = load_clock_state()
        self.clock_enabled = dict(self.clock_state.get("enabled") or {})
        self.info_panel = normalize_info_panel(load_state().get("info_panel"))
        self._panel_hits: list[tuple[str, int, int, int, int]] = []
        self._alarm_dlg: tk.Toplevel | None = None
        self._alarm_pulses = 0
        self._modules = info_modules.default_host()
        self.check_updates = bool(load_state().get("check_updates", True))
        self._update_info: app_update.LatestRelease | None = None
        self._update_busy = False
        self._update_results: queue.Queue = queue.Queue()
        self._settings: tk.Toplevel | None = None
        self._drag = None
        self._drag_dx = 0
        self._last_drag_x = 0
        self._tick = 0
        self._busy = False
        self._closing = False
        self._fetch_results: queue.Queue[tuple[dict | None, str | None]] = queue.Queue()
        self._photos: dict[str, object] = {}
        self._anims: dict[str, list] = {}
        self._looks: list = []
        self._anim = "idle"
        self._frame = 0
        self._frame_acc = 0.0
        self._last_anim_at = time.monotonic()
        self._look_target: int | None = None
        self._look_frame: int | None = None
        self._look_acc = 0.0
        self._oneshot: str | None = None
        self._last_activity = time.monotonic()
        self._hover: str | None = None
        self._hover_open = False
        self._hover_armed = False
        self._collapse_job: str | None = None
        self._mouse = (0, 0)
        self._sprite_box = (0, 0, 0, 0)
        self._win_w = SPRITE_W
        self._win_h = SPRITE_H
        self._sprite_y = 0
        self._geom = f"{SPRITE_W}x{SPRITE_H}+48+48"

        print("creating Tk", flush=True)
        self.root = tk.Tk()
        print("Tk created", flush=True)
        pick_ui_fonts(self.root)
        self.root.title(f"Grok Usage Pet v{APP_VERSION}")
        self._apply_app_icon(self.root)
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)
        self.root.configure(bg=CHROMA)
        self.root.update_idletasks()
        print("tk ready", flush=True)
        self.root.geometry(self._geom)

        self.canvas = tk.Canvas(
            self.root,
            width=SPRITE_W,
            height=SPRITE_H,
            bg=CHROMA,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.menu = Menu(self.root, tearoff=0)
        self._rebuild_menu()

        for seq, fn in (
            ("<ButtonPress-1>", self.on_press),
            ("<B1-Motion>", self.on_drag),
            ("<ButtonRelease-1>", self.on_release),
            ("<Double-Button-1>", self.on_double),
            ("<Button-3>", self.on_menu),
            ("<Button-2>", self.on_menu),
            ("<Control-Button-1>", self.on_menu),
            ("<Motion>", self.on_motion),
            ("<Enter>", self.on_enter),
            ("<Leave>", self.on_leave),
        ):
            self.canvas.bind(seq, fn)
            self.root.bind(seq, fn)

        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self._load_sprites()
        self._play_oneshot("waving")
        self._note_activity()
        self._apply_chrome()
        self._apply_layout(initial=True)
        self.draw()
        self._apply_chrome()
        self.root.deiconify()
        self.root.geometry(self._geom)
        self.root.after(100, self._poll_fetch_results)
        self.root.after(100, self._poll_update_results)
        if not self._preview_mode:
            self.root.after(12_000, self._auto_check_update)
        if self._preview_mode:
            if auto_close_ms is not None:
                self.root.after(max(500, auto_close_ms), self.quit)
        else:
            self.refresh_now()
        self.root.after(TICK_MS, self.animate)
        self.root.after(400, self.watch_raise)
        self.root.after(200, self._force_front)
        self.root.after(700, self._arm_hover)

    def _arm_hover(self) -> None:
        self._hover_armed = True

    def _force_front(self) -> None:
        self.root.deiconify()
        self.root.geometry(self._geom)
        self.root.lift()
        self.root.attributes("-topmost", True)

    def _apply_app_icon(self, win: tk.Misc) -> None:
        ico = ASSETS / "app.ico"
        png = ASSETS / "app.png"
        if ico.exists():
            try:
                win.iconbitmap(str(ico))
            except tk.TclError:
                pass
        if ImageTk is None or not png.exists():
            return
        try:
            photo = ImageTk.PhotoImage(file=str(png))
        except OSError:
            return
        self._photos["_app_icon"] = photo
        try:
            win.iconphoto(True, photo)
        except tk.TclError:
            pass

    def _apply_chrome(self) -> None:
        self.root.overrideredirect(True)
        self.root.configure(bg=CHROMA)
        self.canvas.configure(bg=CHROMA)
        try:
            if os.name == "nt":
                self.root.wm_attributes("-transparentcolor", CHROMA)
            elif sys.platform == "darwin":
                self.root.wm_attributes("-transparent", True)
                self.root.configure(bg="systemTransparent")
                self.canvas.configure(bg="systemTransparent")
        except tk.TclError:
            pass

    def available_panels(self) -> tuple[str, ...]:
        panels: list[str] = []
        if quota_sources_enabled(getattr(self, "enabled", DEFAULT_ENABLED)):
            panels.append("quota")
        if clock_module.clock_panel_available(getattr(self, "clock_enabled", {})):
            panels.append("clock")
        return tuple(panels)

    def active_panel(self) -> str | None:
        available = self.available_panels()
        if not available:
            return None
        return clamp_info_panel(getattr(self, "info_panel", "quota"), available)

    def bars_visible(self) -> bool:
        return bool(
            (getattr(self, "pinned", False) or getattr(self, "_hover_open", False))
            and self.available_panels()
        )

    def _layout_metrics(self) -> tuple[int, int, int]:
        ui = style()
        extra = int(ui.get("bubble_bottom") or 0)
        if not self.bars_visible():
            return SPRITE_W, SPRITE_H, 0
        panel = self.active_panel()
        tabs = len(self.available_panels()) > 1
        if panel == "clock":
            bubble_h = ui["bubble_top"] + clock_module.clock_panel_height(
                getattr(self, "clock_enabled", {}),
                tabs=tabs,
            ) + extra
        else:
            rows = self.visible_rows()
            tab_h = clock_module.PANEL_TAB_H if tabs else 0
            bubble_h = ui["bubble_top"] + tab_h + len(rows) * ui["row_h"] + extra
        win_w = ui["bubble_w"]
        return win_w, bubble_h + SPRITE_H, bubble_h

    def _clamp_pos(self, x: int, y: int, w: int, h: int) -> tuple[int, int]:
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(-w + 40, min(x, sw - 40))
        y = max(-h + 40, min(y, sh - 40))
        return x, y

    def _collapsed_origin(self) -> tuple[int, int]:
        try:
            x = self.root.winfo_x() + (self._win_w - SPRITE_W) // 2
            y = self.root.winfo_y() + self._sprite_y
        except tk.TclError:
            return 48, 48
        return x, y

    def _begin_layout_repaint(self, *, initial: bool) -> float | None:
        """Hide a visible Windows layer while its geometry and canvas diverge."""
        if initial or os.name != "nt":
            return None
        previous: float | None = None
        try:
            if not self.root.winfo_viewable():
                return None
            previous = float(self.root.attributes("-alpha"))
            self.root.attributes("-alpha", 0.0)
            # Force the compositor to stop presenting the old canvas before
            # Tk applies the new size/position and sprite coordinates.
            self.root.update_idletasks()
            return previous
        except (tk.TclError, TypeError, ValueError):
            if previous is not None:
                try:
                    self.root.attributes("-alpha", previous)
                except tk.TclError:
                    pass
            return None

    def _finish_layout_repaint(self, previous_alpha: float | None) -> None:
        if previous_alpha is None:
            return
        try:
            # Paint the complete new layout while the layered window is hidden,
            # then reveal it as one finished frame. This avoids a sprite being
            # composited briefly at the old quota-bubble origin.
            self.draw()
            self.root.update_idletasks()
        finally:
            try:
                self.root.attributes("-alpha", previous_alpha)
            except tk.TclError:
                pass

    def _apply_layout(self, initial: bool = False) -> None:
        win_w, win_h, sprite_y = self._layout_metrics()
        if (
            not initial
            and win_w == self._win_w
            and win_h == self._win_h
            and sprite_y == self._sprite_y
        ):
            return
        try:
            old_x = self.root.winfo_x()
            old_y = self.root.winfo_y()
        except tk.TclError:
            old_x, old_y = 48, 48
        old_cx = old_x + self._win_w // 2
        new_x = old_cx - win_w // 2
        new_y = old_y + self._sprite_y - sprite_y
        if initial:
            st = load_state()
            sx, sy = st.get("x"), st.get("y")
            if isinstance(sx, int) and isinstance(sy, int):
                new_x, new_y = sx, sy
            else:
                new_x, new_y = 48, 48
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            new_x = max(0, min(new_x, max(0, sw - win_w)))
            new_y = max(0, min(new_y, max(0, sh - win_h)))
        else:
            new_x, new_y = self._clamp_pos(new_x, new_y, win_w, win_h)
        previous_alpha = self._begin_layout_repaint(initial=initial)
        try:
            self._win_w, self._win_h, self._sprite_y = win_w, win_h, sprite_y
            self._geom = f"{win_w}x{win_h}+{new_x}+{new_y}"
            self.canvas.config(width=win_w, height=win_h)
            self.root.geometry(self._geom)
            self._apply_chrome()
            self._finish_layout_repaint(previous_alpha)
        except Exception:
            if previous_alpha is not None:
                try:
                    self.root.attributes("-alpha", previous_alpha)
                except tk.TclError:
                    pass
            raise
        print(
            f"layout {self._geom} hover_open={self._hover_open} pinned={self.pinned}",
            flush=True,
        )

    def _load_sprites(self) -> None:
        if ImageTk is None:
            return
        loaded = load_atlas_frames()
        self._looks = list(loaded.pop("_looks", []))
        self._anims = loaded
        if self._anims:
            return
        for key, name in (
            ("idle", "pet_idle.png"),
            ("happy", "pet_happy.png"),
            ("low", "pet_low.png"),
        ):
            photo = load_sprite(name, SPRITE_H)
            if photo is not None:
                self._photos[key] = photo

    def mood(self) -> str:
        remaining = self._remainings()
        if not remaining:
            return "idle"
        worst = min(remaining)
        if worst < 20:
            return "low"
        if worst >= 55:
            return "happy"
        return "idle"

    def _note_activity(self) -> None:
        self._last_activity = time.monotonic()

    def _maybe_idle_wave(self, now: float) -> None:
        if self._drag or self._oneshot or self._closing:
            return
        if not idle_wave_due(self._last_activity, now):
            return
        self._play_oneshot("waving")
        self._last_activity = now

    def _play_oneshot(self, name: str) -> None:
        if name not in self._anims:
            return
        self._oneshot = name
        if self._anim == name:
            self._frame = 0
            self._frame_acc = 0.0

    def _play_module_reaction(self, name: str) -> None:
        if self._drag or self._oneshot in {"waving", "jumping"}:
            return
        self._play_oneshot(name)

    def _look_index(self) -> int | None:
        if len(self._looks) < 16:
            return None
        try:
            px = self.root.winfo_pointerx()
            py = self.root.winfo_pointery()
            wx = self.root.winfo_rootx()
            wy = self.root.winfo_rooty()
        except tk.TclError:
            return None
        x0, y0, x1, y1 = self._sprite_box
        cx = wx + (x0 + x1) / 2
        cy = wy + (y0 + y1) / 2
        dx = px - cx
        dy = py - cy
        dist = math.hypot(dx, dy)
        active = self._anim == "look" and self._look_target is not None
        min_dist, max_dist = LOOK_STAY_DISTANCE if active else LOOK_ENTER_DISTANCE
        if dist < min_dist or dist > max_dist:
            return None
        ang = math.degrees(math.atan2(dx, -dy))
        if ang < 0:
            ang += 360
        if active:
            target_center = self._look_target * LOOK_STEP_DEGREES
            hold_angle = LOOK_STEP_DEGREES / 2 + LOOK_SECTOR_HYSTERESIS_DEGREES
            if _angular_distance_degrees(ang, target_center) <= hold_angle:
                return self._look_target
        return int((ang + LOOK_STEP_DEGREES / 2) / LOOK_STEP_DEGREES) % LOOK_SECTORS

    def _current_anim(self) -> str:
        # Pointer interaction is an explicit user action. Keep it ahead of the
        # ambient waiting/running/review states; otherwise a fresh machine with
        # no snapshot yet, an in-flight refresh, or an open quota bubble can
        # calculate a look target but never display any of the 16 look frames.
        self._look_target = self._look_index()
        resolved = resolve_animation_state(
            dragging=bool(self._drag),
            drag_dx=getattr(self, "_drag_dx", 0),
            oneshot=getattr(self, "_oneshot", None),
            look_target=self._look_target,
            snapshot_present=self.snap is not None,
            busy=getattr(self, "_busy", False),
            bars_visible=self.bars_visible(),
            animations=self._anims,
            quota_enabled=quota_sources_enabled(getattr(self, "enabled", DEFAULT_ENABLED)),
            current_animation=getattr(self, "_anim", "idle"),
        )
        if resolved is not None:
            return resolved
        return self.mood()

    def _current_photo(self):
        if self._anim == "look":
            if self._look_frame is not None and len(self._looks) >= LOOK_SECTORS:
                return self._looks[self._look_frame % len(self._looks)]
        frames = self._anims.get(self._anim) or self._anims.get("idle") or []
        if frames:
            return frames[self._frame % len(frames)]
        mood = self.mood()
        return self._photos.get(mood) or self._photos.get("idle")

    def visible_rows(self) -> tuple[str, ...]:
        return tuple(key for key in BUBBLE_ROWS if self.enabled.get(key, True))

    def persist(self) -> None:
        x, y = self._collapsed_origin()
        clock = clock_module.normalize_clock_state(getattr(self, "clock_state", {}))
        clock["enabled"] = dict(getattr(self, "clock_enabled", clock.get("enabled") or {}))
        payload = {
            "x": x,
            "y": y,
            "enabled": dict(self.enabled),
            "skin": self.skin_id,
            "check_updates": self.check_updates,
            "info_panel": self.active_panel() or "quota",
            "modules": {
                "quota": {"enabled": dict(self.enabled)},
                "clock": clock,
            },
        }
        try:
            save_state(payload)
        except tk.TclError:
            save_state(
                {
                    "enabled": dict(self.enabled),
                    "skin": self.skin_id,
                    "check_updates": self.check_updates,
                    "info_panel": payload.get("info_panel") or "quota",
                    "modules": payload["modules"],
                }
            )

    def _remainings(self) -> list[float]:
        if not self.snap:
            return []
        vals: list[float] = []
        pools = self._pools()
        for key in self.visible_rows():
            if key not in BUBBLE_ROWS:
                continue
            vals.extend(pool_remainings(pools[key]))
        return vals

    def _reveal_bars(self, *, jump: bool = True) -> None:
        was = self.bars_visible()
        self._hover_open = True
        if jump and not was:
            self._play_oneshot("jumping")
        self._apply_layout()

    def on_enter(self, event) -> None:
        if not self._hover_armed:
            return
        self._note_activity()
        self._cancel_collapse()
        if self._drag:
            return
        if not self._hover_open:
            self._reveal_bars()
            self._hover = "pet"
            self.draw()

    def on_motion(self, event) -> None:
        if not self._hover_armed:
            return
        self._note_activity()
        self._mouse = (event.x, event.y)
        self._cancel_collapse()
        if self._drag:
            return
        if not self._hover_open:
            self._reveal_bars()
            self._hover = "pet"
            self.draw()
            return
        target = self._hit_target(event.x, event.y)
        if target != self._hover:
            self._hover = target
            self.draw()

    def on_leave(self, event) -> None:
        self._hover = None
        self._schedule_collapse()
        self.draw()

    def _cancel_collapse(self) -> None:
        if self._collapse_job is not None:
            try:
                self.root.after_cancel(self._collapse_job)
            except tk.TclError:
                pass
            self._collapse_job = None

    def _schedule_collapse(self) -> None:
        if self.pinned or self._drag:
            return
        self._cancel_collapse()
        self._collapse_job = self.root.after(COLLAPSE_MS, self._collapse)

    def _collapse(self) -> None:
        self._collapse_job = None
        if self.pinned or self._drag:
            return
        if self._hover_open:
            self._hover_open = False
            self._hover = None
            if self._oneshot == "jumping":
                self._oneshot = None
            self._apply_layout()
            self.draw()

    def _hit_target(self, x: int, y: int) -> str | None:
        for key, x0, y0, x1, y1 in getattr(self, "_panel_hits", []):
            if x0 <= x <= x1 and y0 <= y <= y1:
                return key
        if self.bars_visible() and self.active_panel() == "quota":
            ui = style()
            rows = self.visible_rows()
            tabs = len(self.available_panels()) > 1
            origin = ui["bubble_top"] + (clock_module.PANEL_TAB_H if tabs else 0)
            for i, key in enumerate(rows):
                top = origin + i * ui["row_h"]
                if top <= y < top + ui["row_h"]:
                    return key
        x0, y0, x1, y1 = self._sprite_box
        if x0 <= x < x1 and y0 <= y < y1:
            return "pet"
        return None

    def on_press(self, event) -> None:
        self._note_activity()
        self._press_root = (event.x_root, event.y_root)
        self._press_hit = self._hit_target(event.x, event.y)
        self._drag = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y())
        self._last_drag_x = event.x_root
        self._drag_dx = 0

    def on_drag(self, event) -> None:
        if not self._drag:
            return
        self._note_activity()
        sx, sy, wx, wy = self._drag
        dx = event.x_root - self._last_drag_x
        if abs(dx) >= 2:
            self._drag_dx = dx
        self._last_drag_x = event.x_root
        new_x = wx + (event.x_root - sx)
        new_y = wy + (event.y_root - sy)
        self._geom = f"{self._win_w}x{self._win_h}+{new_x}+{new_y}"
        self.root.geometry(f"+{new_x}+{new_y}")

    def on_release(self, event) -> None:
        press = getattr(self, "_press_root", None)
        hit = getattr(self, "_press_hit", None)
        self._drag = None
        self._drag_dx = 0
        self._press_root = None
        self._press_hit = None
        if press is not None:
            dx = event.x_root - press[0]
            dy = event.y_root - press[1]
            if dx * dx + dy * dy <= 36:
                if hit == "tab:quota":
                    self._set_info_panel("quota")
                    return
                if hit == "tab:clock":
                    self._set_info_panel("clock")
                    return
                if hit == "tmr_toggle":
                    self._toggle_timer()
                    return
                if hit == "tmr_reset":
                    self._reset_timer()
                    return
                if hit == "tmr_mode_stopwatch":
                    self._set_timer_mode("stopwatch")
                    return
                if hit == "tmr_mode_countdown":
                    self._set_timer_mode("countdown")
                    return
                if str(hit or "").startswith("tmr_preset_"):
                    try:
                        minutes = int(str(hit).split("_")[-1])
                    except ValueError:
                        minutes = 5
                    self._set_countdown_minutes(minutes)
                    return
        self.persist()

    def on_double(self, event) -> None:
        hit = self._hit_target(event.x, event.y)
        if hit in {"tmr_toggle", "tmr_reset", "tab:quota", "tab:clock", "tmr_mode_stopwatch", "tmr_mode_countdown"} or str(hit or "").startswith("tmr_preset_"):
            return
        self.toggle_expand()

    def _set_info_panel(self, panel: str) -> None:
        self._note_activity()
        available = self.available_panels()
        self.info_panel = clamp_info_panel(panel, available)
        self.persist()
        self._rebuild_menu()
        self._apply_layout()
        self.draw()

    def _rebuild_menu(self) -> None:
        menu = getattr(self, "menu", None)
        if menu is None or not hasattr(menu, "delete") or not hasattr(menu, "add_command"):
            return
        try:
            menu.delete(0, "end")
            menu.add_command(label="固定 / 取消固定面板", command=self.toggle_expand)
            menu.add_command(label="设置…", command=self.open_settings)
            available = self.available_panels()
            if "quota" in available and "clock" in available:
                other = "clock" if self.active_panel() == "quota" else "quota"
                menu.add_command(
                    label="切换到时钟" if other == "clock" else "切换到额度",
                    command=lambda p=other: self._set_info_panel(p),
                )
            if getattr(self, "clock_enabled", {}).get("timer") and self.active_panel() == "clock":
                state = clock_module.normalize_clock_state(getattr(self, "clock_state", {}))
                running = bool(state.get("timer_running"))
                ringing = bool(state.get("timer_ringing"))
                menu.add_command(label="关掉铃声" if ringing else ("暂停闹钟" if running else "开始闹钟"), command=self._toggle_timer)
                menu.add_command(label="计时归零", command=self._reset_timer)
            if quota_sources_enabled(getattr(self, "enabled", DEFAULT_ENABLED)):
                menu.add_command(label="刷新额度", command=self.refresh_now)
            menu.add_command(label="创建桌面快捷方式", command=self.install_shortcut)
            menu.add_separator()
            menu.add_command(label="打开数据目录", command=self.open_data_dir)
            menu.add_command(label="退出宠物", command=self.quit)
        except tk.TclError:
            return

    def _toggle_timer(self) -> None:
        self._note_activity()
        now = time.time()
        self.clock_state = clock_module.toggle_timer(getattr(self, "clock_state", {}), now)
        self.clock_enabled = dict(self.clock_state.get("enabled") or self.clock_enabled)
        self.persist()
        self._rebuild_menu()
        if not self.clock_state.get("timer_ringing"):
            self._dismiss_alarm_banner()
        self.draw()

    def _reset_timer(self) -> None:
        self._note_activity()
        self.clock_state = clock_module.reset_timer(getattr(self, "clock_state", {}))
        self.clock_enabled = dict(self.clock_state.get("enabled") or self.clock_enabled)
        self.persist()
        self._rebuild_menu()
        self._dismiss_alarm_banner()
        self.draw()

    def _raise_alarm(self) -> None:
        if getattr(self, "_closing", False):
            return
        self._alarm_pulses = 0
        if "clock" in self.available_panels():
            self.info_panel = "clock"
        self._hover_open = True
        self._apply_layout()
        if not self._drag:
            self._play_module_reaction("jumping")
            if self._oneshot == "jumping":
                self._alarm_pulses = 1
        self._play_alarm_sound()
        self._show_alarm_banner()

    def _play_alarm_sound(self) -> None:
        def work() -> None:
            if os.name != "nt":
                return
            try:
                import winsound

                for _ in range(3):
                    winsound.Beep(880, 160)
                    time.sleep(0.08)
                    winsound.Beep(1175, 200)
                    time.sleep(0.16)
            except Exception:
                return

        threading.Thread(target=work, daemon=True).start()

    def _show_alarm_banner(self) -> None:
        if getattr(self, "_closing", False):
            return
        existing = getattr(self, "_alarm_dlg", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.attributes("-topmost", True)
                    return
            except tk.TclError:
                pass
        ui = style()
        dlg = tk.Toplevel(self.root)
        dlg.title("时间到")
        dlg.attributes("-topmost", True)
        dlg.resizable(False, False)
        dlg.configure(bg=ui["settings_bg"])
        self._apply_app_icon(dlg)
        tk.Label(
            dlg,
            text="倒计时结束",
            bg=ui["settings_bg"],
            fg=ui.get("bar_low") or ui["accent"],
            font=ui["font_title"],
        ).pack(padx=22, pady=(16, 4))
        tk.Label(
            dlg,
            text="点「关掉」或闹钟上的开始按钮即可停止。",
            bg=ui["settings_bg"],
            fg=ui["settings_text"],
            font=ui["font_ui"],
            wraplength=260,
            justify="left",
        ).pack(padx=22, pady=(0, 10))
        btn = tk.Label(
            dlg,
            text="关掉",
            bg=ui.get("bar_low") or ui.get("accent", "#c94b4b"),
            fg="#ffffff",
            font=ui["font_title"],
            padx=22,
            pady=6,
        )
        btn.pack(pady=(0, 16))

        def close(_event=None) -> None:
            self._dismiss_alarm_banner()
            if clock_module.normalize_clock_state(getattr(self, "clock_state", {})).get("timer_ringing"):
                self._toggle_timer()

        btn.bind("<Button-1>", close)
        dlg.bind("<Return>", close)
        dlg.bind("<Escape>", close)
        dlg.protocol("WM_DELETE_WINDOW", close)
        try:
            dlg.geometry(f"+{self.root.winfo_rootx() + 40}+{self.root.winfo_rooty() - 8}")
        except tk.TclError:
            pass
        self._alarm_dlg = dlg
        dlg.after(12000, lambda: close() if dlg.winfo_exists() else None)

    def _dismiss_alarm_banner(self) -> None:
        dlg = getattr(self, "_alarm_dlg", None)
        self._alarm_dlg = None
        self._alarm_pulses = 0
        if dlg is None:
            return
        try:
            if dlg.winfo_exists():
                dlg.destroy()
        except tk.TclError:
            return

    def _set_timer_mode(self, mode: str) -> None:
        self._note_activity()
        self.clock_state = clock_module.set_timer_mode(getattr(self, "clock_state", {}), mode)
        self.clock_enabled = dict(self.clock_state.get("enabled") or self.clock_enabled)
        self.persist()
        self._rebuild_menu()
        self.draw()

    def _set_countdown_minutes(self, minutes: int) -> None:
        self._note_activity()
        self.clock_state = clock_module.set_countdown_minutes(getattr(self, "clock_state", {}), minutes)
        self.clock_enabled = dict(self.clock_state.get("enabled") or self.clock_enabled)
        self.persist()
        self._rebuild_menu()
        self.draw()

    def on_menu(self, event) -> None:
        self._note_activity()
        self._cancel_collapse()
        if not self._hover_open:
            self._reveal_bars(jump=False)
            self.draw()
        self._rebuild_menu()
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self.menu.grab_release()
            except tk.TclError:
                pass
            if not self._closing and not self.pinned:
                try:
                    self._schedule_collapse()
                except tk.TclError:
                    pass

    def toggle_expand(self) -> None:
        self._note_activity()
        self.pinned = not self.pinned
        if self.pinned:
            self._reveal_bars()
        elif self._hover is None:
            self._hover_open = False
            self._oneshot = None
        self.persist()
        self._apply_layout()
        self.draw()

    def open_settings(self) -> None:
        self._note_activity()
        if self._settings is not None and self._settings.winfo_exists():
            self._sync_setting_vars()
            self._settings.deiconify()
            self._settings.lift()
            self._settings.focus_force()
            return
        ui = style()
        win = tk.Toplevel(self.root)
        self._settings = win
        win.title(f"设置 · v{APP_VERSION}")
        self._apply_app_icon(win)
        win.attributes("-topmost", True)
        win.resizable(False, False)
        bg = ui["settings_bg"]
        card_bg = ui.get("inner", "#ffffff")
        win.configure(bg=bg)
        wrap = 300
        self._settings_paints: list = []
        self._skin_chips: dict[str, tk.Frame] = {}
        self._skin_var = tk.StringVar(value=self.skin_id)

        shell = tk.Frame(win, bg=bg)
        shell.pack(fill="both", expand=True, padx=16, pady=(8, 16))

        def heading(text: str) -> None:
            tk.Label(
                shell,
                text=text,
                bg=bg,
                fg=ui["settings_fg"],
                font=ui["font_title"],
                anchor="w",
            ).pack(fill="x", pady=(12, 6))

        def hint(text: str) -> None:
            tk.Label(
                shell,
                text=text,
                bg=bg,
                fg=ui["settings_muted"],
                font=ui["font"],
                wraplength=wrap,
                justify="left",
                anchor="w",
            ).pack(fill="x", pady=(4, 0))

        def card() -> tk.Frame:
            wrap_fr = tk.Frame(
                shell,
                bg=card_bg,
                highlightbackground=ui["bubble_outline"],
                highlightcolor=ui["bubble_outline"],
                highlightthickness=1,
                bd=0,
            )
            wrap_fr.pack(fill="x")
            inner = tk.Frame(wrap_fr, bg=card_bg)
            inner.pack(fill="x", padx=12, pady=8)
            return inner

        def add_switch(parent: tk.Frame, text: str, var: tk.BooleanVar, command) -> None:
            row = tk.Frame(parent, bg=card_bg)
            row.pack(fill="x", pady=5)
            tk.Label(
                row,
                text=text,
                bg=card_bg,
                fg=ui["settings_text"],
                font=ui["font_ui"],
                anchor="w",
            ).pack(side="left", fill="x", expand=True)
            cv = tk.Canvas(row, width=46, height=26, bg=card_bg, highlightthickness=0, bd=0)
            cv.pack(side="right")

            def paint(_var=var, _cv=cv) -> None:
                _cv.delete("all")
                on = bool(_var.get())
                fill = ui.get("accent", "#c94b4b") if on else ui["bar_track"]
                rounded = ui.get("bar_style") != "square"
                if rounded:
                    canvas_round_rect(_cv, 2, 4, 44, 22, 9, fill=fill, outline="")
                    knob = 33 if on else 13
                    _cv.create_oval(knob - 8, 5, knob + 8, 21, fill="#ffffff", outline="")
                else:
                    _cv.create_rectangle(2, 4, 44, 22, fill=fill, outline="")
                    knob = 30 if on else 10
                    _cv.create_rectangle(knob - 6, 6, knob + 10, 20, fill="#ffffff", outline="")

            def click(_event=None, _var=var, _cmd=command) -> None:
                _var.set(not bool(_var.get()))
                paint()
                _cmd()

            cv.bind("<Button-1>", click)
            self._settings_paints.append(paint)
            paint()

        heading("形象")
        chips = tk.Frame(shell, bg=bg)
        chips.pack(fill="x")
        skins = list_skins()
        for i, spec in enumerate(skins):
            sid = str(spec.get("id") or "")
            ready = bool(spec.get("_ready"))
            chip = tk.Frame(chips, bg=card_bg, highlightthickness=2, bd=0)
            chip.pack(side="left", fill="x", expand=True, padx=(0, 8) if i < len(skins) - 1 else 0)
            name = tk.Label(
                chip,
                text=str(spec.get("displayName") or sid),
                bg=card_bg,
                fg=ui["settings_fg"],
                font=ui["font_title"],
            )
            name.pack(anchor="w", padx=10, pady=(8, 0))
            sub = tk.Label(
                chip,
                text="已就绪" if ready else "待补素材",
                bg=card_bg,
                fg=ui["accent"] if ready else ui["settings_muted"],
                font=ui["font"],
            )
            sub.pack(anchor="w", padx=10, pady=(0, 8))

            def bind(widget, skin_id=sid, ok=ready) -> None:
                widget.bind("<Button-1>", lambda _e, s=skin_id, r=ok: self._pick_skin(s, r))

            bind(chip)
            bind(name)
            bind(sub)
            self._skin_chips[sid] = chip
        self._paint_skin_chips()
        hint("形象决定角色、配色和装饰。Original 是科技蓝，加藤惠是暖色圆角。")

        heading("时钟板块")
        inner = card()
        self._clock_vars = {}
        clock_labels = {"time": "显示时间", "timer": "闹钟与秒表"}
        for key in ("time", "timer"):
            var = tk.BooleanVar(value=self.clock_enabled.get(key, True))
            self._clock_vars[key] = var
            add_switch(inner, clock_labels[key], var, lambda k=key: self._on_toggle_clock(k))
        clock_mod = self._modules.get("clock")
        clock_perm = clock_mod.spec.permission_hint() if clock_mod is not None else ""
        hint(
            "本地功能，不需要账号。展开后点顶部「时钟 / 额度」切换。"
            "闹钟按主题绘制，可倒计时或秒表。时间到会弹窗、跳跃，并响一声短提示音。"
            + (f" {clock_perm}。" if clock_perm else "")
        )

        heading("额度板块")
        inner = card()
        self._enabled_vars = {}
        for key in BUBBLE_ROWS:
            var = tk.BooleanVar(value=self.enabled.get(key, True))
            self._enabled_vars[key] = var
            meta = POOL_META[key]
            add_switch(inner, f"{meta['title']}  {meta['tag']}", var, lambda k=key: self._on_toggle(k))
        quota_mod = self._modules.get("quota")
        perm = quota_mod.spec.permission_hint() if quota_mod is not None else ""
        hint(
            "可选信息模块。关掉全部来源后不再显示该板块，桌宠仍可单独使用。"
            + (f" {perm}。" if perm else "")
        )

        heading("随软件启动")
        inner = card()
        self._grok_start_var = tk.BooleanVar(value=grok_autostart_on())
        self._cursor_start_var = tk.BooleanVar(value=cursor_autostart_on())
        add_switch(inner, "随 Grok Build 启动", self._grok_start_var, self._on_toggle_grok_start)
        add_switch(inner, "随 Cursor 启动", self._cursor_start_var, self._on_toggle_cursor_start)
        hint("打开 Grok 或 Cursor 后几秒内出现。登录 Windows 后会在后台等待这两个软件。")

        heading("更新")
        inner = card()
        self._check_updates_var = tk.BooleanVar(value=self.check_updates)
        add_switch(inner, "启动后检查 GitHub 新版本", self._check_updates_var, self._on_toggle_check_updates)
        self._update_status = tk.Label(
            inner,
            text=self._update_status_text(),
            bg=card_bg,
            fg=ui["settings_muted"],
            font=ui["font"],
            wraplength=260,
            justify="left",
            anchor="w",
        )
        self._update_status.pack(fill="x", pady=(4, 4))
        tk.Button(
            inner,
            text="现在检查",
            command=lambda: self._check_update_now(manual=True),
            bg=card_bg,
            fg=ui["settings_text"],
            font=ui["font_ui"],
            activebackground=ui.get("settings_select", card_bg),
            activeforeground=ui["settings_text"],
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            anchor="w",
        ).pack(fill="x", pady=2)
        tk.Button(
            inner,
            text="下载并安装",
            command=self._apply_update,
            bg=card_bg,
            fg=ui["settings_text"],
            font=ui["font_ui"],
            activebackground=ui.get("settings_select", card_bg),
            activeforeground=ui["settings_text"],
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            anchor="w",
        ).pack(fill="x", pady=2)
        hint("只从 GitHub Release 下载官方 zip，校验 SHA256 后才会替换。不会静默安装。源码运行只能打开网页，不会改源码目录。")

        heading("卸载")
        inner = card()
        tk.Button(
            inner,
            text="清除本机数据并退出",
            command=self._confirm_purge,
            bg=card_bg,
            fg=ui["settings_text"],
            font=ui["font_ui"],
            activebackground=ui.get("settings_select", card_bg),
            activeforeground=ui["settings_text"],
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            anchor="w",
        ).pack(fill="x", pady=2)
        hint("删除自启、桌面快捷方式和额度快照，然后退出。不会退出 Grok / Cursor / Codex，也不会删除程序文件夹。")

        win.protocol("WM_DELETE_WINDOW", win.destroy)

    def _paint_skin_chips(self) -> None:
        ui = style()
        card_bg = ui.get("inner", "#ffffff")
        for sid, chip in (getattr(self, "_skin_chips", {}) or {}).items():
            selected = sid == self.skin_id
            edge = ui.get("accent", "#c94b4b") if selected else ui["bubble_outline"]
            chip.configure(highlightbackground=edge, highlightcolor=edge, bg=card_bg)
            for child in chip.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(bg=card_bg)

    def _pick_skin(self, skin_id: str, ready: bool) -> None:
        self._skin_var.set(skin_id)
        if not ready:
            self._on_skin()
            self._paint_skin_chips()
            return
        self._on_skin()
        self._paint_skin_chips()

    def _sync_setting_vars(self) -> None:
        if not hasattr(self, "_grok_start_var"):
            return
        self._grok_start_var.set(grok_autostart_on())
        self._cursor_start_var.set(cursor_autostart_on())
        if hasattr(self, "_check_updates_var"):
            self._check_updates_var.set(self.check_updates)
        if hasattr(self, "_update_status"):
            self._update_status.configure(text=self._update_status_text())
        if hasattr(self, "_skin_var"):
            self._skin_var.set(self.skin_id)
        for key, var in self._enabled_vars.items():
            var.set(self.enabled.get(key, True))
        for key, var in getattr(self, "_clock_vars", {}).items():
            var.set(self.clock_enabled.get(key, True))
        for paint in getattr(self, "_settings_paints", []):
            paint()
        self._paint_skin_chips()

    def _on_skin(self) -> None:
        want = str(self._skin_var.get() or "")
        if not want or want == self.skin_id:
            return
        if not skin_ready(want):
            self._skin_var.set(self.skin_id)
            self._toast(
                "还没有图集。\n请把 spritesheet.webp 放到：\n"
                + str(skin_folder(want))
                + "\n（说明见 素材说明.txt）"
            )
            return
        self.skin_id = activate_skin(want)
        self._photos.pop("_app_icon", None)
        self._load_sprites()
        self._play_oneshot("waving")
        self._note_activity()
        self._apply_app_icon(self.root)
        settings_geom = None
        if self._settings is not None and self._settings.winfo_exists():
            settings_geom = self._settings.geometry()
            self._settings.destroy()
            self._settings = None
        self.persist()
        self._apply_layout()
        self.draw()
        if settings_geom:
            self.open_settings()
            if self._settings is not None and self._settings.winfo_exists():
                self._settings.geometry(settings_geom)
        else:
            self._paint_skin_chips()

    def _on_toggle(self, key: str) -> None:
        var = self._enabled_vars.get(key)
        if var is None:
            return
        self._note_activity()
        self.enabled[key] = bool(var.get())
        self.info_panel = self.active_panel() or "quota"
        self.persist()
        self._rebuild_menu()
        self._apply_layout()
        self.draw()

    def _on_toggle_clock(self, key: str) -> None:
        var = getattr(self, "_clock_vars", {}).get(key)
        if var is None:
            return
        self._note_activity()
        self.clock_enabled[key] = bool(var.get())
        self.clock_state = clock_module.normalize_clock_state(self.clock_state)
        self.clock_state["enabled"] = dict(self.clock_enabled)
        self.info_panel = self.active_panel() or "quota"
        self.persist()
        self._rebuild_menu()
        self._apply_layout()
        self.draw()

    def _on_toggle_grok_start(self) -> None:
        want = bool(self._grok_start_var.get())
        try:
            if want:
                install_hook()
            else:
                uninstall_hook()
        except Exception as exc:
            self._grok_start_var.set(not want)
            self._toast(f"无法更改 Grok 启动：{exc}")
            return
        self._grok_start_var.set(grok_autostart_on())
        sync_watcher()

    def _on_toggle_cursor_start(self) -> None:
        want = bool(self._cursor_start_var.get())
        try:
            if want:
                install_cursor_hook()
            else:
                uninstall_cursor_hook()
        except Exception as exc:
            self._cursor_start_var.set(not want)
            self._toast(f"无法更改 Cursor 启动：{exc}")
            return
        self._cursor_start_var.set(cursor_autostart_on())
        sync_watcher()

    def _update_status_text(self) -> str:
        if self._update_busy:
            return "正在检查或下载…"
        info = self._update_info
        if info is None:
            return f"当前 v{APP_VERSION}。有新版本时会提示，需手动安装。"
        if app_update.is_newer(info.version):
            extra = "可下载安装。" if app_update.can_apply_inplace() else "请打开发布页自行下载。"
            return f"发现 v{info.version}。{extra}"
        return f"已是最新 v{APP_VERSION}。"

    def _refresh_update_status(self) -> None:
        if getattr(self, "_update_status", None) is not None:
            try:
                if self._update_status.winfo_exists():
                    self._update_status.configure(text=self._update_status_text())
            except tk.TclError:
                pass

    def _on_toggle_check_updates(self) -> None:
        self._note_activity()
        self.check_updates = bool(self._check_updates_var.get())
        self.persist()

    def _auto_check_update(self) -> None:
        if self._closing or not self.check_updates:
            return
        last = load_state().get("last_update_check")
        try:
            last_ts = float(last)
        except (TypeError, ValueError):
            last_ts = 0.0
        if time.time() - last_ts < app_update.CHECK_INTERVAL_S:
            return
        self._check_update_now(manual=False)

    def _check_update_now(self, *, manual: bool) -> None:
        if self._update_busy or self._closing:
            return
        self._update_busy = True
        self._refresh_update_status()

        def work() -> None:
            try:
                release = app_update.fetch_latest_release()
                self._update_results.put(("checked", release, manual, ""))
            except Exception as exc:
                self._update_results.put(("checked", None, manual, fu.redact_sensitive_text(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _apply_update(self) -> None:
        if self._update_busy or self._closing:
            return
        info = self._update_info
        if info is None or not app_update.is_newer(info.version):
            self._toast("请先检查更新。")
            return
        if not app_update.can_apply_inplace():
            self._open_release_page(info)
            self._toast("源码运行不会改文件。已打开 GitHub 发布页。")
            return
        self._update_busy = True
        self._refresh_update_status()
        release = info

        def work() -> None:
            try:
                work_dir = DATA_DIR / "update-staging"
                payload = app_update.download_verified_payload(release, work_dir)
                self._update_results.put(("ready", payload, True, ""))
            except Exception as exc:
                self._update_results.put(("ready", None, True, fu.redact_sensitive_text(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _open_release_page(self, info: app_update.LatestRelease | None) -> None:
        url = app_update.HTML_RELEASE_PREFIX + "latest"
        if info is not None and app_update.allowed_html_url(info.html_url):
            url = info.html_url
        webbrowser.open(url)

    def _poll_update_results(self) -> None:
        if self._closing:
            return
        try:
            while True:
                kind, payload, manual, err = self._update_results.get_nowait()
                self._apply_update_result(kind, payload, manual, err)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_update_results)

    def _apply_update_result(self, kind: str, payload, manual: bool, err: str) -> None:
        self._update_busy = False
        if kind == "checked":
            if err:
                self._refresh_update_status()
                if manual:
                    self._toast(f"检查失败：{err}")
                return
            save_state({"last_update_check": time.time()})
            info = payload
            self._update_info = info
            self._refresh_update_status()
            if info is not None and app_update.is_newer(info.version):
                if manual:
                    self._open_release_page(info)
                self._toast(f"有新版本 v{info.version}。")
            elif manual:
                self._toast(f"已是最新 v{APP_VERSION}。")
            return
        if err:
            self._refresh_update_status()
            if kind == "launched":
                self._toast(f"无法开始安装：{err}")
            else:
                self._toast(f"下载失败：{err}")
            return
        if kind == "ready":
            self._update_busy = True
            self._refresh_update_status()
            prepared = payload

            def launch() -> None:
                restart_watcher = grok_autostart_on() or cursor_autostart_on()
                try:
                    stop_app_processes()
                    app_update.launch_apply(
                        prepared,
                        fu.install_dir(),
                        os.getpid(),
                        restart_watcher=restart_watcher,
                    )
                except Exception as exc:
                    try:
                        app_update.discard_prepared_update(prepared)
                    except Exception:
                        pass
                    if restart_watcher:
                        try:
                            sync_watcher()
                        except Exception:
                            pass
                    self._update_results.put(("launched", None, True, fu.redact_sensitive_text(exc)))
                    return
                self._update_results.put(("launched", None, True, ""))

            threading.Thread(target=launch, daemon=True).start()
            return
        if kind != "launched":
            self._refresh_update_status()
            self._toast("更新状态无效。")
            return
        self._toast("将退出并安装新版本。")
        self.root.after(400, lambda: self.quit(mark_dismissed=False))

    def quit(self, *, keep_data: bool = True, mark_dismissed: bool = True) -> None:
        self._closing = True
        self._dismiss_alarm_banner()
        if keep_data and not self._preview_mode:
            self.persist()
            if mark_dismissed:
                try:
                    import watch_apps

                    watch_apps.mark_dismissed()
                except Exception:
                    pass
        try:
            if LOCK_FILE.exists() and LOCK_FILE.read_text(encoding="utf-8").strip() == str(os.getpid()):
                LOCK_FILE.unlink()
        except OSError:
            pass
        self.root.destroy()

    def watch_raise(self) -> None:
        if RAISE_FILE.exists():
            try:
                RAISE_FILE.unlink()
            except OSError:
                pass
            self._force_front()
        self.root.after(400, self.watch_raise)

    def install_shortcut(self) -> None:
        try:
            path = create_desktop_shortcut()
            try:
                on_desktop = path.parent.resolve() == desktop_dir().resolve()
            except OSError:
                on_desktop = False
            if on_desktop:
                self._toast(f"快捷方式：\n{path}")
            else:
                self._toast(
                    "桌面写入被拦截，已放在程序目录：\n"
                    f"{path}\n"
                    "可把它拖到桌面，或在 Windows 安全中心允许本程序访问桌面。"
                )
        except Exception as exc:
            self._toast(f"创建失败：{exc}")

    def _toast(self, text: str) -> None:
        ui = style()
        dlg = tk.Toplevel(self.root)
        dlg.title("提示")
        dlg.attributes("-topmost", True)
        dlg.resizable(False, False)
        dlg.configure(bg=ui["settings_bg"])
        self._apply_app_icon(dlg)
        tk.Label(
            dlg,
            text=text,
            bg=ui["settings_bg"],
            fg=ui["settings_text"],
            font=ui["font_ui"],
            wraplength=280,
            justify="left",
        ).pack(padx=18, pady=(16, 10))
        btn = tk.Label(
            dlg,
            text="好",
            bg=ui.get("accent", "#c94b4b"),
            fg="#ffffff",
            font=ui["font_title"],
            padx=20,
            pady=6,
        )
        btn.pack(pady=(0, 16))
        btn.bind("<Button-1>", lambda _e: dlg.destroy())
        dlg.bind("<Return>", lambda _e: dlg.destroy())
        dlg.transient(self.root)
        dlg.grab_set()

    def _confirm_purge(self) -> None:
        ui = style()
        remove_program = validated_self_delete_dir() is not None
        parent = self._settings if self._settings is not None and self._settings.winfo_exists() else self.root
        dlg = tk.Toplevel(parent)
        dlg.title("清除本机数据")
        dlg.attributes("-topmost", True)
        dlg.resizable(False, False)
        dlg.configure(bg=ui["settings_bg"])
        self._apply_app_icon(dlg)
        tk.Label(
            dlg,
            text=(
                "将删除自启、桌面快捷方式和额度快照，然后退出宠物。\n"
                "不会动 Grok / Cursor / Codex 的登录。\n"
                + (
                    "退出后会自动删除整个便携程序文件夹。"
                    if remove_program
                    else "源码 clone 或未验证目录请自行删除。"
                )
            ),
            bg=ui["settings_bg"],
            fg=ui["settings_text"],
            font=ui["font_ui"],
            wraplength=300,
            justify="left",
        ).pack(padx=18, pady=(16, 10))
        row = tk.Frame(dlg, bg=ui["settings_bg"])
        row.pack(fill="x", padx=18, pady=(0, 14))

        def cancel() -> None:
            dlg.destroy()

        def confirm() -> None:
            dlg.destroy()
            self._run_purge()

        tk.Button(
            row,
            text="取消",
            command=cancel,
            bg=ui.get("inner", "#ffffff"),
            fg=ui["settings_text"],
            font=ui["font"],
            relief="flat",
            bd=0,
        ).pack(side="right")
        tk.Button(
            row,
            text="完整卸载并退出" if remove_program else "清除并退出",
            command=confirm,
            bg=ui.get("accent", "#c94b4b"),
            fg="#ffffff",
            font=ui["font_title"],
            relief="flat",
            bd=0,
        ).pack(side="right", padx=(0, 8))
        dlg.bind("<Escape>", lambda _e: cancel())
        dlg.transient(parent)
        dlg.grab_set()
        dlg.focus_force()

    def _run_purge(self) -> None:
        result = purge_local_residue()
        if result["errors"]:
            self._toast(format_purge_report(result))
            self.root.after(50, lambda: self.quit(keep_data=False))
            return
        try:
            program_scheduled = schedule_self_delete()
        except Exception as exc:
            result["errors"].append(f"程序文件夹：{exc}")
            self._toast(format_purge_report(result))
            self.root.after(50, lambda: self.quit(keep_data=False))
            return
        if not program_scheduled and getattr(sys, "frozen", False):
            self._toast(format_purge_report(result))
            self.root.after(800, lambda: self.quit(keep_data=False))
            return
        self.quit(keep_data=False)

    def open_data_dir(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        path = str(DATA_DIR)
        # os.startfile() inside a Tk menu callback can take down pythonw on Windows.
        self.root.after(50, lambda: self._open_folder(path))

    def _open_folder(self, path: str) -> None:
        try:
            if os.name == "nt":
                subprocess.Popen(
                    ["explorer.exe", path],
                    close_fds=True,
                    creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                )
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path], start_new_session=True)
            else:
                subprocess.Popen(["xdg-open", path], start_new_session=True)
        except Exception as exc:
            self._toast(f"无法打开目录：{exc}")
            return
        self.root.after(200, self._force_front)

    def refresh_now(self) -> None:
        host = getattr(self, "_modules", None)
        if self._busy or self._closing:
            return
        if host is not None:
            if not host.wants_refresh(self.enabled):
                return
        elif not quota_sources_enabled(self.enabled):
            return
        self._busy = True
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self) -> None:
        host = getattr(self, "_modules", None) or info_modules.default_host()
        results = host.refresh_enabled(self.enabled)
        quota = results.get("quota")
        if quota is None:
            self._fetch_results.put((None, None))
            return
        self._fetch_results.put((quota.snapshot, quota.error))

    def _poll_fetch_results(self) -> None:
        if self._closing:
            return
        try:
            while True:
                snap, err = self._fetch_results.get_nowait()
                self._apply_fetch_result(snap, err)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_fetch_results)

    def _apply_fetch_result(self, snap: dict | None, err: str | None) -> None:
        self._busy = False
        if snap is not None and fu.snapshot_is_usable(snap):
            self.snap = snap
            self.error = err
            reaction = quota_fetch_oneshot(
                self._remainings(),
                error=bool(self.error),
                has_snap=self.snap is not None,
            )
            if reaction:
                self._play_module_reaction(reaction)
        else:
            self.error = err
        self._apply_layout()
        self.draw()

    def animate(self) -> None:
        self._tick += 1
        now = time.monotonic()
        elapsed_ms = (now - self._last_anim_at) * 1000.0
        self._last_anim_at = now
        self._maybe_idle_wave(now)
        name = self._current_anim()
        frames = self._anims.get(name) or []
        if name != self._anim:
            self._anim = name
            self._frame = 0
            self._frame_acc = 0.0
            self._look_acc = 0.0
            if name == "look":
                self._look_frame = self._look_target
        else:
            if name == "look" and self._look_target is not None:
                if self._look_frame is None:
                    self._look_frame = self._look_target
                steps, self._look_acc = _frame_clock_steps(
                    self._look_acc,
                    elapsed_ms,
                    LOOK_TRANSITION_MS,
                )
                for _ in range(min(steps, LOOK_SECTORS)):
                    if self._look_frame == self._look_target:
                        break
                    self._look_frame = _step_circular_index(
                        self._look_frame,
                        self._look_target,
                    )
            elif frames:
                delay = ANIM_MS.get(name, 200)
                steps, self._frame_acc = _frame_clock_steps(
                    self._frame_acc,
                    elapsed_ms,
                    delay,
                )
                last = len(frames) - 1
                if steps and self._oneshot == name and name in ONESHOT_ANIMS:
                    next_frame = self._frame + steps
                    if next_frame > last:
                        self._frame = last
                        self._frame_acc = 0.0
                        if self._oneshot == name:
                            self._oneshot = None
                    else:
                        self._frame = next_frame
                elif steps:
                    self._frame = (self._frame + steps) % len(frames)
        if getattr(self, "clock_enabled", {}).get("timer"):
            was_ringing = bool(clock_module.normalize_clock_state(getattr(self, "clock_state", {})).get("timer_ringing"))
            self.clock_state = clock_module.advance_timer(getattr(self, "clock_state", {}), time.time())
            if self.clock_state.get("timer_ringing") and not was_ringing:
                self._raise_alarm()
                self.persist()
            elif self.clock_state.get("timer_ringing") and not self._drag:
                pulses = getattr(self, "_alarm_pulses", 0)
                if self._oneshot is None and pulses < 4:
                    self._play_module_reaction("jumping")
                    if self._oneshot == "jumping":
                        self._alarm_pulses = pulses + 1
        self.draw()
        self.root.after(TICK_MS, self.animate)
        host = getattr(self, "_modules", None)
        interval = host.refresh_ms(self.enabled) if host is not None else (
            REFRESH_MS if quota_sources_enabled(self.enabled) else None
        )
        if interval and self._tick * TICK_MS % interval < TICK_MS:
            self.refresh_now()

    def draw(self) -> None:
        c = self.canvas
        c.delete("all")
        sprite_y = self._sprite_y
        cx = self._win_w // 2
        photo = self._current_photo()
        if photo is not None:
            h = photo.height()
            w = photo.width()
            c.create_image(cx, sprite_y + h // 2, image=photo)
            self._sprite_box = (cx - w // 2, sprite_y, cx + w // 2, sprite_y + h)
        else:
            c.create_oval(
                cx - 48,
                sprite_y + 20,
                cx + 48,
                sprite_y + 120,
                fill="#f7f7f7",
                outline="#222",
                width=2,
            )
            c.create_text(cx, sprite_y + 70, text=":)", font=("Segoe UI", 18, "bold"))
            self._sprite_box = (cx - 48, sprite_y + 20, cx + 48, sprite_y + 120)

        if self.bars_visible():
            self._draw_bubble()
        if self._hover in BUBBLE_ROWS or str(self._hover or "").startswith(("tmr_", "tab:")):
            self._draw_reset_tip()

    def _pools(self) -> dict:
        return build_pools(self.snap)

    def _draw_panel_tabs(self, c, x0: int, x1: int, y0: int, ui: dict) -> int:
        pad = 14
        track_y = y0 + 2
        track_h = clock_module.PANEL_TAB_H - 6
        tx0, tx1 = x0 + pad, x1 - pad
        mid = (tx0 + tx1) / 2
        rounded = ui.get("bar_style") != "square"
        inner = ui.get("inner") or ui["bar_track"]
        if rounded:
            canvas_round_rect(c, tx0, track_y, tx1, track_y + track_h, track_h / 2, fill=inner, outline="")
        else:
            c.create_rectangle(tx0, track_y, tx1, track_y + track_h, fill=inner, outline=ui["bubble_outline"])
        active = self.active_panel()
        for pid, label, left, right in (
            ("clock", "时钟", tx0, mid),
            ("quota", "额度", mid, tx1),
        ):
            on = pid == active
            if on:
                if rounded:
                    canvas_round_rect(
                        c, left + 3, track_y + 2, right - 3, track_y + track_h - 2,
                        (track_h - 4) / 2, fill=ui["accent"], outline="",
                    )
                else:
                    c.create_rectangle(left + 2, track_y + 2, right - 2, track_y + track_h - 2, fill=ui["accent"], outline="")
            if on:
                text_fill = "#10243A" if ui.get("decoration") == "circuit" else "#ffffff"
            else:
                text_fill = ui["label"]
            c.create_text(
                (left + right) / 2,
                track_y + track_h / 2,
                text=label,
                fill=text_fill,
                font=ui["font_title"],
            )
            self._panel_hits.append((f"tab:{pid}", int(left), int(track_y), int(right), int(track_y + track_h)))
        return y0 + clock_module.PANEL_TAB_H

    def _alarm_hand(self, c, cx: float, cy: float, length: float, angle: float, color: str, width: float) -> None:
        rad = math.radians(float(angle) - 90.0)
        c.create_line(
            cx, cy,
            cx + length * math.cos(rad),
            cy + length * math.sin(rad),
            fill=color, width=width, capstyle=tk.ROUND,
        )

    def _draw_alarm_clock(self, c, cx: float, cy: float, radius: float, ui: dict, view: dict) -> None:
        tick = getattr(self, "_tick", 0)
        shake = math.sin(tick / 1.6) * 6.0 if view.get("timer_ringing") else 0.0
        cx += shake
        style_key = ui.get("decoration") or "none"
        accent = ui["accent"]
        outline = ui["bubble_outline"]
        face = ui.get("inner") or ui["bubble_fill"]
        pct = ui["pct"]
        low = ui.get("bar_low") or accent
        if view.get("timer_ringing"):
            accent = low
        hour_deg = float(view.get("hour_deg") or 0)
        minute_deg = float(view.get("minute_deg") or 0)
        second_deg = float(view.get("second_deg") or 0)
        if style_key == "circuit":
            c.create_oval(cx - radius - 3, cy - radius - 3, cx + radius + 3, cy + radius + 3, outline=outline, width=2)
            c.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill=face, outline=accent, width=2)
            for deg in range(0, 360, 30):
                rad = math.radians(deg - 90)
                inner = radius - 4 if deg % 90 else radius - 7
                c.create_line(
                    cx + inner * math.cos(rad), cy + inner * math.sin(rad),
                    cx + (radius - 1) * math.cos(rad), cy + (radius - 1) * math.sin(rad),
                    fill=accent, width=2 if deg % 90 == 0 else 1,
                )
            fin = radius * 0.42
            for sign in (-1, 1):
                c.create_polygon(
                    cx + sign * 8, cy - radius - 2,
                    cx + sign * (8 + fin), cy - radius - 10,
                    cx + sign * (4 + fin), cy - radius - 16,
                    cx + sign * 4, cy - radius - 6,
                    fill=outline, outline=accent,
                )
            c.create_rectangle(cx - 3, cy - radius - 8, cx + 3, cy - radius - 2, fill=accent, outline="")
            if view.get("timer_mode") == "countdown":
                extent = max(8.0, min(359.0, 360.0 * float(view.get("progress") or 0)))
                c.create_arc(
                    cx - radius + 5, cy - radius + 5, cx + radius - 5, cy + radius - 5,
                    start=90, extent=-extent, style=tk.ARC, outline=accent, width=3,
                )
            self._alarm_hand(c, cx, cy, radius * 0.45, hour_deg, pct, 3)
            self._alarm_hand(c, cx, cy, radius * 0.68, minute_deg, accent, 2)
            self._alarm_hand(c, cx, cy, radius * 0.78, second_deg, low, 1)
            c.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=accent, outline="")
            return
        if style_key == "bow":
            bell_y = cy - radius - 4
            for sign in (-1, 1):
                c.create_oval(
                    cx + sign * 12 - 11, bell_y - 11,
                    cx + sign * 12 + 11, bell_y + 9,
                    fill=accent, outline=outline, width=1,
                )
                c.create_oval(
                    cx + sign * 12 - 6, bell_y - 8,
                    cx + sign * 12 + 2, bell_y - 1,
                    fill="#fff7f2", outline="",
                )
            c.create_oval(cx - 4, bell_y - 6, cx + 4, bell_y + 6, fill=ui.get("label_hot") or accent, outline=outline)
            c.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill="#fffaf6", outline=outline, width=2)
            c.create_oval(cx - radius + 4, cy - radius + 4, cx + radius - 4, cy + radius - 4, fill="#fff7f2", outline="")
            c.create_oval(cx - 16, cy + 4, cx - 6, cy + 12, fill="#f4c4bc", outline="")
            c.create_oval(cx + 6, cy + 4, cx + 16, cy + 12, fill="#f4c4bc", outline="")
            for deg in (0, 90, 180, 270):
                rad = math.radians(deg - 90)
                c.create_oval(
                    cx + (radius - 8) * math.cos(rad) - 2,
                    cy + (radius - 8) * math.sin(rad) - 2,
                    cx + (radius - 8) * math.cos(rad) + 2,
                    cy + (radius - 8) * math.sin(rad) + 2,
                    fill=accent, outline="",
                )
            c.create_line(cx - 7, cy + radius + 2, cx - 11, cy + radius + 10, fill=outline, width=2)
            c.create_line(cx + 7, cy + radius + 2, cx + 11, cy + radius + 10, fill=outline, width=2)
            if view.get("timer_mode") == "countdown":
                extent = max(8.0, min(359.0, 360.0 * float(view.get("progress") or 0)))
                c.create_arc(
                    cx - radius + 6, cy - radius + 6, cx + radius - 6, cy + radius - 6,
                    start=90, extent=-extent, style=tk.ARC, outline=accent, width=3,
                )
            self._alarm_hand(c, cx, cy, radius * 0.42, hour_deg, ui["label"], 3)
            self._alarm_hand(c, cx, cy, radius * 0.62, minute_deg, accent, 2)
            self._alarm_hand(c, cx, cy, radius * 0.72, second_deg, ui.get("label_hot") or accent, 1)
            c.create_oval(cx - 3.5, cy - 3.5, cx + 3.5, cy + 3.5, fill=accent, outline="")
            return
        c.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill=face, outline=outline, width=2)
        c.create_rectangle(cx - 14, cy - radius - 8, cx - 4, cy - radius + 2, fill=outline, outline="")
        c.create_rectangle(cx + 4, cy - radius - 8, cx + 14, cy - radius + 2, fill=outline, outline="")
        self._alarm_hand(c, cx, cy, radius * 0.5, minute_deg, accent, 2)
        self._alarm_hand(c, cx, cy, radius * 0.7, second_deg, pct, 1)
        c.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill=accent, outline="")

    def _draw_clock_button(self, c, x0: int, y0: int, x1: int, y1: int, text: str, key: str, ui: dict, *, primary: bool) -> None:
        rounded = ui.get("bar_style") != "square"
        fill = ui["accent"] if primary else ui["bar_track"]
        if rounded:
            canvas_round_rect(c, x0, y0, x1, y1, (y1 - y0) / 2, fill=fill, outline="")
        else:
            c.create_rectangle(x0, y0, x1, y1, fill=fill, outline=ui["bubble_outline"])
        if primary:
            text_fill = "#10243A" if ui.get("decoration") == "circuit" else "#ffffff"
        else:
            text_fill = ui["label"]
        c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=text, fill=text_fill, font=ui["font_title"])
        self._panel_hits.append((key, int(x0), int(y0), int(x1), int(y1)))

    def _draw_clock_panel(self, c, x0: int, x1: int, y: int, ui: dict) -> None:
        view = clock_module.clock_panel_view(
            getattr(self, "clock_enabled", {}),
            getattr(self, "clock_state", {}),
            now=time.time(),
        )
        family = ui["font_title"][0]
        pad = 16
        cx = (x0 + x1) / 2
        rounded = ui.get("bubble_style") != "classic"
        if view["show_time"]:
            c.create_text(
                x0 + pad, y + 12,
                text=f"{view['weekday']}  {view['date']}",
                fill=ui["muted"], font=ui["font_title"], anchor="w",
            )
            colon = ":" if view["colon_on"] else " "
            c.create_text(cx - 10, y + 54, text=view["hours"], fill=ui["pct"], font=(family, 24, "bold"), anchor="e")
            c.create_text(cx, y + 50, text=colon, fill=ui["accent"], font=(family, 22, "bold"))
            c.create_text(cx + 10, y + 54, text=view["minutes"], fill=ui["pct"], font=(family, 24, "bold"), anchor="w")
            c.create_text(x1 - pad, y + 54, text=view["seconds"], fill=ui["accent"], font=ui["font_title"], anchor="e")
            y += clock_module.CLOCK_TIME_H
        if view["show_timer"]:
            inner = ui.get("inner") or ui["bar_track"]
            card_y0 = y
            card_y1 = y + clock_module.CLOCK_TIMER_H - 8
            if rounded:
                canvas_round_rect(c, x0 + pad, card_y0, x1 - pad, card_y1, 16, fill=inner, outline="")
            else:
                c.create_rectangle(x0 + pad, card_y0, x1 - pad, card_y1, fill=inner, outline=ui["bubble_outline"])
            mode_y = card_y0 + 10
            mode_h = 22
            mid = (x0 + x1) / 2
            self._draw_clock_button(
                c, x0 + pad + 10, mode_y, mid - 4, mode_y + mode_h, "闹钟", "tmr_mode_countdown", ui,
                primary=view["timer_mode"] == "countdown",
            )
            self._draw_clock_button(
                c, mid + 4, mode_y, x1 - pad - 10, mode_y + mode_h, "秒表", "tmr_mode_stopwatch", ui,
                primary=view["timer_mode"] == "stopwatch",
            )
            face_cx = x0 + pad + 40
            face_cy = card_y0 + 72
            self._draw_alarm_clock(c, face_cx, face_cy, 28, ui, view)
            text_x = face_cx + 42
            c.create_text(text_x, card_y0 + 48, text=view["timer_status"], fill=ui["accent"], font=ui["font"], anchor="w")
            c.create_text(text_x, card_y0 + 74, text=view["timer_text"], fill=ui["pct"], font=(family, 18, "bold"), anchor="w")
            if view["timer_mode"] == "countdown":
                chip_y0 = card_y0 + 98
                chip_y1 = chip_y0 + 20
                chip_x = text_x
                for preset in view["presets"]:
                    right = chip_x + 34
                    self._draw_clock_button(
                        c, chip_x, chip_y0, right, chip_y1, preset["label"],
                        f"tmr_preset_{preset['minutes']}", ui, primary=bool(preset["selected"]),
                    )
                    chip_x = right + 6
            bw, bh = 54, 22
            by1 = card_y1 - 10
            by0 = by1 - bh
            reset_x1 = x1 - pad - 12
            reset_x0 = reset_x1 - bw
            tog_x1 = reset_x0 - 8
            tog_x0 = tog_x1 - bw
            self._draw_clock_button(c, tog_x0, by0, tog_x1, by1, view["toggle_label"], "tmr_toggle", ui, primary=True)
            self._draw_clock_button(c, reset_x0, by0, reset_x1, by1, view["reset_label"], "tmr_reset", ui, primary=False)

    def _draw_bubble(self) -> None:
        self._panel_hits = []
        panel = self.active_panel()
        if panel is None:
            return
        c = self.canvas
        ui = style()
        rounded = ui.get("bubble_style") != "classic"
        y0 = ui["bubble_top"]
        _w, _h, bubble_h = self._layout_metrics()
        y1 = bubble_h
        x0, x1 = 10, self._win_w - 10
        r = ui.get("radius") or 0
        cx = self._win_w // 2
        if rounded:
            canvas_round_rect(
                c, x0 + 3, y0 + 4, x1 + 3, y1 + 4, r,
                fill=ui["bubble_shadow"], outline="",
            )
            canvas_round_rect(
                c, x0, y0, x1, y1, r,
                fill=ui["bubble_fill"], outline=ui["bubble_outline"], width=2,
            )
            c.create_polygon(
                cx - 12, y1 - 8,
                cx + 12, y1 - 8,
                cx, y1 + 12,
                fill=ui["bubble_outline"], outline=ui["bubble_outline"],
            )
            c.create_polygon(
                cx - 10, y1 - 10,
                cx + 10, y1 - 10,
                cx, y1 + 10,
                fill=ui["bubble_fill"], outline=ui["bubble_fill"],
            )
            self._draw_decoration(cx, y0)
        else:
            c.create_rectangle(x0, y0, x1, y1, fill=ui["bubble_fill"], outline=ui["bubble_outline"], width=1)
            c.create_polygon(
                cx - 8, y1, cx + 8, y1, cx, y1 + 10,
                fill=ui["bubble_fill"], outline=ui["bubble_fill"],
            )
        tabs = len(self.available_panels()) > 1
        content_top = self._draw_panel_tabs(c, x0, x1, y0, ui) if tabs else y0
        if panel == "clock":
            self._draw_clock_panel(c, x0, x1, content_top, ui)
            return
        rows = self.visible_rows()
        if not rows:
            return
        pools = self._pools()
        pad = 16
        title_x = x0 + pad
        pct_right = x1 - pad
        title_font = tkfont.Font(font=ui["font"])
        pct_font = tkfont.Font(font=ui["font_title"])
        max_title = max((title_font.measure(pools[key]["title"]) for key in rows), default=0)
        max_pct = max((pct_font.measure(format_pool_pct(pools[key])) for key in rows), default=0)
        max_pct = max(max_pct, pct_font.measure("100%  100%"))
        period_x = title_x + max_title + 12
        pct_left = pct_right - max_pct
        for i, key in enumerate(rows):
            top = content_top + i * ui["row_h"]
            hot = self._hover in (key, "both")
            fill = ui["label_hot"] if hot else ui["label"]
            pool = pools[key]
            c.create_text(
                title_x,
                top + 14,
                text=pool["title"],
                fill=fill,
                font=ui["font_title"] if hot else ui["font"],
                anchor="w",
            )
            tag = str(pool.get("tag") or "")
            if tag and period_x + title_font.measure(tag) <= pct_left - 8:
                c.create_text(
                    period_x,
                    top + 14,
                    text=tag,
                    fill=ui.get("muted") or ui["label"],
                    font=ui["font"],
                    anchor="w",
                )
            c.create_text(
                pct_right,
                top + 14,
                text=format_pool_pct(pool),
                fill=ui["pct"] if not hot else ui["label_hot"],
                font=ui["font_title"],
                anchor="e",
            )
            if pool.get("show_bar", True):
                self._bar(
                    title_x,
                    top + 24,
                    (x1 - x0) - pad * 2,
                    12,
                    pool["remaining"],
                    layers=pool.get("layers"),
                )

    def _draw_bow(self, x: float, y: float) -> None:
        c = self.canvas
        red = style().get("accent", "#c94b4b")
        edge = _blend_hex(red, "#000000", 0.25)
        inner = _blend_hex(red, "#ffffff", 0.28)
        c.create_oval(x - 8, y - 5, x - 1, y + 5, fill=red, outline=edge, width=1)
        c.create_oval(x + 1, y - 5, x + 8, y + 5, fill=red, outline=edge, width=1)
        c.create_oval(x - 2.5, y - 3, x + 2.5, y + 3, fill=inner, outline=edge, width=1)

    def _draw_circuit(self, x: float, y: float) -> None:
        c = self.canvas
        accent = style().get("accent", "#45DFF2")
        c.create_line(x - 20, y, x - 7, y, fill=accent, width=2)
        c.create_line(x + 7, y, x + 20, y, fill=accent, width=2)
        c.create_line(x, y - 9, x, y + 9, fill=accent, width=2)
        c.create_oval(x - 5, y - 5, x + 5, y + 5, outline=accent, width=2)
        c.create_oval(x - 22, y - 3, x - 16, y + 3, outline=accent, width=1)
        c.create_oval(x + 16, y - 3, x + 22, y + 3, outline=accent, width=1)

    def _draw_decoration(self, x: float, y: float) -> None:
        mark = style().get("decoration") or "none"
        if mark == "bow":
            self._draw_bow(x, y)
        elif mark == "circuit":
            self._draw_circuit(x, y)

    def _wrap_text(self, text: str, font: tkfont.Font, max_px: int) -> list[str]:
        if max_px <= 8 or font.measure(text) <= max_px:
            return [text]
        lines: list[str] = []
        current = ""
        for ch in text:
            trial = current + ch
            if current and font.measure(trial) > max_px:
                lines.append(current.rstrip())
                current = "" if ch == " " else ch
            else:
                current = trial
        if current:
            lines.append(current.rstrip())
        return lines or [text]

    def _reset_lines(self) -> list[str]:
        hover = self._hover
        if hover == "tab:quota":
            return ["额度板块", "查看 AI 工具剩余额度"]
        if hover == "tab:clock":
            return ["时钟板块", "本地时间、秒表和倒计时闹钟"]
        if hover == "tmr_toggle":
            state = clock_module.normalize_clock_state(getattr(self, "clock_state", {}))
            if state.get("timer_ringing"):
                return ["闹钟", "关掉铃声"]
            label = "倒计时" if state.get("timer_mode") == "countdown" else "秒表"
            return [label, "暂停" if state.get("timer_running") else "开始"]
        if hover == "tmr_reset":
            return ["闹钟", "归零"]
        if hover == "tmr_mode_stopwatch":
            return ["秒表", "正向计时"]
        if hover == "tmr_mode_countdown":
            return ["闹钟", "倒计时"]
        if str(hover or "").startswith("tmr_preset_"):
            return ["倒计时", f"{str(hover).split('_')[-1]} 分钟"]
        pools = self._pools()
        if hover == "both":
            keys = list(self.visible_rows())
        elif hover in BUBBLE_ROWS:
            keys = [hover]
        else:
            keys = []
        lines: list[str] = []
        fetching = self._busy or self.snap is None
        for i, key in enumerate(keys):
            if i:
                lines.append("")
            lines.extend(pool_tip_lines(pools[key], fetching=fetching))
        return lines

    def _draw_reset_tip(self) -> None:
        if self._drag:
            return
        rows = self._reset_lines()
        if not any(rows):
            return
        c = self.canvas
        mx, my = self._mouse
        ui = style()
        pad_x, pad_y = 10, 8
        width = max(160, min(240, self._win_w - 16))
        inner = width - 2 * pad_x
        font_b = tkfont.Font(font=ui["font_title"])
        font_n = tkfont.Font(font=ui["font"])
        line_h = max(font_n.metrics("linespace"), 16)
        chunks: list[tuple[str, bool] | None] = []
        height = pad_y * 2
        for line in rows:
            if line == "":
                chunks.append(None)
                height += 6
                continue
            title = line in ROW_LABELS.values() or line in {meta["title"] for meta in POOL_META.values()}
            font = font_b if title else font_n
            wrapped = self._wrap_text(line, font, inner)
            for i, piece in enumerate(wrapped):
                chunks.append((piece, title and i == 0))
                height += line_h
        tx = mx + 14
        ty = my + 16
        if tx + width > self._win_w - 6:
            tx = mx - width - 8
        if ty + height > self._win_h - 6:
            ty = my - height - 8
        tx = max(6, min(tx, self._win_w - width - 6))
        ty = max(6, min(ty, self._win_h - height - 6))
        rounded = style().get("tip_style") != "square"
        if rounded:
            canvas_round_rect(
                c, tx, ty, tx + width, ty + height, 12,
                fill=ui["tip_fill"], outline=ui["tip_outline"], width=2,
            )
        else:
            c.create_rectangle(
                tx,
                ty,
                tx + width,
                ty + height,
                fill=ui["tip_fill"],
                outline=ui["tip_outline"],
                width=1,
            )
        y = ty + pad_y + 2
        for item in chunks:
            if item is None:
                y += 6
                continue
            piece, title = item
            c.create_text(
                tx + pad_x,
                y,
                text=piece,
                fill=ui["tip_title"] if title else ui["tip_text"],
                font=ui["font_title"] if title else ui["font"],
                anchor="nw",
            )
            y += line_h

    def _draw_spinner(self, cx: float, cy: float, radius: float = 6, color: str | None = None) -> None:
        if color is None:
            color = style()["spinner"]
        start = (-self._tick * 16) % 360
        self.canvas.create_arc(
            cx - radius,
            cy - radius,
            cx + radius,
            cy + radius,
            start=start,
            extent=270,
            style=tk.ARC,
            outline=color,
            width=2,
        )

    def _fill_bar(self, x: int, y: int, w: int, h: int, pct: float, fill: str, cute: bool) -> None:
        if pct <= 0:
            return
        fw = max(2, int(round(w * pct / 100.0)))
        x2 = x + min(w, fw)
        if cute:
            canvas_round_rect(self.canvas, x, y, x2, y + h, h / 2, fill=fill, outline="")
        else:
            self.canvas.create_rectangle(x, y, x2, y + h, fill=fill, outline="")

    def _bar(self, x: int, y: int, w: int, h: int, remaining, layers=None) -> None:
        c = self.canvas
        ui = style()
        cute = style().get("bar_style") != "square"
        if cute:
            canvas_round_rect(c, x, y, x + w, y + h, h / 2, fill=ui["bar_track"], outline="")
        else:
            c.create_rectangle(x, y, x + w, y + h, fill=ui["bar_track"], outline="")
        fills: list[tuple[float, str, str]] = []
        for layer in layers or []:
            rem = layer.get("remaining")
            if rem is None:
                continue
            pct = max(0.0, min(100.0, float(rem)))
            tone = layer.get("tone") or "dark"
            color = remaining_bar_fill(pct, ui, tone=tone)
            fills.append((pct, color, tone))
        if fills:
            for pct, color, _tone in sorted(
                fills, key=lambda item: (-item[0], 0 if item[2] == "light" else 1)
            ):
                self._fill_bar(x, y, w, h, pct, color, cute)
            return
        if remaining is None:
            pulse = 0.55 + 0.25 * math.sin(self._tick / 7.0)
            fill = _blend_hex(ui["bar_track"], ui.get("spinner") or ui["bar_ok"], pulse)
            sweep = int((w - 22) * (0.35 + 0.2 * math.sin(self._tick / 8.0)))
            offset = int((w - 22 - sweep) * (0.5 + 0.5 * math.sin(self._tick / 11.0)))
            x1 = x + offset
            x2 = x + offset + max(8, sweep)
            if cute:
                canvas_round_rect(c, x1, y, x2, y + h, h / 2, fill=fill, outline="")
            else:
                c.create_rectangle(x1, y, x2, y + h, fill=fill, outline="")
            self._draw_spinner(x + w - 10, y + h / 2, radius=5)
            return
        pct = max(0.0, min(100.0, float(remaining)))
        self._fill_bar(x, y, w, h, pct, remaining_bar_fill(pct, ui), cute)

    def run(self) -> None:
        print("entering mainloop", flush=True)
        self.root.mainloop()
        print("mainloop exit", flush=True)


def smoke_test() -> None:
    if Image is None:
        raise RuntimeError("Pillow is not available")
    default_spec = load_skin_spec(DEFAULT_SKIN_ID)
    atlas_path = skin_atlas_path(DEFAULT_SKIN_ID)
    if atlas_path is None:
        raise RuntimeError("default spritesheet is missing")
    atlas = default_spec.get("atlas") or {}
    expected = (int(atlas.get("width") or 0), int(atlas.get("height") or 0))
    with Image.open(atlas_path) as image:
        if image.size != expected:
            raise RuntimeError(f"spritesheet size {image.size} does not match {expected}")
        image.verify()
    icon_dir = skin_folder(DEFAULT_SKIN_ID)
    if not (icon_dir / "app.ico").exists() or not (icon_dir / "app.png").exists():
        raise RuntimeError("application icons are missing")
    print(f"smoke test OK: v{APP_VERSION} {atlas_path} {expected}")


def visual_smoke_snapshot() -> dict:
    return {
        "status": fu.STATUS_COMPLETE,
        "plan": "Visual Smoke",
        "period": {"end": "2030-01-01T00:00:00Z"},
        "used_percent": 28.0,
        "remaining_percent": 72.0,
        "products_used_percent": {"GrokChat": 28.0},
        "cursor": {
            "source_status": fu.SOURCE_OK,
            "grok_bot": {
                "used_percent": 39.0,
                "remaining_percent": 61.0,
                "resets_at": "2030-01-02T00:00:00Z",
            },
            "cursor_monthly": {
                "billing_cycle_end": "2030-01-31T00:00:00Z",
                "included_limit_cents": 2000,
                "included_used_cents": 650,
                "on_demand_allowed": False,
                "cursor_models": {"remaining_percent": 48.0, "hint": "Visual smoke test"},
                "other_models": {"remaining_percent": 84.0, "hint": "Visual smoke test"},
            },
        },
        "codex": {
            "source_status": fu.SOURCE_OK,
            "plan_type": "pro",
            "primary": {
                "remaining_percent": 67.0,
                "resets_at": "2030-01-01T05:00:00Z",
                "hint": "5 小时窗口",
            },
            "secondary": {
                "remaining_percent": 81.0,
                "resets_at": "2030-01-07T00:00:00Z",
                "hint": "7 天窗口",
            },
        },
        "errors": None,
    }


def main() -> None:
    args = sys.argv[1:]
    if "--smoke-test" in args:
        smoke_test()
        return
    if "--visual-smoke-test" in args:
        UsagePet(preview_snapshot=visual_smoke_snapshot(), auto_close_ms=3000).run()
        return
    if "--hook" in args:
        launch_detached()
        return
    if "--watch" in args:
        import watch_apps

        watch_apps.main()
        return
    if "--install" in args:
        activate_skin(str(load_state().get("skin") or DEFAULT_SKIN_ID))
        print(install_hook())
        print(create_desktop_shortcut())
        return
    if "--uninstall" in args:
        result = purge_local_residue()
        program_scheduled = False
        if not result["errors"]:
            try:
                program_scheduled = schedule_self_delete()
            except Exception as exc:
                result["errors"].append(f"program folder: {exc}")
        print(format_purge_report(result, program_scheduled=program_scheduled), flush=True)
        if result["errors"]:
            raise SystemExit(1)
        return
    if "--cli" in args:
        snap = fu.snapshot()
        if fu.write_snapshot(snap):
            print("updated local usage snapshot")
        else:
            print("usage unavailable; kept previous local snapshot", file=sys.stderr)
        raise SystemExit(fu.exit_code_for_snapshot(snap))

    log = DATA_DIR / "pet.log"
    try:
        sys.stderr = open(log, "a", encoding="utf-8")
        sys.stdout = sys.stderr
        print(f"start pid={os.getpid()}", flush=True)
    except OSError:
        pass
    try:
        if not claim_singleton():
            return
        try:
            import watch_apps

            watch_apps.clear_dismissed()
        except Exception:
            pass
        UsagePet().run()
    except Exception:
        import traceback

        try:
            log.write_text(fu.redact_sensitive_text(traceback.format_exc(), limit=4000), encoding="utf-8")
        except OSError:
            pass
        raise


if __name__ == "__main__":
    main()
