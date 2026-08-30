from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".ps1", ".bat", ".spec", ".yml", ".yaml"}
PUBLIC_DIRS = (ROOT / ".github", ROOT / "docs", ROOT / "skins", ROOT / "test", ROOT / "tests")
ROOT_PUBLIC_FILES = (
    ROOT / ".gitignore",
    ROOT / "README.md",
    ROOT / "README.zh-CN.md",
    ROOT / "NOTICE.md",
    ROOT / "ASSETS_NOTICE.md",
    ROOT / "SECURITY.md",
    ROOT / "CHANGELOG.md",
    ROOT / "LICENSE",
    ROOT / "GrokUsagePet.spec",
    ROOT / "pack-windows.ps1",
    ROOT / "pack-kawaii.ps1",
    ROOT / "pack.ps1",
    ROOT / "pack-mac.sh",
    ROOT / "launch-desktop.ps1",
    ROOT / "register_watch.ps1",
    ROOT / "start_pet.bat",
)
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\."),
)


def public_text_files() -> list[Path]:
    files = [path for path in ROOT_PUBLIC_FILES if path.exists()]
    for directory in PUBLIC_DIRS:
        if not directory.exists():
            continue
        files.extend(
            path
            for path in directory.rglob("*")
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES
        )
    return sorted(set(files))


class RepositoryHygieneTests(unittest.TestCase):
    def test_runtime_and_credential_files_are_ignored(self) -> None:
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        required = {
            "auth.json",
            "state.vscdb",
            "usage.json",
            "usage.txt",
            "pet_state.json",
            "*.log",
            "*.db",
            "*.sqlite",
            "*.sqlite3",
        }
        self.assertFalse(required - set(ignored))

    def test_public_text_has_no_personal_windows_home_path(self) -> None:
        leaks = []
        for path in public_text_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            if re.search(r"C:\\Users\\[^<%\\]+", text, flags=re.IGNORECASE):
                leaks.append(str(path.relative_to(ROOT)))
        self.assertEqual(leaks, [])

    def test_public_text_has_no_common_secret_shapes(self) -> None:
        leaks = []
        for path in public_text_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(pattern.search(text) for pattern in SECRET_PATTERNS):
                leaks.append(str(path.relative_to(ROOT)))
        self.assertEqual(leaks, [])


if __name__ == "__main__":
    unittest.main()
