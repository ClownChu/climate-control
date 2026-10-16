"""Record Ambient Weather GET uploads into UTC 12-hour JSONL buckets."""

import io
import json
import logging
import re
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import yaml

from src.routines import catalog as routine_catalog
from src.routines.catalog import (
    ROUTINE_NAMES,
    describe_routines,
    routine_path,
    write_routine,
)
from src.utils import weather_config
from src.utils.log import LOG_NAMES, configure_logging, service_logs
from src.utils.weather_calc import apply_derived
from src.utils.weather_config import (
    DEFAULT_HISTORY,
    DEFAULT_PORT,
    control_identity,
    sensi_settings,
    set_device_id,
    set_routine,
    set_sensi_settings,
    set_weather_history_interval,
    weather_history_interval,
)
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
SETTINGS_SCRIPT = _ROOT / "settings.js"
_MAX_BODY = 65536
_STATIC = {
    "/dashboard": (DASHBOARD_PAGE, "text/html; charset=utf-8"),
    "/dashboard.js": (DASHBOARD_SCRIPT, "text/javascript; charset=utf-8"),
    "/dashboard-series.js": (_ROOT / "dashboard-series.js", "text/javascript; charset=utf-8"),
    "/dashboard-cards.js": (_ROOT / "dashboard-cards.js", "text/javascript; charset=utf-8"),
    "/dashboard-range.js": (_ROOT / "dashboard-range.js", "text/javascript; charset=utf-8"),
    "/services": (SERVICES_PAGE, "text/html; charset=utf-8"),
    "/services.js": (SERVICES_SCRIPT, "text/javascript; charset=utf-8"),
    "/settings.js": (SETTINGS_SCRIPT, "text/javascript; charset=utf-8"),
}
_CHART_FIELDS = (
    "tempf",
    "feelsLike",
    "dewPoint",
    "tempinf",
    "feelsLikein",
    "dewPointin",
    "humidity",
    "humidityin",
    "winddir",
    "windspeedmph",
    "windgustmph",
    "maxdailygust",
    "hourlyrainin",
    "eventrainin",
    "dailyrainin",
    "weeklyrainin",
    "monthlyrainin",
    "totalrainin",
    "lastRain",
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
    apply_derived(reading, read_snapshot(latest_path(history_dir)))
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
    return 200, {
        "source": source,
        "from": start,
        "to": end,
        "step": step,
        "total": total,
        "records": records,
    }


def redact_passkey(text):
    return _PASSKEY_LOG.sub(r"\1REDACTED", text)


def json_dict(raw):
    if not isinstance(raw, (bytes, bytearray)):
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def history_interval_get():
    try:
        return 200, {"weather_history_interval": weather_history_interval()}
    except (OSError, ValueError, KeyError, TypeError):
        return 500, {"ok": False}


def history_interval_post(data):
    if not isinstance(data, dict) or "weather_history_interval" not in data:
        return 400, {"ok": False}
    try:
        value = set_weather_history_interval(data["weather_history_interval"])
    except ValueError:
        return 400, {"ok": False}
    return 200, {"weather_history_interval": value}


def sensi_get():
    try:
        return 200, sensi_settings()
    except (OSError, ValueError, KeyError, TypeError):
        return 500, {"ok": False}


def sensi_post(data):
    if not isinstance(data, dict) or "client_secret" in data or "CLIENT_SECRET" in data:
        return 400, {"ok": False}
    try:
        saved = set_sensi_settings(data.get("oauth_url"), data.get("ws_url"), data.get("client_id"))
    except ValueError:
        return 400, {"ok": False}
    return 200, saved


def routines_get():
    try:
        device_id, routine = control_identity()
        routines = describe_routines(routine)
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError):
        return 500, {"ok": False}
    return 200, {"device_id": device_id, "routine": routine, "routines": routines}


def routines_active_post(data):
    if not isinstance(data, dict):
        return 400, {"ok": False}
    try:
        name = set_routine(data.get("routine"))
    except ValueError:
        return 400, {"ok": False}
    return 200, {"routine": name}


def routines_device_post(data):
    if not isinstance(data, dict):
        return 400, {"ok": False}
    try:
        device_id = set_device_id(data.get("device_id"))
    except ValueError:
        return 400, {"ok": False}
    return 200, {"device_id": device_id}


def routines_put(name, data):
    try:
        saved = write_routine(name, data)
    except KeyError:
        return 404, {"ok": False}
    except (OSError, ValueError, yaml.YAMLError):
        return 500, {"ok": False}
    if saved is None:
        return 400, {"ok": False}
    try:
        _device, active = control_identity()
    except (OSError, ValueError, KeyError, TypeError):
        active = None
    saved["active"] = saved["name"] == active
    return 200, saved


