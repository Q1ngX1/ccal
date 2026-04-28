import hashlib
import json
import os
import tomllib
from pathlib import Path
from typing import Any

import keyring

APP_NAME = "ccal"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME
CONFIG_FILE = CONFIG_DIR / "config.toml"
KEYRING_SERVICE = "ccal"

DEFAULT_CONFIG: dict[str, Any] = {
    "llm": {
        "provider": "openai",
        "model": "openai/gpt-4o",
    },
    "output": {
        "default": "ics",  # "ics" or "google"
    },
    "google": {
        "calendar_id": "primary",
        "credentials_path": str(CONFIG_DIR / "google_credentials.json"),
        "auth_mode": "desktop",
    },
}


def load_config() -> dict[str, Any]:
    """Load config from ~/.config/ccal/config.toml, falling back to defaults."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "rb") as f:
                user_config = tomllib.load(f)
        except tomllib.TOMLDecodeError:
            return DEFAULT_CONFIG.copy()
        # Merge with defaults
        config = DEFAULT_CONFIG.copy()
        for section, values in user_config.items():
            if section in config and isinstance(config[section], dict):
                config[section] = {**config[section], **values}
            else:
                config[section] = values
        return config
    return DEFAULT_CONFIG.copy()


def save_config(config: dict[str, Any]) -> None:
    """Save config to ~/.config/ccal/config.toml."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for section, values in config.items():
        if isinstance(values, dict):
            lines.append(f"[{section}]")
            for key, val in values.items():
                if isinstance(val, str):
                    lines.append(f"{key} = {json.dumps(val, ensure_ascii=False)}")
                elif isinstance(val, bool):
                    lines.append(f"{key} = {'true' if val else 'false'}")
                elif isinstance(val, int | float):
                    lines.append(f"{key} = {val}")
            lines.append("")
    CONFIG_FILE.write_text("\n".join(lines))


def get_api_key(provider: str) -> str | None:
    """Retrieve an API key from the system keyring."""
    return keyring.get_password(KEYRING_SERVICE, f"{provider}_api_key")


def set_api_key(provider: str, key: str) -> None:
    """Store an API key in the system keyring."""
    keyring.set_password(KEYRING_SERVICE, f"{provider}_api_key", key)


def get_google_token_path(config: dict[str, Any] | None = None) -> Path:
    """Path for cached Google OAuth token."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    cache_key = _google_token_cache_key(config)
    return CONFIG_DIR / f"google_token_{cache_key}.json"


def get_google_credentials_dir(config: dict[str, Any] | None = None) -> Path:
    """Directory containing Google OAuth client credentials."""
    if config:
        google_config = config.get("google", {})
        credentials_path = google_config.get("credentials_path")
        if credentials_path:
            return Path(credentials_path).expanduser().parent
        credentials_dir = google_config.get("credentials_dir")
        if credentials_dir:
            return Path(credentials_dir).expanduser()
    return CONFIG_DIR


def get_google_credentials_path(config: dict[str, Any] | None = None) -> Path:
    """Path for Google OAuth client credentials JSON."""
    if config:
        google_config = config.get("google", {})
        credentials_path = google_config.get("credentials_path")
        if credentials_path:
            return Path(credentials_path).expanduser()
        credentials_dir = google_config.get("credentials_dir")
        if credentials_dir:
            return Path(credentials_dir).expanduser() / "google_credentials.json"
    return CONFIG_DIR / "google_credentials.json"


def _google_token_cache_key(config: dict[str, Any] | None = None) -> str:
    """Derive a stable cache key from the selected Google credentials and auth mode."""
    credentials_path = get_google_credentials_path(config)
    auth_mode = "desktop"
    if config:
        auth_mode = config.get("google", {}).get("auth_mode", auth_mode)
    canonical_path = str(credentials_path.expanduser().resolve(strict=False))
    raw_key = f"{canonical_path}|{auth_mode}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]
