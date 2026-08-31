#!/usr/bin/env python3
"""Launch the pet when Grok or Cursor is running and autostart is enabled."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pet  # noqa: E402

CREATE_NO_WINDOW = 0x08000000
GROK_PROCS = {"grok.exe", "agent.exe"}
CURSOR_PROCS = {"cursor.exe"}
GROK_MAIN_PROCS = {"grok.exe"}
CURSOR_MAIN_PROCS = {"cursor.exe"}
DISMISS_NAME = "dismissed.json"


def dismiss_file() -> Path:
    return pet.DATA_DIR / DISMISS_NAME


def running_procs() -> dict[str, set[int]]:
    procs: dict[str, set[int]] = {}
    if os.name == "nt":
        try:
            out = subprocess.check_output(
                ["tasklist", "/FO", "CSV", "/NH"],
                creationflags=CREATE_NO_WINDOW,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
        except Exception:
            return procs
        for line in out.splitlines():
            if not line.startswith('"'):
                continue
            parts = line.split('","')
            if len(parts) < 2:
                continue
            name = parts[0].strip('"').lower()
            try:
                pid = int(parts[1].strip('"'))
            except ValueError:
                continue
            procs.setdefault(name, set()).add(pid)
        return procs
    try:
        out = subprocess.check_output(["ps", "-ax", "-o", "pid=,comm="], text=True, errors="ignore")
    except Exception:
        return procs
    for line in out.splitlines():
        raw = line.strip()
        if not raw:
            continue
        pid_text, _, rest = raw.partition(" ")
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        name = Path(rest.strip()).name.lower()
        if name:
            procs.setdefault(name, set()).add(pid)
    return procs


def running_names(procs: dict[str, set[int]] | None = None) -> set[str]:
    if procs is None:
        procs = running_procs()
    return {name for name, pids in procs.items() if pids}


def family_pids(procs: dict[str, set[int]], names: set[str]) -> set[int]:
    pids: set[int] = set()
    for name in names:
        pids |= set(procs.get(name) or ())
    return pids


def want_launch(running: set[str]) -> bool:
    if pet.grok_autostart_on() and running & GROK_PROCS:
        return True
    if pet.cursor_autostart_on() and running & CURSOR_PROCS:
        return True
    return False


def load_dismiss() -> dict | None:
    path = dismiss_file()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def save_dismiss(data: dict) -> None:
    pet.DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = dismiss_file()
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def mark_dismissed(procs: dict[str, set[int]] | None = None) -> None:
    if procs is None:
        procs = running_procs()
    save_dismiss(
        {
            "dismissed": True,
            "at": time.time(),
            "grok_pids": sorted(family_pids(procs, GROK_MAIN_PROCS)),
            "cursor_pids": sorted(family_pids(procs, CURSOR_MAIN_PROCS)),
        }
    )


def clear_dismissed() -> None:
    path = dismiss_file()
    try:
        path.unlink()
    except OSError:
        pass


def _pid_set(values) -> set[int]:
    pids: set[int] = set()
    for value in values or []:
        try:
            pids.add(int(value))
        except (TypeError, ValueError):
            continue
    return pids


def allow_autostart(
    procs: dict[str, set[int]],
    *,
    dismiss: dict | None = None,
) -> bool:
    """Whether an automatic launch may run. Manual GUI starts do not use this."""
    if not want_launch(running_names(procs)):
        return False
    if dismiss is None:
        dismiss = load_dismiss()
    if not dismiss or not dismiss.get("dismissed"):
        return True
    grok_now = family_pids(procs, GROK_MAIN_PROCS)
    cursor_now = family_pids(procs, CURSOR_MAIN_PROCS)
    saved_grok = _pid_set(dismiss.get("grok_pids"))
    saved_cursor = _pid_set(dismiss.get("cursor_pids"))
    if pet.grok_autostart_on() and grok_now and not grok_now <= saved_grok:
        return True
    if pet.cursor_autostart_on() and cursor_now and not cursor_now <= saved_cursor:
        return True
    return False


def main() -> None:
    log = pet.DATA_DIR / "watch.log"
    pet.DATA_DIR.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            procs = running_procs()
            if want_launch(running_names(procs)):
                try:
                    pid = int(pet.LOCK_FILE.read_text(encoding="utf-8").strip())
                except Exception:
                    pid = 0
                if not pet.pid_running(pid) and allow_autostart(procs):
                    pet.launch_detached()
        except Exception as exc:
            try:
                with log.open("a", encoding="utf-8") as fh:
                    fh.write(f"{exc}\n")
            except OSError:
                pass
        time.sleep(2)


if __name__ == "__main__":
    main()
