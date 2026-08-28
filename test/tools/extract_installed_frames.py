from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


CELL_W = 192
CELL_H = 208
STANDARD_ROWS = {
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("atlas", type=Path)
    parser.add_argument("frames_root", type=Path)
    args = parser.parse_args()

    atlas = Image.open(args.atlas).convert("RGBA")
    if atlas.size != (1536, 2288):
        raise SystemExit(f"unexpected atlas size: {atlas.size}")

    for state, (row, count) in STANDARD_ROWS.items():
        state_dir = args.frames_root / state
        state_dir.mkdir(parents=True, exist_ok=True)
        for column in range(count):
            box = (
                column * CELL_W,
                row * CELL_H,
                (column + 1) * CELL_W,
                (row + 1) * CELL_H,
            )
            atlas.crop(box).save(state_dir / f"{column:02d}.png")


if __name__ == "__main__":
    main()
