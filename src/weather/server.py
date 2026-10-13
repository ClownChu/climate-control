"""Record Ambient Weather GET uploads into UTC 12-hour JSONL buckets."""

import io
import json
import logging
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from src.utils.log import LOG_NAMES, configure_logging, service_logs
from src.utils.weather_config import DEFAULT_HISTORY, DEFAULT_PORT
from src.utils.weather_store import (
    append_record,
    bucket_path,
    latest_path,
    parse_timestamp,
    project_record,
    query_history,
    write_latest,
)

# python -m sets __name__ to __main__; the spec keeps src.weather.server.
LOG = logging.getLogger(__spec__.name if __spec__ is not None else __name__)
_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_PAGE = _ROOT / "dashboard.html"
DASHBOARD_SCRIPT = _ROOT / "dashboard.js"
SERVICES_PAGE = _ROOT / "services.html"
SERVICES_SCRIPT = _ROOT / "services.js"
_CHART_FIELDS = (
    "tempf",
    "tempinf",
    "humidity",
    "humidityin",
    "windspeedmph",
    "windgustmph",
    "hourlyrainin",
    "dailyrainin",
    "baromrelin",
    "solarradiation",
    "uv",
)
_SERIES_LIMIT = 1500
_PASSKEY_LOG = re.compile(r"(?i)(PASSKEY=)[^&\s]*")
_FLOAT = re.compile(r"-?\d+\.\d+")
_INT = re.compile(r"-?\d+")
_STRING_KEYS = {"stationtype", "dateutc"}


def coerce_value(value):
    """Integers and decimals become numbers; everything else stays a string."""
    if _FLOAT.fullmatch(value):
        return float(value)
    if _INT.fullmatch(value):
        return int(value)
    return value


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


def ingest_reading(history_dir, query):
    reading = reading_from_query(query)
    if reading is None:
        return 400, {"ok": False}
    append_record(bucket_path(history_dir, reading["dateutc"]), reading)
    write_latest(latest_path(history_dir), reading)
    return 200, {"ok": True}


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


def historical_dir(station_dir):
    return station_dir.parent / "historical"


