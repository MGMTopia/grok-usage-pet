#!/usr/bin/env python3
"""Launch the pet when Grok or Cursor is running and autostart is enabled."""

from __future__ import annotations

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


def running_names() -> set[str]:
    names: set[str] = set()
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
            return names
        for line in out.splitlines():
            if line.startswith('"'):
                names.add(line.split('","')[0].strip('"').lower())
        return names
    try:
        out = subprocess.check_output(["ps", "-ax", "-o", "comm="], text=True, errors="ignore")
    except Exception:
        return names
    for line in out.splitlines():
        names.add(Path(line.strip()).name.lower())
    return names


def want_launch(running: set[str]) -> bool:
    if pet.grok_autostart_on() and running & GROK_PROCS:
        return True
    if pet.cursor_autostart_on() and running & CURSOR_PROCS:
        return True
    return False


def main() -> None:
    log = pet.DATA_DIR / "watch.log"
    pet.DATA_DIR.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            running = running_names()
            if want_launch(running):
                try:
                    pid = int(pet.LOCK_FILE.read_text(encoding="utf-8").strip())
                except Exception:
                    pid = 0
                if not pet.pid_running(pid):
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
