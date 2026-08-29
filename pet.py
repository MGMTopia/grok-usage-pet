#!/usr/bin/env python3
"""Desktop pet that shows SuperGrok + Grok Bot remaining usage."""

from __future__ import annotations

import json
import math
import os
import shlex
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import Menu
from tkinter import font as tkfont

if getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))))
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import fetch_usage as fu

APP_DIR = fu.install_dir()
DATA_DIR = fu.data_dir()
LOCK_FILE = DATA_DIR / "pet.lock"
RAISE_FILE = DATA_DIR / "pet.raise"
STATE_FILE = DATA_DIR / "pet_state.json"
SKINS_DIR = fu.resource_dir() / "skins"
LEGACY_ASSETS = fu.resource_dir() / "assets"
DEFAULT_SKIN_ID = "megumi-kato"
ASSETS = LEGACY_ASSETS
HOOK_FILE = fu.grok_home() / "hooks" / "usage-pet.json"
CURSOR_HOOK_FILE = Path.home() / ".cursor" / "hooks.json"
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
# "classic" is the previous dark quota UI; kept but not offered in settings.
UI_THEME = "kawaii"
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
    },
    "kawaii": {
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
    },
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


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def skin_folder(skin_id: str) -> Path:
    return SKINS_DIR / skin_id


def load_skin_spec(skin_id: str) -> dict:
    spec = _read_json(skin_folder(skin_id) / "pet.json")
    if not spec and skin_id == DEFAULT_SKIN_ID:
        spec = _read_json(LEGACY_ASSETS / "pet.json")
    spec.setdefault("id", skin_id)
    spec.setdefault("displayName", skin_id)
    spec.setdefault("spritesheetPath", "spritesheet.webp")
    spec.setdefault("icon", "app.ico")
    spec.setdefault("iconPng", "app.png")
    spec.setdefault(
        "atlas",
        {
            "width": ATLAS_SIZE[0],
            "height": ATLAS_SIZE[1],
            "cellWidth": CELL_W,
            "cellHeight": CELL_H,
            "columns": 8,
            "rows": 11,
        },
    )
    if "animations" not in spec:
        spec["animations"] = {
            name: {"row": row, "frames": count, "ms": ANIM_MS.get(name, 200)}
            for name, (row, count) in ANIMATIONS.items()
        }
    spec.setdefault("look", {"rows": [9, 10], "framesPerRow": 8, "origin": "up", "order": "clockwise"})
    return spec


def skin_atlas_path(skin_id: str) -> Path | None:
    spec = load_skin_spec(skin_id)
    name = str(spec.get("spritesheetPath") or "spritesheet.webp")
    folders = [skin_folder(skin_id)]
    if skin_id == DEFAULT_SKIN_ID:
        folders.append(LEGACY_ASSETS)
    for folder in folders:
        path = folder / name
        if path.exists():
            return path
    return None


def skin_ready(skin_id: str) -> bool:
    return skin_atlas_path(skin_id) is not None


def list_skins() -> list[dict]:
    ids: list[str] = []
    if SKINS_DIR.exists():
        ids = [p.name for p in sorted(SKINS_DIR.iterdir()) if p.is_dir() and (p / "pet.json").exists()]
    if DEFAULT_SKIN_ID not in ids:
        ids.insert(0, DEFAULT_SKIN_ID)
    out: list[dict] = []
    for skin_id in ids:
        spec = load_skin_spec(skin_id)
        spec["_ready"] = skin_ready(skin_id)
        out.append(spec)
    return out


def activate_skin(skin_id: str) -> str:
    global ASSETS, CELL_W, CELL_H, SPRITE_W, SPRITE_H, ATLAS_SIZE, ATLAS_NAME, ANIMATIONS, ANIM_MS, LOOK_ROWS
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
    return str(spec.get("id") or skin_id)


def style() -> dict:
    return STYLES.get(UI_THEME) or STYLES["kawaii"]


def pick_ui_fonts(root: tk.Tk) -> None:
    families = {name.lower() for name in tkfont.families(root)}
    cute = None
    for name in ("幼圆", "YouYuan", "Yu Gothic", "Microsoft YaHei UI", "Segoe UI"):
        if name.lower() in families:
            cute = name
            break
    if not cute:
        cute = "Microsoft YaHei UI"
    STYLES["kawaii"]["font"] = (cute, 9)
    STYLES["kawaii"]["font_title"] = (cute, 9, "bold")
    STYLES["kawaii"]["font_ui"] = (cute, 10)


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
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
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


