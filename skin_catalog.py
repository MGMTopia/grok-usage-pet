"""Filesystem-backed skin discovery and manifest defaults."""

from __future__ import annotations

import json
from pathlib import Path


DEFAULT_ATLAS = {
    "width": 1536,
    "height": 2288,
    "cellWidth": 192,
    "cellHeight": 208,
    "columns": 8,
    "rows": 11,
}
MAX_ATLAS_DIMENSION = 4096
MAX_ATLAS_PIXELS = 16_777_216
MAX_ATLAS_GRID = 64
MAX_CELL_DIMENSION = 1024
MAX_ANIMATION_FRAMES = 64
MAX_LOOK_ROWS = 4
MIN_ANIMATION_MS = 16
MAX_ANIMATION_MS = 10_000


def _bounded_int(value: object, fallback: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return fallback
    return number if minimum <= number <= maximum else fallback


def _safe_atlas(value: object) -> dict[str, int]:
    raw = value if isinstance(value, dict) else {}
    atlas = {
        "width": _bounded_int(raw.get("width"), DEFAULT_ATLAS["width"], 1, MAX_ATLAS_DIMENSION),
        "height": _bounded_int(raw.get("height"), DEFAULT_ATLAS["height"], 1, MAX_ATLAS_DIMENSION),
        "cellWidth": _bounded_int(raw.get("cellWidth"), DEFAULT_ATLAS["cellWidth"], 1, MAX_CELL_DIMENSION),
        "cellHeight": _bounded_int(raw.get("cellHeight"), DEFAULT_ATLAS["cellHeight"], 1, MAX_CELL_DIMENSION),
        "columns": _bounded_int(raw.get("columns"), DEFAULT_ATLAS["columns"], 1, MAX_ATLAS_GRID),
        "rows": _bounded_int(raw.get("rows"), DEFAULT_ATLAS["rows"], 1, MAX_ATLAS_GRID),
    }
    if (
        atlas["width"] * atlas["height"] > MAX_ATLAS_PIXELS
        or atlas["columns"] * atlas["cellWidth"] != atlas["width"]
        or atlas["rows"] * atlas["cellHeight"] != atlas["height"]
    ):
        return dict(DEFAULT_ATLAS)
    return atlas


def is_safe_skin_id(skin_id: str) -> bool:
    if not skin_id or skin_id in {".", ".."}:
        return False
    return all(ch.isalnum() or ch in "._-" for ch in skin_id) and ".." not in skin_id


def is_safe_asset_name(name: str) -> bool:
    if not name or name in {".", ".."}:
        return False
    path = Path(name)
    return len(path.parts) == 1 and path.parts[0] not in {".", ".."}


class SkinCatalog:
    def __init__(
        self,
        skins_dir: Path,
        default_skin_id: str,
        default_animations: dict[str, tuple[int, int]],
        default_animation_ms: dict[str, int],
    ) -> None:
        self.skins_dir = skins_dir
        self.default_skin_id = default_skin_id
        self.default_animations = default_animations
        self.default_animation_ms = default_animation_ms

    @staticmethod
    def read_json(path: Path) -> dict:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def folder(self, skin_id: str) -> Path:
        safe_id = skin_id if is_safe_skin_id(skin_id) else self.default_skin_id
        root = self.skins_dir.resolve()
        path = (self.skins_dir / safe_id).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            return (self.skins_dir / self.default_skin_id).resolve()
        return path

    def _child_file(self, skin_id: str, name: str) -> Path | None:
        if not is_safe_asset_name(name):
            return None
        folder = self.folder(skin_id)
        path = (folder / name).resolve()
        try:
            path.relative_to(folder.resolve())
        except ValueError:
            return None
        return path

    def load_spec(self, skin_id: str) -> dict:
        spec = self.read_json(self.folder(skin_id) / "pet.json")
        spec.setdefault("id", skin_id)
        spec.setdefault("displayName", skin_id)
        spec.setdefault("spritesheetPath", "spritesheet.webp")
        spec.setdefault("icon", "app.ico")
        spec.setdefault("iconPng", "app.png")
        atlas = _safe_atlas(spec.get("atlas"))
        spec["atlas"] = atlas
        raw_animations = spec.get("animations") if isinstance(spec.get("animations"), dict) else {}
        animations: dict[str, dict[str, int]] = {}
        for name, (default_row, default_count) in self.default_animations.items():
            raw = raw_animations.get(name)
            cfg = raw if isinstance(raw, dict) else {}
            animations[name] = {
                "row": _bounded_int(cfg.get("row"), default_row, 0, atlas["rows"] - 1),
                "frames": _bounded_int(
                    cfg.get("frames"),
                    default_count,
                    1,
                    min(atlas["columns"], MAX_ANIMATION_FRAMES),
                ),
                "ms": _bounded_int(
                    cfg.get("ms"),
                    self.default_animation_ms.get(name, 200),
                    MIN_ANIMATION_MS,
                    MAX_ANIMATION_MS,
                ),
            }
        spec["animations"] = animations
        raw_look = spec.get("look") if isinstance(spec.get("look"), dict) else {}
        raw_rows = raw_look.get("rows") if isinstance(raw_look.get("rows"), list) else [9, 10]
        look_rows: list[int] = []
        for raw_row in raw_rows[:MAX_LOOK_ROWS]:
            try:
                row = int(raw_row)
            except (TypeError, ValueError, OverflowError):
                continue
            if 0 <= row < atlas["rows"] and row not in look_rows:
                look_rows.append(row)
        if not look_rows:
            look_rows = [row for row in (9, 10) if row < atlas["rows"]] or [atlas["rows"] - 1]
        spec["look"] = {
            "rows": look_rows,
            "framesPerRow": _bounded_int(
                raw_look.get("framesPerRow"),
                min(8, atlas["columns"]),
                1,
                atlas["columns"],
            ),
            "origin": raw_look.get("origin") if raw_look.get("origin") in {"up"} else "up",
            "order": raw_look.get("order") if raw_look.get("order") in {"clockwise"} else "clockwise",
        }
        if not is_safe_skin_id(str(spec.get("id") or "")):
            spec["id"] = skin_id if is_safe_skin_id(skin_id) else self.default_skin_id
        for key, fallback in (
            ("spritesheetPath", "spritesheet.webp"),
            ("icon", "app.ico"),
            ("iconPng", "app.png"),
        ):
            if not is_safe_asset_name(str(spec.get(key) or "")):
                spec[key] = fallback
        if Path(str(spec["spritesheetPath"])).suffix.lower() != ".webp":
            spec["spritesheetPath"] = "spritesheet.webp"
        return spec

    def atlas_path(self, skin_id: str) -> Path | None:
        if not is_safe_skin_id(skin_id):
            return None
        spec = self.load_spec(skin_id)
        name = str(spec.get("spritesheetPath") or "spritesheet.webp")
        path = self._child_file(skin_id, name)
        if path is not None and path.exists():
            return path
        return None

    def ready(self, skin_id: str) -> bool:
        return self.atlas_path(skin_id) is not None

    def list_specs(self) -> list[dict]:
        ids: list[str] = []
        if self.skins_dir.exists():
            ids = [
                path.name
                for path in sorted(self.skins_dir.iterdir())
                if path.is_dir() and (path / "pet.json").exists()
            ]
        if self.default_skin_id in ids:
            ids.remove(self.default_skin_id)
        ids.insert(0, self.default_skin_id)
        result: list[dict] = []
        for skin_id in ids:
            spec = self.load_spec(skin_id)
            spec["_ready"] = self.ready(skin_id)
            result.append(spec)
        return result
