"""Check GitHub Releases and apply a verified portable update."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import ssl
import stat
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app_version import APP_VERSION, INSTALL_MARKER_NAME, INSTALL_MARKER_VALUE

GITHUB_OWNER = "liruilong0805"
GITHUB_REPO = "grok-usage-pet"
LATEST_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
HTML_RELEASE_PREFIX = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/"
API_HOST = "api.github.com"
CDN_HOSTS = {
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "github-releases.githubusercontent.com",
}
ZIP_NAME_RE = re.compile(r"^GrokUsagePet-v(\d+\.\d+\.\d+)-Windows-x64\.zip$")
SHA_NAME_RE = re.compile(r"^GrokUsagePet-v(\d+\.\d+\.\d+)-Windows-x64\.zip\.sha256$")
MAX_JSON_BYTES = 256 * 1024
MAX_SHA_BYTES = 4096
MAX_ZIP_BYTES = 80 * 1024 * 1024
MAX_EXTRACT_BYTES = 256 * 1024 * 1024
MAX_ZIP_ENTRIES = 4096
CHECK_INTERVAL_S = 24 * 60 * 60
USER_AGENT = f"GrokUsagePet/{APP_VERSION} (+https://github.com/{GITHUB_OWNER}/{GITHUB_REPO})"
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    url: str
    size: int
    digest: str


@dataclass(frozen=True)
class LatestRelease:
    version: str
    tag: str
    html_url: str
    zip_asset: ReleaseAsset
    sha_asset: ReleaseAsset


@dataclass(frozen=True)
class PreparedUpdate:
    payload_dir: Path
    staging_root: Path
    version: str


class AllowlistRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        previous = str(getattr(req, "full_url", "") or "")
        previous_is_asset = allowed_download_url(previous) or allowed_cdn_url(previous)
        if allowed_api_url(newurl):
            allowed = allowed_api_url(previous)
        else:
            allowed = previous_is_asset and (allowed_download_url(newurl) or allowed_cdn_url(newurl))
        if not allowed:
            raise RuntimeError("更新地址无效")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def parse_version(text: str) -> tuple[int, ...]:
    raw = str(text or "").strip()
    if raw.startswith(("v", "V")):
        raw = raw[1:]
    parts = raw.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError("invalid version")
    return tuple(int(part) for part in parts)


def is_newer(remote: str, local: str = APP_VERSION) -> bool:
    try:
        return parse_version(remote) > parse_version(local)
    except ValueError:
        return False


def allowed_api_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(str(url or "").strip())
    return (
        parsed.scheme == "https"
        and parsed.hostname == API_HOST
        and parsed.port in (None, 443)
        and not parsed.username
        and not parsed.password
        and parsed.path == f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
        and not parsed.query
        and not parsed.fragment
    )


def allowed_download_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(str(url or "").strip())
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        return False
    parts = parsed.path.split("/")
    if len(parts) != 7 or parts[1:5] != [GITHUB_OWNER, GITHUB_REPO, "releases", "download"]:
        return False
    tag = parts[5]
    filename = urllib.parse.unquote(parts[6])
    if not filename or Path(filename).name != filename:
        return False
    match = ZIP_NAME_RE.fullmatch(filename) or SHA_NAME_RE.fullmatch(filename)
    return bool(match and tag == f"v{match.group(1)}")


def allowed_cdn_url(url: str) -> bool:
    """Accept HTTPS release-asset redirects, including GitHub's signed query."""
    parsed = urllib.parse.urlparse(str(url or "").strip())
    return (
        parsed.scheme == "https"
        and parsed.hostname in CDN_HOSTS
        and parsed.port in (None, 443)
        and not parsed.username
        and not parsed.password
        and bool(parsed.path and parsed.path != "/")
        and not parsed.fragment
    )


def allowed_html_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(str(url or "").strip())
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        return False
    return str(url).startswith(HTML_RELEASE_PREFIX)


def _opener() -> urllib.request.OpenerDirector:
    context = ssl.create_default_context()
    https = urllib.request.HTTPSHandler(context=context)
    return urllib.request.build_opener(https, AllowlistRedirectHandler)


