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
    },
}


def load_config() -> dict[str, Any]:
    """Load config from ~/.config/ccal/config.toml, falling back to defaults."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "rb") as f:
            user_config = tomllib.load(f)
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
                    lines.append(f'{key} = "{val}"')
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


def get_google_token_path() -> Path:
    """Path for cached Google OAuth token."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR / "google_token.json"


def get_google_credentials_path() -> Path:
    """Path for Google OAuth client credentials."""
    return CONFIG_DIR / "google_credentials.json"
