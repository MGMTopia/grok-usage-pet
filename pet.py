#!/usr/bin/env python3
"""Desktop pet that shows SuperGrok + Grok Bot remaining usage."""

from __future__ import annotations

import json
import math
import os
import queue
import re
import shlex
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import Menu
from tkinter import font as tkfont

if getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))))
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import fetch_usage as fu
import cursor_hooks
from app_version import APP_VERSION
from pet_view_model import build_pools, format_reset
from skin_catalog import SkinCatalog

DATA_DIR = fu.data_dir()
LOCK_FILE = DATA_DIR / "pet.lock"
RAISE_FILE = DATA_DIR / "pet.raise"
STATE_FILE = DATA_DIR / "pet_state.json"
SKINS_DIR = fu.resource_dir() / "skins"
DEFAULT_SKIN_ID = "original"
ASSETS = SKINS_DIR / DEFAULT_SKIN_ID
HOOK_FILE = fu.grok_home() / "hooks" / "usage-pet.json"
CURSOR_HOOK_FILE = Path.home() / ".cursor" / "hooks.json"
CURSOR_HOOK_MARKER = cursor_hooks.MARKER
BG = "#1b1b1f"
CHROMA = "#ff00ff"
CHROMA_RGB = (255, 0, 255)
REFRESH_MS = 60_000
TICK_MS = 40
COLLAPSE_MS = 380
CELL_W = 192
CELL_H = 208
SPRITE_W = 192
SPRITE_H = 208
# "classic" is the previous dark quota UI; kept as a compatibility preset.
DEFAULT_THEME_PRESET = "soft"
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
        "radius": 0,
        "bubble_style": "classic",
        "bar_style": "square",
        "tip_style": "square",
        "decoration": "none",
        "accent": "#5eead4",
        "inner": "#111111",
    },
    "tech": {
        "row_h": 44,
        "bubble_w": 276,
        "bubble_top": 20,
        "bubble_bottom": 14,
        "bubble_fill": "#10243a",
        "bubble_outline": "#45dff2",
        "bubble_shadow": "#071522",
        "label": "#a9c9d8",
        "label_hot": "#72f1ff",
        "bar_track": "#203b52",
        "bar_ok": "#36d9c4",
        "bar_mid": "#f0bd57",
        "bar_low": "#ff6688",
        "pct": "#d9f8ff",
        "tip_fill": "#0d1d30",
        "tip_outline": "#45dff2",
        "tip_title": "#72f1ff",
        "tip_text": "#d7eaf2",
        "spinner": "#72f1ff",
        "font": ("Microsoft YaHei UI", 9),
        "font_title": ("Microsoft YaHei UI", 9, "bold"),
        "font_ui": ("Microsoft YaHei UI", 10),
        "settings_bg": "#0b1b2b",
        "settings_fg": "#d7eaf2",
        "settings_muted": "#7898aa",
        "settings_text": "#d7eaf2",
        "settings_select": "#17334a",
        "settings_active": "#72f1ff",
        "radius": 10,
        "accent": "#45dff2",
        "inner": "#10243a",
        "bubble_style": "rounded",
        "bar_style": "rounded",
        "tip_style": "rounded",
        "decoration": "circuit",
    },
    "soft": {
        "row_h": 44,
        "bubble_w": 276,
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
        "radius": 18,
        "accent": "#c94b4b",
        "inner": "#ffffff",
        "bubble_style": "rounded",
        "bar_style": "rounded",
        "tip_style": "rounded",
        "decoration": "bow",
    },
}
ACTIVE_STYLE = dict(STYLES[DEFAULT_THEME_PRESET])
THEME_COLOR_KEYS = {
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
    "settingsBackground": "settings_bg",
    "settingsForeground": "settings_fg",
    "settingsMuted": "settings_muted",
    "settingsText": "settings_text",
    "settingsSelect": "settings_select",
    "settingsActive": "settings_active",
    "inner": "inner",
}
THEME_STYLE_KEYS = {
    "bubbleStyle": ("bubble_style", {"classic", "rounded"}),
    "barStyle": ("bar_style", {"square", "rounded"}),
    "tipStyle": ("tip_style", {"square", "rounded"}),
    "decoration": ("decoration", {"none", "bow", "circuit"}),
}
BUBBLE_ROWS = ("sg", "bot", "cm", "om")
ROW_LABELS = {
    "sg": "SuperGrok",
    "bot": "Grok Bot",
    "cm": "Cursor 模型",
    "om": "其他模型",
}
DEFAULT_ENABLED = {"sg": True, "bot": True, "cm": True, "om": True}
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
ONESHOT_ANIMS = {"jumping", "waving", "failed"}
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
    global ASSETS, CELL_W, CELL_H, SPRITE_W, SPRITE_H, ATLAS_SIZE, ATLAS_NAME, ANIMATIONS, ANIM_MS, LOOK_ROWS, ACTIVE_STYLE
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
    ASSETS = folder
    ACTIVE_STYLE = resolve_theme(spec.get("theme"))
    return str(spec.get("id") or skin_id)