def _get_bytes(url: str, *, limit: int, timeout: int = 30) -> bytes:
    if not (allowed_api_url(url) or allowed_download_url(url)):
        raise RuntimeError("更新地址无效")
    headers = {"User-Agent": USER_AGENT}
    if allowed_api_url(url):
        headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
    else:
        headers["Accept"] = "application/octet-stream"
    req = urllib.request.Request(url, headers=headers, method="GET")
    with _opener().open(req, timeout=timeout) as resp:
        declared = resp.headers.get("Content-Length")
        if declared is not None:
            try:
                if int(declared) > limit:
                    raise RuntimeError("更新文件过大")
            except ValueError:
                pass
        chunks: list[bytes] = []
        total = 0
        while True:
            piece = resp.read(64 * 1024)
            if not piece:
                break
            total += len(piece)
            if total > limit:
                raise RuntimeError("更新文件过大")
            chunks.append(piece)
    return b"".join(chunks)


def parse_latest_payload(payload: dict) -> LatestRelease:
    if payload.get("draft") is True or payload.get("prerelease") is True:
        raise RuntimeError("更新版本尚未正式发布")
    if payload.get("immutable") is not True:
        raise RuntimeError("更新版本尚未锁定")
    tag = str(payload.get("tag_name") or "")
    version = tag[1:] if tag.startswith(("v", "V")) else tag
    parse_version(version)
    html_url = str(payload.get("html_url") or "")
    if not allowed_html_url(html_url):
        raise RuntimeError("更新说明地址无效")
    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise RuntimeError("更新资源无效")
    zip_asset = None
    sha_asset = None
    for raw in assets:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "")
        url = str(raw.get("browser_download_url") or "")
        try:
            size = int(raw.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        digest = str(raw.get("digest") or "").lower()
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            continue
        if not allowed_download_url(url) or size <= 0:
            continue
        zip_match = ZIP_NAME_RE.fullmatch(name)
        sha_match = SHA_NAME_RE.fullmatch(name)
        if zip_match and zip_match.group(1) == version and size <= MAX_ZIP_BYTES:
            zip_asset = ReleaseAsset(name=name, url=url, size=size, digest=digest.removeprefix("sha256:"))
        elif sha_match and sha_match.group(1) == version and size <= MAX_SHA_BYTES:
            sha_asset = ReleaseAsset(name=name, url=url, size=size, digest=digest.removeprefix("sha256:"))
    if zip_asset is None or sha_asset is None:
        raise RuntimeError("未找到可校验的 Windows 更新包")
    return LatestRelease(
        version=version,
        tag=tag if tag.startswith("v") else f"v{version}",
        html_url=html_url,
        zip_asset=zip_asset,
        sha_asset=sha_asset,
    )


def fetch_latest_release() -> LatestRelease:
    raw = _get_bytes(LATEST_URL, limit=MAX_JSON_BYTES, timeout=20)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("更新信息无法解析") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("更新信息无效")
    return parse_latest_payload(payload)


def parse_sha256_text(text: str, filename: str) -> str:
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.replace("*", " ").split()
        if len(parts) < 1:
            continue
        digest = parts[0].lower()
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            continue
        if len(parts) == 1 or Path(parts[-1]).name == filename:
            return digest
    raise RuntimeError("校验文件无效")


def _zip_parts(info: zipfile.ZipInfo) -> tuple[str, ...]:
    name = info.filename.replace("\\", "/")
    if not name or name.startswith("/") or "\x00" in name:
        raise RuntimeError("更新包路径无效")
    parts = PurePosixPath(name).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise RuntimeError("更新包路径无效")
    for part in parts:
        if ":" in part or part.endswith((" ", ".")):
            raise RuntimeError("更新包路径无效")
        stem = part.split(".", 1)[0].rstrip(" .").upper()
        if stem in WINDOWS_RESERVED_NAMES:
            raise RuntimeError("更新包路径无效")
    mode = (info.external_attr >> 16) & 0o170000
    if mode == stat.S_IFLNK:
        raise RuntimeError("更新包不允许符号链接")
    return parts


def _safe_extract(archive: zipfile.ZipFile, dest: Path) -> None:
    entries = archive.infolist()
    if len(entries) > MAX_ZIP_ENTRIES:
        raise RuntimeError("更新包文件过多")
    planned: list[tuple[zipfile.ZipInfo, tuple[str, ...]]] = []
    seen: set[str] = set()
    total_declared = 0
    for info in entries:
        parts = _zip_parts(info)
        key = "/".join(parts).casefold()
        if key in seen:
            raise RuntimeError("更新包包含重复路径")
        seen.add(key)
        if info.file_size < 0 or info.file_size > MAX_EXTRACT_BYTES:
            raise RuntimeError("更新文件过大")
        total_declared += info.file_size
        if total_declared > MAX_EXTRACT_BYTES:
            raise RuntimeError("更新包解压后过大")
        planned.append((info, parts))

    dest = dest.resolve()
    if dest.exists() or dest.is_symlink():
        _rmtree(dest)
    dest.mkdir(parents=True, exist_ok=False)
    total_copied = 0
    for info, parts in planned:
        target = dest.joinpath(*parts)
        try:
            target.resolve().relative_to(dest)
        except ValueError as exc:
            raise RuntimeError("更新包路径无效") from exc
        if info.is_dir() or info.filename.endswith(("/", "\\")):
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with archive.open(info) as src, target.open("xb") as out:
                while True:
                    chunk = src.read(64 * 1024)
                    if not chunk:
                        break
                    total_copied += len(chunk)
                    if total_copied > MAX_EXTRACT_BYTES:
                        raise RuntimeError("更新包解压后过大")
                    out.write(chunk)
        except FileExistsError as exc:
            raise RuntimeError("更新包包含重复路径") from exc


def find_payload_dir(extracted: Path, expected_name: str | None = None) -> Path:
    matches = [
        path
        for path in extracted.rglob("GrokUsagePet.exe")
        if path.is_file() and path.name == "GrokUsagePet.exe"
    ]
    if len(matches) != 1:
        raise RuntimeError("更新包结构无效")
    payload = matches[0].parent
    if expected_name is not None:
        children = list(extracted.iterdir())
        if len(children) != 1 or payload.parent.resolve() != extracted.resolve() or payload.name != expected_name:
            raise RuntimeError("更新包结构无效")
    if not (payload / "_internal").is_dir():
        raise RuntimeError("更新包缺少运行文件")
    if expected_name is not None:
        marker = payload / INSTALL_MARKER_NAME
        try:
            marker_value = marker.read_text(encoding="ascii").strip()
        except OSError as exc:
            raise RuntimeError("更新包缺少安装标记") from exc
        if marker.is_symlink() or marker_value != INSTALL_MARKER_VALUE:
            raise RuntimeError("更新包安装标记无效")
    try:
        payload.resolve().relative_to(extracted.resolve())
    except ValueError as exc:
        raise RuntimeError("更新包路径无效") from exc
    return payload


def download_verified_payload(release: LatestRelease, work_dir: Path) -> PreparedUpdate:
    if work_dir.is_symlink():
        raise RuntimeError("更新暂存目录无效")
    work_dir.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(prefix=f"v{release.version}-", dir=work_dir)).resolve()
    try:
        sha_bytes = _get_bytes(release.sha_asset.url, limit=MAX_SHA_BYTES, timeout=20)
        if len(sha_bytes) != release.sha_asset.size or hashlib.sha256(sha_bytes).hexdigest() != release.sha_asset.digest:
            raise RuntimeError("校验文件与发布记录不匹配")
        expected = parse_sha256_text(
            sha_bytes.decode("utf-8", errors="replace"), release.zip_asset.name
        )
        zip_path = staging_root / release.zip_asset.name
        zip_bytes = _get_bytes(release.zip_asset.url, limit=MAX_ZIP_BYTES, timeout=120)
        if len(zip_bytes) != release.zip_asset.size:
            raise RuntimeError("更新包大小不匹配")
        actual = hashlib.sha256(zip_bytes).hexdigest()
        if actual != expected or actual != release.zip_asset.digest:
            raise RuntimeError("更新包校验失败")
        zip_path.write_bytes(zip_bytes)
        extract_dir = staging_root / "extracted"
        try:
            with zipfile.ZipFile(zip_path) as archive:
                _safe_extract(archive, extract_dir)
        except (OSError, zipfile.BadZipFile) as exc:
            raise RuntimeError("更新包无法解压") from exc
        expected_root = f"GrokUsagePet-v{release.version}-Windows-x64"
        payload = find_payload_dir(extract_dir, expected_name=expected_root)
        zip_path.unlink()
        return PreparedUpdate(payload_dir=payload, staging_root=staging_root, version=release.version)
    except Exception:
        _rmtree(staging_root)
        raise


