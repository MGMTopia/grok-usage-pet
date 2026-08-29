from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TkThreadBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = ast.parse((ROOT / "pet.py").read_text(encoding="utf-8"))

    def method(self, name: str) -> ast.FunctionDef:
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef) and node.name == "UsagePet":
                for child in node.body:
                    if isinstance(child, ast.FunctionDef) and child.name == name:
                        return child
        self.fail(f"UsagePet.{name} not found")

    def test_worker_fetch_never_calls_tk(self) -> None:
        worker = self.method("_fetch")
        attributes = {
            node.attr
            for node in ast.walk(worker)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "self"
            and node.value.attr == "root"
        }
        self.assertEqual(attributes, set())

    def test_main_thread_poll_owns_tk_scheduling(self) -> None:
        poll = self.method("_poll_fetch_results")
        calls_after = [
            node
            for node in ast.walk(poll)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "after"
        ]
        self.assertEqual(len(calls_after), 1)


if __name__ == "__main__":
    unittest.main()
