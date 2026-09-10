from __future__ import annotations

import unittest
from unittest import mock

import info_modules
from info_modules import ModuleHost, ModuleRefreshResult, ModuleSpec
from quota_module import QuotaModule


class _BoomModule:
    spec = ModuleSpec(id="boom", title="Boom", permissions=(), refresh_ms=1000)

    def wants_refresh(self, enabled: dict[str, bool] | None) -> bool:
        return True

    def refresh(self) -> ModuleRefreshResult:
        raise RuntimeError("module exploded")


class _OkModule:
    spec = ModuleSpec(id="ok", title="Ok", permissions=(), refresh_ms=1000)

    def wants_refresh(self, enabled: dict[str, bool] | None) -> bool:
        return True

    def refresh(self) -> ModuleRefreshResult:
        return ModuleRefreshResult(ok=True, snapshot={"id": "ok"})


class InfoModuleHostTests(unittest.TestCase):
    def test_quota_is_the_default_registered_module(self) -> None:
        host = info_modules.default_host()
        quota = host.get("quota")
        self.assertIsNotNone(quota)
        self.assertEqual(quota.spec.id, "quota")
        self.assertTrue(quota.spec.permission_hint())
        self.assertEqual(info_modules.known_modules(), ("quota", "clock"))
        self.assertIsNotNone(host.get("clock"))
        self.assertFalse(host.get("clock").wants_refresh({"time": True, "timer": True}))

    def test_disabled_quota_does_not_refresh(self) -> None:
        host = ModuleHost((QuotaModule(),))
        enabled = {key: False for key in info_modules.quota_sources()}
        self.assertFalse(host.wants_refresh(enabled))
        self.assertEqual(host.refresh_enabled(enabled), {})
        self.assertIsNone(host.refresh_ms(enabled))

    def test_host_isolates_a_crashing_module(self) -> None:
        host = ModuleHost((_BoomModule(), _OkModule()))
        results = host.refresh_enabled({})
        self.assertFalse(results["boom"].ok)
        self.assertIn("exploded", results["boom"].error or "")
        self.assertTrue(results["ok"].ok)
        self.assertEqual(results["ok"].snapshot, {"id": "ok"})

    def test_quota_refresh_swallows_provider_exceptions(self) -> None:
        module = QuotaModule()
        with mock.patch("quota_module.fu.snapshot", side_effect=RuntimeError("token leak secret")):
            with mock.patch("quota_module.fu.redact_sensitive_text", return_value="redacted"):
                result = module.refresh()
        self.assertFalse(result.ok)
        self.assertIsNone(result.snapshot)
        self.assertEqual(result.error, "redacted")

    def test_quota_refresh_keeps_unusable_snapshot_out_of_result(self) -> None:
        module = QuotaModule()
        snap = {"status": "failed", "errors": {"grok": "down"}}
        with mock.patch("quota_module.fu.snapshot", return_value=snap):
            with mock.patch("quota_module.fu.write_snapshot"):
                with mock.patch("quota_module.fu.snapshot_is_usable", return_value=False):
                    result = module.refresh()
        self.assertFalse(result.ok)
        self.assertIsNone(result.snapshot)
        self.assertIn("grok", result.error or "")


if __name__ == "__main__":
    unittest.main()