def stride_series(records, limit=_SERIES_LIMIT):
    total = len(records)
    if total <= limit:
        return records, 1
    # ponytail: even stride hides spikes such as gusts; dragging a shorter
    # interval refetches that window at full resolution. Upgrade path: min/max
    # buckets per stride.
    slots = limit - 2
    step = max(2, (total - 2 + slots - 1) // slots)
    chosen = [records[0]]
    index = step
    last = total - 1
    while index < last and len(chosen) < limit - 1:
        chosen.append(records[index])
        index += step
    chosen.append(records[last])
    return chosen, step


def read_snapshot(path):
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def dashboard_series(history_dir, query, now=None):
    """One source over [from, to]. Missing ends are the last 24 hours."""
    params = {
        key: (values[0] if values else "")
        for key, values in parse_qs(query, keep_blank_values=True).items()
    }
    source = (params.get("source") or "historical").strip() or "historical"
    if source == "historical":
        folder = historical_dir(history_dir)
    elif source == "station":
        folder = history_dir
    else:
        return 400, {"ok": False}
    snapshot = latest_path(folder)

    clock = now if now is not None else datetime.now(timezone.utc).replace(tzinfo=None)
    default_to = clock.strftime("%Y-%m-%dT%H:%M:%SZ")
    default_from = (clock - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw_from = params.get("from", "").strip()
    raw_to = params.get("to", "").strip()
    start = parse_timestamp(raw_from) if raw_from else default_from
    end = parse_timestamp(raw_to) if raw_to else default_to
    if start is None or end is None or start > end:
        return 400, {"ok": False}

    records, _opened = query_history(folder, start, end, _CHART_FIELDS)
    total = len(records)
    records, step = stride_series(records)
    latest = read_snapshot(snapshot)
    return 200, {
        "source": source,
        "from": start,
        "to": end,
        "step": step,
        "total": total,
        "latest": project_record(latest, _CHART_FIELDS) if latest else None,
        "records": records,
    }


def redact_passkey(text):
    return _PASSKEY_LOG.sub(r"\1REDACTED", text)


class WeatherHandler(BaseHTTPRequestHandler):
    history_dir = DEFAULT_HISTORY

    def do_GET(self):
        split = urlsplit(self.path)
        if split.path == "/dashboard":
            self._reply_bytes(
                200, "text/html; charset=utf-8", DASHBOARD_PAGE.read_bytes()
            )
            return
        if split.path == "/dashboard.js":
            self._reply_bytes(
                200, "text/javascript; charset=utf-8", DASHBOARD_SCRIPT.read_bytes()
            )
            return
        if split.path == "/services":
            self._reply_bytes(
                200, "text/html; charset=utf-8", SERVICES_PAGE.read_bytes()
            )
            return
        if split.path == "/services.js":
            self._reply_bytes(
                200, "text/javascript; charset=utf-8", SERVICES_SCRIPT.read_bytes()
            )
            return
        if split.path == "/services/logs":
            self._reply(200, service_logs())
            return
        if split.path in ("/data/report", "/data/report/"):
            status, payload = ingest_reading(self.history_dir, split.query)
        elif split.path == "/weather/latest":
            status, payload = weather_response(self.history_dir, "")
        elif split.path == "/weather":
            status, payload = weather_response(self.history_dir, split.query)
        elif split.path == "/dashboard/series":
            status, payload = dashboard_series(self.history_dir, split.query)
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
        LOG.info("%s", redact_passkey(fmt % args))

    def _reply(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _reply_bytes(self, status, content_type, data):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def serve(port, history):
    WeatherHandler.history_dir = history
    # ponytail: HTTPServer handles one request at a time, which matches one station.
    server = HTTPServer(("0.0.0.0", port), WeatherHandler)
    LOG.info(f"listening on 0.0.0.0:{port} -> {history}")
    server.serve_forever()


def self_check():
    assert DASHBOARD_PAGE == _ROOT / "dashboard.html"
    assert DASHBOARD_SCRIPT == _ROOT / "dashboard.js"
    assert SERVICES_PAGE == _ROOT / "services.html"
    assert SERVICES_SCRIPT == _ROOT / "services.js"
    assert DEFAULT_HISTORY == _ROOT / "data" / "station"
    assert DEFAULT_PORT == 8099

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

        assert latest_path(history) == history / "_latest.json"
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
        with (history / "2026-10-11_12.jsonl").open("a", encoding="utf-8") as handle:
            handle.write("\x00" * 8 + "\n")
        kept, _opened = query_history(
            history,
            "2026-10-11T11:30:00Z",
            "2026-10-11T16:00:00Z",
            ["tempf", "humidity"],
        )
        assert kept == records

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

    with tempfile.TemporaryDirectory() as directory:
        history = Path(directory) / "station"
        historical = history.parent / "historical"
        now = datetime(2026, 10, 11, 16, 0, 0)
        append_record(
            bucket_path(historical, "2026-10-10T15:00:00Z"),
            {"dateutc": "2026-10-10T15:00:00Z", "tempf": 10.0},
        )
        append_record(
            bucket_path(historical, "2026-10-11T12:00:00Z"),
            {"dateutc": "2026-10-11T12:00:00Z", "tempf": 60.0},
        )
        append_record(
            bucket_path(historical, "2026-10-11T15:00:00Z"),
            {"dateutc": "2026-10-11T15:00:00Z", "tempf": 62.0, "PASSKEY": "secret"},
        )
        append_record(
            bucket_path(history, "2026-10-11T14:30:00Z"),
            {"dateutc": "2026-10-11T14:30:00Z", "tempf": 1.0},
        )
        append_record(
            bucket_path(history, "2026-10-11T15:00:00Z"),
            {"dateutc": "2026-10-11T15:00:00Z", "tempf": 9.0},
        )
        append_record(
            bucket_path(history, "2026-10-11T15:30:00Z"),
            {"dateutc": "2026-10-11T15:30:00Z", "tempf": 64.0},
        )
        write_latest(
            latest_path(historical),
            {"dateutc": "2026-10-11T15:00:00Z", "tempf": 62.0},
        )
        write_latest(
            latest_path(history),
            {"dateutc": "2026-10-11T15:40:00Z", "tempf": 65.5},
        )
        status, payload = dashboard_series(history, "", now)
        assert status == 200
        assert payload["source"] == "historical"
        assert payload["from"] == "2026-10-10T16:00:00Z"
        assert payload["to"] == "2026-10-11T16:00:00Z"
        assert payload["step"] == 1
        assert payload["total"] == 2
        assert [row["dateutc"] for row in payload["records"]] == [
            "2026-10-11T12:00:00Z",
            "2026-10-11T15:00:00Z",
        ]
        assert [row["tempf"] for row in payload["records"]] == [60.0, 62.0]
        assert all("PASSKEY" not in row for row in payload["records"])
        assert payload["latest"]["dateutc"] == "2026-10-11T15:00:00Z"
        assert payload["latest"]["tempf"] == 62.0
        assert "2026-10-11T14:30:00Z" not in [
            row["dateutc"] for row in payload["records"]
        ]

        same, same_body = dashboard_series(history, "source=historical", now)
        assert same == 200 and same_body["records"] == payload["records"]
        assert same_body["latest"] == payload["latest"]

        status, history_body = dashboard_series(history, "source=station", now)
        assert status == 200
        assert history_body["source"] == "station"
        assert history_body["from"] == payload["from"] and history_body["to"] == payload["to"]
        assert [row["dateutc"] for row in history_body["records"]] == [
            "2026-10-11T14:30:00Z",
            "2026-10-11T15:00:00Z",
            "2026-10-11T15:30:00Z",
        ]
        assert [row["tempf"] for row in history_body["records"]] == [1.0, 9.0, 64.0]
        assert history_body["latest"]["dateutc"] == "2026-10-11T15:40:00Z"
        assert history_body["latest"]["tempf"] == 65.5
        assert "2026-10-11T12:00:00Z" not in [
            row["dateutc"] for row in history_body["records"]
        ]

        assert dashboard_series(history, "source=nope", now)[0] == 400
        assert dashboard_series(history, "from=not-a-time", now)[0] == 400
        assert dashboard_series(history, "to=not-a-time", now)[0] == 400
        assert dashboard_series(
            history,
            "from=2026-10-11T18:00:00Z&to=2026-10-11T12:00:00Z",
            now,
        )[0] == 400

        count = 1501
        origin = datetime(2026, 1, 1, 0, 0, 0)
        lines = []
        for index in range(count):
            stamp = (origin + timedelta(seconds=index)).strftime("%Y-%m-%dT%H:%M:%SZ")
            lines.append(json.dumps({"dateutc": stamp, "tempf": index}))
        (history / "2026-01-01_00.jsonl").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
        last_stamp = (origin + timedelta(seconds=count - 1)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        status, long_body = dashboard_series(
            history,
            "source=station&from=2026-01-01T00:00:00Z&to=2026-01-01T00:30:00Z",
            now,
        )
        assert status == 200
        assert long_body["step"] > 1
        assert long_body["total"] == count
        assert len(long_body["records"]) < count
        assert long_body["records"][0]["dateutc"] == "2026-01-01T00:00:00Z"
        assert long_body["records"][-1]["dateutc"] == last_stamp

    handler = WeatherHandler.__new__(WeatherHandler)
    handler.path = "/dashboard"
    handler.wfile = io.BytesIO()
    handler.send_response = lambda code, message=None: None
    handler.send_header = lambda key, value: None
    handler.end_headers = lambda: None
    handler.do_GET()
    page = handler.wfile.getvalue()
    assert b'src="/dashboard.js"' in page
    assert b'data-source="historical"' in page
    assert b'data-source="station"' in page
    assert b'href="/services"' in page
    assert b"xl:grid-cols-7" in page
    handler.wfile = io.BytesIO()
    handler.path = "/dashboard.js"
    handler.do_GET()
    script = handler.wfile.getvalue()
    assert b"/dashboard/series" in script
    assert b"spanGaps: false" in script
    assert b"breakSeriesGaps" in script
    assert b'source = "historical"' in script
    handler.wfile = io.BytesIO()
    handler.path = "/services"
    handler.do_GET()
    assert b'src="/services.js"' in handler.wfile.getvalue()
    handler.wfile = io.BytesIO()
    handler.path = "/services.js"
    handler.do_GET()
    assert b"/services/logs" in handler.wfile.getvalue()
    handler.wfile = io.BytesIO()
    handler.path = "/services/logs"
    handler.do_GET()
    logs = json.loads(handler.wfile.getvalue())
    assert [item["name"] for item in logs["loggers"]] == list(LOG_NAMES)
    assert all(isinstance(item["lines"], list) for item in logs["loggers"])

    print("self-check ok")


def main(argv):
    configure_logging()
    if "--self-check" in argv:
        self_check()
        return 0
    args = argv[1:]
    port = int(args[0]) if args else DEFAULT_PORT
    history = Path(args[1]) if len(args) > 1 else DEFAULT_HISTORY
    if not history.is_absolute():
        history = Path.cwd() / history
    serve(port, history)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