def format_reset(iso: str | None) -> tuple[str, str]:
    if not iso:
        return "到期时间未知", ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return str(iso), ""
    local = dt.astimezone()
    now = datetime.now().astimezone()
    secs = max(0, int((local - now).total_seconds()))
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    mins = rem // 60
    if days:
        left = f"还剩 {days} 天 {hours} 小时"
    elif hours:
        left = f"还剩 {hours} 小时 {mins} 分"
    else:
        left = f"还剩 {mins} 分钟"
    return f"重置 {local.strftime('%m月%d日 %H:%M')}", left


def _to_photo(im):
    im = im.convert("RGBA")
    alpha = im.getchannel("A").point(lambda v: 0 if v < 16 else v)
    im.putalpha(alpha)
    if os.name == "nt":
        bg = Image.new("RGBA", im.size, (*CHROMA_RGB, 255))
        bg.alpha_composite(im)
        return ImageTk.PhotoImage(bg.convert("RGB"))
    return ImageTk.PhotoImage(im)


def load_sprite(name: str, height: int):
    if Image is None or ImageTk is None:
        return None
    path = ASSETS / name
    if not path.exists():
        return None
    im = Image.open(path).convert("RGBA")
    ratio = height / im.height
    im = im.resize((max(1, int(im.width * ratio)), height), Image.Resampling.NEAREST)
    return _to_photo(im)


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
    return "GrokUsagePetKawaiiLaunch" if fu.pack_id() == "kawaii" else "GrokUsagePetLaunch"


def watch_task_name() -> str:
    return "GrokUsagePetKawaiiWatch" if fu.pack_id() == "kawaii" else "GrokUsagePetWatch"


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
    if not isinstance(entry, dict):
        return False
    cmd = str(entry.get("command") or "")
    return any(mark in cmd for mark in ("GrokUsagePet", "start_pet", "pet.py"))


