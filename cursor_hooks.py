"""Safe management of the shared Cursor hooks configuration."""

from __future__ import annotations

import json
import os
from pathlib import Path

from snapshot_store import write_text_atomic


MARKER = "grok-usage-pet"


def is_managed_entry(entry: object, expected_command: str) -> bool:
    if not isinstance(entry, dict):
        return False
    if entry.get("managedBy") == MARKER:
        return True
    command = str(entry.get("command") or "").strip()
    expected = expected_command.strip()
    if os.name == "nt":
        return os.path.normcase(command) == os.path.normcase(expected)
    return command == expected


def load_config(path: Path) -> tuple[dict, dict, list]:
    if not path.exists():
        payload: dict = {"version": 1, "hooks": {}}
    else:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Cursor hooks 配置无法读取，未作修改：{exc}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Cursor hooks 配置顶层必须是对象，未作修改")
    if "hooks" not in payload:
        payload["hooks"] = {}
    hooks = payload["hooks"]
    if not isinstance(hooks, dict):
        raise RuntimeError("Cursor hooks 字段必须是对象，未作修改")
    if "sessionStart" not in hooks:
        hooks["sessionStart"] = []
    session = hooks["sessionStart"]
    if not isinstance(session, list):
        raise RuntimeError("Cursor sessionStart 字段必须是数组，未作修改")
    return payload, hooks, session


def write_config(path: Path, payload: dict) -> None:
    write_text_atomic(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def install(path: Path, command: str) -> Path:
    payload, hooks, existing = load_config(path)
    session = [entry for entry in existing if not is_managed_entry(entry, command)]
    session.append({"command": command, "timeout": 15, "managedBy": MARKER})
    hooks["sessionStart"] = session
    payload["version"] = payload.get("version") or 1
    write_config(path, payload)
    return path


def uninstall(path: Path, command: str) -> None:
    if not path.exists():
        return
    payload, hooks, existing = load_config(path)
    session = [entry for entry in existing if not is_managed_entry(entry, command)]
    if session:
        hooks["sessionStart"] = session
    else:
        hooks.pop("sessionStart", None)
    payload["hooks"] = hooks
    write_config(path, payload)


def is_enabled(path: Path, command: str) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    hooks = payload.get("hooks") if isinstance(payload, dict) else None
    if not isinstance(hooks, dict):
        return False
    session = hooks.get("sessionStart")
    if not isinstance(session, list):
        return False
    return any(is_managed_entry(entry, command) for entry in session)
