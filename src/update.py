from __future__ import annotations

import importlib.metadata
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from src.config import CONFIG_DIR


DEFAULT_REPO = os.environ.get("CCAL_REPO", "Q1ngX1/ccal")


class UpdateError(RuntimeError):
    """Raised when ccal cannot update itself."""


def update_latest(repo: str = DEFAULT_REPO) -> str:
    """Download and install the latest standalone release for this platform."""
    if not getattr(sys, "frozen", False):
        raise UpdateError("ccal update is available for standalone builds only.")

    release = fetch_latest_release(repo)
    latest_tag = normalize_version(str(release.get("tag_name") or release.get("name") or ""))
    current_tag = normalize_version(current_version())

    if current_tag and current_tag == latest_tag:
        return f"ccal {current_tag} is already up to date."

    platform_key = detect_platform_key()
    asset = select_release_asset(release.get("assets", []), platform_key)
    if not asset:
        raise UpdateError("No release asset found for this platform.")

    download_dir = Path(tempfile.mkdtemp(prefix="ccal-update-"))
    downloaded = download_dir / str(asset["name"])
    download_file(str(asset["browser_download_url"]), downloaded)

    target = Path(sys.executable).resolve()
    if is_windows():
        schedule_windows_swap(downloaded, target)
        return f"Downloaded {latest_tag}. It will replace {target.name} after ccal exits."

    try:
        os.replace(downloaded, target)
        try:
            os.chmod(target, 0o755)
        except OSError:
            pass
        return f"Updated ccal to {latest_tag}."
    finally:
        shutil.rmtree(download_dir, ignore_errors=True)


def uninstall_current(purge: bool = False) -> str:
    """Remove the current standalone executable, optionally purging config."""
    if not getattr(sys, "frozen", False):
        raise UpdateError("ccal uninstall is available for standalone builds only.")

    target = Path(sys.executable).resolve()
    if is_windows():
        schedule_windows_uninstall(target, CONFIG_DIR if purge else None)
        return f"Uninstall scheduled for {target.name}."

    try:
        target.unlink(missing_ok=True)
        if purge:
            shutil.rmtree(CONFIG_DIR, ignore_errors=True)
        return f"Removed {target.name}."
    except OSError as exc:
        raise UpdateError(f"Failed to uninstall ccal: {exc}") from None


def current_version() -> str | None:
    """Return the installed package version when available."""
    try:
        return importlib.metadata.version("ccal")
    except importlib.metadata.PackageNotFoundError:
        return None


def fetch_latest_release(repo: str) -> dict[str, Any]:
    """Fetch the latest GitHub release metadata."""
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("CCAL_GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest", headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            import json

            return json.load(response)
    except urllib.error.URLError as exc:
        raise UpdateError(f"Failed to fetch latest release: {exc}") from None


def detect_platform_key() -> tuple[str, str]:
    """Return the current OS/architecture tuple used to select a release asset."""
    os_name = platform.system().lower()
    machine = platform.machine().lower()

    if os_name.startswith("win"):
        return ("windows", normalize_arch(machine))
    if os_name == "darwin":
        return ("macos", normalize_arch(machine))
    if os_name == "linux":
        return ("linux", normalize_arch(machine))

    raise UpdateError(f"Unsupported platform: {platform.system()}")


def normalize_arch(machine: str) -> str:
    if machine in {"x86_64", "amd64"}:
        return "x64"
    if machine in {"arm64", "aarch64"}:
        return "arm64"
    raise UpdateError(f"Unsupported architecture: {machine}")


def normalize_version(value: str | None) -> str:
    if not value:
        return ""
    return value[1:] if value.startswith("v") else value


def select_release_asset(assets: list[dict[str, Any]] | Any, platform_key: tuple[str, str]) -> dict[str, Any] | None:
    """Choose the best release asset for the current platform."""
    os_name, arch = platform_key
    candidates = asset_candidates(os_name, arch)
    for candidate in candidates:
        for asset in assets:
            if asset.get("name") == candidate:
                return asset
    return None


def asset_candidates(os_name: str, arch: str) -> list[str]:
    if os_name == "windows":
        return [f"ccal-windows-{arch}.exe", f"ccal-windows-{arch}"]
    if os_name == "linux":
        if arch == "x64":
            return ["ccal-linux-x64", "ccal-linux-x86_64", "ccal-linux"]
        return ["ccal-linux-arm64", "ccal-linux-aarch64", "ccal-linux"]
    if os_name == "macos":
        if arch == "x64":
            return ["ccal-macos-x86_64", "ccal-macos-x64", "ccal-macos"]
        return ["ccal-macos-arm64", "ccal-macos-aarch64", "ccal-macos"]
    raise UpdateError(f"Unsupported platform: {os_name}")


def download_file(url: str, destination: Path) -> None:
    """Download a release asset to a local path."""
    request = urllib.request.Request(url, headers={"User-Agent": "ccal-update"})
    try:
        with urllib.request.urlopen(request) as response, open(destination, "wb") as output:
            shutil.copyfileobj(response, output)
    except urllib.error.URLError as exc:
        raise UpdateError(f"Failed to download release asset: {exc}") from None


def schedule_windows_swap(source: Path, target: Path) -> None:
    """Replace the running Windows executable after the current process exits."""
    script = f"""
$ccalPid = {os.getpid()}
$source = '{_ps_quote(str(source))}'
$target = '{_ps_quote(str(target))}'
$parent = Split-Path -Parent $source
while (Get-Process -Id $ccalPid -ErrorAction SilentlyContinue) {{
    Start-Sleep -Milliseconds 300
}}
Copy-Item -Force -LiteralPath $source -Destination $target
Remove-Item -Force -LiteralPath $source -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force -LiteralPath $parent -ErrorAction SilentlyContinue
"""
    try:
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-WindowStyle",
                "Hidden",
                "-Command",
                script,
            ],
            close_fds=True,
        )
    except FileNotFoundError as exc:
        raise UpdateError("PowerShell is required to update ccal on Windows.") from exc


def schedule_windows_uninstall(target: Path, config_dir: Path | None = None) -> None:
    """Remove the current Windows executable after the current process exits."""
    config_line = ""
    if config_dir is not None:
        config_line = f"Remove-Item -Recurse -Force -LiteralPath '{_ps_quote(str(config_dir))}' -ErrorAction SilentlyContinue"

    script = f"""
$ccalPid = {os.getpid()}
$target = '{_ps_quote(str(target))}'
while (Get-Process -Id $ccalPid -ErrorAction SilentlyContinue) {{
    Start-Sleep -Milliseconds 300
}}
Remove-Item -Force -LiteralPath $target -ErrorAction SilentlyContinue
{config_line}
"""
    try:
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-WindowStyle",
                "Hidden",
                "-Command",
                script,
            ],
            close_fds=True,
        )
    except FileNotFoundError as exc:
        raise UpdateError("PowerShell is required to uninstall ccal on Windows.") from exc


def is_windows() -> bool:
    return platform.system().lower().startswith("win")


def _ps_quote(value: str) -> str:
    return value.replace("'", "''")
