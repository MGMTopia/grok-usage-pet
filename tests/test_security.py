from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock


_IMPORT_ROOT = tempfile.TemporaryDirectory()
os.environ["LOCALAPPDATA"] = str(Path(_IMPORT_ROOT.name) / "local")
os.environ["GROK_HOME"] = str(Path(_IMPORT_ROOT.name) / "grok")
_HOME_PATCH = mock.patch.object(Path, "home", return_value=Path(_IMPORT_ROOT.name) / "home")
_HOME_PATCH.start()

import fetch_usage as fu  # noqa: E402
import pet  # noqa: E402
import skin_catalog as skins  # noqa: E402


class AuthWriteTests(unittest.TestCase):
    def test_auth_write_is_complete_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "auth.json"

            fu._write_auth(path, {"account": {"key": "secret"}})

            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["account"]["key"], "secret")
            self.assertEqual(list(path.parent.glob(".auth.json.*.tmp")), [])

    @unittest.skipIf(os.name == "nt", "POSIX mode bits are not authoritative on Windows")
    def test_auth_refresh_preserves_private_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "auth.json"
            path.write_text("{}\n", encoding="utf-8")
            path.chmod(0o600)

            fu._write_auth(path, {"account": {"key": "secret"}})

            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["account"]["key"], "secret")

    def test_replace_failure_keeps_original_auth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "auth.json"
            original = '{"account": {"key": "old"}}\n'
            path.write_text(original, encoding="utf-8")

            with mock.patch.object(fu.os, "replace", side_effect=OSError("replace failed")):
                with self.assertRaises(OSError):
                    fu._write_auth(path, {"account": {"key": "new"}})

            self.assertEqual(path.read_text(encoding="utf-8"), original)
            self.assertEqual(list(path.parent.glob(".auth.json.*.tmp")), [])


class GrokOidcAllowlistTests(unittest.TestCase):
    def test_https_auth_x_ai_is_accepted(self) -> None:
        self.assertEqual(fu._grok_https_url("https://auth.x.ai"), "https://auth.x.ai")
        self.assertEqual(
            fu._grok_https_url("https://auth.x.ai/oauth/token"),
            "https://auth.x.ai/oauth/token",
        )

    def test_non_https_or_other_hosts_are_rejected(self) -> None:
        for url in (
            "http://auth.x.ai",
            "https://evil.example",
            "https://auth.x.ai.evil.com",
            "https://user@auth.x.ai",
            "https://auth.x.ai:8443",
            "https://auth.x.ai/oauth/token?next=https://evil",
        ):
            with self.subTest(url=url):
                with self.assertRaises(RuntimeError):
                    fu._grok_https_url(url)

    def test_discovery_rejects_foreign_token_endpoint(self) -> None:
        issuer = "https://auth.x.ai"
        cfg = json.dumps({"token_endpoint": "https://evil.example/token"}).encode("utf-8")

        class FakeResp:
            def read(self):
                return cfg

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with mock.patch.object(fu.urllib.request, "urlopen", return_value=FakeResp()):
            with self.assertRaises(RuntimeError):
                fu._oidc_token_url(issuer)


class SkinPathTests(unittest.TestCase):
    def test_ids_and_asset_names_stay_inside_skins(self) -> None:
        self.assertTrue(skins.is_safe_skin_id("megumi-kato"))
        self.assertTrue(skins.is_safe_asset_name("spritesheet.webp"))
        self.assertFalse(skins.is_safe_skin_id(".."))
        self.assertFalse(skins.is_safe_skin_id("../evil"))
        self.assertFalse(skins.is_safe_skin_id("foo/bar"))
        self.assertFalse(skins.is_safe_asset_name("../secret.webp"))
        self.assertFalse(skins.is_safe_asset_name("sub/sheet.webp"))


class CursorHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.hooks_file = Path(self.tmp.name) / "hooks.json"
        self.file_patch = mock.patch.object(pet, "CURSOR_HOOK_FILE", self.hooks_file)
        self.command_patch = mock.patch.object(
            pet, "cursor_hook_command", return_value=r"C:\Apps\GrokUsagePet\start_pet.bat"
        )
        self.file_patch.start()
        self.command_patch.start()

    def tearDown(self) -> None:
        self.command_patch.stop()
        self.file_patch.stop()
        self.tmp.cleanup()

    def test_invalid_json_is_never_overwritten(self) -> None:
        original = "{broken"
        self.hooks_file.write_text(original, encoding="utf-8")

        with self.assertRaises(RuntimeError):
            pet.install_cursor_hook()

        self.assertEqual(self.hooks_file.read_text(encoding="utf-8"), original)

    def test_third_party_pet_command_is_not_ours(self) -> None:
        entry = {"command": r"C:\Tools\pet.py --backup", "timeout": 10}
        self.assertFalse(pet._is_our_cursor_hook(entry))

    def test_install_is_idempotent_and_preserves_unknown_fields(self) -> None:
        third_party = {"command": "third-party.exe", "custom": True}
        payload = {
            "version": 7,
            "customTopLevel": {"keep": True},
            "hooks": {"otherEvent": [third_party], "sessionStart": [third_party]},
        }
        self.hooks_file.write_text(json.dumps(payload), encoding="utf-8")

        pet.install_cursor_hook()
        pet.install_cursor_hook()

        saved = json.loads(self.hooks_file.read_text(encoding="utf-8"))
        self.assertEqual(saved["version"], 7)
        self.assertEqual(saved["customTopLevel"], {"keep": True})
        self.assertEqual(saved["hooks"]["otherEvent"], [third_party])
        managed = [
            item
            for item in saved["hooks"]["sessionStart"]
            if item.get("managedBy") == pet.CURSOR_HOOK_MARKER
        ]
        self.assertEqual(len(managed), 1)
        self.assertIn(third_party, saved["hooks"]["sessionStart"])

    def test_uninstall_only_removes_managed_entry(self) -> None:
        third_party = {"command": r"C:\Tools\pet.py --backup", "custom": True}
        managed = {
            "command": r"C:\Apps\GrokUsagePet\start_pet.bat",
            "timeout": 15,
            "managedBy": pet.CURSOR_HOOK_MARKER,
        }
        payload = {"version": 1, "note": "keep", "hooks": {"sessionStart": [third_party, managed]}}
        self.hooks_file.write_text(json.dumps(payload), encoding="utf-8")

        pet.uninstall_cursor_hook()

        saved = json.loads(self.hooks_file.read_text(encoding="utf-8"))
        self.assertEqual(saved["note"], "keep")
        self.assertEqual(saved["hooks"]["sessionStart"], [third_party])

    def test_invalid_session_structure_is_never_overwritten(self) -> None:
        payload = {"version": 1, "hooks": {"sessionStart": "not-a-list"}}
        self.hooks_file.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaises(RuntimeError):
            pet.install_cursor_hook()

        self.assertEqual(json.loads(self.hooks_file.read_text(encoding="utf-8")), payload)


if __name__ == "__main__":
    unittest.main()
