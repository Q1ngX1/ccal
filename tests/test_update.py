from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.update import (
    UpdateError,
    asset_candidates,
    normalize_version,
    select_release_asset,
    uninstall_current,
    update_latest,
)


class TestAssetSelection:
    def test_asset_candidates_windows(self):
        assert asset_candidates("windows", "x64") == ["ccal-windows-x64.exe", "ccal-windows-x64"]

    def test_asset_candidates_linux(self):
        assert asset_candidates("linux", "x64") == ["ccal-linux-x64", "ccal-linux-x86_64", "ccal-linux"]

    def test_select_release_asset(self):
        assets = [
            {"name": "ccal-linux-x64", "browser_download_url": "https://example.com/linux"},
            {"name": "ccal-windows-x64.exe", "browser_download_url": "https://example.com/windows"},
        ]
        asset = select_release_asset(assets, ("windows", "x64"))
        assert asset and asset["name"] == "ccal-windows-x64.exe"


class TestVersionHelpers:
    def test_normalize_version(self):
        assert normalize_version("v0.1.10") == "0.1.10"
        assert normalize_version("0.1.10") == "0.1.10"


class TestUpdateLatest:
    def test_update_requires_frozen_build(self):
        with pytest.raises(UpdateError, match="standalone builds only"):
            update_latest()

    def test_update_noop_when_same_version(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.update.sys.frozen", True, raising=False)
        monkeypatch.setattr("src.update.sys.executable", str(tmp_path / "ccal"), raising=False)
        monkeypatch.setattr("src.update.platform.system", lambda: "Linux")
        monkeypatch.setattr("src.update.platform.machine", lambda: "x86_64")
        with (
            patch("src.update.current_version", return_value="0.1.10"),
            patch(
                "src.update.fetch_latest_release",
                return_value={
                    "tag_name": "v0.1.10",
                    "assets": [{"name": "ccal-linux-x64", "browser_download_url": "https://example.com/linux"}],
                },
            ),
        ):
            message = update_latest()
        assert "already up to date" in message

    def test_update_replaces_unix_binary(self, tmp_path, monkeypatch):
        target = tmp_path / "ccal"
        target.write_text("old")
        monkeypatch.setattr("src.update.sys.frozen", True, raising=False)
        monkeypatch.setattr("src.update.sys.executable", str(target), raising=False)
        monkeypatch.setattr("src.update.platform.system", lambda: "Linux")
        monkeypatch.setattr("src.update.platform.machine", lambda: "x86_64")

        def fake_download(url: str, destination: Path) -> None:
            destination.write_text("new")

        with (
            patch("src.update.current_version", return_value="0.1.9"),
            patch(
                "src.update.fetch_latest_release",
                return_value={
                    "tag_name": "v0.1.10",
                    "assets": [{"name": "ccal-linux-x64", "browser_download_url": "https://example.com/linux"}],
                },
            ),
            patch("src.update.download_file", side_effect=fake_download),
            patch("src.update.os.replace") as mock_replace,
            patch("src.update.os.chmod") as mock_chmod,
        ):
            message = update_latest()

        assert "Updated ccal to 0.1.10." in message
        mock_replace.assert_called_once()
        mock_chmod.assert_called_once()

    def test_update_windows_schedules_swap(self, tmp_path, monkeypatch):
        target = tmp_path / "ccal.exe"
        target.write_text("old")
        monkeypatch.setattr("src.update.sys.frozen", True, raising=False)
        monkeypatch.setattr("src.update.sys.executable", str(target), raising=False)
        monkeypatch.setattr("src.update.platform.system", lambda: "Windows")
        monkeypatch.setattr("src.update.platform.machine", lambda: "AMD64")

        def fake_download(url: str, destination: Path) -> None:
            destination.write_text("new")

        with (
            patch("src.update.current_version", return_value="0.1.9"),
            patch(
                "src.update.fetch_latest_release",
                return_value={
                    "tag_name": "v0.1.10",
                    "assets": [{"name": "ccal-windows-x64.exe", "browser_download_url": "https://example.com/windows"}],
                },
            ),
            patch("src.update.download_file", side_effect=fake_download),
            patch("src.update.subprocess.Popen") as mock_popen,
        ):
            message = update_latest()

        assert "It will replace" in message
        mock_popen.assert_called_once()


class TestUninstallCurrent:
    def test_uninstall_requires_frozen_build(self):
        with pytest.raises(UpdateError, match="standalone builds only"):
            uninstall_current()

    def test_uninstall_removes_unix_binary_and_config(self, tmp_path, monkeypatch):
        target = tmp_path / "ccal"
        target.write_text("binary")
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        monkeypatch.setattr("src.update.sys.frozen", True, raising=False)
        monkeypatch.setattr("src.update.sys.executable", str(target), raising=False)
        monkeypatch.setattr("src.update.platform.system", lambda: "Linux")
        monkeypatch.setattr("src.update.CONFIG_DIR", config_dir)

        with (
            patch("src.update.Path.unlink") as mock_unlink,
            patch("src.update.shutil.rmtree") as mock_rmtree,
        ):
            message = uninstall_current(purge=True)

        assert "Removed" in message
        mock_unlink.assert_called_once_with(missing_ok=True)
        mock_rmtree.assert_called_once_with(config_dir, ignore_errors=True)

    def test_uninstall_windows_schedules_removal(self, tmp_path, monkeypatch):
        target = tmp_path / "ccal.exe"
        target.write_text("binary")
        config_dir = tmp_path / "config"
        monkeypatch.setattr("src.update.sys.frozen", True, raising=False)
        monkeypatch.setattr("src.update.sys.executable", str(target), raising=False)
        monkeypatch.setattr("src.update.platform.system", lambda: "Windows")
        monkeypatch.setattr("src.update.CONFIG_DIR", config_dir)

        with patch("src.update.schedule_windows_uninstall") as mock_schedule:
            message = uninstall_current(purge=True)

        assert "Uninstall scheduled" in message
        mock_schedule.assert_called_once_with(target.resolve(), config_dir)
