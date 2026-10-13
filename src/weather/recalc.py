"""Rewrite station JSONL buckets with dew point, feels-like, and last rain."""

import json
import sys
import tempfile
from pathlib import Path

from src.utils.weather_calc import apply_derived
from src.utils.weather_config import DEFAULT_HISTORY
from src.utils.weather_store import atomic_write, latest_path, write_latest

_BUCKETS = "????-??-??_??.jsonl"


def _dump(record):
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"))


def recalculate(station_dir):
    """Recompute derived keys in name order. `_latest.json` follows the newest dateutc."""
    # ponytail: no file lock. An upload during the replace can be dropped.
    # Re-run this command. Upgrade path: lock the bucket for the replace.
    previous = None
    newest = None
    for path in sorted(station_dir.glob(_BUCKETS)):
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            apply_derived(record, previous)
            previous = record
            stamp = record.get("dateutc", "")
            if newest is None or stamp >= newest.get("dateutc", ""):
                newest = record
            rows.append(_dump(record))
        atomic_write(path, "".join(row + "\n" for row in rows))
    if newest is not None:
        write_latest(latest_path(station_dir), newest)
    return newest


def _write_bucket(path, records):
    path.write_text("".join(_dump(record) + "\n" for record in records), encoding="utf-8")


def self_check():
    with tempfile.TemporaryDirectory() as directory:
        station = Path(directory)
        _write_bucket(
            station / "2026-10-12_00.jsonl",
            [
                {
                    "stationtype": "AMBWeatherV4.3.8",
                    "dateutc": "2026-10-12T11:00:20Z",
                    "tempf": 64.4,
                    "humidity": 76,
                    "tempinf": 67.8,
                    "humidityin": 68,
                    "hourlyrainin": 0.01,
                },
                {
                    "dateutc": "2026-10-12T18:00:00Z",
                    "tempf": 60.0,
                    "humidity": 0,
                    "hourlyrainin": 0,
                },
            ],
        )
        _write_bucket(
            station / "2026-10-12_12.jsonl",
            [
                {
                    "dateutc": "2026-10-12T12:10:00Z",
                    "tempf": 68.4,
                    "humidity": 35,
                    "windspeedmph": 0,
                    "hourlyrainin": 0,
                },
                {
                    "dateutc": "2026-10-12T10:00:00Z",
                    "tempf": 43.9,
                    "humidity": 50,
                    "windspeedmph": 4,
                    "hourlyrainin": 0.02,
                },
            ],
        )
        write_latest(
            latest_path(station),
            {"dateutc": "2099-01-01T00:00:00Z", "tempf": 1},
        )
        recalculate(station)

        morning = [
            json.loads(line)
            for line in (station / "2026-10-12_00.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        afternoon = [
            json.loads(line)
            for line in (station / "2026-10-12_12.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        calm, dry_gap = morning
        warm, chill = afternoon
        assert calm["stationtype"] == "AMBWeatherV4.3.8"
        assert calm["feelsLike"] == 64.4
        assert calm["dewPoint"] == 56.66
        assert calm["feelsLikein"] == 67.8
        assert calm["dewPointin"] == 56.8
        assert calm["lastRain"] == "2026-10-12T11:00:00Z"
        assert dry_gap["feelsLike"] == 60.0
        assert "dewPoint" not in dry_gap
        assert dry_gap["lastRain"] == "2026-10-12T11:00:00Z"
        assert warm["feelsLike"] == 66.59
        assert warm["lastRain"] == "2026-10-12T11:00:00Z"
        assert chill["feelsLike"] == 41.82
        assert chill["lastRain"] == "2026-10-12T11:00:00Z"
        latest = json.loads(latest_path(station).read_text(encoding="utf-8"))
        assert latest["dateutc"] == "2026-10-12T18:00:00Z"
        assert latest["feelsLike"] == 60.0
        assert latest["lastRain"] == "2026-10-12T11:00:00Z"

        before = {
            path.name: path.read_bytes()
            for path in sorted(station.iterdir())
            if path.is_file()
        }
        recalculate(station)
        after = {
            path.name: path.read_bytes()
            for path in sorted(station.iterdir())
            if path.is_file()
        }
        assert before == after
    print("self-check ok")


def main(argv):
    if "--self-check" in argv:
        self_check()
        return 0
    args = [arg for arg in argv[1:] if not arg.startswith("--")]
    station = Path(args[0]) if args else DEFAULT_HISTORY
    if not station.is_absolute():
        station = Path.cwd() / station
    recalculate(station)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
