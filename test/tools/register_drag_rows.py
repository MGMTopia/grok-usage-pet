from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from PIL import Image


CELL_W = 192
CELL_H = 208
DRAG_ROWS = {"running-right": 1, "running-left": 2}


def core_center_x(cell: Image.Image) -> float:
    alpha = cell.getchannel("A")
    pixels = alpha.load()
    weighted_x = 0
    weight = 0
    # Hat, head, neck, and upper torso form a much more stable anchor than
    # the complete silhouette, whose hands and feet deliberately extend.
    for y in range(0, 125):
        for x in range(CELL_W):
            value = pixels[x, y]
            if value > 8:
                weighted_x += x * value
                weight += value
    if not weight:
        raise ValueError("empty core region")
    return weighted_x / weight


def translate(cell: Image.Image, dx: int) -> Image.Image:
    shifted = Image.new("RGBA", cell.size, (0, 0, 0, 0))
    shifted.alpha_composite(cell, (dx, 0))
    return shifted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_png", type=Path)
    parser.add_argument("output_webp", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()

    atlas = Image.open(args.source).convert("RGBA")
    if atlas.size != (1536, 2288):
        raise SystemExit(f"unexpected atlas size: {atlas.size}")

    repaired = atlas.copy()
    rows_report: dict[str, object] = {}

    for state, row in DRAG_ROWS.items():
        cells = [
            atlas.crop(
                (
                    column * CELL_W,
                    row * CELL_H,
                    (column + 1) * CELL_W,
                    (row + 1) * CELL_H,
                )
            )
            for column in range(8)
        ]
        before = [core_center_x(cell) for cell in cells]
        target = statistics.median(before)
        shifts = [round(target - center) for center in before]
        after = []

        for column, (cell, dx) in enumerate(zip(cells, shifts, strict=True)):
            moved = translate(cell, dx)
            bbox = moved.getchannel("A").getbbox()
            if bbox is None or bbox[0] <= 0 or bbox[2] >= CELL_W:
                raise SystemExit(f"{state} frame {column} would clip after shift {dx}")
            # Replace the complete RGBA cell. Supplying the sprite itself as a
            # paste mask would multiply its edge alpha and damage antialiasing.
            repaired.paste(moved, (column * CELL_W, row * CELL_H))
            after.append(core_center_x(moved))

        rows_report[state] = {
            "target_core_x": round(target, 3),
            "before_core_x": [round(value, 3) for value in before],
            "before_range": round(max(before) - min(before), 3),
            "integer_shifts": shifts,
            "after_core_x": [round(value, 3) for value in after],
            "after_range": round(max(after) - min(after), 3),
        }

    args.output_png.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    # WebP can retain hidden RGB beneath fully transparent pixels. Clear it so
    # the installed atlas continues to satisfy the v2 deterministic validator.
    pixels = repaired.load()
    for y in range(repaired.height):
        for x in range(repaired.width):
            if pixels[x, y][3] == 0:
                pixels[x, y] = (0, 0, 0, 0)

    repaired.save(args.output_png)
    repaired.save(args.output_webp, format="WEBP", lossless=True, method=6)
    args.report.write_text(
        json.dumps({"ok": True, "rows": rows_report}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
