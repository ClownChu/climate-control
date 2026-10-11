"""Record Ambient Weather GET uploads into UTC 12-hour JSONL buckets."""

import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

DEFAULT_PORT = 8099
DEFAULT_HISTORY = Path(__file__).resolve().parent / "data" / "history"
_PASSKEY_LOG = re.compile(r"(?i)(PASSKEY=)[^&\s]*")
_FLOAT = re.compile(r"-?\d+\.\d+")
_INT = re.compile(r"-?\d+")
_STRING_KEYS = {"stationtype", "dateutc"}
_BUCKET_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})_(00|12)$")
_TIMESTAMP_FORMATS = ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S")


def coerce_value(value):
    """Integers and decimals become numbers; everything else stays a string."""
    if _FLOAT.fullmatch(value):
        return float(value)
    if _INT.fullmatch(value):
        return int(value)
    return value


def parse_timestamp(value):
    """UTC clock as ISO-8601 Z, or None when the text is not a timestamp."""
    text = value.strip()
    for fmt in _TIMESTAMP_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
    return None


def reading_from_query(query):
    """One flat reading. PASSKEY is dropped; dateutc is normalized to UTC."""
    pairs = parse_qs(query, keep_blank_values=True)
    reading = {}
    for key, values in pairs.items():
        if key == "PASSKEY":
            continue
        raw = values[0] if values else ""
        if key in _STRING_KEYS:
            reading[key] = raw
        else:
            reading[key] = coerce_value(raw)
    if "dateutc" not in reading:
        return None
    normalized = parse_timestamp(reading["dateutc"])
    if normalized is None:
        return None
    reading["dateutc"] = normalized
    return reading


def bucket_path(history_dir, dateutc):
    """12-hour file for a UTC timestamp. 00:00 stays in _00; 12:00 starts _12."""
    hour = int(dateutc[11:13])
    slot = "00" if hour < 12 else "12"
    return history_dir / f"{dateutc[:10]}_{slot}.jsonl"


def latest_path(history_dir):
    return history_dir.parent / "weather-latest.json"


