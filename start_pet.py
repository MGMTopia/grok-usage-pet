#!/usr/bin/env python3
"""Launch the usage pet detached so a Grok SessionStart hook can exit immediately."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pet  # noqa: E402


if __name__ == "__main__":
    pet.launch_detached()
