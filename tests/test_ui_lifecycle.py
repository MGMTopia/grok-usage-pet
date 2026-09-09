from __future__ import annotations

import tkinter as tk
import unittest
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


if __name__ == "__main__":
    unittest.main()
