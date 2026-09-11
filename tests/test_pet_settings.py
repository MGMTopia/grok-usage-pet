from __future__ import annotations

import unittest

import info_modules
from pet_settings import (
    DEFAULT_QUOTA_ENABLED,
    SETTINGS_SCHEMA,
    normalize_enabled,
    normalize_state,
    quota_module_enabled,
)


class SettingsMigrationTests(unittest.TestCase):
    def test_legacy_flat_state_is_classified_into_layers(self) -> None:
        state = normalize_state(
            {
                "skin": "megumi-kato",
                "x": 12,
                "y": 34,
                "enabled": {"sg": True, "bot": False, "cm": True, "om": False, "cx": True},
                "check_updates": False,
                "last_update_check": 99,
                "pinned": True,
                "expanded": True,
            }
        )
        self.assertEqual(state["schema"], SETTINGS_SCHEMA)
        self.assertEqual(state["pet"]["skin"], "megumi-kato")
        self.assertEqual(state["pet"]["x"], 12)
        self.assertEqual(state["pet"]["y"], 34)
        self.assertEqual(state["skin"], "megumi-kato")
        self.assertEqual(state["x"], 12)
        self.assertFalse(state["modules"]["quota"]["enabled"]["bot"])
        self.assertEqual(state["enabled"]["bot"], False)
        self.assertFalse(state["system"]["check_updates"])
        self.assertEqual(state["system"]["last_update_check"], 99)
        self.assertEqual(state["interaction"], {"info_panel": "quota"})
        self.assertEqual(state["info_panel"], "quota")
        self.assertNotIn("pinned", state)
        self.assertNotIn("expanded", state)

    def test_legacy_codex_toggles_merge_into_quota_module(self) -> None:
        state = normalize_state({"enabled": {"cx5": False, "cxw": True}})
        self.assertTrue(state["enabled"]["cx"])
        self.assertNotIn("cx5", state["enabled"])
        self.assertTrue(state["modules"]["quota"]["enabled"]["cx"])

    def test_nested_quota_is_used_when_flat_enabled_is_missing(self) -> None:
        state = normalize_state(
            {
                "pet": {"skin": "original"},
                "modules": {"quota": {"enabled": {"sg": False, "bot": False, "cm": False, "om": False, "cx": False}}},
            }
        )
        self.assertEqual(state["enabled"], {key: False for key in DEFAULT_QUOTA_ENABLED})
        self.assertFalse(quota_module_enabled(state))
        self.assertFalse(info_modules.is_quota_enabled(state))

    def test_flat_enabled_wins_when_both_shapes_exist(self) -> None:
        state = normalize_state(
            {
                "enabled": {"sg": True, "bot": True, "cm": True, "om": True, "cx": True},
                "modules": {"quota": {"enabled": {"sg": False, "bot": False, "cm": False, "om": False, "cx": False}}},
            }
        )
        self.assertTrue(state["enabled"]["sg"])
        self.assertTrue(state["modules"]["quota"]["enabled"]["sg"])
        self.assertTrue(quota_module_enabled(state))

    def test_broken_quota_module_does_not_drop_pet_core(self) -> None:
        state = normalize_state({"skin": "original", "x": 8, "modules": {"quota": "nope"}})
        self.assertEqual(state["pet"]["skin"], "original")
        self.assertEqual(state["x"], 8)
        self.assertEqual(state["enabled"], dict(DEFAULT_QUOTA_ENABLED))
        self.assertEqual(info_modules.known_modules(), ("quota", "clock"))
        self.assertEqual(state["modules"]["clock"]["enabled"]["time"], True)

    def test_normalize_is_idempotent(self) -> None:
        first = normalize_state({"skin": "original", "enabled": {"sg": False}})
        second = normalize_state(first)
        self.assertEqual(first, second)

    def test_unknown_top_level_keys_are_kept(self) -> None:
        state = normalize_state({"skin": "original", "custom_note": "keep"})
        self.assertEqual(state["custom_note"], "keep")

    def test_language_is_normalized_and_persisted_in_system_layer(self) -> None:
        state = normalize_state({"language": "en-US"})
        self.assertEqual(state["language"], "en")
        self.assertEqual(state["system"]["language"], "en")
        self.assertEqual(normalize_state({})["language"], "zh-CN")

    def test_normalize_enabled_matches_legacy_defaults(self) -> None:
        self.assertEqual(normalize_enabled(None), dict(DEFAULT_QUOTA_ENABLED))
        self.assertEqual(normalize_enabled({"sg": False})["sg"], False)
        self.assertTrue(normalize_enabled({"sg": False})["bot"])


if __name__ == "__main__":
    unittest.main()
