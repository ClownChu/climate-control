"""Load weather_config.yml once. Data paths resolve from the repo root."""

from datetime import timedelta
from pathlib import Path

import yaml

_FILE = Path(__file__).resolve()
ROOT = _FILE.parents[2]

with open(_FILE.parents[1] / "config" / "weather_config.yml") as stream:
    CONFIG = yaml.safe_load(stream)


def _repo_path(value):
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT / path


BASE_URL = CONFIG["base_url"]
LIMIT = int(CONFIG["history_limit"])
WINDOW = timedelta(hours=int(CONFIG["window_hours"]))
NEAR = timedelta(minutes=int(CONFIG["near_minutes"]))
LOOKBACK = timedelta(days=int(CONFIG["lookback_days"]))
MAX_ATTEMPTS = int(CONFIG["max_attempts"])
MAX_BACKOFF_SECONDS = int(CONFIG["max_backoff_seconds"])
DEFAULT_PORT = int(CONFIG["port"])
DEFAULT_INTERVAL = int(CONFIG["default_interval"])
DEFAULT_HISTORY = _repo_path(CONFIG["history_dir"])
DEFAULT_AMBIENT = _repo_path(CONFIG["ambient_dir"])
DOTENV = ROOT / ".env"
