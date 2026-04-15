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
from urllib.parse import urlparse


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
    is_unix = platform.system() != "Windows"
    dir_path = _config_dir()
    dir_path.mkdir(parents=True, exist_ok=True)
    if is_unix:
        dir_path.chmod(0o700)

    data = {"api_key": api_key}
    if base_url is not None:
        data["base_url"] = base_url

    path = _config_path()

    # Merge with existing config
    try:
        existing = json.loads(path.read_text())
        existing.update(data)
        data = existing
    except (json.JSONDecodeError, OSError):
        pass

    content = json.dumps(data, indent=2) + "\n"

    # Write with restricted permissions to avoid a world-readable window
    if is_unix:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, content.encode())
        finally:
            os.close(fd)
    else:
        path.write_text(content)

    return str(path)


def get_api_key() -> str | None:
    """Get the API key from env var or config file."""
    return load_config().get("api_key")


def is_https_or_localhost(url: str) -> bool:
    """Return True if URL uses HTTPS or targets localhost (for local dev)."""
    parsed = urlparse(url)
    if parsed.scheme == "https":
        return True
    return parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1")


def get_base_url() -> str:
    """Get the base URL from env var or config file, with a default.

    Raises ValueError if the URL is not HTTPS (except localhost for local dev).
    """
    url = load_config().get("base_url", "https://api.trydatapoint.com/data-labelling/v1")
    if not is_https_or_localhost(url):
        raise ValueError(f"base_url must use HTTPS (got {url.split('/', 3)[:3]})")
    return url
