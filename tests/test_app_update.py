from __future__ import annotations

import io
import hashlib
import os
import stat
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import app_update as upd


def _release_payload(version: str = "0.3.8") -> dict:
    return {
        "tag_name": f"v{version}",
        "draft": False,
        "prerelease": False,
        "immutable": True,
        "html_url": f"https://github.com/liruilong0805/grok-usage-pet/releases/tag/v{version}",
        "assets": [
            {
                "name": f"GrokUsagePet-v{version}-Windows-x64.zip",
                "browser_download_url": (
                    f"https://github.com/liruilong0805/grok-usage-pet/releases/download/"
                    f"v{version}/GrokUsagePet-v{version}-Windows-x64.zip"
                ),
                "size": 12,
                "digest": "sha256:" + "a" * 64,
            },
            {
                "name": f"GrokUsagePet-v{version}-Windows-x64.zip.sha256",
                "browser_download_url": (
                    f"https://github.com/liruilong0805/grok-usage-pet/releases/download/"
                    f"v{version}/GrokUsagePet-v{version}-Windows-x64.zip.sha256"
                ),
                "size": 80,
                "digest": "sha256:" + "b" * 64,
            },
        ],
    }


class AppUpdateTests(unittest.TestCase):
    def test_parse_and_compare_versions(self) -> None:
        self.assertEqual(upd.parse_version("v0.3.10"), (0, 3, 10))
        self.assertTrue(upd.is_newer("0.3.8", "0.3.7"))
        self.assertFalse(upd.is_newer("0.3.7", "0.3.7"))
        self.assertFalse(upd.is_newer("0.3.6", "0.3.7"))

    def test_url_allowlists(self) -> None:
        self.assertTrue(upd.allowed_api_url(upd.LATEST_URL))
        self.assertFalse(upd.allowed_api_url("https://evil.example/releases/latest"))
        self.assertFalse(upd.allowed_api_url(upd.LATEST_URL + "?page=1"))
        zip_url = (
            "https://github.com/liruilong0805/grok-usage-pet/releases/download/"
            "v0.3.8/GrokUsagePet-v0.3.8-Windows-x64.zip"
        )
        self.assertTrue(upd.allowed_download_url(zip_url))
        self.assertFalse(
            upd.allowed_download_url("https://github.com/other/repo/releases/download/v1/x.zip")
        )
        cdn_url = "https://release-assets.githubusercontent.com/item?sp=r&sig=signed"
        self.assertTrue(upd.allowed_cdn_url(cdn_url))
        self.assertFalse(upd.allowed_download_url(cdn_url))
        self.assertFalse(upd.allowed_download_url(zip_url + "?unexpected=1"))
        self.assertFalse(upd.allowed_html_url("https://evil.example/releases/tag/v1"))

    def test_api_and_asset_accept_headers_are_distinct(self) -> None:
        requests = []

        class Response:
            headers = {}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _size):
                return b""

        class Opener:
            def open(self, request, timeout):
                requests.append((request, timeout))
                return Response()

        with mock.patch.object(upd, "_opener", return_value=Opener()):
            upd._get_bytes(upd.LATEST_URL, limit=100)
            asset_url = (
                "https://github.com/liruilong0805/grok-usage-pet/releases/download/"
                "v0.3.8/GrokUsagePet-v0.3.8-Windows-x64.zip.sha256"
            )
            upd._get_bytes(asset_url, limit=100)

        self.assertEqual(requests[0][0].get_header("Accept"), "application/vnd.github+json")
        self.assertEqual(requests[1][0].get_header("Accept"), "application/octet-stream")

    def test_parse_latest_payload_requires_matching_windows_assets(self) -> None:
        release = upd.parse_latest_payload(_release_payload())
        self.assertEqual(release.version, "0.3.8")
        self.assertTrue(release.zip_asset.name.endswith(".zip"))
        payload = _release_payload()
        payload["assets"][0]["browser_download_url"] = "https://evil.example/x.zip"
        with self.assertRaises(RuntimeError):
            upd.parse_latest_payload(payload)
        payload = _release_payload()
        payload["immutable"] = False
        with self.assertRaises(RuntimeError):
            upd.parse_latest_payload(payload)

    def test_parse_sha256_text(self) -> None:
        digest = "a" * 64
        name = "GrokUsagePet-v0.3.8-Windows-x64.zip"
        self.assertEqual(upd.parse_sha256_text(f"{digest} *{name}\n", name), digest)
        with self.assertRaises(RuntimeError):
            upd.parse_sha256_text("not-a-hash\n", name)

    def test_safe_extract_rejects_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "bad.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../evil.exe", b"nope")
            dest = Path(tmp) / "out"
            with zipfile.ZipFile(archive_path) as archive:
                with self.assertRaises(RuntimeError):
                    upd._safe_extract(archive, dest)

    def test_safe_extract_rejects_total_size_and_windows_special_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            aggregate = root / "aggregate.zip"
            with zipfile.ZipFile(aggregate, "w") as archive:
                archive.writestr("a.bin", b"123")
                archive.writestr("b.bin", b"456")
            with zipfile.ZipFile(aggregate) as archive, mock.patch.object(
                upd, "MAX_EXTRACT_BYTES", 5
            ):
                with self.assertRaisesRegex(RuntimeError, "解压后过大"):
                    upd._safe_extract(archive, root / "aggregate-out")

            reserved = root / "reserved.zip"
            with zipfile.ZipFile(reserved, "w") as archive:
                archive.writestr("payload/CON.txt", b"nope")
            with zipfile.ZipFile(reserved) as archive:
                with self.assertRaisesRegex(RuntimeError, "路径无效"):
                    upd._safe_extract(archive, root / "reserved-out")

    def test_safe_extract_rejects_symlinks_and_case_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            symlink_zip = root / "symlink.zip"
            link = zipfile.ZipInfo("payload/link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(symlink_zip, "w") as archive:
                archive.writestr(link, "target")
            with zipfile.ZipFile(symlink_zip) as archive:
                with self.assertRaisesRegex(RuntimeError, "符号链接"):
                    upd._safe_extract(archive, root / "symlink-out")

            collision_zip = root / "collision.zip"
            with zipfile.ZipFile(collision_zip, "w") as archive:
                archive.writestr("payload/File.txt", b"one")
                archive.writestr("payload/file.txt", b"two")
            with zipfile.ZipFile(collision_zip) as archive:
                with self.assertRaisesRegex(RuntimeError, "重复路径"):
                    upd._safe_extract(archive, root / "collision-out")

    def test_find_payload_dir_requires_internal_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "GrokUsagePet.exe").write_bytes(b"x")
            with self.assertRaises(RuntimeError):
                upd.find_payload_dir(root)
            (root / "_internal").mkdir()
            self.assertEqual(upd.find_payload_dir(root), root)

    def test_apply_script_is_quoted_transactional_and_self_cleaning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "stage$`'quoted"
            payload = staging / "extracted" / "GrokUsagePet-v0.3.8-Windows-x64"
            install = root / "install$`'quoted"
            (payload / "_internal").mkdir(parents=True)
            (payload / "GrokUsagePet.exe").write_bytes(b"new")
            install.mkdir()
            (install / "GrokUsagePet.exe").write_bytes(b"old")
            prepared = upd.PreparedUpdate(payload, staging, "0.3.8")

            script = upd._build_apply_script(
                prepared,
                install,
                123,
                restart_watcher=True,
                token="fixed",
                ready_path=root / "ready$`'quoted",
            )

        self.assertIn("stage$`''quoted", script)
        self.assertIn("install$`''quoted", script)
        self.assertIn("--smoke-test", script)
        self.assertIn("Move-Item -LiteralPath $dst -Destination $backup", script)
        self.assertIn("register_watch.ps1", script)
        self.assertIn("Set-Content -LiteralPath $ready", script)
        self.assertIn("WaitForExit(15000)", script)
        self.assertIn("$PSCommandPath", script)
        self.assertIn("throw $failure", script)

    @unittest.skipUnless(os.name == "nt", "PowerShell parser is Windows-specific")
    def test_apply_script_is_valid_powershell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "stage"
            payload = staging / "extracted" / "GrokUsagePet-v0.3.8-Windows-x64"
            install = root / "install"
            (payload / "_internal").mkdir(parents=True)
            (payload / "GrokUsagePet.exe").write_bytes(b"new")
            install.mkdir()
            (install / "GrokUsagePet.exe").write_bytes(b"old")
            script = upd._build_apply_script(
                upd.PreparedUpdate(payload, staging, "0.3.8"),
                install,
                123,
                restart_watcher=True,
                token="fixed",
                ready_path=root / "ready",
            )

        parsed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "$text=[Console]::In.ReadToEnd(); [scriptblock]::Create($text) | Out-Null",
            ],
            input=script,
            text=True,
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(parsed.returncode, 0, parsed.stderr)

    def test_apply_preflight_requires_ready_signal(self) -> None:
        class Running:
            def poll(self):
                return None

        class Exited:
            def poll(self):
                return 1

        with tempfile.TemporaryDirectory() as tmp:
            ready = Path(tmp) / "ready"
            ready.write_text("ready", encoding="ascii")
            upd._wait_for_apply_preflight(Running(), ready, timeout_s=0.1)
            ready.unlink()
            with self.assertRaisesRegex(RuntimeError, "预检失败"):
                upd._wait_for_apply_preflight(Exited(), ready, timeout_s=0.1)

    def test_discard_prepared_update_rejects_outside_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "staging"
            outside = root / "outside"
            staging.mkdir()
            outside.mkdir()
            prepared = upd.PreparedUpdate(outside, staging, "0.3.9")
            with self.assertRaisesRegex(RuntimeError, "暂存路径无效"):
                upd.discard_prepared_update(prepared)
            self.assertTrue(staging.is_dir())

            payload = staging / "extracted" / "GrokUsagePet-v0.3.9-Windows-x64"
            payload.mkdir(parents=True)
            upd.discard_prepared_update(upd.PreparedUpdate(payload, staging, "0.3.9"))
            self.assertFalse(staging.exists())

    def test_download_payload_requires_api_and_checksum_digests(self) -> None:
        version = "0.3.8"
        root_name = f"GrokUsagePet-v{version}-Windows-x64"
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(f"{root_name}/GrokUsagePet.exe", b"exe")
            archive.writestr(f"{root_name}/_internal/runtime.txt", b"runtime")
            archive.writestr(
                f"{root_name}/{upd.INSTALL_MARKER_NAME}",
                upd.INSTALL_MARKER_VALUE.encode("ascii"),
            )
        zip_bytes = buffer.getvalue()
        zip_digest = hashlib.sha256(zip_bytes).hexdigest()
        zip_name = f"{root_name}.zip"
        sha_bytes = f"{zip_digest} *{zip_name}\n".encode()
        release = upd.LatestRelease(
            version=version,
            tag=f"v{version}",
            html_url=f"https://github.com/liruilong0805/grok-usage-pet/releases/tag/v{version}",
            zip_asset=upd.ReleaseAsset(zip_name, "zip-url", len(zip_bytes), zip_digest),
            sha_asset=upd.ReleaseAsset(
                f"{zip_name}.sha256",
                "sha-url",
                len(sha_bytes),
                hashlib.sha256(sha_bytes).hexdigest(),
            ),
        )

        def fake_get(url, **_kwargs):
            return sha_bytes if url == "sha-url" else zip_bytes

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            upd, "_get_bytes", side_effect=fake_get
        ):
            prepared = upd.download_verified_payload(release, Path(tmp))
            self.assertEqual(prepared.version, version)
            self.assertTrue((prepared.payload_dir / "GrokUsagePet.exe").is_file())
            self.assertFalse(any(prepared.staging_root.glob("*.zip")))


if __name__ == "__main__":
    unittest.main()