def resolve_theme(raw: object) -> dict:
    theme = raw if isinstance(raw, dict) else {}
    preset = str(theme.get("preset") or DEFAULT_THEME_PRESET).strip().lower()
    if preset not in STYLES:
        preset = DEFAULT_THEME_PRESET
    resolved = dict(STYLES[preset])
    for public_key, internal_key in THEME_COLOR_KEYS.items():
        value = theme.get(public_key)
        if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            resolved[internal_key] = value
    for public_key, (internal_key, allowed) in THEME_STYLE_KEYS.items():
        value = str(theme.get(public_key) or "").strip().lower()
        if value in allowed:
            resolved[internal_key] = value
    radius = theme.get("radius")
    if isinstance(radius, (int, float)) and not isinstance(radius, bool):
        resolved["radius"] = max(0, min(28, int(radius)))
    return resolved


def style() -> dict:
    return ACTIVE_STYLE


def pick_ui_fonts(root: tk.Tk) -> None:
    families = {name.lower() for name in tkfont.families(root)}
    cute = None
    for name in ("幼圆", "YouYuan", "Yu Gothic", "Microsoft YaHei UI", "Segoe UI"):
        if name.lower() in families:
            cute = name
            break
    if not cute:
        cute = "Microsoft YaHei UI"
    for preset in STYLES.values():
        size = 8 if preset.get("bubble_style") == "classic" else 9
        preset["font"] = (cute, size)
        preset["font_title"] = (cute, size, "bold")
        preset["font_ui"] = (cute, 10)
    size = 8 if ACTIVE_STYLE.get("bubble_style") == "classic" else 9
    ACTIVE_STYLE["font"] = (cute, size)
    ACTIVE_STYLE["font_title"] = (cute, size, "bold")
    ACTIVE_STYLE["font_ui"] = (cute, 10)


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
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        if isinstance(data, dict):
            # Fixed-open is a session interaction. Older builds persisted both
            # fields, which could make the quota card look permanently stuck.
            data.pop("expanded", None)
            data.pop("pinned", None)
            return data
    return {}


def save_state(data: dict) -> None:
    current = load_state()
    current.update(data)
    STATE_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")


def load_enabled() -> dict[str, bool]:
    raw = (load_state().get("enabled") or {}) if STATE_FILE.exists() else {}
    enabled = dict(DEFAULT_ENABLED)
    for key in BUBBLE_ROWS:
        if key in raw:
            enabled[key] = bool(raw[key])
    return enabled


def _to_photo(im):
    im = im.convert("RGBA")
    alpha = im.getchannel("A").point(lambda v: 0 if v < 16 else v)
    im.putalpha(alpha)
    if os.name == "nt":
        bg = Image.new("RGBA", im.size, (*CHROMA_RGB, 255))
        bg.alpha_composite(im)
        return ImageTk.PhotoImage(bg.convert("RGB"))
    return ImageTk.PhotoImage(im)


