"""Backfill Ambient Weather history into data/ambient JSONL buckets."""

import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import requests

from envfile import load_dotenv
from weather_server import (
    append_record,
    bucket_path,
    parse_timestamp,
    write_latest,
)

DEFAULT_AMBIENT = Path(__file__).resolve().parent / "data" / "ambient"
DOTENV = Path(__file__).resolve().parent / ".env"

BASE_URL = "https://api.ambientweather.net"
LIMIT = 288
WINDOW = timedelta(hours=6)
NEAR = timedelta(minutes=5)
LOOKBACK = timedelta(days=2110)
MAX_ATTEMPTS = 8
MAX_BACKOFF_SECONDS = 60
_ISO = "%Y-%m-%dT%H:%M:%SZ"


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _from_ms(ms):
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)


def _to_ms(moment):
    return int(moment.timestamp() * 1000)


def _iso(moment):
    return moment.astimezone(timezone.utc).strftime(_ISO)


def _parse_iso(text):
    return datetime.strptime(text, _ISO).replace(tzinfo=timezone.utc)


def epoch_ms(value):
    """Unix milliseconds, or None when value is not a whole-number timestamp."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def as_iso(value):
    """UTC `YYYY-MM-DDTHH:MM:SSZ`, or None when value is not a timestamp."""
    ms = epoch_ms(value)
    if ms is not None:
        return _iso(_from_ms(ms))
    if not isinstance(value, str):
        return None
    text = value.strip()
    if "." in text and text.endswith("Z"):
        text = text.split(".", 1)[0] + "Z"
    if text.endswith("+00:00"):
        text = text[: -6] + "Z"
    return parse_timestamp(text)


def clamped_end(end, now):
    """History rejects a future endDate; send UTC now instead."""
    if end > now:
        return now
    return end


def checkpoint_path(history_dir):
    return history_dir / "checkpoint"


def latest_path(history_dir):
    return history_dir / "_latest.json"


def read_checkpoint(path):
    if not path.is_file():
        return None
    return int(path.read_text(encoding="utf-8").strip())


def write_checkpoint(path, ms):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=".checkpoint-", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(str(int(ms)))
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def record_from_api(row):
    """One archive object. Absent sensors stay absent; `date` is not stored."""
    if not isinstance(row, dict):
        return None
    iso = as_iso(row.get("dateutc"))
    if iso is None:
        return None
    record = {}
    for key, value in row.items():
        if key == "date":
            continue
        if key == "dateutc":
            record["dateutc"] = iso
            continue
        if key == "lastRain" and value is not None:
            converted = as_iso(value)
            record[key] = converted if converted is not None else value
            continue
        record[key] = value
    return record


def load_stamps(path):
    stamps = set()
    if not path.is_file():
        return stamps
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            stamps.add(json.loads(line).get("dateutc"))
    return stamps


def write_latest_if_newer(history_dir, record):
    path = latest_path(history_dir)
    if path.is_file():
        current = json.loads(path.read_text(encoding="utf-8"))
        current_stamp = current.get("dateutc", "")
        if isinstance(current_stamp, str) and current_stamp >= record["dateutc"]:
            return
    write_latest(path, record)


class AmbientClient:
    """GET devices and device history. Callers sleep after a successful return."""

    def __init__(self, api_key, application_key):
        self._api_key = api_key
        self._application_key = application_key

    def _get(self, path, params):
        query = {
            "applicationKey": self._application_key,
            "apiKey": self._api_key,
        }
        query.update(params)
        response = requests.get(BASE_URL + path, params=query, timeout=60)
        response.raise_for_status()
        return response.json()

    def devices(self):
        body = self._get("/v1/devices", {})
        if not isinstance(body, list):
            raise RuntimeError("device list was not a list")
        return body

    def history(self, mac, end):
        params = {"endDate": _iso(end), "limit": str(LIMIT)}
        body = self._get("/v1/devices/" + mac, params)
        if not isinstance(body, list):
            raise RuntimeError("history was not a list")
        return body


_SECRET_QUERY = {"apikey", "applicationkey"}
_SECRET_TEXT = re.compile(r"(?i)(apiKey|applicationKey)=[^&\s\"']*")


def failure_detail(exc):
    """Status, path, and non-secret query fields. The keys stay out of the log."""
    response = getattr(exc, "response", None)
    if response is None:
        return type(exc).__name__
    parts = urlsplit(getattr(response, "url", "") or "")
    query = parse_qs(parts.query, keep_blank_values=True)
    extra = [
        f"{key}={values[0]}"
        for key, values in query.items()
        if key.lower() not in _SECRET_QUERY and values
    ]
    body = " ".join((getattr(response, "text", "") or "").split())
    body = _SECRET_TEXT.sub(r"\1=REDACTED", body)
    if len(body) > 300:
        body = body[:300] + "..."
    detail = f"HTTP {response.status_code} {response.reason} {parts.path}"
    if extra:
        detail = f"{detail} {' '.join(extra)}"
    if body:
        detail = f"{detail}: {body}"
    return detail


def call_with_retry(operation, sleep):
    """Eight tries, then a non-zero exit. Backoff is 1, 2, 4, ... seconds, cap 60."""
    delay = 1
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = operation()
        except Exception as exc:
            print(f"attempt {attempt} failed: {failure_detail(exc)}", flush=True)
            if attempt == MAX_ATTEMPTS:
                raise SystemExit(1)
            sleep(delay)
            delay = min(delay * 2, MAX_BACKOFF_SECONDS)
            continue
        sleep(1)
        return result


def select_mac(devices, wanted):
    macs = []
    for device in devices:
        if isinstance(device, dict) and device.get("macAddress"):
            macs.append(device["macAddress"])
    if wanted:
        if wanted not in macs:
            print("AMBIENT_MAC did not match a device", flush=True)
            raise SystemExit(1)
        return wanted
    if len(macs) == 1:
        return macs[0]
    print(f"{len(macs)} devices; set AMBIENT_MAC", flush=True)
    raise SystemExit(1)


def _newest_ms(rows):
    for row in rows:
        if not isinstance(row, dict):
            continue
        ms = epoch_ms(row.get("dateutc"))
        if ms is not None:
            return ms
    return None


def collect(history_dir, client, mac, now, sleep):
    """Walk forward in 6-hour windows and append rows the archive does not have."""
    path = checkpoint_path(history_dir)
    saved = read_checkpoint(path)
    if saved is None:
        cursor = now() - LOOKBACK
    else:
        cursor = _from_ms(saved)
    watermark = cursor
    # ponytail: stamp set is read once per bucket; a live push between read and
    # append can duplicate one line. A later row in that bucket still dedups.
    known = {}
    final = False
    while True:
        requested = cursor
        current = now()
        rows = call_with_retry(
            lambda requested=requested, current=current: client.history(
                mac, clamped_end(requested, current)
            ),
            sleep,
        )
        if not isinstance(rows, list):
            rows = []
        newest_ms = _newest_ms(rows)
        appended = 0
        newest_appended = None
        watermark_iso = _iso(watermark)
        for row in reversed(rows):
            record = record_from_api(row)
            if record is None:
                continue
            stamp = record["dateutc"]
            if stamp <= watermark_iso:
                continue
            bucket = bucket_path(history_dir, stamp)
            cached = known.get(bucket)
            if cached is None:
                cached = load_stamps(bucket)
                known[bucket] = cached
            if stamp in cached:
                continue
            append_record(bucket, record)
            cached.add(stamp)
            write_latest_if_newer(history_dir, record)
            appended += 1
            appended_at = _parse_iso(stamp)
            if newest_appended is None or appended_at > newest_appended:
                newest_appended = appended_at
        if newest_appended is not None and newest_appended > watermark:
            watermark = newest_appended
        if newest_ms is not None and _from_ms(newest_ms) >= requested - NEAR:
            cursor = _from_ms(newest_ms)
        write_checkpoint(path, _to_ms(watermark))
        print(
            f"{_iso(current)} end={_iso(requested)} api={len(rows)} appended={appended}",
            flush=True,
        )
        if final:
            break
        cursor = cursor + WINDOW
        if cursor + NEAR >= now():
            final = True


def run(history_dir, now=utc_now, sleep=time.sleep):
    load_dotenv(DOTENV)
    api_key = os.environ.get("AMBIENT_API_KEY", "")
    application_key = os.environ.get("AMBIENT_APPLICATION_KEY", "")

    if not api_key or not application_key:
        print(
            "AMBIENT_API_KEY and AMBIENT_APPLICATION_KEY are required", flush=True
        )
        raise SystemExit(1)
    client = AmbientClient(api_key, application_key)
    devices = call_with_retry(client.devices, sleep)
    mac = select_mac(devices, os.environ.get("AMBIENT_MAC") or None)
    print(f"collecting {mac} into {history_dir}", flush=True)
    collect(history_dir, client, mac, now, sleep)


class _FakeClient:
    def __init__(self, batches):
        self._batches = list(batches)
        self.calls = []

    def history(self, mac, end):
        self.calls.append(end)
        if not self._batches:
            return []
        return self._batches.pop(0)


def _at(text):
    return _parse_iso(text)


def _api_row(text, **extra):
    payload = {"dateutc": _to_ms(_at(text))}
    payload.update(extra)
    return payload


def _lines(history_dir, text):
    path = bucket_path(history_dir, text)
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def self_check():
    key = "DOTENV_SELF_CHECK"
    os.environ.pop(key, None)
    handle, path = tempfile.mkstemp()
    os.close(handle)
    with open(path, "w") as stream:
        stream.write(f"{key}=from-file\n# comment\n\n")
    try:
        load_dotenv(path)
        assert os.environ.get(key) == "from-file"
        os.environ[key] = "already"
        load_dotenv(path)
        assert os.environ[key] == "already"
    finally:
        os.remove(path)
        os.environ.pop(key, None)

    slept = []

    def sleep(seconds):
        slept.append(seconds)

    class _Response:
        status_code = 404
        reason = "Not Found"
        url = (
            "https://api.ambientweather.net/v1/devices/AA:BB"
            "?apiKey=secret&applicationKey=secret&endDate=1&limit=288"
        )
        text = "no device apiKey=secret"

    class _HTTPError(Exception):
        response = _Response()

    detail = failure_detail(_HTTPError())
    assert detail == (
        "HTTP 404 Not Found /v1/devices/AA:BB endDate=1 limit=288: "
        "no device apiKey=REDACTED"
    )
    assert "secret" not in detail
    assert failure_detail(RuntimeError("nope")) == "RuntimeError"

    def fail():
        raise RuntimeError("down")

    try:
        call_with_retry(fail, lambda _seconds: None)
        raise AssertionError("retry exhaustion should exit")
    except SystemExit as exc:
        assert exc.code == 1

    sent = {}
    probe = AmbientClient("k", "a")

    def fake_get(path, params):
        sent["path"] = path
        sent["params"] = params
        return []

    probe._get = fake_get
    probe.history("AA:BB", _at("2024-06-25T04:15:00Z"))
    assert sent["params"]["endDate"] == "2024-06-25T04:15:00Z"

    assert DEFAULT_AMBIENT == Path(__file__).resolve().parent / "data" / "ambient"

    now = _at("2026-10-11T15:00:00Z")
    assert clamped_end(_at("2026-10-11T20:00:00Z"), now) == now
    assert clamped_end(_at("2026-10-11T14:00:00Z"), now) == _at("2026-10-11T14:00:00Z")

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        history = root / "a" / "ambient"
        assert checkpoint_path(history) == history / "checkpoint"
        assert latest_path(history) == history / "_latest.json"
        seed = {"dateutc": "2026-10-11T14:30:00Z", "tempf": 50}
        append_record(bucket_path(history, seed["dateutc"]), seed)
        write_latest(
            latest_path(history), {"dateutc": "2026-10-11T14:10:00Z", "tempf": 40}
        )
        write_checkpoint(checkpoint_path(history), _to_ms(_at("2026-10-11T14:00:00Z")))
        kept = _api_row(
            "2026-10-11T15:00:00Z",
            tempf=61.2,
            battout=1,
            totalrainin=3.5,
            lastRain=_to_ms(_at("2026-10-11T13:00:00Z")),
            date="2026-10-11T15:00:00.000Z",
        )
        client = _FakeClient(
            [
                [_api_row("2026-10-11T14:00:00Z", tempf=48)],
                [
                    kept,
                    _api_row("2026-10-11T14:30:00Z", tempf=50),
                    _api_row("2026-10-11T14:00:00Z", tempf=48),
                ],
            ]
        )
        collect(history, client, "AA:BB", lambda: now, sleep)
        assert client.calls == [_at("2026-10-11T14:00:00Z"), now]
        records = _lines(history, "2026-10-11T15:00:00Z")
        assert [record["dateutc"] for record in records] == [
            "2026-10-11T14:30:00Z",
            "2026-10-11T15:00:00Z",
        ]
        assert set(records[-1]) == {
            "dateutc",
            "tempf",
            "battout",
            "totalrainin",
            "lastRain",
        }
        assert records[-1]["lastRain"] == "2026-10-11T13:00:00Z"
        assert records[-1]["tempf"] == 61.2
        latest = json.loads(latest_path(history).read_text(encoding="utf-8"))
        assert latest["dateutc"] == "2026-10-11T15:00:00Z"
        assert latest_path(history).parent == history
        assert read_checkpoint(checkpoint_path(history)) == _to_ms(now)
        assert checkpoint_path(history).parent == history
        assert not (history.parent / "weather.checkpoint").exists()
        assert not (history.parent / "weather-latest.json").exists()
        assert not (history / "latest.json").exists()

        write_latest(
            latest_path(history), {"dateutc": "2026-10-11T17:00:00Z", "tempf": 70}
        )
        resume = _FakeClient(
            [
                [_api_row("2026-10-11T15:00:00Z", tempf=61.2)],
                [
                    _api_row("2026-10-11T15:10:00Z", tempf=62),
                    _api_row("2026-10-11T15:00:00Z", tempf=61.2),
                ],
            ]
        )
        collect(history, resume, "AA:BB", lambda: now, sleep)
        records = _lines(history, "2026-10-11T15:00:00Z")
        assert [record["dateutc"] for record in records] == [
            "2026-10-11T14:30:00Z",
            "2026-10-11T15:00:00Z",
            "2026-10-11T15:10:00Z",
        ]
        assert resume.calls == [now, now]
        latest = json.loads(latest_path(history).read_text(encoding="utf-8"))
        assert latest["dateutc"] == "2026-10-11T17:00:00Z"
        assert read_checkpoint(checkpoint_path(history)) == _to_ms(
            _at("2026-10-11T15:10:00Z")
        )

        sparse_dir = root / "b" / "ambient"
        now2 = _at("2026-10-11T18:00:00Z")
        write_checkpoint(
            checkpoint_path(sparse_dir), _to_ms(_at("2026-10-11T06:00:00Z"))
        )
        sparse = _FakeClient(
            [
                [],
                [_api_row("2026-10-11T10:00:00Z", tempf=55)],
                [],
            ]
        )
        collect(sparse_dir, sparse, "AA:BB", lambda: now2, sleep)
        assert sparse.calls == [
            _at("2026-10-11T06:00:00Z"),
            _at("2026-10-11T12:00:00Z"),
            _at("2026-10-11T18:00:00Z"),
        ]
        morning = _lines(sparse_dir, "2026-10-11T10:00:00Z")
        assert morning == [{"dateutc": "2026-10-11T10:00:00Z", "tempf": 55}]
        assert read_checkpoint(checkpoint_path(sparse_dir)) == _to_ms(
            _at("2026-10-11T10:00:00Z")
        )
        assert checkpoint_path(sparse_dir).parent == sparse_dir
        assert latest_path(sparse_dir).parent == sparse_dir

    assert slept and all(seconds == 1 for seconds in slept)
    print("self-check ok")


def main(argv):
    if "--self-check" in argv:
        self_check()
        return 0
    args = [arg for arg in argv[1:] if not arg.startswith("--")]
    history = Path(args[0]) if args else DEFAULT_AMBIENT
    if not history.is_absolute():
        history = Path.cwd() / history
    run(history)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
