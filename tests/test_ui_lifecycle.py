from __future__ import annotations

import tkinter as tk
import unittest
from types import SimpleNamespace

import pet


class UiLifecycleTests(unittest.TestCase):
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