def _rmtree(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def discard_prepared_update(update: PreparedUpdate) -> None:
    """Remove one updater-owned staging tree after validating containment."""
    payload = update.payload_dir.resolve()
    staging_root = update.staging_root.resolve()
    try:
        payload.relative_to(staging_root)
    except ValueError as exc:
        raise RuntimeError("更新暂存路径无效") from exc
    if payload == staging_root or staging_root.parent == staging_root:
        raise RuntimeError("更新暂存路径无效")
    _rmtree(staging_root)


def _powershell_literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _build_apply_script(
    update: PreparedUpdate,
    install_dir: Path,
    wait_pid: int,
    *,
    restart_watcher: bool,
    token: str,
    ready_path: Path,
) -> str:
    src = update.payload_dir.resolve()
    staging_root = update.staging_root.resolve()
    dst = install_dir.resolve()
    incoming = dst.parent / f".{dst.name}.incoming-{token}"
    backup = dst.parent / f".{dst.name}.backup-{token}"
    failed = dst.parent / f".{dst.name}.failed-{token}"
    restart = "$true" if restart_watcher else "$false"
    return f"""
$ErrorActionPreference = 'Stop'
$src = {_powershell_literal(src)}
$stagingRoot = {_powershell_literal(staging_root)}
$dst = {_powershell_literal(dst)}
$incoming = {_powershell_literal(incoming)}
$backup = {_powershell_literal(backup)}
$failed = {_powershell_literal(failed)}
$ready = {_powershell_literal(ready_path)}
$waitPid = {int(wait_pid)}
$restartWatcher = {restart}
$oldMoved = $false
$newMoved = $false
$started = $null

function Remove-TreeBestEffort([string]$path) {{
    if (Test-Path -LiteralPath $path) {{
        Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
    }}
}}

try {{
    if (-not (Test-Path -LiteralPath $src -PathType Container)) {{ throw 'staged payload missing' }}
    if (-not (Test-Path -LiteralPath $dst -PathType Container)) {{ throw 'install directory missing' }}
    if ((Test-Path -LiteralPath $incoming) -or (Test-Path -LiteralPath $backup) -or (Test-Path -LiteralPath $failed)) {{
        throw 'update transaction path already exists'
    }}

    [IO.Directory]::CreateDirectory($incoming) | Out-Null
    Get-ChildItem -LiteralPath $src -Force | Copy-Item -Destination $incoming -Recurse -Force
    $incomingExe = Join-Path $incoming 'GrokUsagePet.exe'
    if (-not (Test-Path -LiteralPath $incomingExe -PathType Leaf)) {{ throw 'new executable missing' }}
    if (-not (Test-Path -LiteralPath (Join-Path $incoming '_internal') -PathType Container)) {{ throw 'new runtime missing' }}
    $smoke = Start-Process -FilePath $incomingExe -ArgumentList '--smoke-test' -WorkingDirectory $incoming -WindowStyle Hidden -PassThru
    if (-not $smoke.WaitForExit(15000)) {{
        Stop-Process -Id $smoke.Id -Force -ErrorAction SilentlyContinue
        throw 'new executable smoke test timed out'
    }}
    if ($smoke.ExitCode -ne 0) {{ throw "new executable smoke test failed: $($smoke.ExitCode)" }}
    Set-Content -LiteralPath $ready -Value 'ready' -Encoding Ascii

    for ($i = 0; $i -lt 60; $i++) {{
        if (-not (Get-Process -Id $waitPid -ErrorAction SilentlyContinue)) {{ break }}
        Start-Sleep -Milliseconds 500
    }}
    if (Get-Process -Id $waitPid -ErrorAction SilentlyContinue) {{ throw 'running app did not exit' }}
    Start-Sleep -Milliseconds 400

    Move-Item -LiteralPath $dst -Destination $backup
    $oldMoved = $true
    Move-Item -LiteralPath $incoming -Destination $dst
    $newMoved = $true
    $exe = Join-Path $dst 'GrokUsagePet.exe'
    $started = Start-Process -FilePath $exe -WorkingDirectory $dst -PassThru
    Start-Sleep -Milliseconds 1200
    if ($started.HasExited) {{ throw "new application exited early: $($started.ExitCode)" }}

    if ($restartWatcher) {{
        $register = Join-Path $dst 'register_watch.ps1'
        if (-not (Test-Path -LiteralPath $register -PathType Leaf)) {{ throw 'watcher registration script missing' }}
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $register -Action Enable
        if ($LASTEXITCODE -ne 0) {{ throw "watcher restart failed: $LASTEXITCODE" }}
    }}

    Remove-TreeBestEffort $backup
    Remove-TreeBestEffort $stagingRoot
}} catch {{
    $failure = $_
    if ($restartWatcher) {{
        Stop-ScheduledTask -TaskName 'GrokUsagePetWatch' -ErrorAction SilentlyContinue
    }}
    if ($started -and -not $started.HasExited) {{
        Stop-Process -Id $started.Id -Force -ErrorAction SilentlyContinue
        $started.WaitForExit(5000) | Out-Null
    }}
    if ($newMoved -and (Test-Path -LiteralPath $dst)) {{
        Move-Item -LiteralPath $dst -Destination $failed -ErrorAction SilentlyContinue
    }}
    if ($oldMoved -and (Test-Path -LiteralPath $backup)) {{
        Move-Item -LiteralPath $backup -Destination $dst
    }}
    $restoreExe = Join-Path $dst 'GrokUsagePet.exe'
    if (-not (Get-Process -Id $waitPid -ErrorAction SilentlyContinue) -and (Test-Path -LiteralPath $restoreExe -PathType Leaf)) {{
        Start-Process -FilePath $restoreExe -WorkingDirectory $dst -ErrorAction SilentlyContinue
    }}
    Remove-TreeBestEffort $incoming
    Remove-TreeBestEffort $failed
    Remove-TreeBestEffort $stagingRoot
    throw $failure
}} finally {{
    Remove-Item -LiteralPath $ready -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
}}
"""


def _wait_for_apply_preflight(
    process: subprocess.Popen,
    ready_path: Path,
    *,
    timeout_s: float = 30.0,
) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if ready_path.is_file():
            return
        if process.poll() is not None:
            raise RuntimeError("更新预检失败，当前版本未被替换")
        time.sleep(0.05)
    raise RuntimeError("更新预检超时，当前版本未被替换")


def launch_apply(
    update: PreparedUpdate,
    install_dir: Path,
    wait_pid: int,
    *,
    restart_watcher: bool = False,
) -> None:
    if os.name != "nt":
        raise RuntimeError("仅 Windows 安装包支持应用内更新")
    payload = update.payload_dir.resolve()
    staging_root = update.staging_root.resolve()
    destination = install_dir.resolve()
    if not is_newer(update.version):
        raise RuntimeError("更新版本不是较新版本")
    if not payload.is_dir() or not staging_root.is_dir() or not destination.is_dir():
        raise RuntimeError("更新路径无效")
    try:
        payload.relative_to(staging_root)
    except ValueError as exc:
        raise RuntimeError("更新暂存路径无效") from exc
    if destination == staging_root or destination.is_relative_to(staging_root) or staging_root.is_relative_to(destination):
        raise RuntimeError("更新路径重叠")
    if payload.name != f"GrokUsagePet-v{update.version}-Windows-x64":
        raise RuntimeError("更新包目录与版本不匹配")
    if not (payload / "GrokUsagePet.exe").is_file() or not (payload / "_internal").is_dir():
        raise RuntimeError("更新包缺少运行文件")
    token = uuid.uuid4().hex
    ready_handle, ready_name = tempfile.mkstemp(prefix="grok-usage-pet-apply-", suffix=".ready")
    os.close(ready_handle)
    ready_path = Path(ready_name)
    ready_path.unlink()
    script = _build_apply_script(
        update,
        destination,
        wait_pid,
        restart_watcher=restart_watcher,
        token=token,
        ready_path=ready_path,
    )
    handle, name = tempfile.mkstemp(prefix="grok-usage-pet-apply-", suffix=".ps1")
    os.close(handle)
    try:
        Path(name).write_text(script, encoding="utf-8")
    except Exception:
        Path(name).unlink(missing_ok=True)
        raise
    flags = 0x00000008 | 0x08000000  # DETACHED_PROCESS | CREATE_NO_WINDOW
    try:
        process = subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", name],
            close_fds=True,
            creationflags=flags,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _wait_for_apply_preflight(process, ready_path)
    except Exception:
        try:
            if "process" in locals() and process.poll() is None:
                process.terminate()
        except Exception:
            pass
        ready_path.unlink(missing_ok=True)
        Path(name).unlink(missing_ok=True)
        raise
    ready_path.unlink(missing_ok=True)


def can_apply_inplace() -> bool:
    if not bool(getattr(sys, "frozen", False)):
        return False
    from fetch_usage import install_dir

    return (install_dir() / "GrokUsagePet.exe").is_file()
