"""Filesystem-backed skin discovery and manifest defaults."""

from __future__ import annotations

import json
from pathlib import Path


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
        return self.skins_dir / skin_id

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
        return spec

    def atlas_path(self, skin_id: str) -> Path | None:
        spec = self.load_spec(skin_id)
        name = str(spec.get("spritesheetPath") or "spritesheet.webp")
        path = self.folder(skin_id) / name
        if path.exists():
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
