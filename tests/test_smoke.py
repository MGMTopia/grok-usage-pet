from __future__ import annotations

import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


_IMPORT_ROOT = tempfile.TemporaryDirectory()
os.environ["LOCALAPPDATA"] = str(Path(_IMPORT_ROOT.name) / "local")
os.environ["GROK_HOME"] = str(Path(_IMPORT_ROOT.name) / "grok")
_HOME_PATCH = mock.patch.object(Path, "home", return_value=Path(_IMPORT_ROOT.name) / "home")
_HOME_PATCH.start()

from PIL import Image  # noqa: E402

import fetch_usage  # noqa: E402
import pet  # noqa: E402
import watch_apps  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]


class SourceSmokeTests(unittest.TestCase):
    def test_entry_modules_import_without_gui_or_network(self) -> None:
        self.assertTrue(callable(fetch_usage.snapshot))
        self.assertTrue(callable(pet.main))
        self.assertTrue(callable(watch_apps.main))

    def test_application_smoke_check_passes_without_tk_window(self) -> None:
        pet.smoke_test()

    def test_visual_smoke_snapshot_is_complete_and_offline(self) -> None:
        snap = pet.visual_smoke_snapshot()
        self.assertEqual(snap["status"], fetch_usage.STATUS_COMPLETE)
        self.assertIsNone(snap["errors"])
        self.assertEqual(set(pet.build_pools(snap)), {"sg", "bot", "cm", "om"})

    def test_default_skin_metadata_matches_sprite_dimensions(self) -> None:
        spec = json.loads((ROOT / "skins" / "original" / "pet.json").read_text(encoding="utf-8"))
        atlas = spec["atlas"]
        sprite = ROOT / "skins" / "original" / spec["spritesheetPath"]
        with Image.open(sprite) as image:
            self.assertEqual(image.size, (atlas["width"], atlas["height"]))
            image.verify()
        self.assertEqual(atlas["columns"] * atlas["cellWidth"], atlas["width"])
        self.assertEqual(atlas["rows"] * atlas["cellHeight"], atlas["height"])

    def test_all_skin_metadata_is_valid_json(self) -> None:
        specs = list((ROOT / "skins").glob("*/pet.json"))
        self.assertGreaterEqual(len(specs), 2)
        for path in specs:
            with self.subTest(path=path):
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertTrue(payload["id"])
                self.assertTrue(payload["spritesheetPath"])
                self.assertIn("atlas", payload)
                self.assertIn("animations", payload)
                self.assertIn("theme", payload)
                atlas = payload["atlas"]
                self.assertEqual(atlas["columns"] * atlas["cellWidth"], atlas["width"])
                self.assertEqual(atlas["rows"] * atlas["cellHeight"], atlas["height"])

    def test_original_is_the_default_and_first_theme(self) -> None:
        specs = pet.list_skins()
        self.assertGreaterEqual(len(specs), 2)
        self.assertEqual(pet.DEFAULT_SKIN_ID, "original")
        self.assertEqual(specs[0]["id"], "original")
        self.assertEqual(pet.activate_skin("missing-theme"), "original")

    def test_skin_themes_are_distinct_and_invalid_tokens_fall_back(self) -> None:
        try:
            pet.activate_skin("original")
            original = dict(pet.style())
            pet.activate_skin("megumi-kato")
            megumi = dict(pet.style())
        finally:
            pet.activate_skin("original")
        self.assertEqual(original["decoration"], "circuit")
        self.assertEqual(megumi["decoration"], "bow")
        self.assertNotEqual(original["bubble_fill"], megumi["bubble_fill"])

        fallback = pet.resolve_theme(
            {"preset": "missing", "bubbleFill": "red", "barStyle": "pill", "radius": 999}
        )
        self.assertEqual(fallback["bubble_fill"], pet.STYLES[pet.DEFAULT_THEME_PRESET]["bubble_fill"])
        self.assertEqual(fallback["bar_style"], "rounded")
        self.assertEqual(fallback["radius"], 28)

        custom = pet.resolve_theme({"preset": "tech", "accent": "#ABCDEF"})
        self.assertEqual(custom["accent"], "#ABCDEF")

    def test_legacy_fixed_open_state_is_not_restored(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_file = Path(td) / "pet_state.json"
            state_file.write_text(
                json.dumps({"x": 12, "pinned": True, "expanded": True, "skin": "original"}),
                encoding="utf-8",
            )
            with mock.patch.object(pet, "STATE_FILE", state_file):
                state = pet.load_state()
                self.assertEqual(state["x"], 12)
                self.assertNotIn("pinned", state)
                self.assertNotIn("expanded", state)
                pet.save_state({"skin": "original"})
            persisted = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertNotIn("pinned", persisted)
            self.assertNotIn("expanded", persisted)

    def test_watcher_launch_policy_is_pure(self) -> None:
        with (
            mock.patch.object(pet, "grok_autostart_on", return_value=True),
            mock.patch.object(pet, "cursor_autostart_on", return_value=False),
        ):
            self.assertTrue(watch_apps.want_launch({"grok.exe"}))
            self.assertFalse(watch_apps.want_launch({"cursor.exe"}))


class ReleaseSafetySmokeTests(unittest.TestCase):
    def test_existing_zip_contains_no_user_secrets(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        archive = ROOT / "release" / f"GrokUsagePet-v{version}-Windows-x64.zip"
        if not archive.exists():
            self.skipTest("release archive not built")
        forbidden = {
            "auth.json",
            "state.vscdb",
            "pet_state.json",
            "usage.json",
            "usage.txt",
            "pet.log",
            "watch.log",
        }
        with zipfile.ZipFile(archive) as package:
            packaged_names = {Path(name.replace("\\", "/")).name.lower() for name in package.namelist()}
        self.assertEqual(packaged_names & forbidden, set())


if __name__ == "__main__":
    unittest.main()
