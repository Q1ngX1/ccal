"""Tests for src/config.py — config loading, saving, and keyring operations."""
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import tomllib

from src.config import (
    load_config,
    save_config,
    get_api_key,
    set_api_key,
    get_google_token_path,
    get_google_credentials_dir,
    get_google_credentials_path,
    DEFAULT_CONFIG,
    CONFIG_DIR,
)


class TestLoadConfig:
    def test_returns_defaults_when_no_file(self, tmp_path):
        fake_file = tmp_path / "config.toml"
        with patch("src.config.CONFIG_FILE", fake_file):
            config = load_config()
        assert config == DEFAULT_CONFIG
        assert config is not DEFAULT_CONFIG  # should be a copy

    def test_merges_user_config_with_defaults(self, tmp_path):
        fake_file = tmp_path / "config.toml"
        fake_file.write_text('[llm]\nprovider = "anthropic"\n')
        with patch("src.config.CONFIG_FILE", fake_file):
            config = load_config()
        assert config["llm"]["provider"] == "anthropic"
        # model from defaults still present
        assert config["llm"]["model"] == DEFAULT_CONFIG["llm"]["model"]

    def test_preserves_extra_sections(self, tmp_path):
        fake_file = tmp_path / "config.toml"
        fake_file.write_text('[apple]\ncalendar_name = "Work"\n')
        with patch("src.config.CONFIG_FILE", fake_file):
            config = load_config()
        assert config["apple"]["calendar_name"] == "Work"

    def test_invalid_toml_falls_back_to_defaults(self, tmp_path):
        fake_file = tmp_path / "config.toml"
        fake_file.write_text('google = "C:\\Users\\test\\google_credentials.json"')
        with patch("src.config.CONFIG_FILE", fake_file):
            config = load_config()
        assert config["google"]["calendar_id"] == DEFAULT_CONFIG["google"]["calendar_id"]


class TestSaveConfig:
    def test_saves_and_reloads(self, tmp_path):
        fake_dir = tmp_path / "ccal"
        fake_file = fake_dir / "config.toml"
        config = {
            "llm": {"provider": "anthropic", "model": "anthropic/claude-sonnet-4-20250514"},
            "output": {"default": "google"},
        }
        with patch("src.config.CONFIG_DIR", fake_dir), patch("src.config.CONFIG_FILE", fake_file):
            save_config(config)
            assert fake_file.exists()
            loaded = load_config()
        assert loaded["llm"]["provider"] == "anthropic"
        assert loaded["output"]["default"] == "google"

    def test_handles_bool_and_int(self, tmp_path):
        fake_dir = tmp_path / "ccal"
        fake_file = fake_dir / "config.toml"
        config = {"test": {"flag": True, "count": 42}}
        with patch("src.config.CONFIG_DIR", fake_dir), patch("src.config.CONFIG_FILE", fake_file):
            save_config(config)
            content = fake_file.read_text()
        assert "flag = true" in content
        assert "count = 42" in content

    def test_escapes_windows_paths(self, tmp_path):
        fake_dir = tmp_path / "ccal"
        fake_file = fake_dir / "config.toml"
        path = r"C:\Users\zansh\Code\ccal\google_credentials.json"
        config = {"google": {"credentials_path": path, "calendar_id": "primary"}}
        with patch("src.config.CONFIG_DIR", fake_dir), patch("src.config.CONFIG_FILE", fake_file):
            save_config(config)
            content = fake_file.read_text()
        assert 'credentials_path = "C:\\\\Users\\\\zansh\\\\Code\\\\ccal\\\\google_credentials.json"' in content
        parsed = tomllib.loads(content)
        assert parsed["google"]["credentials_path"] == path


class TestApiKey:
    def test_get_api_key(self):
        with patch("src.config.keyring.get_password", return_value="sk-test-123") as mock_get:
            key = get_api_key("openai")
            mock_get.assert_called_once_with("ccal", "openai_api_key")
            assert key == "sk-test-123"

    def test_get_api_key_not_found(self):
        with patch("src.config.keyring.get_password", return_value=None):
            assert get_api_key("nonexistent") is None

    def test_set_api_key(self):
        with patch("src.config.keyring.set_password") as mock_set:
            set_api_key("openai", "sk-new-key")
            mock_set.assert_called_once_with("ccal", "openai_api_key", "sk-new-key")


class TestGooglePaths:
    def test_google_token_path(self, tmp_path):
        fake_dir = tmp_path / "ccal"
        with patch("src.config.CONFIG_DIR", fake_dir):
            path = get_google_token_path()
        assert path.parent == fake_dir
        assert path.name.startswith("google_token_")
        assert fake_dir.exists()  # should create dir

    def test_google_credentials_path(self):
        path = get_google_credentials_path()
        assert path.name == "google_credentials.json"
        assert str(path).endswith("ccal/google_credentials.json")

    def test_google_credentials_path_uses_config_path(self, tmp_path):
        config = {"google": {"credentials_path": str(tmp_path / "creds.json")}}
        path = get_google_credentials_path(config)
        assert path == tmp_path / "creds.json"

    def test_google_credentials_path_uses_config_dir(self, tmp_path):
        config = {"google": {"credentials_dir": str(tmp_path / "custom-google")}}
        path = get_google_credentials_path(config)
        assert path == tmp_path / "custom-google" / "google_credentials.json"

    def test_google_credentials_dir_default(self):
        assert get_google_credentials_dir() == CONFIG_DIR
