from __future__ import annotations

import unittest

from pet_view_model import build_pools, cursor_extra, format_reset


class PetViewModelTests(unittest.TestCase):
    def test_build_pools_handles_empty_snapshot(self) -> None:
        pools = build_pools(None)
        self.assertEqual(set(pools), {"sg", "bot", "cm", "om"})
        self.assertTrue(all(pool["remaining"] is None for pool in pools.values()))

    def test_cursor_money_values_accept_numeric_strings(self) -> None:
        monthly = {
            "included_limit_cents": "2000",
            "included_used_cents": "125",
            "other_models": {},
        }
        self.assertIn("套餐内 $1.25 / $20.00", cursor_extra(monthly, "other_models"))

    def test_invalid_reset_is_displayed_without_crashing(self) -> None:
        self.assertEqual(format_reset("not-a-date"), ("not-a-date", ""))


if __name__ == "__main__":
    unittest.main()
