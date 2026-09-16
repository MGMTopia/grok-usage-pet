from __future__ import annotations

import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pet


class UiLifecycleTests(unittest.TestCase):
    def test_layout_transition_is_painted_while_windows_layer_is_hidden(self) -> None:
        calls: list[tuple] = []

        class Root:
            def winfo_x(self) -> int:
                return 100

            def winfo_y(self) -> int:
                return 200

            def winfo_screenwidth(self) -> int:
                return 1920

            def winfo_screenheight(self) -> int:
                return 1080

            def winfo_viewable(self) -> bool:
                return True

            def attributes(self, *args):
                if args == ("-alpha",):
                    return 1.0
                calls.append(("alpha", args[1]))

            def update_idletasks(self) -> None:
                calls.append(("flush",))

            def geometry(self, value: str) -> None:
                calls.append(("geometry", value))

        class Canvas:
            def config(self, **kwargs) -> None:
                calls.append(("canvas", kwargs["width"], kwargs["height"]))

        instance = pet.UsagePet.__new__(pet.UsagePet)
        instance.root = Root()
        instance.canvas = Canvas()
        instance._win_w = 420
        instance._win_h = 500
        instance._sprite_y = 292
        instance._hover_open = False
        instance.pinned = False
        instance._layout_metrics = lambda: (192, 208, 0)
        instance._clamp_pos = lambda x, y, _w, _h: (x, y)
        instance._apply_chrome = lambda: calls.append(("chrome",))
        instance.draw = lambda: calls.append(("draw",))

        with mock.patch.object(pet.os, "name", "nt"):
            instance._apply_layout()

        self.assertEqual(calls[0], ("alpha", 0.0))
        self.assertLess(calls.index(("geometry", "192x208+214+492")), calls.index(("draw",)))
        self.assertEqual(calls[-1], ("alpha", 1.0))

    def test_menu_cleanup_tolerates_window_destroy(self) -> None:
        class DestroyedMenu:
            def tk_popup(self, _x, _y) -> None:
                return None

            def grab_release(self) -> None:
                raise tk.TclError("application has been destroyed")

        instance = pet.UsagePet.__new__(pet.UsagePet)
        instance.menu = DestroyedMenu()
        instance._hover_open = True
        instance._closing = True
        instance.pinned = False
        instance._note_activity = lambda: None
        instance._cancel_collapse = lambda: None

        instance.on_menu(SimpleNamespace(x_root=10, y_root=20))

    def test_pointer_over_sprite_cell_counts_as_content(self) -> None:
        box = (0, 284, 192, 492)
        self.assertTrue(
            pet.pointer_over_pet_content(
                40, 300, sprite_box=box, bars_visible=True, win_w=292, sprite_y=284
            )
        )
        self.assertTrue(
            pet.pointer_over_pet_content(
                146, 40, sprite_box=box, bars_visible=True, win_w=292, sprite_y=284
            )
        )
        self.assertFalse(
            pet.pointer_over_pet_content(
                400, 10, sprite_box=box, bars_visible=True, win_w=292, sprite_y=284
            )
        )

    def test_leave_over_sprite_does_not_collapse_on_animation_update(self) -> None:
        instance = pet.UsagePet.__new__(pet.UsagePet)
        instance._hover_open = True
        instance._hover = "pet"
        instance.pinned = False
        instance._drag = False
        collapsed: list[str] = []
        instance._pointer_over_content = lambda: True
        instance._schedule_collapse = lambda: collapsed.append("collapse")
        instance.draw = lambda: collapsed.append("draw")

        instance.on_leave(SimpleNamespace())

        self.assertEqual(collapsed, [])
        self.assertEqual(instance._hover, "pet")
        self.assertTrue(instance._hover_open)

    def test_leave_outside_pet_schedules_collapse(self) -> None:
        instance = pet.UsagePet.__new__(pet.UsagePet)
        instance._hover_open = True
        instance._hover = "pet"
        instance.pinned = False
        instance._drag = False
        collapsed: list[str] = []
        instance._pointer_over_content = lambda: False
        instance._schedule_collapse = lambda: collapsed.append("collapse")
        instance.draw = lambda: collapsed.append("draw")

        instance.on_leave(SimpleNamespace())

        self.assertEqual(collapsed, ["collapse", "draw"])
        self.assertIsNone(instance._hover)

    def test_manual_update_check_stays_in_settings_without_toast(self) -> None:
        instance = pet.UsagePet.__new__(pet.UsagePet)
        instance.language = "zh-CN"
        instance._update_busy = True
        instance._closing = False
        instance._settings = SimpleNamespace(winfo_exists=lambda: True)
        instance._update_status = None
        toasted: list[str] = []
        opened: list[object] = []
        instance._toast = lambda text: toasted.append(text)
        instance._refresh_update_status = lambda: None
        instance._open_release_page = lambda info: opened.append(info)
        release = SimpleNamespace(version="0.3.16", html_url="https://example.invalid")
        with mock.patch.object(pet, "save_state"), mock.patch.object(pet.app_update, "is_newer", return_value=False):
            instance._apply_update_result("checked", release, True, "")
        self.assertEqual(toasted, [])
        self.assertEqual(opened, [])
        self.assertIs(instance._update_info, release)

    def test_toast_does_not_steal_the_mouse_with_grab(self) -> None:
        import ast

        source = (Path(__file__).resolve().parents[1] / "pet.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        toast = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_toast":
                toast = node
                break
        self.assertIsNotNone(toast)
        attrs = {
            child.attr
            for child in ast.walk(toast)
            if isinstance(child, ast.Attribute)
        }
        self.assertNotIn("grab_set", attrs)
        self.assertIn("_front_parent", attrs)


if __name__ == "__main__":
    unittest.main()
