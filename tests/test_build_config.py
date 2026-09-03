from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BuildConfigTests(unittest.TestCase):
    def test_windows_spec_is_single_resource_source_of_truth(self) -> None:
        spec = (ROOT / "GrokUsagePet.spec").read_text(encoding="utf-8")
        self.assertNotIn("('assets', 'assets')", spec)
        self.assertIn("('skins', 'skins')", spec)
        self.assertIn("'watch_apps'", spec)
        self.assertIn("skins/original/app.ico", spec)

    def test_pack_script_builds_the_spec_without_duplicate_cli_options(self) -> None:
        script = (ROOT / "pack-windows.ps1").read_text(encoding="utf-8")
        self.assertIn('PyInstaller --noconfirm --clean "GrokUsagePet.spec"', script)
        self.assertNotIn("--add-data", script)
        self.assertNotIn("--hidden-import", script)
        self.assertIn("requirements-build.lock", script)
        self.assertIn("--visual-smoke-test", script)
        self.assertIn("CHANGELOG.md", script)
        self.assertIn("NOTICE.md", script)
        self.assertIn("ASSETS_NOTICE.md", script)
        self.assertIn("THIRD_PARTY_NOTICES.md", script)
        self.assertIn("PILLOW_LICENSE.txt", script)
        self.assertIn("PYTHON_LICENSE.txt", script)
        self.assertIn("LICENSE", script)
        self.assertIn(".sha256", script)
        self.assertIn("secretPatterns", script)
        self.assertIn("build dependency mismatch", script)
        self.assertIn("--require-hashes -r requirements-build.lock", script)

    def test_dependency_files_cover_runtime_and_builder(self) -> None:
        runtime = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        build = (ROOT / "requirements-build.txt").read_text(encoding="utf-8")
        lock = (ROOT / "requirements-build.lock").read_text(encoding="utf-8")
        self.assertIn("Pillow==12.3.0", runtime)
        self.assertIn("PyInstaller==6.22.2", build)
        self.assertIn("pyinstaller-hooks-contrib==2026.7", build)
        self.assertIn("-r requirements.txt", build)
        self.assertIn("Pillow==12.3.0", lock)
        self.assertIn("--hash=sha256:", lock)

    def test_version_is_documented_consistently(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        version_module = (ROOT / "app_version.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        instructions = (ROOT / "使用说明.txt").read_text(encoding="utf-8")
        for content in (version_module, readme, changelog, instructions):
            self.assertIn(version, content)
        self.assertIn("0.1.0", changelog)
        self.assertIn(f"v{version}", readme)

    def test_code_and_asset_licenses_are_separate(self) -> None:
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        assets = (ROOT / "ASSETS_NOTICE.md").read_text(encoding="utf-8")
        self.assertIn("MIT License", license_text)
        self.assertIn("megumi-kato", assets)

    def test_release_workflow_binds_tag_version_and_changelog(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn('if ($env:GITHUB_REF_NAME -ne $expected)', workflow)
        self.assertIn("CHANGELOG section for $version not found", workflow)
        self.assertIn("--notes-file release-notes.md", workflow)
        self.assertIn("--require-hashes -r requirements-build.lock", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6", workflow)
        self.assertIn("--draft", workflow)
        self.assertIn("--draft=false", workflow)

    def test_workflows_pin_actions_to_commit_shas(self) -> None:
        for name in ("test.yml", "release.yml"):
            workflow = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            uses = re.findall(r"^\s*-?\s*uses:\s*([^\s#]+)", workflow, flags=re.MULTILINE)
            self.assertTrue(uses, name)
            for action in uses:
                revision = action.rsplit("@", 1)[-1]
                self.assertRegex(revision, r"^[0-9a-f]{40}$", f"{name}: {action}")


if __name__ == "__main__":
    unittest.main()
