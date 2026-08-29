from __future__ import annotations

import json
import os
import sys
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


def cursor_result(*, status: str = fu.SOURCE_OK) -> dict:
    return {
        "source_status": status,
        "grok_bot": {
            "used_percent": 25.0 if status == fu.SOURCE_OK else None,
            "remaining_percent": 75.0 if status == fu.SOURCE_OK else None,
            "resets_at": "2030-01-01T00:00:00Z",
        },
        "cursor_monthly": {
            "cursor_models": {"remaining_percent": None},
            "other_models": {"remaining_percent": None},
        },
        "errors": None,
    }


def billing_result() -> dict:
    return {
        "config": {
            "creditUsagePercent": 20,
            "currentPeriod": {"end": "2030-01-01T00:00:00Z"},
            "productUsage": [],
        }
    }


class SnapshotContractTests(unittest.TestCase):
    def test_grok_only_is_partial_and_usable(self) -> None:
        def get_json(url: str, _token: str) -> dict:
            if url == fu.BILLING_URL:
                return billing_result()
            return {"subscription_tier_display": "SuperGrok"}

        with (
            mock.patch.object(fu, "load_token", return_value=("token", {})),
            mock.patch.object(fu, "get_json", side_effect=get_json),
            mock.patch.object(fu, "fetch_cursor", return_value=None),
        ):
            snap = fu.snapshot()

        self.assertEqual(snap["status"], fu.STATUS_PARTIAL)
        self.assertEqual(snap["sources"]["grok"]["status"], fu.SOURCE_OK)
        self.assertEqual(snap["sources"]["cursor"]["status"], fu.SOURCE_UNAVAILABLE)
        self.assertTrue(fu.snapshot_is_usable(snap))
        self.assertEqual(fu.exit_code_for_snapshot(snap), 0)

    def test_cursor_only_is_partial_and_usable(self) -> None:
        with (
            mock.patch.object(fu, "load_token", side_effect=RuntimeError("未找到 Grok 登录")),
            mock.patch.object(fu, "fetch_cursor", return_value=cursor_result()),
        ):
            snap = fu.snapshot()

        self.assertEqual(snap["status"], fu.STATUS_PARTIAL)
        self.assertEqual(snap["sources"]["grok"]["status"], fu.SOURCE_UNAVAILABLE)
        self.assertEqual(snap["sources"]["cursor"]["status"], fu.SOURCE_OK)
        self.assertEqual(fu.exit_code_for_snapshot(snap), 0)

    def test_no_sources_is_failed(self) -> None:
        with (
            mock.patch.object(fu, "load_token", side_effect=RuntimeError("未找到 Grok 登录")),
            mock.patch.object(fu, "fetch_cursor", return_value=None),
        ):
            snap = fu.snapshot()

        self.assertEqual(snap["status"], fu.STATUS_FAILED)
        self.assertFalse(fu.snapshot_is_usable(snap))
        self.assertEqual(fu.exit_code_for_snapshot(snap), 1)
        self.assertNotIn("remaining 0%", fu.one_line(snap))

    def test_both_sources_are_complete_even_if_optional_settings_fail(self) -> None:
        def get_json(url: str, _token: str) -> dict:
            if url == fu.BILLING_URL:
                return billing_result()
            raise TimeoutError("settings timeout")

        with (
            mock.patch.object(fu, "load_token", return_value=("token", {})),
            mock.patch.object(fu, "get_json", side_effect=get_json),
            mock.patch.object(fu, "fetch_cursor", return_value=cursor_result()),
        ):
            snap = fu.snapshot()

        self.assertEqual(snap["status"], fu.STATUS_COMPLETE)
        self.assertIn("grok_settings", snap["errors"])

    def test_cursor_rpc_total_failure_is_error_not_unavailable(self) -> None:
        with (
            mock.patch.object(fu, "load_cursor_token", return_value={"token": "cursor-token"}),
            mock.patch.object(fu, "cursor_rpc", side_effect=TimeoutError("offline")),
        ):
            result = fu.fetch_cursor()

        self.assertIsNotNone(result)
        self.assertEqual(result["source_status"], fu.SOURCE_ERROR)
        self.assertTrue(result["errors"])


class SnapshotStorageTests(unittest.TestCase):
    def test_failed_snapshot_never_overwrites_last_good_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            old_json = '{"status": "partial", "marker": "old"}\n'
            old_text = "old snapshot\n"
            (out / "usage.json").write_text(old_json, encoding="utf-8")
            (out / "usage.txt").write_text(old_text, encoding="utf-8")
            failed = {"status": fu.STATUS_FAILED, "errors": {"grok": "offline"}}

            with mock.patch.object(fu, "data_dir", return_value=out):
                written = fu.write_snapshot(failed)

            self.assertFalse(written)
            self.assertEqual((out / "usage.json").read_text(encoding="utf-8"), old_json)
            self.assertEqual((out / "usage.txt").read_text(encoding="utf-8"), old_text)

    def test_partial_snapshot_is_written_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            snap = {
                "status": fu.STATUS_PARTIAL,
                "remaining_percent": 80.0,
                "used_percent": 20.0,
                "period": {"end": "2030-01-01T00:00:00Z"},
                "products_used_percent": {},
                "cursor": None,
                "errors": None,
            }

            with mock.patch.object(fu, "data_dir", return_value=out):
                written = fu.write_snapshot(snap)

            self.assertTrue(written)
            self.assertEqual(json.loads((out / "usage.json").read_text(encoding="utf-8"))["status"], "partial")
            self.assertEqual(list(out.glob(".usage.*.tmp")), [])


class CliContractTests(unittest.TestCase):
    def test_fetch_main_returns_failed_exit_code(self) -> None:
        failed = {"status": fu.STATUS_FAILED}
        with (
            mock.patch.object(sys, "argv", ["fetch_usage.py", "--quiet"]),
            mock.patch.object(fu, "fetch_once", return_value=failed),
        ):
            self.assertEqual(fu.main(), 1)

    def test_fetch_main_returns_two_for_internal_error(self) -> None:
        with (
            mock.patch.object(sys, "argv", ["fetch_usage.py", "--quiet"]),
            mock.patch.object(fu, "fetch_once", side_effect=OSError("disk full")),
            mock.patch.object(sys, "stderr"),
        ):
            self.assertEqual(fu.main(), 2)

    def test_pet_cli_uses_same_failed_exit_code(self) -> None:
        failed = {"status": fu.STATUS_FAILED, "errors": {"grok": "offline"}}
        with (
            mock.patch.object(sys, "argv", ["pet.py", "--cli"]),
            mock.patch.object(pet.fu, "snapshot", return_value=failed),
            mock.patch.object(pet.fu, "write_snapshot", return_value=False),
            mock.patch("builtins.print"),
        ):
            with self.assertRaises(SystemExit) as caught:
                pet.main()

        self.assertEqual(caught.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
