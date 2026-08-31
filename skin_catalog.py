"""Filesystem-backed skin discovery and manifest defaults."""

from __future__ import annotations

import json
from pathlib import Path


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
        spec.setdefault(
            "atlas",
            {
                "width": 1536,
                "height": 2288,
                "cellWidth": 192,
                "cellHeight": 208,
                "columns": 8,
                "rows": 11,
            },
        )
        if "animations" not in spec:
            spec["animations"] = {
                name: {"row": row, "frames": count, "ms": self.default_animation_ms.get(name, 200)}
                for name, (row, count) in self.default_animations.items()
            }
        spec.setdefault("look", {"rows": [9, 10], "framesPerRow": 8, "origin": "up", "order": "clockwise"})
        if not is_safe_skin_id(str(spec.get("id") or "")):
            spec["id"] = skin_id if is_safe_skin_id(skin_id) else self.default_skin_id
        for key, fallback in (
            ("spritesheetPath", "spritesheet.webp"),
            ("icon", "app.ico"),
            ("iconPng", "app.png"),
        ):
            if not is_safe_asset_name(str(spec.get(key) or "")):
                spec[key] = fallback
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
