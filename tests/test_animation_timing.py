from __future__ import annotations

import unittest
import math

import pet


class AnimationTimingTests(unittest.TestCase):
    def test_frame_clock_preserves_remainder(self) -> None:
        steps, remainder = pet._frame_clock_steps(80, 40, 110)
        self.assertEqual(steps, 1)
        self.assertEqual(remainder, 10)

        steps, remainder = pet._frame_clock_steps(remainder, 100, 110)
        self.assertEqual(steps, 1)
        self.assertEqual(remainder, 0)

    def test_frame_clock_clamps_long_ui_pause(self) -> None:
        steps, remainder = pet._frame_clock_steps(0, 5000, 100)
        self.assertEqual(steps, pet.MAX_ANIM_ELAPSED_MS // 100)
        self.assertEqual(remainder, pet.MAX_ANIM_ELAPSED_MS % 100)

    def test_circular_step_uses_shortest_wraparound_path(self) -> None:
        self.assertEqual(pet._step_circular_index(15, 1), 0)
        self.assertEqual(pet._step_circular_index(0, 15), 15)
        self.assertEqual(pet._step_circular_index(5, 5), 5)

    def test_angular_distance_wraps_at_north(self) -> None:
        self.assertEqual(pet._angular_distance_degrees(359, 1), 2)
        self.assertEqual(pet._angular_distance_degrees(10, 350), 20)

    def test_look_direction_holds_near_a_sector_boundary(self) -> None:
        class PointerRoot:
            def __init__(self, heading: float, distance: float = 100) -> None:
                radians = math.radians(heading)
                self.px = 96 + math.sin(radians) * distance
                self.py = 104 - math.cos(radians) * distance

            def winfo_pointerx(self):
                return self.px

            def winfo_pointery(self):
                return self.py

            def winfo_rootx(self):
                return 0

            def winfo_rooty(self):
                return 0

        instance = pet.UsagePet.__new__(pet.UsagePet)
        instance._looks = [object()] * pet.LOOK_SECTORS
        instance._sprite_box = (0, 0, 192, 208)
        instance._anim = "look"
        instance._look_target = 0

        instance.root = PointerRoot(12)
        self.assertEqual(instance._look_index(), 0)

        instance.root = PointerRoot(15)
        self.assertEqual(instance._look_index(), 1)

    def test_look_distance_uses_enter_and_stay_hysteresis(self) -> None:
        class PointerRoot:
            def __init__(self, distance: float) -> None:
                self.distance = distance

            def winfo_pointerx(self):
                return 96

            def winfo_pointery(self):
                return 104 - self.distance

            def winfo_rootx(self):
                return 0

            def winfo_rooty(self):
                return 0

        instance = pet.UsagePet.__new__(pet.UsagePet)
        instance._looks = [object()] * pet.LOOK_SECTORS
        instance._sprite_box = (0, 0, 192, 208)
        instance.root = PointerRoot(40)
        instance._anim = "idle"
        instance._look_target = None
        self.assertIsNone(instance._look_index())

        instance._anim = "look"
        instance._look_target = 0
        self.assertEqual(instance._look_index(), 0)

    def test_quota_fetch_oneshot_uses_low_and_healthy_thresholds(self) -> None:
        self.assertEqual(pet.quota_fetch_oneshot([19.9]), "failed")
        self.assertEqual(pet.quota_fetch_oneshot([5.0, 88.0]), "failed")
        self.assertEqual(pet.quota_fetch_oneshot([20.0]), None)
        self.assertEqual(pet.quota_fetch_oneshot([20.1]), "waiting")
        self.assertEqual(pet.quota_fetch_oneshot([72.0, 41.0]), "waiting")
        self.assertIsNone(pet.quota_fetch_oneshot([]))
        self.assertEqual(
            pet.quota_fetch_oneshot([], error=True, has_snap=True),
            "failed",
        )
        self.assertIsNone(pet.quota_fetch_oneshot([], error=True, has_snap=False))

    def test_idle_wave_due_after_five_minutes(self) -> None:
        self.assertFalse(pet.idle_wave_due(0.0, 299.9))
        self.assertTrue(pet.idle_wave_due(0.0, 300.0))
        self.assertFalse(pet.idle_wave_due(100.0, 399.9, idle_s=300.0))
        self.assertTrue(pet.idle_wave_due(100.0, 400.0, idle_s=300.0))

    def test_waving_oneshot_beats_loading_wait(self) -> None:
        instance = pet.UsagePet.__new__(pet.UsagePet)
        instance._drag = None
        instance.snap = None
        instance._oneshot = "waving"
        instance._anims = {"waving": [object()], "waiting": [object()], "idle": [object()]}
        self.assertEqual(instance._current_anim(), "waving")
        instance._oneshot = None
        self.assertEqual(instance._current_anim(), "waiting")


if __name__ == "__main__":
    unittest.main()
