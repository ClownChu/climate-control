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


def save_app_config(data):
    atomic_write(APP_CONFIG, json.dumps(data, indent=2) + "\n")


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


def control_identity():
    """Device id and routine the control process was configured to run."""
    data = load_app_config()
    device_id = data.get("device_id")
    routine = data.get("routine")
    if not isinstance(device_id, str) or not isinstance(routine, str):
        raise ValueError("device_id and routine are required")
    return device_id.strip(), routine.strip()


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
