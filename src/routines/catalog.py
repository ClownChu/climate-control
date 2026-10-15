"""Routine names, YAML paths, and the band settings the routines page edits."""

from pathlib import Path

import yaml

from src.utils.weather_store import atomic_write

ROOT = Path(__file__).resolve().parents[2]

CATALOG = (
    {
        "name": "keep_temperature_in_range",
        "file": "src/config/keep_temperature_in_range_config.yml",
        "summary": "Daily bands. Heat or off, with a 1° offset.",
    },
    {
        "name": "keep_temperature_in_range_spring",
        "file": "src/config/keep_temperature_in_range_spring_config.yml",
        "summary": "Same control, spring bands.",
    },
    {
        "name": "keep_house_from_freezing",
        "file": "src/config/keep_house_from_freezing_config.yml",
        "summary": "Freeze-protection bands.",
    },
    {
        "name": "always_heated",
        "file": "src/config/always_heated_config.yml",
        "summary": "Heat, with fan cycling from the config.",
    },
    {
        "name": "out_and_warm",
        "file": "src/config/out_and_warm_config.yml",
        "summary": "Away bands.",
    },
)

ROUTINE_NAMES = tuple(item["name"] for item in CATALOG)
_BY_NAME = {item["name"]: item for item in CATALOG}
_FAN_INTS = (
    "min_temp_gain",
    "max_temp_loss",
    "end_fan_after",
    "cycle_end_max_temp_loss",
)


def routine_path(name, root=None):
    item = _BY_NAME.get(name)
    if item is None:
        return None
    base = ROOT if root is None else root
    return Path(base) / item["file"]


def _tidy(value):
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _hour(key):
    if isinstance(key, bool):
        return None
    if isinstance(key, int):
        hour = key
    elif isinstance(key, str) and key.strip().isdigit():
        hour = int(key.strip())
    else:
        return None
    if hour < 0 or hour > 23:
        return None
    return hour


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def settings_from_payload(payload):
    """Temps and fan fields, or None when the payload cannot be stored."""
    if not isinstance(payload, dict):
        return None
    incoming = payload.get("temps")
    if not isinstance(incoming, dict) or not incoming:
        return None
    temps = {}
    for key, band in incoming.items():
        hour = _hour(key)
        if hour is None or hour in temps or not isinstance(band, dict):
            return None
        low = _number(band.get("min"))
        high = _number(band.get("max"))
        if low is None or high is None or low > high:
            return None
        temps[hour] = {"min": _tidy(low), "max": _tidy(high)}
    if not isinstance(payload.get("use_fan"), bool):
        return None
    fan = {"use_fan": payload["use_fan"]}
    for name in _FAN_INTS:
        value = payload.get(name)
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        fan[name] = value
    settings = {"temps": {hour: temps[hour] for hour in sorted(temps)}}
    settings.update(fan)
    return settings


def read_routine(name, root=None):
    path = routine_path(name, root)
    if path is None or not path.is_file():
        raise FileNotFoundError(name)
    with path.open(encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)
    if not isinstance(raw, dict) or not isinstance(raw.get("temps"), dict):
        raise ValueError(name)
    temps = {}
    for key, band in raw["temps"].items():
        hour = _hour(key)
        if hour is None or not isinstance(band, dict):
            raise ValueError(name)
        temps[str(hour)] = {"min": band["min"], "max": band["max"]}
    item = _BY_NAME[name]
    body = {
        "name": name,
        "path": item["file"],
        "summary": item["summary"],
        "temps": temps,
        "use_fan": bool(raw.get("use_fan", False)),
    }
    for field in _FAN_INTS:
        body[field] = int(raw.get(field, 0))
    return body


def write_routine(name, payload, root=None):
    """Replace one routine YAML. Returns the stored record, or None if invalid."""
    if name not in _BY_NAME:
        raise KeyError(name)
    settings = settings_from_payload(payload)
    if settings is None:
        return None
    item = _BY_NAME[name]
    text = "# " + item["summary"] + "\n" + yaml.safe_dump(
        settings, sort_keys=False, default_flow_style=False
    )
    atomic_write(routine_path(name, root), text)
    return read_routine(name, root)


def describe_routines(active, root=None):
    routines = []
    for name in ROUTINE_NAMES:
        record = read_routine(name, root)
        record["active"] = name == active
        routines.append(record)
    return routines