def install_cursor_hook() -> Path:
    CURSOR_HOOK_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload: dict = {"version": 1, "hooks": {}}
    if CURSOR_HOOK_FILE.exists():
        try:
            loaded = json.loads(CURSOR_HOOK_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload.update(loaded)
        except json.JSONDecodeError:
            pass
    hooks = payload.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        payload["hooks"] = hooks
    session = [h for h in (hooks.get("sessionStart") or []) if not _is_our_cursor_hook(h)]
    session.append({"command": cursor_hook_command(), "timeout": 15})
    hooks["sessionStart"] = session
    payload["version"] = payload.get("version") or 1
    CURSOR_HOOK_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return CURSOR_HOOK_FILE


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
    if not CURSOR_HOOK_FILE.exists():
        return False
    try:
        payload = json.loads(CURSOR_HOOK_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    hooks = payload.get("hooks") if isinstance(payload, dict) else None
    if not isinstance(hooks, dict):
        return False
    return any(_is_our_cursor_hook(h) for h in (hooks.get("sessionStart") or []))


def uninstall_cursor_hook() -> None:
    if not CURSOR_HOOK_FILE.exists():
        return
    try:
        payload = json.loads(CURSOR_HOOK_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    hooks = payload.get("hooks")
    if not isinstance(hooks, dict):
        return
    session = [h for h in (hooks.get("sessionStart") or []) if not _is_our_cursor_hook(h)]
    if session:
        hooks["sessionStart"] = session
    else:
        hooks.pop("sessionStart", None)
    if hooks:
        payload["hooks"] = hooks
        CURSOR_HOOK_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    else:
        CURSOR_HOOK_FILE.unlink()


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
        shortcut_name = "Grok额度宠物-可爱版.lnk" if fu.pack_id() == "kawaii" else "Grok额度宠物.lnk"
        name = desktop / shortcut_name
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
    def __init__(self) -> None:
        self.snap: dict | None = None
        self.error: str | None = None
        self.pinned = bool(load_state().get("pinned", False))
        self.skin_id = activate_skin(str(load_state().get("skin") or DEFAULT_SKIN_ID))
        self.enabled = load_enabled()
        self._settings: tk.Toplevel | None = None
        self._drag = None
        self._drag_dx = 0
        self._last_drag_x = 0
        self._tick = 0
        self._busy = False
        self._photos: dict[str, object] = {}
        self._anims: dict[str, list] = {}
        self._looks: list = []
        self._anim = "idle"
        self._frame = 0
        self._frame_acc = 0
        self._oneshot: str | None = None
        self._waved = False
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
        self.root.title("Grok 额度")
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
        self.menu.add_command(label="固定 / 取消固定额度", command=self.toggle_expand)
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
            "pinned": self.pinned,
            "skin": self.skin_id,
        }
        try:
            save_state(payload)
        except tk.TclError:
            save_state({"enabled": dict(self.enabled), "pinned": self.pinned, "skin": self.skin_id})

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
        win = tk.Toplevel(self.root)
        self._settings = win
        ui = style()
        win.title("设置")
        self._apply_app_icon(win)
        win.attributes("-topmost", True)
        win.resizable(False, False)
        win.configure(bg=ui["settings_bg"])

        def heading(text: str, pady=(14, 8)) -> None:
            tk.Label(
                win,
                text=text,
                bg=ui["settings_bg"],
                fg=ui["settings_fg"],
                font=ui["font_title"],
            ).pack(anchor="w", padx=16, pady=pady)

        def hint(text: str, pady=(2, 8)) -> None:
            tk.Label(
                win,
                text=text,
                bg=ui["settings_bg"],
                fg=ui["settings_muted"],
                font=ui["font"],
                wraplength=260,
                justify="left",
            ).pack(anchor="w", padx=16, pady=pady)

        def checkbox(text: str, var: tk.BooleanVar, command) -> None:
            tk.Checkbutton(
                win,
                text=text,
                variable=var,
                command=command,
                bg=ui["settings_bg"],
                fg=ui["settings_text"],
                selectcolor=ui["settings_select"],
                activebackground=ui["settings_bg"],
                activeforeground=ui["settings_active"],
                highlightthickness=0,
                font=ui["font_ui"],
                anchor="w",
            ).pack(fill="x", padx=16, pady=2)

        heading("形象")
        self._skin_var = tk.StringVar(value=self.skin_id)
        for spec in list_skins():
            sid = str(spec.get("id") or "")
            label = str(spec.get("displayName") or sid)
            if not spec.get("_ready"):
                label += "（待补素材）"
            tk.Radiobutton(
                win,
                text=label,
                value=sid,
                variable=self._skin_var,
                command=self._on_skin,
                bg=ui["settings_bg"],
                fg=ui["settings_text"],
                selectcolor=ui["settings_select"],
                activebackground=ui["settings_bg"],
                activeforeground=ui["settings_active"],
                highlightthickness=0,
                font=ui["font_ui"],
                anchor="w",
            ).pack(fill="x", padx=16, pady=2)
        hint("原创形象把图集放到 skins\\original\\spritesheet.webp 后再选。布局见该目录「素材说明.txt」。")

        heading("显示哪些额度条")
        self._enabled_vars = {}
        for key in BUBBLE_ROWS:
            var = tk.BooleanVar(value=self.enabled.get(key, True))
            self._enabled_vars[key] = var
            checkbox(ROW_LABELS[key], var, lambda k=key: self._on_toggle(k))
        hint("关掉的条目不再显示，也不参与表情判断。")

        heading("随软件启动", pady=(6, 8))
        self._grok_start_var = tk.BooleanVar(value=grok_autostart_on())
        self._cursor_start_var = tk.BooleanVar(value=cursor_autostart_on())
        checkbox("随 Grok Build 启动", self._grok_start_var, self._on_toggle_grok_start)
        checkbox("随 Cursor 启动", self._cursor_start_var, self._on_toggle_cursor_start)
        hint("打开 Grok 或 Cursor 后几秒内出现。登录 Windows 后会在后台等待这两个软件。", pady=(4, 14))

        win.protocol("WM_DELETE_WINDOW", win.destroy)

    def _sync_setting_vars(self) -> None:
        if not hasattr(self, "_grok_start_var"):
            return
        self._grok_start_var.set(grok_autostart_on())
        self._cursor_start_var.set(cursor_autostart_on())
        if hasattr(self, "_skin_var"):
            self._skin_var.set(self.skin_id)
        for key, var in self._enabled_vars.items():
            var.set(self.enabled.get(key, True))

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
        self._oneshot = None
        self._waved = False
        self._failed_played = False
        self._photos.pop("_app_icon", None)
        self._load_sprites()
        self._apply_app_icon(self.root)
        if self._settings is not None and self._settings.winfo_exists():
            self._apply_app_icon(self._settings)
        self.persist()
        self._apply_layout()
        self.draw()

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
        from tkinter import messagebox

        messagebox.showinfo("Grok 额度", text)

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
        if self._busy:
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
        def apply() -> None:
            first = self.snap is None
            self._busy = False
            if snap is not None:
                self.snap = snap
                self.error = err
            else:
                self.error = err
            if first and snap is not None and not self._waved:
                vals = self._remainings()
                worst = min(vals) if vals else None
                if worst is None or worst >= 20:
                    self._play_oneshot("waving")
                self._waved = True
            self._apply_layout()
            self.draw()
        self.root.after(0, apply)

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
        snap = self.snap or {}
        cur = snap.get("cursor") or {}
        monthly = cur.get("cursor_monthly") or {}
        return {
            "sg": {
                "title": "SuperGrok",
                "remaining": snap.get("remaining_percent"),
                "reset": (snap.get("period") or {}).get("end"),
                "extra": ["Chat / Build / Imagine 共用周池"],
            },
            "bot": {
                "title": "Grok Bot",
                "remaining": (cur.get("grok_bot") or {}).get("remaining_percent"),
                "reset": (cur.get("grok_bot") or {}).get("resets_at"),
                "extra": ["Cursor 账号上的独立周额度"],
            },
            "cm": {
                "title": "Cursor 模型",
                "remaining": (monthly.get("cursor_models") or {}).get("remaining_percent"),
                "reset": monthly.get("billing_cycle_end"),
                "extra": self._cursor_extra(monthly, "cursor_models"),
            },
            "om": {
                "title": "其他模型",
                "remaining": (monthly.get("other_models") or {}).get("remaining_percent"),
                "reset": monthly.get("billing_cycle_end"),
                "extra": self._cursor_extra(monthly, "other_models"),
            },
        }

    def _cursor_extra(self, monthly: dict, key: str) -> list[str]:
        pool = monthly.get(key) or {}
        lines = [pool.get("hint") or ""]
        limit = monthly.get("included_limit_cents")
        used = monthly.get("included_used_cents")
        if key == "om" and limit is not None:
            used_v = (used or 0) / 100
            limit_v = limit / 100
            lines.append(f"套餐内 ${used_v:.2f} / ${limit_v:.2f}")
        lines.append("On-Demand 开" if monthly.get("on_demand_allowed") else "On-Demand 关")
        if monthly.get("display_message") and key == "om":
            lines.append(str(monthly["display_message"]))
        hint_msg = pool.get("display_message")
        if hint_msg:
            lines.append(str(hint_msg))
        return [line for line in lines if line]

    def _draw_bubble(self) -> None:
        if UI_THEME == "classic":
            self._draw_bubble_classic()
            return
        self._draw_bubble_kawaii()

    def _draw_bubble_classic(self) -> None:
        c = self.canvas
        ui = STYLES["classic"]
        rows = self.visible_rows()
        if not rows:
            return
        y1 = ui["bubble_top"] + len(rows) * ui["row_h"]
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
        self._draw_bow(cx, y0)
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
        if UI_THEME == "kawaii":
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
        cute = UI_THEME == "kawaii"
        if cute:
            canvas_round_rect(c, x, y, x + w, y + h, h / 2, fill=ui["bar_track"], outline="")
        else:
            c.create_rectangle(x, y, x + w, y + h, fill=ui["bar_track"], outline="")
        if remaining is None:
            pulse = 0.55 + 0.25 * math.sin(self._tick / 7.0)
            if cute:
                mix = int(180 + 40 * pulse)
                fill = f"#{mix:02x}{int(mix * 0.72):02x}{int(mix * 0.70):02x}"
            else:
                gray = int(40 + 50 * pulse)
                fill = f"#{gray:02x}{gray:02x}{int(gray * 1.15):02x}"
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
        fill = ui["bar_ok"] if pct >= 50 else ui["bar_mid"] if pct >= 20 else ui["bar_low"]
        fw = max(h if cute else 2, int(w * pct / 100.0)) if pct > 0 else 0
        if fw > 0:
            if cute:
                canvas_round_rect(c, x, y, x + min(w, fw), y + h, h / 2, fill=fill, outline="")
            else:
                c.create_rectangle(x, y, x + fw, y + h, fill=fill, outline="")
        if not cute:
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


def main() -> None:
    args = sys.argv[1:]
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
        return

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
