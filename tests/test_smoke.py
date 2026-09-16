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
        self.assertEqual(set(pet.build_pools(snap)), {"sg", "bot", "cm", "om", "cx"})

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

    def test_skin_loader_rejects_disguised_non_webp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "spritesheet.webp"
            Image.new("RGBA", (8, 8), (0, 0, 0, 0)).save(path, format="PNG")

            self.assertIsNone(
                pet._open_skin_image(path, {"WEBP"}, expected_size=(8, 8))
            )

    def test_original_is_the_default_and_first_theme(self) -> None:
        specs = pet.list_skins()
        self.assertGreaterEqual(len(specs), 2)
        self.assertEqual(pet.DEFAULT_SKIN_ID, "original")
        self.assertEqual(specs[0]["id"], "original")
        self.assertEqual(pet.activate_skin("missing-theme"), "original")
        self.assertEqual(pet.activate_skin("..\\evil"), "original")
        self.assertEqual(pet.activate_skin("../evil"), "original")
        self.assertFalse(pet.skin_ready(".."))
        self.assertFalse(pet.skin_ready("original/../../evil"))

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

    def test_quota_decorations_are_skin_specific_and_offline(self) -> None:
        class RecordingCanvas:
            def __init__(self) -> None:
                self.calls: list[tuple[str, tuple]] = []

            def __getattr__(self, name: str):
                if not name.startswith("create_"):
                    raise AttributeError(name)

                def record(*args, **_kwargs):
                    self.calls.append((name, args))
                    return len(self.calls)

                return record

        expected = {
            "megumi-kato": ("beret", "create_polygon"),
            "original": ("pcb", "create_rectangle"),
            "chujiu": ("paw", "create_oval"),
        }
        try:
            for skin_id, (mark, required_shape) in expected.items():
                with self.subTest(skin=skin_id):
                    pet.activate_skin(skin_id)
                    self.assertEqual(pet.style()["bubble_decoration"], mark)
                    app = pet.UsagePet.__new__(pet.UsagePet)
                    app.canvas = RecordingCanvas()
                    app._draw_decoration(100, 20)
                    self.assertIn(required_shape, {name for name, _args in app.canvas.calls})
                    self.assertTrue(app.canvas.calls)
        finally:
            pet.activate_skin("original")
        legacy = pet.resolve_theme({"preset": "soft", "decoration": "bow"})
        self.assertEqual(legacy["bubble_decoration"], "bow")
        no_mark = pet.resolve_theme({"preset": "soft", "decoration": "none"})
        self.assertEqual(no_mark["bubble_decoration"], "none")
        invalid = pet.resolve_theme({"bubbleDecoration": "cat"})
        self.assertEqual(invalid["bubble_decoration"], invalid["decoration"])

    def test_theme_app_icons_are_skin_portraits(self) -> None:
        import skin_catalog

        for skin_id in skin_catalog.RELEASE_SKIN_IDS:
            with self.subTest(skin=skin_id):
                spec = pet.load_skin_spec(skin_id)
                ui = pet.resolve_theme(spec.get("theme"))
                decoration = pet.render_bubble_decoration_icon(ui, 256)
                ico, png = pet.app_icon_paths(skin_id)
                self.assertTrue(ico.is_file(), ico)
                self.assertTrue(png.is_file(), png)
                stored = Image.open(png).convert("RGBA")
                self.assertEqual(stored.size, (256, 256))
                self.assertNotEqual(decoration.tobytes(), stored.tobytes())
                portrait = pet.load_skin_icon_image(skin_id, 256)
                self.assertIsNotNone(portrait)
                self.assertEqual(portrait.size, (256, 256))
                self.assertEqual(portrait.tobytes(), stored.tobytes())
                pet.activate_skin(skin_id)
                self.assertEqual(pet.active_skin_id(), skin_id)
        pet.activate_skin("original")

    def test_hard_edge_has_no_magenta_blend(self) -> None:
        image = Image.new("RGBA", (3, 1))
        image.putdata([(20, 11, 11, 53), (20, 11, 11, 160), (20, 11, 11, 255)])
        keyed = pet._windows_sprite_rgb(image, hard_edge=True)
        legacy = pet._windows_sprite_rgb(image, hard_edge=False)
        self.assertEqual(keyed.getpixel((0, 0)), pet.CHROMA_RGB)
        self.assertEqual(keyed.getpixel((1, 0)), (20, 11, 11))
        self.assertEqual(keyed.getpixel((2, 0)), (20, 11, 11))
        self.assertNotEqual(legacy.getpixel((1, 0)), (20, 11, 11))
        self.assertEqual(legacy.getpixel((2, 0)), (20, 11, 11))

    def test_sprite_edge_mode_is_generic_and_switches_with_skin(self) -> None:
        try:
            pet.activate_skin("megumi-kato")
            self.assertEqual(pet.SPRITE_EDGE_MODE, "legacy-matte")
            pet.activate_skin("original")
            self.assertEqual(pet.SPRITE_EDGE_MODE, "matte-free")
        finally:
            pet.activate_skin("original")
        with mock.patch.object(pet.SKIN_CATALOG, "read_json", return_value={"spriteEdgeMode": []}):
            self.assertEqual(pet.load_skin_spec("original")["spriteEdgeMode"], "matte-free")

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

    def test_legacy_codex_toggles_merge_into_one_row(self) -> None:
        cases = (
            ({"cx5": True, "cxw": True}, True),
            ({"cx5": False, "cxw": True}, True),
            ({"cx5": True, "cxw": False}, True),
            ({"cx5": False, "cxw": False}, False),
            ({"cx": False, "cx5": True, "cxw": True}, False),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                with tempfile.TemporaryDirectory() as td:
                    state_file = Path(td) / "pet_state.json"
                    state_file.write_text(json.dumps({"enabled": raw}), encoding="utf-8")
                    with mock.patch.object(pet, "STATE_FILE", state_file):
                        enabled = pet.load_enabled()
                self.assertNotIn("cx5", enabled)
                self.assertNotIn("cxw", enabled)
                self.assertEqual(enabled["cx"], expected)

    def test_watcher_launch_policy_is_pure(self) -> None:
        with (
            mock.patch.object(pet, "grok_autostart_on", return_value=True),
            mock.patch.object(pet, "cursor_autostart_on", return_value=False),
        ):
            self.assertTrue(watch_apps.want_launch({"grok.exe"}))
            self.assertFalse(watch_apps.want_launch({"cursor.exe"}))

    def test_manual_close_blocks_autostart_until_app_restarts(self) -> None:
        dismiss = {"dismissed": True, "grok_pids": [10], "cursor_pids": [20]}
        with (
            mock.patch.object(pet, "grok_autostart_on", return_value=True),
            mock.patch.object(pet, "cursor_autostart_on", return_value=True),
        ):
            self.assertFalse(watch_apps.allow_autostart({"grok.exe": {10}, "cursor.exe": {20}}, dismiss=dismiss))
            self.assertFalse(watch_apps.allow_autostart({"grok.exe": {10}, "agent.exe": {99}}, dismiss=dismiss))
            self.assertTrue(watch_apps.allow_autostart({"grok.exe": {11}, "cursor.exe": {20}}, dismiss=dismiss))
            self.assertTrue(watch_apps.allow_autostart({"grok.exe": {10}, "cursor.exe": {21}}, dismiss=dismiss))
            self.assertTrue(watch_apps.allow_autostart({"grok.exe": {10}}, dismiss=None))


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
            marker_names = [name for name in package.namelist() if Path(name).name == pet.INSTALL_MARKER_NAME]
            self.assertEqual(len(marker_names), 1)
            marker_value = package.read(marker_names[0]).decode("ascii").strip()
        self.assertEqual(packaged_names & forbidden, set())
        self.assertEqual(marker_value, pet.INSTALL_MARKER_VALUE)


if __name__ == "__main__":
    unittest.main()
