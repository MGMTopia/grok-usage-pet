from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pet


ROOT = Path(__file__).resolve().parents[1]


class ShortcutTests(unittest.TestCase):
    def test_argument_string_quotes_spaces_and_leaves_plain_paths(self) -> None:
        self.assertEqual(pet._shortcut_argument_string([r"D:\ai\pet.py"]), r"D:\ai\pet.py")
        self.assertEqual(
            pet._shortcut_argument_string([r"C:\Program Files\pet.py"]),
            '"C:\\Program Files\\pet.py"',
        )

    def test_spec_points_at_desktop_and_existing_icon(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            desktop = Path(tmp)
            with mock.patch.object(pet, "desktop_dir", return_value=desktop):
                spec = pet.desktop_shortcut_spec()
            path = Path(spec["path"])
            self.assertEqual(path.parent, desktop)
            self.assertTrue(path.name.endswith(".lnk" if os.name == "nt" else ".command"))
            self.assertTrue(str(spec["target"]))
            icon = Path(str(spec["icon"]))
            self.assertTrue(icon.is_file())
            self.assertEqual(icon.name.lower(), "app.ico")

    @unittest.skipUnless(os.name == "nt", "Windows shortcut COM")
    def test_desktop_dir_does_not_spawn_powershell(self) -> None:
        with mock.patch.object(pet.subprocess, "check_output") as check_output:
            folder = pet.desktop_dir()
        check_output.assert_not_called()
        self.assertTrue(folder.is_dir())

    def test_shortcut_helpers_do_not_use_encoded_powershell(self) -> None:
        source = (ROOT / "pet.py").read_text(encoding="utf-8")
        self.assertNotIn("-EncodedCommand", source)
        self.assertNotIn("_write_windows_lnk_powershell", source)

    @unittest.skipUnless(os.name == "nt", "Windows shortcut COM")
    def test_create_desktop_shortcut_writes_lnk_without_powershell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            desktop = Path(tmp)
            with mock.patch.object(pet, "desktop_dir", return_value=desktop):
                with mock.patch.object(pet.subprocess, "run") as run:
                    path = pet.create_desktop_shortcut()
            run.assert_not_called()
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 60)
            self.assertEqual(path.suffix.lower(), ".lnk")

    @unittest.skipUnless(os.name == "nt", "Windows shortcut COM")
    def test_desktop_block_falls_back_to_install_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            desktop = root / "Desktop"
            install = root / "Install"
            desktop.mkdir()
            install.mkdir()

            def write(spec: dict[str, object]) -> None:
                path = Path(spec["path"])
                if path.parent.resolve() == desktop.resolve():
                    raise OSError("IPersistFile.Save failed (0x80070005)")
                path.write_bytes(b"lnk-fallback")

            with mock.patch.object(pet, "desktop_dir", return_value=desktop):
                with mock.patch.object(pet.fu, "install_dir", return_value=install):
                    with mock.patch.object(pet, "_write_windows_lnk_com", side_effect=write):
                        path = pet.create_desktop_shortcut()
            self.assertEqual(path, install / "AI Quota Pet.lnk")
            self.assertTrue(path.is_file())
            self.assertFalse((desktop / "AI Quota Pet.lnk").exists())


if __name__ == "__main__":
    unittest.main()
