from __future__ import annotations

import unittest

from pet_view_model import (
    POOL_META,
    build_pools,
    cursor_extra,
    format_pool_pct,
    format_reset,
    pool_remainings,
    pool_tip_lines,
)


class PetViewModelTests(unittest.TestCase):
    def test_build_pools_handles_empty_snapshot(self) -> None:
        pools = build_pools(None)
        self.assertEqual(set(pools), {"sg", "bot", "cm", "om", "cx"})
        self.assertTrue(all(pool["remaining"] is None for pool in pools.values()))
        self.assertEqual(len(pools["cx"]["layers"]), 2)
        for key, meta in POOL_META.items():
            self.assertEqual(pools[key]["title"], meta["title"])
            self.assertEqual(pools[key]["tag"], meta["tag"])
            self.assertEqual(pools[key]["period"], meta["period"])

    def test_codex_layers_use_dark_hour_and_light_week(self) -> None:
        pools = build_pools(
            {
                "codex": {
                    "primary": {"remaining_percent": 19.0, "resets_at": "2030-01-01T05:00:00Z"},
                    "secondary": {"remaining_percent": 87.0, "resets_at": "2030-01-07T00:00:00Z"},
                }
            }
        )
        cx = pools["cx"]
        self.assertEqual(cx["title"], "Codex")
        self.assertEqual(cx["remaining"], 19.0)
        self.assertEqual(format_pool_pct(cx), "19%  87%")
        self.assertEqual(pool_remainings(cx), [19.0, 87.0])
        hour, week = cx["layers"]
        self.assertEqual(hour["label"], "5小时")
        self.assertEqual(hour["tone"], "dark")
        self.assertEqual(hour["remaining"], 19.0)
        self.assertEqual(week["label"], "周额度")
        self.assertEqual(week["tone"], "light")
        self.assertEqual(week["remaining"], 87.0)
        self.assertEqual(cx["period"], "5小时 + 周额度")
        self.assertIn("深色 5小时 · 浅色 周额度", cx["extra"])
        tip = pool_tip_lines(cx)
        self.assertEqual(tip[0], "Codex")
        self.assertEqual(tip[1], "5小时 + 周额度")
        self.assertEqual(cx["tag"], "5h+周")
        self.assertEqual(tip[2], "19%  87%")

    def test_cursor_money_values_accept_numeric_strings(self) -> None:
        monthly = {
            "included_limit_cents": "2000",
            "included_used_cents": "125",
            "other_models": {},
        }
        extra = cursor_extra(monthly, "other_models")
        self.assertIn("套餐内 $1.25 / $20.00", extra)
        self.assertTrue(any(line.startswith("按量付费") for line in extra))
        self.assertFalse(any("On-Demand" in line or "display_message" in line for line in extra))

    def test_invalid_reset_is_displayed_without_crashing(self) -> None:
        self.assertEqual(format_reset("not-a-date"), ("not-a-date", ""))


if __name__ == "__main__":
    unittest.main()