def bucket_window(path):
    """Half-open UTC window [start, end) for a bucket filename, or None."""
    match = _BUCKET_NAME.match(path.stem)
    if match is None:
        return None
    start = datetime.strptime(
        f"{match.group(1)} {match.group(2)}:00:00", "%Y-%m-%d %H:%M:%S"
    )
    end = start + timedelta(hours=12)
    return (
        start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def append_record(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    # ponytail: one station and a single-threaded HTTPServer; no file lock.
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()


def write_latest(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".latest-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def ingest_reading(history_dir, query):
    reading = reading_from_query(query)
    if reading is None:
        return 400, {"ok": False}
    append_record(bucket_path(history_dir, reading["dateutc"]), reading)
    write_latest(latest_path(history_dir), reading)
    return 200, {"ok": True}


def overlapping_files(history_dir, start, end):
    """Bucket files whose 12-hour window overlaps [start, end]. None is open."""
    if not history_dir.is_dir():
        return []
    chosen = []
    for path in sorted(history_dir.glob("????-??-??_??.jsonl")):
        window = bucket_window(path)
        if window is None:
            continue
        file_start, file_end = window
        if end is not None and file_start > end:
            continue
        if start is not None and file_end <= start:
            continue
        chosen.append(path)
    return chosen


def project_record(record, fields):
    clean = {key: value for key, value in record.items() if key != "PASSKEY"}
    if fields is None:
        return clean
    projected = {"dateutc": clean.get("dateutc")}
    for name in fields:
        if name in ("dateutc", "PASSKEY"):
            continue
        if name in clean:
            projected[name] = clean[name]
    return projected


def query_history(history_dir, start, end, fields):
    opened = overlapping_files(history_dir, start, end)
    records = []
    for path in opened:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                stamp = record.get("dateutc", "")
                if start is not None and stamp < start:
                    continue
                if end is not None and stamp > end:
                    continue
                records.append(project_record(record, fields))
    return records, opened


def weather_response(history_dir, query):
    params = {
        key: (values[0] if values else "")
        for key, values in parse_qs(query, keep_blank_values=True).items()
    }
    start = end = None
    if params.get("from", "").strip():
        start = parse_timestamp(params["from"])
        if start is None:
            return 400, {"ok": False}
    if params.get("to", "").strip():
        end = parse_timestamp(params["to"])
        if end is None:
            return 400, {"ok": False}
    fields = None
    if "fields" in params:
        fields = [part.strip() for part in params["fields"].split(",") if part.strip()]
    if start is None and end is None:
        path = latest_path(history_dir)
        if not path.is_file():
            return 404, {"ok": False}
        record = json.loads(path.read_text(encoding="utf-8"))
        return 200, project_record(record, fields)
    records, _opened = query_history(history_dir, start, end, fields)
    return 200, {"records": records}


def redact_passkey(text):
    return _PASSKEY_LOG.sub(r"\1REDACTED", text)


class WeatherHandler(BaseHTTPRequestHandler):
    history_dir = DEFAULT_HISTORY

    def do_GET(self):
        split = urlsplit(self.path)
        if split.path in ("/data/report", "/data/report/"):
            status, payload = ingest_reading(self.history_dir, split.query)
        elif split.path == "/weather/latest":
            status, payload = weather_response(self.history_dir, "")
        elif split.path == "/weather":
            status, payload = weather_response(self.history_dir, split.query)
        else:
            status, payload = 404, {"ok": False}
        self._reply(status, payload)

    def do_POST(self):
        self._reply(404, {"ok": False})

    do_PUT = do_POST
    do_DELETE = do_POST
    do_HEAD = do_POST
    do_PATCH = do_POST
    do_OPTIONS = do_POST

    def log_message(self, fmt, *args):
        message = redact_passkey(fmt % args)
        sys.stderr.write(
            "%s - - [%s] %s\n"
            % (self.address_string(), self.log_date_time_string(), message)
        )

    def _reply(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def self_check():
    fixture = (
        "stationtype=AMBWeatherV4.3.8&PASSKEY=fake-passkey"
        "&dateutc=2026-10-11+15:10:16&tempf=61.0&humidity=99"
    )
    reading = reading_from_query(fixture)
    assert reading["tempf"] == 61.0 and isinstance(reading["tempf"], float)
    assert reading["humidity"] == 99 and isinstance(reading["humidity"], int)
    assert reading["stationtype"] == "AMBWeatherV4.3.8"
    assert reading["dateutc"] == "2026-10-11T15:10:16Z"
    assert "PASSKEY" not in reading
    logged = "GET /data/report?PASSKEY=fake-passkey&tempf=61.0 HTTP/1.1"
    assert "fake-passkey" not in redact_passkey(logged)

    with tempfile.TemporaryDirectory() as directory:
        history = Path(directory) / "history"
        assert bucket_path(history, "2026-10-11T00:00:00Z").name == "2026-10-11_00.jsonl"
        assert bucket_path(history, "2026-10-11T12:00:00Z").name == "2026-10-11_12.jsonl"

        queries = (
            "stationtype=AMBWeatherV4.3.8&PASSKEY=fake-passkey"
            "&dateutc=2026-10-11+00:10:00&tempf=50.0&humidity=80",
            "stationtype=AMBWeatherV4.3.8&PASSKEY=fake-passkey"
            "&dateutc=2026-10-11+11:40:00&tempf=55.5&humidity=90",
            "stationtype=AMBWeatherV4.3.8&PASSKEY=fake-passkey"
            "&dateutc=2026-10-11+18:00:00&tempf=70.0&humidity=40",
            fixture,
        )
        for query in queries:
            status, payload = ingest_reading(history, query)
            assert status == 200 and payload == {"ok": True}

        morning = (history / "2026-10-11_00.jsonl").read_text(encoding="utf-8")
        afternoon = (history / "2026-10-11_12.jsonl").read_text(encoding="utf-8")
        assert "2026-10-11T00:10:00Z" in morning
        assert "2026-10-11T15:10:16Z" in afternoon
        assert "fake-passkey" not in morning and "fake-passkey" not in afternoon
        assert "PASSKEY" not in morning and "PASSKEY" not in afternoon
        stored = json.loads(afternoon.strip().splitlines()[-1])
        assert stored["tempf"] == 61.0 and stored["humidity"] == 99

        latest = json.loads(latest_path(history).read_text(encoding="utf-8"))
        assert latest["dateutc"] == "2026-10-11T15:10:16Z"
        assert "PASSKEY" not in latest

        records, opened = query_history(
            history,
            "2026-10-11T11:30:00Z",
            "2026-10-11T16:00:00Z",
            ["tempf", "humidity"],
        )
        assert [path.name for path in opened] == [
            "2026-10-11_00.jsonl",
            "2026-10-11_12.jsonl",
        ]
        assert records == [
            {"dateutc": "2026-10-11T11:40:00Z", "tempf": 55.5, "humidity": 90},
            {"dateutc": "2026-10-11T15:10:16Z", "tempf": 61.0, "humidity": 99},
        ]

        _skipped, afternoon_files = query_history(
            history, "2026-10-11T13:00:00Z", "2026-10-11T14:00:00Z", None
        )
        assert [path.name for path in afternoon_files] == ["2026-10-11_12.jsonl"]

        status, payload = weather_response(history, "from=not-a-time")
        assert status == 400 and payload == {"ok": False}
        status, payload = weather_response(
            history,
            "from=2026-10-11T11:30:00Z&to=2026-10-11+16:00:00&fields=tempf,humidity",
        )
        assert status == 200 and payload == {"records": records}

    print("self-check ok")


def main(argv):
    if "--self-check" in argv:
        self_check()
        return

    args = argv[1:]
    port = int(args[0]) if args else DEFAULT_PORT
    history = Path(args[1]) if len(args) > 1 else DEFAULT_HISTORY
    if not history.is_absolute():
        history = Path.cwd() / history
    WeatherHandler.history_dir = history

    # ponytail: HTTPServer handles one request at a time, which matches one station.
    server = HTTPServer(("0.0.0.0", port), WeatherHandler)
    print(f"listening on 0.0.0.0:{port} -> {history}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main(sys.argv)