class WeatherHandler(BaseHTTPRequestHandler):
    history_dir = DEFAULT_HISTORY

    def do_GET(self):
        split = urlsplit(self.path)
        static = _STATIC.get(split.path)
        if static is not None:
            path, content_type = static
            self._reply_bytes(200, content_type, path.read_bytes())
            return
        if split.path == "/services/logs":
            self._reply(200, service_logs())
            return
        if split.path == "/routines":
            status, payload = routines_get()
            self._reply(status, payload)
            return
        if split.path == "/config/history-interval":
            status, payload = history_interval_get()
            self._reply(status, payload)
            return
        if split.path == "/config/sensi":
            status, payload = sensi_get()
            self._reply(status, payload)
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

    def _read_body(self):
        headers = getattr(self, "headers", None) or {}
        try:
            length = int(headers.get("Content-Length", "0") or 0)
        except (TypeError, ValueError):
            return None
        if length < 0 or length > _MAX_BODY:
            return None
        reader = getattr(self, "rfile", None)
        if reader is None:
            return b""
        return reader.read(length)

    def do_POST(self):
        split = urlsplit(self.path)
        data = json_dict(self._read_body())
        if split.path == "/config/history-interval":
            status, payload = history_interval_post(data)
        elif split.path == "/config/sensi":
            status, payload = sensi_post(data)
        elif split.path == "/routines/active":
            status, payload = routines_active_post(data)
        elif split.path == "/routines/device":
            status, payload = routines_device_post(data)
        else:
            status, payload = 404, {"ok": False}
        self._reply(status, payload)

    def do_PUT(self):
        split = urlsplit(self.path)
        prefix = "/routines/"
        if not split.path.startswith(prefix) or "/" in split.path[len(prefix):]:
            self._reply(404, {"ok": False})
            return
        name = unquote(split.path[len(prefix):])
        status, payload = routines_put(name, json_dict(self._read_body()))
        self._reply(status, payload)

    def _reject(self):
        self._reply(404, {"ok": False})

    do_DELETE = _reject
    do_HEAD = _reject
    do_PATCH = _reject
    do_OPTIONS = _reject

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
    assert SETTINGS_SCRIPT == _ROOT / "settings.js"
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
        assert stored["feelsLike"] == 61.0
        assert "lastRain" not in stored

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
        assert "latest" not in payload
        assert "2026-10-11T14:30:00Z" not in [
            row["dateutc"] for row in payload["records"]
        ]

        same, same_body = dashboard_series(history, "source=historical", now)
        assert same == 200 and same_body["records"] == payload["records"]

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
        assert "latest" not in history_body
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

    with tempfile.TemporaryDirectory() as directory:
        history = Path(directory) / "derived"
        wet = (
            "stationtype=AMBWeatherV4.3.8&PASSKEY=fake-passkey"
            "&dateutc=2026-10-12+12:27:20&tempf=64.4&humidity=76"
            "&hourlyrainin=0.01&tempinf=67.8&humidityin=68"
        )
        status, payload = ingest_reading(history, wet)
        assert status == 200 and payload == {"ok": True}
        stored = json.loads((history / "2026-10-12_12.jsonl").read_text(encoding="utf-8"))
        assert stored["feelsLike"] == 64.4
        assert stored["dewPoint"] == 56.66
        assert stored["feelsLikein"] == 67.8
        assert stored["dewPointin"] == 56.8
        assert stored["lastRain"] == "2026-10-12T12:27:00Z"
        dry = (
            "stationtype=AMBWeatherV4.3.8&PASSKEY=fake-passkey"
            "&dateutc=2026-10-12+12:28:05&tempf=68.4&humidity=35"
            "&windspeedmph=0&hourlyrainin=0"
        )
        assert ingest_reading(history, dry)[0] == 200
        chill = (
            "stationtype=AMBWeatherV4.3.8&PASSKEY=fake-passkey"
            "&dateutc=2026-10-12+12:29:00&tempf=43.9&humidity=50"
            "&windspeedmph=4&hourlyrainin=0"
        )
        assert ingest_reading(history, chill)[0] == 200
        lines = (history / "2026-10-12_12.jsonl").read_text(encoding="utf-8").splitlines()
        warm = json.loads(lines[1])
        chilled = json.loads(lines[2])
        assert warm["feelsLike"] == 66.59
        assert warm["lastRain"] == "2026-10-12T12:27:00Z"
        assert chilled["feelsLike"] == 41.82
        assert chilled["lastRain"] == "2026-10-12T12:27:00Z"
        latest = json.loads(latest_path(history).read_text(encoding="utf-8"))
        assert latest["feelsLike"] == 41.82
        assert latest["lastRain"] == "2026-10-12T12:27:00Z"

    handler = WeatherHandler.__new__(WeatherHandler)
    handler.path = "/dashboard"
    handler.wfile = io.BytesIO()
    handler.send_response = lambda code, message=None: None
    handler.send_header = lambda key, value: None
    handler.end_headers = lambda: None
    handler.do_GET()
    page = handler.wfile.getvalue()
    assert b'type="module" src="/dashboard.js"' in page
    assert b'data-source="historical"' in page
    assert b'data-source="station"' in page
    assert b'href="/services"' in page
    assert b'id="settings-open"' in page
    assert b'src="/settings.js"' in page
    assert b'href="/routines"' not in page
    handler.wfile = io.BytesIO()
    handler.path = "/dashboard.js"
    handler.do_GET()
    script = handler.wfile.getvalue()
    assert b"/dashboard/series" in script
    for path in ("/dashboard-series.js", "/dashboard-cards.js", "/dashboard-range.js"):
        handler.wfile = io.BytesIO()
        handler.path = path
        handler.do_GET()
        assert b"export " in handler.wfile.getvalue()
    handler.wfile = io.BytesIO()
    handler.path = "/services"
    handler.do_GET()
    services_page = handler.wfile.getvalue()
    assert b'src="/services.js"' in services_page
    assert b'id="settings-open"' in services_page
    assert b'src="/settings.js"' in services_page
    handler.wfile = io.BytesIO()
    handler.path = "/services.js"
    handler.do_GET()
    assert b"/services/logs" in handler.wfile.getvalue()
    handler.wfile = io.BytesIO()
    handler.path = "/settings.js"
    handler.do_GET()
    settings_script = handler.wfile.getvalue()
    assert b"General" in settings_script
    assert b"Routines" in settings_script
    assert b"/config/history-interval" in settings_script
    assert b"/config/sensi" in settings_script
    assert b"SENSI_FLEET_CLIENT_SECRET" in settings_script
    assert b"/routines/active" in settings_script
    assert b"/routines/device" in settings_script
    assert b"PUT" in settings_script
    assert b"Saved." in settings_script
    assert b"Activated." in settings_script
    handler.wfile = io.BytesIO()
    handler.path = "/services/logs"
    handler.do_GET()
    logs = json.loads(handler.wfile.getvalue())
    assert [item["name"] for item in logs["loggers"]] == list(LOG_NAMES)
    assert all(isinstance(item["lines"], list) for item in logs["loggers"])

    real_app = weather_config.APP_CONFIG
    real_root = routine_catalog.ROOT
    real_text = real_app.read_text(encoding="utf-8")

    def dispatch(path, method="GET", body=b"", accept=""):
        probe = WeatherHandler.__new__(WeatherHandler)
        probe.path = path
        probe.headers = {"Content-Length": str(len(body)), "Accept": accept}
        probe.rfile = io.BytesIO(body)
        probe.wfile = io.BytesIO()
        codes = []
        probe.send_response = lambda code, message=None: codes.append(code)
        probe.send_header = lambda key, value: None
        probe.end_headers = lambda: None
        getattr(probe, "do_" + method)()
        return codes[0], probe.wfile.getvalue()

    try:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            config_path = temp / "app_config.json"
            config_path.write_text(real_text, encoding="utf-8")
            for name in ROUTINE_NAMES:
                source = routine_path(name)
                dest = temp / source.relative_to(real_root)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(source, dest)
            weather_config.APP_CONFIG = config_path
            routine_catalog.ROOT = temp

            status, payload = history_interval_get()
            assert status == 200 and payload == {"weather_history_interval": 900}
            rejected = (
                None,
                {},
                {"weather_history_interval": -1},
                {"weather_history_interval": 1.5},
                {"weather_history_interval": "900"},
                {"weather_history_interval": True},
            )
            for raw in rejected:
                assert history_interval_post(raw)[0] == 400
            status, payload = history_interval_post({"weather_history_interval": 30})
            assert status == 200 and payload == {"weather_history_interval": 30}
            assert history_interval_get() == (200, {"weather_history_interval": 30})

            code, body = dispatch("/config/history-interval")
            assert code == 200 and json.loads(body)["weather_history_interval"] == 30
            code, body = dispatch(
                "/config/history-interval",
                "POST",
                b'{"weather_history_interval": 0}',
            )
            assert code == 200 and json.loads(body)["weather_history_interval"] == 0
            code, _body = dispatch("/nope", "POST", b"{}")
            assert code == 404
            code, _body = dispatch("/config/history-interval", "POST", b"")
            assert code == 400
            status, payload = sensi_get()
            assert status == 200
            assert payload["client_id"] == "fleet"
            assert payload["oauth_url"].startswith("https://")
            assert payload["ws_url"].startswith("wss://")
            assert "client_secret" not in payload
            assert sensi_post({"oauth_url": "", "ws_url": payload["ws_url"], "client_id": "fleet"})[0] == 400
            leaked = {
                "oauth_url": payload["oauth_url"],
                "ws_url": payload["ws_url"],
                "client_id": "fleet",
                "client_secret": "nope",
            }
            assert sensi_post(leaked)[0] == 400
            assert "nope" not in config_path.read_text(encoding="utf-8")
            assert "client_secret" not in config_path.read_text(encoding="utf-8")
            huge = WeatherHandler.__new__(WeatherHandler)
            huge.path = "/config/history-interval"
            huge.headers = {"Content-Length": "999999"}
            huge.rfile = io.BytesIO(b"{}")
            huge.wfile = io.BytesIO()
            codes = []
            huge.send_response = lambda status_code, message=None: codes.append(status_code)
            huge.send_header = lambda key, value: None
            huge.end_headers = lambda: None
            huge.do_POST()
            assert codes == [400]

            status, payload = routines_get()
            assert status == 200
            assert payload["device_id"] == "36-6f-92-ff-fe-0d-6c-d1"
            assert payload["routine"] == "keep_temperature_in_range"
            assert [item["name"] for item in payload["routines"]] == list(ROUTINE_NAMES)
            active = [item for item in payload["routines"] if item["active"]]
            assert len(active) == 1 and active[0]["name"] == "keep_temperature_in_range"
            assert active[0]["path"].endswith("keep_temperature_in_range_config.yml")
            assert active[0]["temps"]["5"] == {"min": 66, "max": 68}
            assert "use_fan" in active[0]
            away = [item for item in payload["routines"] if item["name"] == "out_and_warm"][0]
            assert away["path"] == "src/config/out_and_warm_config.yml"
            assert away["active"] is False

            assert routines_active_post({"routine": "nope"})[0] == 400
            assert routines_active_post({})[0] == 400
            status, payload = routines_active_post({"routine": "always_heated"})
            assert status == 200 and payload == {"routine": "always_heated"}
            assert routines_get()[1]["routine"] == "always_heated"
            assert routines_device_post({"device_id": "  "})[0] == 400
            assert routines_device_post({"device_id": 12})[0] == 400
            status, payload = routines_device_post({"device_id": " dev-new "})
            assert status == 200 and payload == {"device_id": "dev-new"}
            assert control_identity() == ("dev-new", "always_heated")

            band = {
                "temps": {"5": {"min": 70, "max": 66}, "8": {"min": 60, "max": 63}},
                "use_fan": False,
                "min_temp_gain": 2,
                "max_temp_loss": 2,
                "end_fan_after": 120,
                "cycle_end_max_temp_loss": 1,
            }
            assert routines_put("keep_temperature_in_range", band)[0] == 400
            band["temps"] = {"24": {"min": 60, "max": 63}, "5": {"min": 66, "max": 68}}
            assert routines_put("keep_temperature_in_range", band)[0] == 400
            band["temps"] = {"5": {"min": 61, "max": 68}}
            status, payload = routines_put("keep_temperature_in_range", band)
            assert status == 200
            assert payload["temps"] == {"5": {"min": 61, "max": 68}}
            assert payload["active"] is False
            assert routines_put("not_a_routine", band) == (404, {"ok": False})
            stored = routine_path("keep_temperature_in_range").read_text(encoding="utf-8")
            assert "min: 61" in stored and "max: 68" in stored

            code, body = dispatch("/routines", accept="text/html")
            catalog = json.loads(body)
            assert code == 200 and catalog["device_id"] == "dev-new"
            assert b"<html" not in body
            code, body = dispatch(
                "/routines/always_heated",
                "PUT",
                json.dumps(band).encode("utf-8"),
            )
            assert code == 200 and json.loads(body)["name"] == "always_heated"
            code, _body = dispatch("/routines/nope/extra", "PUT", b"{}")
            assert code == 404
    finally:
        weather_config.APP_CONFIG = real_app
        routine_catalog.ROOT = real_root
    assert real_app.read_text(encoding="utf-8") == real_text

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
