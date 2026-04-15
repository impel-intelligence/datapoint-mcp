"""Config file management for the Datapoint MCP server.

Stores the API key and base URL in a local config file with
restricted permissions (0600). Supports environment variable overrides.

Locations:
  Unix:    ~/.config/datapoint/config.json
  Windows: %APPDATA%/datapoint/config.json
"""

import json
import os
import platform
import stat
from pathlib import Path


def _config_dir() -> Path:
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
    else:
        base = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return Path(base) / "datapoint"


def _config_path() -> Path:
    return _config_dir() / "config.json"


def load_config() -> dict:
    """Load config, with env var overrides taking precedence."""
    config = {}

    path = _config_path()
    if path.exists():
        try:
            config = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    # Env var overrides
    if os.environ.get("DATAPOINT_API_KEY"):
        config["api_key"] = os.environ["DATAPOINT_API_KEY"]
    if os.environ.get("DATAPOINT_BASE_URL"):
        config["base_url"] = os.environ["DATAPOINT_BASE_URL"]

    return config


def save_config(api_key: str, base_url: str | None = None) -> str:
    """Save API key to config file with restricted permissions. Returns the path."""
    dir_path = _config_dir()
    dir_path.mkdir(parents=True, exist_ok=True)

    data = {"api_key": api_key}
    if base_url:
        data["base_url"] = base_url

    path = _config_path()

    # Merge with existing config
    if path.exists():
        try:
            existing = json.loads(path.read_text())
            existing.update(data)
            data = existing
        except (json.JSONDecodeError, OSError):
            pass

    path.write_text(json.dumps(data, indent=2) + "\n")

    # Set file permissions to owner-only (Unix)
    if platform.system() != "Windows":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600

    return str(path)


def get_api_key() -> str | None:
    """Get the API key from env var or config file."""
    return load_config().get("api_key")


def is_https_or_localhost(url: str) -> bool:
    """Return True if URL uses HTTPS or targets localhost (for local dev)."""
    return url.startswith("https://") or url.startswith("http://localhost")


def get_base_url() -> str:
    """Get the base URL from env var or config file, with a default.

    Raises ValueError if the URL is not HTTPS (except localhost for local dev).
    """
    url = load_config().get("base_url", "https://api.trydatapoint.com/data-labelling/v1")
    if not is_https_or_localhost(url):
        raise ValueError(f"base_url must use HTTPS (got {url.split('/', 3)[:3]})")
    return url