def load_atlas_frames() -> dict[str, list]:
    if Image is None or ImageTk is None:
        return {}
    path = ASSETS / ATLAS_NAME
    if not path.exists():
        return {}
    atlas = Image.open(path).convert("RGBA")
    if atlas.size != ATLAS_SIZE:
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
    return "GrokUsagePetLaunch"


def watch_task_name() -> str:
    return "GrokUsagePetWatch"


def launch_detached() -> None:
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
    payload = {
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
    HOOK_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return HOOK_FILE


def uninstall_hook() -> None:
    if HOOK_FILE.exists():
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
    return HOOK_FILE.exists()


def cursor_autostart_on() -> bool:
    return cursor_hooks.is_enabled(CURSOR_HOOK_FILE, cursor_hook_command())


def uninstall_cursor_hook() -> None:
    cursor_hooks.uninstall(CURSOR_HOOK_FILE, cursor_hook_command())


def desktop_dir() -> Path:
    home = Path.home()
    for candidate in (
        home / "Desktop",
        home / "OneDrive" / "Desktop",
        home / "OneDrive" / "Documents" / "Desktop",
    ):
        if candidate.exists():
            return candidate
    return home / "Desktop"


def create_desktop_shortcut() -> Path:
    _target, args = gui_command()
    desktop = desktop_dir()
    if os.name == "nt":
        name = desktop / "Grok额度宠物.lnk"
        arg_str = ""
        if len(args) > 1:
            arg_str = " ".join(f"'{a}'" for a in args[1:])
        icon = ASSETS / "app.ico"
        icon_ps = f"; $s.IconLocation = '{icon.resolve()},0'" if icon.exists() else ""
        cmd = (
            "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('"
            + str(name)
            + "'); $s.TargetPath = '"
            + _target
            + "'; $s.Arguments = \""
            + arg_str.replace('"', "")
            + "\"; $s.WorkingDirectory = '"
            + str(fu.install_dir())
            + "'; $s.WindowStyle = 1; $s.Description = 'Grok remaining usage pet'"
            + icon_ps
            + "; $s.Save()"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            check=True,
            creationflags=CREATE_NO_WINDOW,
        )
        return name
    name = desktop / "Grok额度宠物.command"
    quoted = " ".join(shlex.quote(part) for part in args)
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
        state = load_state()
        self.pinned = self._preview_mode
        self.skin_id = activate_skin(str(state.get("skin") or DEFAULT_SKIN_ID))
        self.enabled = load_enabled()
        if not self._preview_mode and STATE_FILE.exists():
            save_state({})
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
        self._frame_acc = 0
        self._oneshot: str | None = None
        self._waved = self._preview_mode
        self._failed_played = False
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
        self.root.title(f"Grok 额度 v{APP_VERSION}")
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
        self.menu.add_command(label="刷新额度", command=self.refresh_now)
        self.menu.add_command(label="固定额度条（本次运行）", command=self.toggle_expand)
        self._pin_menu_index = 1
        self.menu.add_command(label="设置…", command=self.open_settings)
        self.menu.add_command(label="创建桌面快捷方式", command=self.install_shortcut)
        self.menu.add_separator()
        self.menu.add_command(label="打开数据目录", command=self.open_data_dir)
        self.menu.add_command(label="退出宠物", command=self.quit)

        for seq, fn in (
            ("<ButtonPress-1>", self.on_press),
            ("<B1-Motion>", self.on_drag),
            ("<ButtonRelease-1>", self.on_release),
            ("<Double-Button-1>", lambda e: self.toggle_expand()),
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
        self._apply_chrome()
        self._apply_layout(initial=True)
        self.draw()
        self._apply_chrome()
        self.root.deiconify()
        self.root.geometry(self._geom)
        self.root.after(100, self._poll_fetch_results)
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

    def bars_visible(self) -> bool:
        return bool((self.pinned or self._hover_open) and self.visible_rows())

    def _layout_metrics(self) -> tuple[int, int, int]:
        ui = style()
        rows = self.visible_rows() if self.bars_visible() else ()
        extra = int(ui.get("bubble_bottom") or 0)
        bubble_h = (ui["bubble_top"] + len(rows) * ui["row_h"] + extra) if rows else 0
        win_w = ui["bubble_w"] if rows else SPRITE_W
        win_h = bubble_h + SPRITE_H
        return win_w, win_h, bubble_h

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
        self._win_w, self._win_h, self._sprite_y = win_w, win_h, sprite_y
        self._geom = f"{win_w}x{win_h}+{new_x}+{new_y}"
        self.canvas.config(width=win_w, height=win_h)
        self.root.geometry(self._geom)
        self._apply_chrome()
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

    def _play_oneshot(self, name: str) -> None:
        if name in self._anims:
            self._oneshot = name

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
        if dist < 40 or dist > 340:
            return None
        ang = math.degrees(math.atan2(dx, -dy))
        if ang < 0:
            ang += 360
        return int((ang + 11.25) / 22.5) % 16

    def _current_anim(self) -> str:
        if self._drag:
            if self._drag_dx < 0 and "running-left" in self._anims:
                return "running-left"
            if self._drag_dx > 0 and "running-right" in self._anims:
                return "running-right"
            return self._anim if self._anim in ("running-left", "running-right") else "idle"
        if self.snap is None and "waiting" in self._anims:
            return "waiting"
        remaining = self._remainings()
        worst = min(remaining) if remaining else None
        low = (worst is not None and worst < 20) or (
            not remaining and self.error and self.snap is not None
        )
        if not low:
            self._failed_played = False
        elif not self._failed_played:
            self._failed_played = True
            self._play_oneshot("failed")
        if self._oneshot and self._oneshot in self._anims:
            return self._oneshot
        if self._busy and "running" in self._anims:
            return "running"
        if self.bars_visible() and "review" in self._anims:
            return "review"
        if self._look_index() is not None:
            return "look"
        if "idle" in self._anims:
            return "idle"
        return self.mood()

    def _current_photo(self):
        if self._anim == "look":
            idx = self._look_index()
            if idx is not None:
                return self._looks[idx]
        frames = self._anims.get(self._anim) or self._anims.get("idle") or []
        if frames:
            return frames[self._frame % len(frames)]
        mood = self.mood()
        return self._photos.get(mood) or self._photos.get("idle")

    def visible_rows(self) -> tuple[str, ...]:
        return tuple(key for key in BUBBLE_ROWS if self.enabled.get(key, True))

    def persist(self) -> None:
        x, y = self._collapsed_origin()
        payload = {
            "x": x,
            "y": y,
            "enabled": dict(self.enabled),
            "skin": self.skin_id,
        }
        try:
            save_state(payload)
        except tk.TclError:
            save_state({"enabled": dict(self.enabled), "skin": self.skin_id})

    def _remainings(self) -> list[float]:
        if not self.snap:
            return []
        vals: list[float] = []
        pools = self._pools()
        for key in self.visible_rows():
            remaining = pools[key].get("remaining")
            if remaining is not None:
                vals.append(float(remaining))
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
        if self.bars_visible():
            ui = style()
            rows = self.visible_rows()
            for i, key in enumerate(rows):
                top = ui["bubble_top"] + i * ui["row_h"]
                if top <= y < top + ui["row_h"]:
                    return key
        x0, y0, x1, y1 = self._sprite_box
        if x0 <= x < x1 and y0 <= y < y1:
            return "pet"
        return None

    def on_press(self, event) -> None:
        self._drag = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y())
        self._last_drag_x = event.x_root
        self._drag_dx = 0

    def on_drag(self, event) -> None:
        if not self._drag:
            return
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
        self._drag = None
        self._drag_dx = 0
        self.persist()

    def on_menu(self, event) -> None:
        self._cancel_collapse()
        self.menu.entryconfigure(
            self._pin_menu_index,
            label="取消固定额度条" if self.pinned else "固定额度条（本次运行）",
        )
        if not self._hover_open:
            self._reveal_bars(jump=False)
            self.draw()
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()
            if not self.pinned:
                self._schedule_collapse()

    def toggle_expand(self) -> None:
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
                canvas_round_rect(_cv, 2, 4, 44, 22, 9, fill=fill, outline="")
                knob = 33 if on else 13
                _cv.create_oval(knob - 8, 5, knob + 8, 21, fill="#ffffff", outline="")

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
        hint("皮肤会同时切换角色、额度卡、提示框与设置配色。")

        heading("额度条")
        inner = card()
        self._enabled_vars = {}
        for key in BUBBLE_ROWS:
            var = tk.BooleanVar(value=self.enabled.get(key, True))
            self._enabled_vars[key] = var
            add_switch(inner, ROW_LABELS[key], var, lambda k=key: self._on_toggle(k))
        hint("关掉的条目不再显示，也不参与表情判断。")

        heading("随软件启动")
        inner = card()
        self._grok_start_var = tk.BooleanVar(value=grok_autostart_on())
        self._cursor_start_var = tk.BooleanVar(value=cursor_autostart_on())
        add_switch(inner, "随 Grok Build 启动", self._grok_start_var, self._on_toggle_grok_start)
        add_switch(inner, "随 Cursor 启动", self._cursor_start_var, self._on_toggle_cursor_start)
        hint("打开 Grok 或 Cursor 后几秒内出现。登录 Windows 后会在后台等待这两个软件。")

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
        changed = self._on_skin()
        if not changed:
            self._paint_skin_chips()

    def _sync_setting_vars(self) -> None:
        if not hasattr(self, "_grok_start_var"):
            return
        self._grok_start_var.set(grok_autostart_on())
        self._cursor_start_var.set(cursor_autostart_on())
        if hasattr(self, "_skin_var"):
            self._skin_var.set(self.skin_id)
        for key, var in self._enabled_vars.items():
            var.set(self.enabled.get(key, True))
        for paint in getattr(self, "_settings_paints", []):
            paint()
        self._paint_skin_chips()

    def _on_skin(self) -> bool:
        want = str(self._skin_var.get() or "")
        if not want or want == self.skin_id:
            return False
        if not skin_ready(want):
            self._skin_var.set(self.skin_id)
            self._toast(
                "还没有图集。\n请把 spritesheet.webp 放到：\n"
                + str(skin_folder(want))
                + "\n（说明见 素材说明.txt）"
            )
            return False
        reopen_settings = self._settings is not None and self._settings.winfo_exists()
        self.skin_id = activate_skin(want)
        self._oneshot = None
        self._waved = False
        self._failed_played = False
        self._photos.pop("_app_icon", None)
        self._load_sprites()
        self._apply_app_icon(self.root)
        if reopen_settings:
            self._settings.destroy()
            self._settings = None
            self._skin_chips = {}
        self.persist()
        self._apply_layout()
        self.draw()
        if reopen_settings:
            self.root.after_idle(self.open_settings)
        else:
            self._paint_skin_chips()
        return True

    def _on_toggle(self, key: str) -> None:
        var = self._enabled_vars.get(key)
        if var is None:
            return
        self.enabled[key] = bool(var.get())
        self.persist()
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

    def quit(self) -> None:
        self._closing = True
        if not self._preview_mode:
            self.persist()
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
            self._toast(f"快捷方式：\n{path}")
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
        if self._busy or self._closing:
            return
        self._busy = True
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self) -> None:
        err = None
        snap = None
        try:
            snap = fu.snapshot()
            fu.write_snapshot(snap)
            if snap.get("errors"):
                err = "；".join(f"{k}: {v}" for k, v in snap["errors"].items())
        except (Exception, SystemExit) as exc:
            err = str(exc)
        self._fetch_results.put((snap, err))

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
        first = self.snap is None
        self._busy = False
        if snap is not None and fu.snapshot_is_usable(snap):
            self.snap = snap
            self.error = err
        else:
            self.error = err
        if first and snap is not None and fu.snapshot_is_usable(snap) and not self._waved:
            vals = self._remainings()
            worst = min(vals) if vals else None
            if worst is None or worst >= 20:
                self._play_oneshot("waving")
            self._waved = True
        self._apply_layout()
        self.draw()

    def animate(self) -> None:
        self._tick += 1
        name = self._current_anim()
        frames = self._anims.get(name) or []
        if name != self._anim:
            self._anim = name
            self._frame = 0
            self._frame_acc = 0
        else:
            self._frame_acc += TICK_MS
            delay = ANIM_MS.get(name, 200)
            if frames and self._frame_acc >= delay:
                self._frame_acc = 0
                last = len(frames) - 1
                if name in ONESHOT_ANIMS and self._frame >= last:
                    if self._oneshot == name:
                        self._oneshot = None
                else:
                    self._frame = (self._frame + 1) % len(frames)
        self.draw()
        self.root.after(TICK_MS, self.animate)
        if self._tick * TICK_MS % REFRESH_MS < TICK_MS:
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
        if self._hover in BUBBLE_ROWS:
            self._draw_reset_tip()

    def _pools(self) -> dict:
        return build_pools(self.snap)

    def _draw_bubble(self) -> None:
        if style().get("bubble_style") == "classic":
            self._draw_bubble_classic()
            return
        self._draw_bubble_kawaii()

    def _draw_bubble_classic(self) -> None:
        c = self.canvas
        ui = style()
        rows = self.visible_rows()
        if not rows:
            return
        y1 = ui["bubble_top"] + len(rows) * ui["row_h"] + int(ui.get("bubble_bottom") or 0)
        x0, y0, x1 = 10, ui["bubble_top"], self._win_w - 10
        c.create_rectangle(x0, y0, x1, y1, fill=ui["bubble_fill"], outline=ui["bubble_outline"], width=1)
        c.create_polygon(
            self._win_w // 2 - 8,
            y1,
            self._win_w // 2 + 8,
            y1,
            self._win_w // 2,
            y1 + 10,
            fill=ui["bubble_fill"],
            outline=ui["bubble_fill"],
        )
        pools = self._pools()
        for i, key in enumerate(rows):
            top = ui["bubble_top"] + i * ui["row_h"]
            hot = self._hover in (key, "both")
            fill = ui["label_hot"] if hot else ui["label"]
            c.create_text(
                22,
                top + 16,
                text=pools[key]["title"],
                fill=fill,
                font=ui["font"],
                anchor="w",
            )
            self._bar(22, top + 20, self._win_w - 34, 14, pools[key]["remaining"])

    def _draw_bow(self, x: float, y: float) -> None:
        c = self.canvas
        red = style().get("accent", "#c94b4b")
        edge = "#b03d3d"
        c.create_oval(x - 8, y - 5, x - 1, y + 5, fill=red, outline=edge, width=1)
        c.create_oval(x + 1, y - 5, x + 8, y + 5, fill=red, outline=edge, width=1)
        c.create_oval(x - 2.5, y - 3, x + 2.5, y + 3, fill="#d96a6a", outline=edge, width=1)

    def _draw_theme_mark(self, x: float, y: float) -> None:
        ui = style()
        decoration = ui.get("decoration", "none")
        if decoration == "bow":
            self._draw_bow(x, y)
        elif decoration == "circuit":
            accent = ui.get("accent", "#45dff2")
            c = self.canvas
            c.create_line(x - 15, y, x - 5, y, x, y + 5, x + 5, y, x + 15, y, fill=accent, width=2)
            c.create_oval(x - 2.5, y + 2.5, x + 2.5, y + 7.5, fill=accent, outline="")

    def _draw_bubble_kawaii(self) -> None:
        c = self.canvas
        ui = style()
        rows = self.visible_rows()
        if not rows:
            return
        y0 = ui["bubble_top"]
        y1 = y0 + len(rows) * ui["row_h"] + int(ui.get("bubble_bottom") or 0)
        x0, x1 = 10, self._win_w - 10
        r = ui["radius"]
        cx = self._win_w // 2
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
        self._draw_theme_mark(cx, y0)
        pools = self._pools()
        for i, key in enumerate(rows):
            top = y0 + i * ui["row_h"]
            hot = self._hover in (key, "both")
            fill = ui["label_hot"] if hot else ui["label"]
            remaining = pools[key]["remaining"]
            if remaining is None:
                pct_text = "…"
            else:
                pct_text = f"{max(0.0, min(100.0, float(remaining))):.0f}%"
            c.create_text(
                x0 + 16,
                top + 14,
                text=pools[key]["title"],
                fill=fill,
                font=ui["font_title"] if hot else ui["font"],
                anchor="w",
            )
            c.create_text(
                x1 - 16,
                top + 14,
                text=pct_text,
                fill=ui["pct"] if not hot else ui["label_hot"],
                font=ui["font_title"],
                anchor="e",
            )
            self._bar(x0 + 16, top + 24, (x1 - x0) - 32, 12, remaining)

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
        pools = self._pools()
        if hover == "both":
            keys = list(self.visible_rows())
        elif hover in BUBBLE_ROWS:
            keys = [hover]
        else:
            keys = []
        lines: list[str] = []
        for i, key in enumerate(keys):
            if i:
                lines.append("")
            pool = pools[key]
            lines.append(pool["title"])
            if pool.get("remaining") is None:
                lines.append("正在获取…" if self._busy or self.snap is None else "暂时没拿到，正在重试")
                continue
            when, left = format_reset(pool.get("reset"))
            lines.append(when)
            if left:
                lines.append(left)
            for extra in pool.get("extra") or []:
                lines.append(extra)
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
            title = line in ("SuperGrok", "Grok Bot", "Cursor 模型", "其他模型")
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
        if ui.get("tip_style") == "rounded":
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

    def _bar(self, x: int, y: int, w: int, h: int, remaining) -> None:
        c = self.canvas
        ui = style()
        rounded = ui.get("bar_style") == "rounded"
        if rounded:
            canvas_round_rect(c, x, y, x + w, y + h, h / 2, fill=ui["bar_track"], outline="")
        else:
            c.create_rectangle(x, y, x + w, y + h, fill=ui["bar_track"], outline="")
        if remaining is None:
            pulse = 0.55 + 0.25 * math.sin(self._tick / 7.0)
            if rounded:
                fill = ui["bar_ok"]
            else:
                gray = int(40 + 50 * pulse)
                fill = f"#{gray:02x}{gray:02x}{int(gray * 1.15):02x}"
            sweep = int((w - 22) * (0.35 + 0.2 * math.sin(self._tick / 8.0)))
            offset = int((w - 22 - sweep) * (0.5 + 0.5 * math.sin(self._tick / 11.0)))
            x1 = x + offset
            x2 = x + offset + max(8, sweep)
            if rounded:
                canvas_round_rect(c, x1, y, x2, y + h, h / 2, fill=fill, outline="")
            else:
                c.create_rectangle(x1, y, x2, y + h, fill=fill, outline="")
            self._draw_spinner(x + w - 10, y + h / 2, radius=5)
            return
        pct = max(0.0, min(100.0, float(remaining)))
        fill = ui["bar_ok"] if pct >= 50 else ui["bar_mid"] if pct >= 20 else ui["bar_low"]
        fw = max(h if rounded else 2, int(w * pct / 100.0)) if pct > 0 else 0
        if fw > 0:
            if rounded:
                canvas_round_rect(c, x, y, x + min(w, fw), y + h, h / 2, fill=fill, outline="")
            else:
                c.create_rectangle(x, y, x + fw, y + h, fill=fill, outline="")
        if not rounded and ui.get("bubble_style") == "classic":
            c.create_text(
                x + w - 2,
                y + h // 2,
                text=f"{pct:.0f}%",
                fill=ui["pct"],
                font=("Segoe UI", 8, "bold"),
                anchor="e",
            )

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
    if not (ASSETS / "app.ico").exists() or not (ASSETS / "app.png").exists():
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
        print(install_hook())
        print(create_desktop_shortcut())
        return
    if "--uninstall" in args:
        uninstall_hook()
        print("uninstalled autostart hook")
        return
    if "--cli" in args:
        snap = fu.snapshot()
        fu.write_snapshot(snap)
        print(fu.one_line(snap))
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
        UsagePet().run()
    except Exception:
        import traceback

        try:
            log.write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        raise


if __name__ == "__main__":
    main()
