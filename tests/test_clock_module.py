from __future__ import annotations

import unittest
from datetime import datetime

import clock_module
from pet_settings import normalize_state


class ClockModuleTests(unittest.TestCase):
    def test_time_and_timer_rows_follow_enabled_flags(self) -> None:
        rows = clock_module.clock_rows(
            {"time": True, "timer": False},
            {},
            now=1_700_000_000.0,
            moment=datetime(2026, 9, 10, 21, 4, 8),
        )
        self.assertIn("clk", rows)
        self.assertNotIn("tmr", rows)
        self.assertEqual(rows["clk"]["value_text"], "21:04:08")
        self.assertEqual(clock_module.visible_clock_rows({"time": True, "timer": False}), ("clk",))
        self.assertEqual(clock_module.visible_clock_rows({}), ())

    def test_toggle_timer_accumulates_and_reset_clears(self) -> None:
        state = clock_module.toggle_timer({}, 100.0)
        self.assertTrue(state["timer_running"])
        paused = clock_module.toggle_timer(state, 112.5)
        self.assertFalse(paused["timer_running"])
        self.assertEqual(paused["timer_accumulated_ms"], 12500.0)
        self.assertEqual(clock_module.format_elapsed(12500), "00:12")
        resumed = clock_module.toggle_timer(paused, 200.0)
        later = clock_module.timer_elapsed_ms(resumed, 205.0)
        self.assertEqual(later, 17500.0)
        cleared = clock_module.reset_timer(resumed)
        self.assertFalse(cleared["timer_running"])
        self.assertEqual(cleared["timer_accumulated_ms"], 0.0)

    def test_legacy_settings_gain_clock_defaults_without_touching_quota(self) -> None:
        state = normalize_state({"enabled": {"sg": False, "bot": True, "cm": True, "om": True, "cx": True}})
        self.assertFalse(state["enabled"]["sg"])
        self.assertNotIn("time", state["enabled"])
        self.assertTrue(state["modules"]["clock"]["enabled"]["time"])
        self.assertTrue(state["modules"]["clock"]["enabled"]["timer"])

    def test_clock_panel_view_uses_weekday_and_labels(self) -> None:
        view = clock_module.clock_panel_view(
            {"time": True, "timer": True},
            {"timer_running": False, "timer_accumulated_ms": 0},
            now=1_700_000_000.0,
            moment=datetime(2026, 9, 10, 21, 4, 8),
        )
        self.assertEqual(view["weekday"], "周四")
        self.assertEqual(view["date"], "9月10日")
        self.assertEqual(view["hours"], "21")
        self.assertEqual(view["minutes"], "04")
        self.assertEqual(view["seconds"], "08")
        self.assertEqual(view["caption"], "本地时间")
        self.assertEqual(view["timer_caption"], "倒计时")
        self.assertEqual(view["timer_status"], "待开始")
        self.assertEqual(view["toggle_label"], "开始")
        self.assertEqual(view["timer_text"], "05:00")
        self.assertFalse(view["timer_ringing"])
        self.assertTrue(clock_module.clock_panel_available({"time": True, "timer": False}))
        self.assertFalse(clock_module.clock_panel_available({}))

    def test_legacy_state_keeps_quota_panel_by_default(self) -> None:
        state = normalize_state({"skin": "original"})
        self.assertEqual(state["info_panel"], "quota")
        self.assertEqual(state["interaction"]["info_panel"], "quota")

    def test_countdown_reaches_zero_and_rings(self) -> None:
        state = clock_module.set_countdown_minutes({}, 1)
        self.assertEqual(state["timer_mode"], "countdown")
        self.assertEqual(state["countdown_ms"], 60_000)
        started = clock_module.toggle_timer(state, 10.0)
        later = clock_module.advance_timer(started, 10.0 + 61)
        self.assertTrue(later["timer_ringing"])
        self.assertFalse(later["timer_running"])
        dismissed = clock_module.toggle_timer(later, 80.0)
        self.assertFalse(dismissed["timer_ringing"])
        hour, minute, second = clock_module.alarm_hand_angles(0, 15_000, countdown=True)
        self.assertEqual(second, 90.0)
        self.assertEqual(minute, 1.5)

    def test_clock_module_never_requests_network_refresh(self) -> None:
        module = clock_module.ClockModule()
        self.assertFalse(module.wants_refresh({"time": True, "timer": True}))
        self.assertTrue(module.refresh().ok)


if __name__ == "__main__":
    unittest.main()
