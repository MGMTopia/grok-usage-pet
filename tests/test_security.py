from __future__ import annotations

import json
import os
import stat
import subprocess
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

            with mock.patch.object(fu, "_replace_auth_file", side_effect=OSError("replace failed")):
                with self.assertRaises(OSError):
                    fu._write_auth(path, {"account": {"key": "new"}})

            self.assertEqual(path.read_text(encoding="utf-8"), original)
            self.assertEqual(list(path.parent.glob(".auth.json.*.tmp")), [])

    def test_revision_mismatch_keeps_newer_auth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "auth.json"
            path.write_text('{"account": {"key": "old"}}\n', encoding="utf-8")
            revision = fu._auth_revision(path)
            newer = '{"account": {"key": "newer"}}\n'
            path.write_text(newer, encoding="utf-8")

            with self.assertRaises(fu.AuthFileChangedError):
                fu._write_auth(
                    path,
                    {"account": {"key": "stale-refresh"}},
                    expected_revision=revision,
                )

            self.assertEqual(path.read_text(encoding="utf-8"), newer)
            self.assertEqual(list(path.parent.glob(".auth.json.*.tmp")), [])

    def test_last_moment_revision_change_cancels_replace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "auth.json"
            path.write_text('{"account": {"key": "old"}}\n', encoding="utf-8")
            revision = fu._auth_revision(path)

            with (
                mock.patch.object(fu, "_auth_revision", side_effect=[revision, "changed"]),
                mock.patch.object(fu, "_replace_auth_file") as replace,
            ):
                with self.assertRaises(fu.AuthFileChangedError):
                    fu._write_auth(
                        path,
                        {"account": {"key": "stale-refresh"}},
                        expected_revision=revision,
                    )

            replace.assert_not_called()
            self.assertEqual(list(path.parent.glob(".auth.json.*.tmp")), [])

    @unittest.skipUnless(os.name == "nt", "ReplaceFileW is Windows-only")
    def test_windows_existing_auth_uses_acl_preserving_replace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "auth.json"
            replacement = Path(tmp) / "replacement.tmp"
            path.write_text("{}\n", encoding="utf-8")
            replacement.write_text("{}\n", encoding="utf-8")

            with mock.patch.object(fu, "_windows_replace_file") as replace:
                fu._replace_auth_file(replacement, path)

            replace.assert_called_once_with(path, replacement)


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

    def test_untrusted_manifest_values_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skins"
            folder = root / "hostile"
            folder.mkdir(parents=True)
            (folder / "spritesheet.webp").write_bytes(b"not-decoded-by-catalog")
            (folder / "pet.json").write_text(
                json.dumps(
                    {
                        "id": "hostile",
                        "spritesheetPath": "payload.png",
                        "atlas": {
                            "width": 2**31,
                            "height": 2**31,
                            "cellWidth": -1,
                            "cellHeight": 0,
                            "columns": 999999,
                            "rows": 999999,
                        },
                        "animations": {
                            "idle": {"row": 999999, "frames": 999999, "ms": -1},
                        },
                        "look": {"rows": [-1, 999999, "bad"], "framesPerRow": 999999},
                    }
                ),
                encoding="utf-8",
            )
            catalog = skins.SkinCatalog(
                root,
                "hostile",
                {"idle": (0, 6)},
                {"idle": 260},
            )

            spec = catalog.load_spec("hostile")

            self.assertEqual(spec["atlas"], skins.DEFAULT_ATLAS)
            self.assertEqual(spec["spritesheetPath"], "spritesheet.webp")
            self.assertEqual(spec["animations"]["idle"], {"row": 0, "frames": 6, "ms": 260})
            self.assertEqual(spec["look"]["rows"], [9, 10])
            self.assertEqual(spec["look"]["framesPerRow"], 8)


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


class ProcessCleanupTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows process discovery only")
    def test_process_sweep_is_scoped_to_project_commands(self) -> None:
        result = mock.Mock(returncode=0, stdout="202\n101\nnot-a-pid\n", stderr="")
        with mock.patch.object(pet.subprocess, "run", return_value=result) as run:
            stopped = pet.stop_app_processes()

        self.assertEqual(stopped, ["101", "202"])
        args = run.call_args.args[0]
        kwargs = run.call_args.kwargs
        self.assertEqual(args[:3], ["powershell", "-NoProfile", "-Command"])
        script = args[3]
        self.assertIn("GrokUsagePet.exe", script)
        self.assertIn("GrokUsagePetKawaii.exe", script)
        self.assertIn("(?:pet|watch_apps)", script)
        self.assertNotIn("grok.exe'", script.lower())
        self.assertEqual(kwargs["env"]["GROK_USAGE_PET_CURRENT_PID"], str(os.getpid()))
        self.assertEqual(
            Path(kwargs["env"]["GROK_USAGE_PET_SOURCE_ROOT"]),
            fu.resource_dir().resolve(),
        )

    @unittest.skipUnless(os.name == "nt", "Windows scheduled tasks only")
    def test_task_cleanup_continues_after_one_command_error(self) -> None:
        calls: list[list[str]] = []

        def fake_run(args, **_kwargs):
            calls.append(list(args))
            if args[:4] == ["schtasks", "/Delete", "/TN", "GrokUsagePetLaunch"]:
                raise subprocess.TimeoutExpired(args, 15)
            return mock.Mock(returncode=1)

        with mock.patch.object(pet.subprocess, "run", side_effect=fake_run):
            removed, errors = pet.remove_scheduled_tasks()

        self.assertEqual(removed, [])
        self.assertTrue(any("delete GrokUsagePetLaunch" in error for error in errors))
        for name in pet.APP_TASK_NAMES:
            self.assertIn(["schtasks", "/Delete", "/TN", name, "/F"], calls)


class PurgeResidueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.data = root / "GrokUsagePet"
        self.legacy = root / "GrokUsagePetKawaii"
        self.desktop = root / "Desktop"
        self.hooks = root / "hooks.json"
        self.grok_hook = root / "usage-pet.json"
        self.data.mkdir()
        self.legacy.mkdir()
        self.desktop.mkdir()
        (self.data / "usage.json").write_text('{"plan":"keep-private"}', encoding="utf-8")
        (self.legacy / "pet_state.json").write_text("{}", encoding="utf-8")
        (self.desktop / "Grok额度宠物.lnk").write_text("shortcut", encoding="utf-8")
        (self.desktop / "notes.txt").write_text("keep", encoding="utf-8")
        self.grok_hook.write_text("{}", encoding="utf-8")
        self.hooks.write_text(
            json.dumps(
                {
                    "hooks": {
                        "sessionStart": [
                            {"command": "keep-me", "timeout": 10},
                            {
                                "command": "our.bat",
                                "timeout": 15,
                                "managedBy": pet.CURSOR_HOOK_MARKER,
                            },
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        self.auth = fu.grok_auth_file()
        self.auth.parent.mkdir(parents=True, exist_ok=True)
        self.auth.write_text('{"account": {"key": "secret"}}', encoding="utf-8")
        self.patches = [
            mock.patch.object(pet, "DATA_DIR", self.data),
            mock.patch.object(pet, "HOOK_FILE", self.grok_hook),
            mock.patch.object(pet, "CURSOR_HOOK_FILE", self.hooks),
            mock.patch.object(pet, "desktop_dir", return_value=self.desktop),
            mock.patch.object(pet, "cursor_hook_command", return_value="our.bat"),
            mock.patch.object(pet, "stop_app_processes", return_value=["101", "202"]),
            mock.patch.object(pet.subprocess, "run", side_effect=self._fake_schtasks),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.tmp.cleanup()

    def _fake_schtasks(self, args, **_kwargs):
        if not hasattr(self, "schtasks_calls"):
            self.schtasks_calls = []
        self.schtasks_calls.append(list(args))
        result = mock.Mock()
        result.returncode = 1
        if len(args) >= 4 and args[:3] == ["schtasks", "/Delete", "/TN"]:
            if args[3] in pet.APP_TASK_NAMES:
                result.returncode = 0
        if len(args) >= 4 and args[:3] == ["schtasks", "/End", "/TN"]:
            if args[3] in pet.WATCH_TASK_NAMES:
                result.returncode = 0
        return result

    def test_purge_removes_app_residue_and_keeps_logins(self) -> None:
        result = pet.purge_local_residue()

        self.assertFalse(self.data.exists())
        self.assertFalse(self.legacy.exists())
        self.assertFalse(self.grok_hook.exists())
        self.assertFalse((self.desktop / "Grok额度宠物.lnk").exists())
        self.assertEqual((self.desktop / "notes.txt").read_text(encoding="utf-8"), "keep")
        saved = json.loads(self.hooks.read_text(encoding="utf-8"))
        self.assertEqual(saved["hooks"]["sessionStart"], [{"command": "keep-me", "timeout": 10}])
        self.assertEqual(json.loads(self.auth.read_text(encoding="utf-8"))["account"]["key"], "secret")
        self.assertIn(str(self.data), result["data"])
        self.assertIn(str(self.legacy), result["data"])
        self.assertEqual(result["processes"], ["101", "202"])
        self.assertEqual(result["errors"], [])
        if os.name == "nt":
            self.assertEqual(set(result["tasks"]), set(pet.APP_TASK_NAMES))
            for name in pet.WATCH_TASK_NAMES:
                end = ["schtasks", "/End", "/TN", name]
                delete = ["schtasks", "/Delete", "/TN", name, "/F"]
                self.assertIn(end, self.schtasks_calls)
                self.assertLess(self.schtasks_calls.index(end), self.schtasks_calls.index(delete))


if __name__ == "__main__":
    unittest.main()
