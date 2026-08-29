"""Atomic persistence for public usage snapshots."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def write_snapshot_files(directory: Path, snap: dict, summary: str) -> None:
    write_text_atomic(directory / "usage.json", json.dumps(snap, indent=2, ensure_ascii=False) + "\n")
    write_text_atomic(directory / "usage.txt", summary + "\n")
