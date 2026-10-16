"""Load app_config.json. Data paths resolve from the repo root."""

import json
from datetime import timedelta
from pathlib import Path

from src.routines.catalog import ROUTINE_NAMES
from src.utils.weather_store import atomic_write

_FILE = Path(__file__).resolve()
ROOT = _FILE.parents[2]
APP_CONFIG = _FILE.parents[1] / "config" / "app_config.json"


def load_app_config():
    with APP_CONFIG.open(encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict):
        raise ValueError("app config must be an object")
    return data


_SECRET_KEYS = {"client_secret", "CLIENT_SECRET"}


def save_app_config(data):
    clean = {key: value for key, value in data.items() if key not in _SECRET_KEYS}
    atomic_write(APP_CONFIG, json.dumps(clean, indent=2) + "\n")


def update_app_config(changes):
    data = load_app_config()
    data.update(changes)
    save_app_config(data)
    return data


def _nonnegative_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def weather_history_interval():
    """Seconds between history passes. Re-read so a dashboard save applies next pass."""
    value = load_app_config()["weather_history_interval"]
    if not _nonnegative_int(value):
        raise ValueError("weather_history_interval must be a non-negative integer")
    return value


def _required_text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name + " is required")
    return value.strip()


def control_identity():
    """Device id and routine the control process was configured to run."""
    data = load_app_config()
    device_id = data.get("device_id")
    routine = data.get("routine")
    if not isinstance(device_id, str) or not isinstance(routine, str):
        raise ValueError("device_id and routine are required")
    return device_id.strip(), routine.strip()


def sensi_settings():
    """Sensi connection values that are safe to store. The client secret is not here."""
    data = load_app_config()
    return {
        "oauth_url": _required_text(data.get("oauth_url"), "oauth_url"),
        "ws_url": _required_text(data.get("ws_url"), "ws_url"),
        "client_id": _required_text(data.get("client_id"), "client_id"),
    }


def set_sensi_settings(oauth_url, ws_url, client_id):
    cleaned = {
        "oauth_url": _required_text(oauth_url, "oauth_url"),
        "ws_url": _required_text(ws_url, "ws_url"),
        "client_id": _required_text(client_id, "client_id"),
    }
    update_app_config(cleaned)
    return cleaned


def control_fingerprint():
    """Values that should restart thermostat control when they change."""
    device_id, routine = control_identity()
    sensi = sensi_settings()
    return (device_id, routine, sensi["oauth_url"], sensi["ws_url"], sensi["client_id"])


def set_weather_history_interval(value):
    if not _nonnegative_int(value):
        raise ValueError("weather_history_interval must be a non-negative integer")
    update_app_config({"weather_history_interval": value})
    return value


def set_device_id(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("device_id is required")
    cleaned = value.strip()
    update_app_config({"device_id": cleaned})
    return cleaned


def set_routine(name):
    if name not in ROUTINE_NAMES:
        raise ValueError("unknown routine")
    update_app_config({"routine": name})
    return name


def _repo_path(value):
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT / path


_CONFIG = load_app_config()
BASE_URL = _CONFIG["base_url"]
LIMIT = int(_CONFIG["history_limit"])
WINDOW = timedelta(hours=int(_CONFIG["window_hours"]))
NEAR = timedelta(minutes=int(_CONFIG["near_minutes"]))
LOOKBACK = timedelta(days=int(_CONFIG["lookback_days"]))
MAX_ATTEMPTS = int(_CONFIG["max_attempts"])
MAX_BACKOFF_SECONDS = int(_CONFIG["max_backoff_seconds"])
DEFAULT_PORT = int(_CONFIG["port"])
DEFAULT_HISTORY = _repo_path(_CONFIG["history_dir"])
DEFAULT_AMBIENT = _repo_path(_CONFIG["ambient_dir"])
DOTENV = ROOT / ".env"
