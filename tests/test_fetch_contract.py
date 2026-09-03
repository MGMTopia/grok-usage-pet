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


class DataDirectoryMigrationTests(unittest.TestCase):
    def test_legacy_state_is_copied_without_overwriting_newer_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            legacy = base / "GrokUsagePetKawaii"
            destination = base / "GrokUsagePet"
            legacy.mkdir()
            destination.mkdir()
            (legacy / "pet_state.json").write_text('{"skin":"megumi-kato"}', encoding="utf-8")
            (legacy / "usage.json").write_text('{"status":"partial"}', encoding="utf-8")
            (destination / "usage.json").write_text('{"status":"complete"}', encoding="utf-8")

            fu._migrate_legacy_data(base, destination)

            self.assertIn("megumi-kato", (destination / "pet_state.json").read_text(encoding="utf-8"))
            self.assertIn("complete", (destination / "usage.json").read_text(encoding="utf-8"))
            self.assertFalse((destination / "pet.lock").exists())


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
            mock.patch.object(fu, "fetch_codex", return_value=None),
        ):
            snap = fu.snapshot()

        self.assertEqual(snap["status"], fu.STATUS_COMPLETE)
        self.assertEqual(snap["sources"]["grok"]["status"], fu.SOURCE_OK)
        self.assertEqual(snap["sources"]["cursor"]["status"], fu.SOURCE_UNAVAILABLE)
        self.assertEqual(snap["sources"]["codex"]["status"], fu.SOURCE_UNAVAILABLE)
        self.assertTrue(fu.snapshot_is_usable(snap))
        self.assertEqual(fu.exit_code_for_snapshot(snap), 0)

    def test_cursor_only_is_complete_when_other_sources_are_absent(self) -> None:
        with (
            mock.patch.object(fu, "load_token", side_effect=RuntimeError("未找到 Grok 登录")),
            mock.patch.object(fu, "fetch_cursor", return_value=cursor_result()),
            mock.patch.object(fu, "fetch_codex", return_value=None),
        ):
            snap = fu.snapshot()

        self.assertEqual(snap["status"], fu.STATUS_COMPLETE)
        self.assertEqual(snap["sources"]["grok"]["status"], fu.SOURCE_UNAVAILABLE)
        self.assertEqual(snap["sources"]["cursor"]["status"], fu.SOURCE_OK)
        self.assertEqual(fu.exit_code_for_snapshot(snap), 0)

    def test_no_sources_is_failed(self) -> None:
        with (
            mock.patch.object(fu, "load_token", side_effect=RuntimeError("未找到 Grok 登录")),
            mock.patch.object(fu, "fetch_cursor", return_value=None),
            mock.patch.object(fu, "fetch_codex", return_value=None),
        ):
            snap = fu.snapshot()

        self.assertEqual(snap["status"], fu.STATUS_FAILED)
        self.assertFalse(fu.snapshot_is_usable(snap))
        self.assertEqual(fu.exit_code_for_snapshot(snap), 1)
        self.assertNotIn("remaining 0%", fu.one_line(snap))

    def test_fetch_once_does_not_print_private_usage_data(self) -> None:
        private = {
            "status": fu.STATUS_COMPLETE,
            "plan": "private-plan",
            "remaining_percent": 42,
            "errors": {"grok": "private-provider-error"},
        }
        with (
            mock.patch.object(fu, "snapshot", return_value=private),
            mock.patch.object(fu, "write_snapshot", return_value=True),
            mock.patch("builtins.print") as printer,
        ):
            self.assertIs(fu.fetch_once(), private)

        rendered = " ".join(str(arg) for call in printer.call_args_list for arg in call.args)
        self.assertEqual(rendered, "updated local usage snapshot")
        self.assertNotIn("private", rendered)

    def test_diagnostics_redact_credentials_queries_and_newlines(self) -> None:
        github_token = "ghp_" + ("a" * 26)
        diagnostic = (
            "Authorization: Bearer abcdefghijklmnopqrstuvwxyz "
            "refresh_token=refresh-secret-value "
            "https://service.example/path?token=query-secret\n"
            + github_token
        )
        rendered = fu.redact_sensitive_text(diagnostic)
        self.assertNotIn(github_token, rendered)
        self.assertNotIn("refresh-secret-value", rendered)
        self.assertNotIn("query-secret", rendered)
        self.assertNotIn("\n", rendered)
        self.assertIn("[redacted]", rendered)

    def test_service_text_is_bounded_and_redacts_email(self) -> None:
        rendered = fu.bounded_service_text("contact person@example.com " + ("x" * 500), limit=80)
        self.assertIsNotNone(rendered)
        self.assertNotIn("person@example.com", rendered)
        self.assertLessEqual(len(rendered), 80)
        self.assertIsNone(fu.bounded_service_text({"unexpected": "shape"}))

    def test_provider_failures_do_not_copy_tokens_into_snapshot(self) -> None:
        canary = "opaque-provider-token-canary"
        with (
            mock.patch.object(fu, "load_token", return_value=(canary, {})),
            mock.patch.object(fu, "get_json", side_effect=TimeoutError("offline")),
            mock.patch.object(fu, "fetch_cursor", return_value=None),
            mock.patch.object(fu, "fetch_codex", return_value=None),
        ):
            snap = fu.snapshot()
        self.assertNotIn(canary, json.dumps(snap, ensure_ascii=False))

    def test_provider_exception_text_redacts_bearer_token_canary(self) -> None:
        canary = "provider-secret-" + ("z" * 24)
        with (
            mock.patch.object(fu, "load_token", return_value=(canary, {})),
            mock.patch.object(
                fu,
                "get_json",
                side_effect=RuntimeError(f"Authorization: Bearer {canary}"),
            ),
            mock.patch.object(fu, "fetch_cursor", return_value=None),
            mock.patch.object(fu, "fetch_codex", return_value=None),
        ):
            snap = fu.snapshot()

        self.assertNotIn(canary, json.dumps(snap, ensure_ascii=False))
        self.assertIn("[redacted]", snap["errors"]["grok"])

    def test_failed_summary_omits_private_provider_errors(self) -> None:
        snap = {
            "status": fu.STATUS_FAILED,
            "errors": {"grok": "private-provider-error"},
        }
        self.assertEqual(fu.one_line(snap), "usage unavailable")

    def test_both_sources_are_complete_even_if_optional_settings_fail(self) -> None:
        def get_json(url: str, _token: str) -> dict:
            if url == fu.BILLING_URL:
                return billing_result()
            raise TimeoutError("settings timeout")

        with (
            mock.patch.object(fu, "load_token", return_value=("token", {})),
            mock.patch.object(fu, "get_json", side_effect=get_json),
            mock.patch.object(fu, "fetch_cursor", return_value=cursor_result()),
            mock.patch.object(fu, "fetch_codex", return_value=None),
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


class CodexContractTests(unittest.TestCase):
    def test_missing_codex_login_is_unavailable(self) -> None:
        self.assertIsNone(fu.fetch_codex())

    def test_api_key_mode_has_no_percent_pool(self) -> None:
        with mock.patch.object(fu, "load_codex_auth", return_value={"mode": "apikey"}):
            result = fu.fetch_codex()
        self.assertEqual(result["source_status"], fu.SOURCE_UNAVAILABLE)
        self.assertIsNone(result["primary"]["remaining_percent"])
        dumped = json.dumps(result)
        self.assertNotIn("access_token", dumped)
        self.assertNotIn("refresh_token", dumped)

    def test_codex_windows_map_to_remaining_percent(self) -> None:
        payload = {
            "plan_type": "pro",
            "rate_limit": {
                "primary_window": {
                    "used_percent": 25,
                    "reset_at": 1893456000,
                    "limit_window_seconds": 18000,
                },
                "secondary_window": {
                    "used_percent": 10,
                    "reset_after_seconds": 1000,
                    "limit_window_seconds": 604800,
                },
            },
            "credits": {"balance": "3"},
        }
        with (
            mock.patch.object(
                fu,
                "load_codex_auth",
                return_value={"mode": "chatgpt", "access_token": "secret-token", "account_id": "acct"},
            ),
            mock.patch.object(fu, "_codex_get", return_value=payload),
        ):
            result = fu.fetch_codex()
        self.assertEqual(result["source_status"], fu.SOURCE_OK)
        self.assertEqual(result["primary"]["remaining_percent"], 75.0)
        self.assertEqual(result["secondary"]["remaining_percent"], 90.0)
        dumped = json.dumps(result)
        self.assertNotIn("secret-token", dumped)
        self.assertNotIn("acct", dumped)


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
        failed = {"status": fu.STATUS_FAILED, "errors": {"grok": "private-provider-error"}}
        with (
            mock.patch.object(sys, "argv", ["pet.py", "--cli"]),
            mock.patch.object(pet.fu, "snapshot", return_value=failed),
            mock.patch.object(pet.fu, "write_snapshot", return_value=False),
            mock.patch("builtins.print") as printer,
        ):
            with self.assertRaises(SystemExit) as caught:
                pet.main()

        self.assertEqual(caught.exception.code, 1)
        rendered = " ".join(str(arg) for call in printer.call_args_list for arg in call.args)
        self.assertNotIn("private-provider-error", rendered)
        self.assertIn("usage unavailable", rendered)


if __name__ == "__main__":
    unittest.main()
