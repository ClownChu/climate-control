"""Ambient Weather HTTP client. Keys stay in the process environment."""

import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import requests

from src.utils.weather_config import (
    BASE_URL,
    LIMIT,
    MAX_ATTEMPTS,
    MAX_BACKOFF_SECONDS,
)
from src.utils.weather_store import format_timestamp

_SECRET_QUERY = {"apikey", "applicationkey"}
_SECRET_TEXT = re.compile(r"(?i)(apiKey|applicationKey)=[^&\s\"']*")


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
        params = {"endDate": format_timestamp(end), "limit": str(LIMIT)}
        body = self._get("/v1/devices/" + mac, params)
        if not isinstance(body, list):
            raise RuntimeError("history was not a list")
        return body


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


def self_check():
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
    moment = datetime.strptime("2024-06-25T04:15:00Z", "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    probe.history("AA:BB", moment)
    assert sent["params"]["endDate"] == "2024-06-25T04:15:00Z"
    assert sent["params"]["limit"] == str(LIMIT)
