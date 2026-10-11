"""Append each weather-station POST as one JSON line."""

import json
import sys
import tempfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

MAX_BODY_BYTES = 1024 * 1024
DEFAULT_PORT = 8099
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "data" / "weather.jsonl"


def flatten_single_values(pairs):
    """Turn parse_qs lists of one item into that item."""
    flat = {}
    for key, values in pairs.items():
        flat[key] = values[0] if len(values) == 1 else values
    return flat


def normalize_body(content_type, raw):
    """JSON object/array, form fields, or {\"raw\": text}. Bad JSON stays raw."""
    text = raw.decode("utf-8", errors="replace")
    media = (content_type or "").split(";", 1)[0].strip().lower()
    if media == "application/json" or media.endswith("+json"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}
        if isinstance(parsed, (dict, list)):
            return parsed
        return {"raw": text}
    if media == "application/x-www-form-urlencoded":
        return flatten_single_values(parse_qs(text, keep_blank_values=True))
    return {"raw": text}


def build_record(path, query, body, received_at=None):
    if received_at is None:
        received_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "received_at": received_at,
        "path": path,
        "query": query,
        "body": body,
    }


def append_record(output_path, record):
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    # ponytail: one station, so a single append+flush is enough; no file lock.
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()


class WeatherHandler(BaseHTTPRequestHandler):
    output_path = DEFAULT_OUTPUT

    def do_POST(self):
        length_header = self.headers.get("Content-Length")
        raw = b""
        if length_header is not None:
            try:
                length = int(length_header)
            except ValueError:
                self._reply(400, {"ok": False})
                return
            if length < 0 or length > MAX_BODY_BYTES:
                self._reply(413, {"ok": False})
                return
            # ponytail: stations send Content-Length; chunked bodies are skipped.
            raw = self.rfile.read(length)

        split = urlsplit(self.path)
        query = flatten_single_values(parse_qs(split.query, keep_blank_values=True))
        body = normalize_body(self.headers.get("Content-Type"), raw)
        append_record(self.output_path, build_record(split.path, query, body))
        self._reply(200, {"ok": True})

    def do_GET(self):
        self._reply(405, {"ok": False}, allow_post=True)

    do_PUT = do_GET
    do_DELETE = do_GET
    do_HEAD = do_GET
    do_PATCH = do_GET
    do_OPTIONS = do_GET

    def _reply(self, status, payload, allow_post=False):
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        if allow_post:
            self.send_header("Allow", "POST")
        self.end_headers()
        self.wfile.write(data)


def self_check():
    json_body = normalize_body("application/json", b'{"temp_c":21.5}')
    assert json_body == {"temp_c": 21.5}
    assert normalize_body("application/json; charset=utf-8", b"[1,2]") == [1, 2]
    assert normalize_body("application/json", b"not-json") == {"raw": "not-json"}

    form_body = normalize_body(
        "application/x-www-form-urlencoded",
        b"temp=21.5&flag=1&flag=2",
    )
    assert form_body == {"temp": "21.5", "flag": ["1", "2"]}

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "weather.jsonl"
        record = build_record(
            "/data/report/",
            {"id": "1"},
            json_body,
            received_at="2026-10-11T14:00:00+00:00",
        )
        append_record(output, record)
        line = output.read_text(encoding="utf-8")
        assert line == (
            '{"received_at":"2026-10-11T14:00:00+00:00",'
            '"path":"/data/report/","query":{"id":"1"},'
            '"body":{"temp_c":21.5}}\n'
        )
        assert json.loads(line)["body"]["temp_c"] == 21.5
    print("self-check ok")


def main(argv):
    if "--self-check" in argv:
        self_check()
        return

    args = argv[1:]
    port = int(args[0]) if args else DEFAULT_PORT
    output = Path(args[1]) if len(args) > 1 else DEFAULT_OUTPUT
    if not output.is_absolute():
        output = Path.cwd() / output
    output.parent.mkdir(parents=True, exist_ok=True)
    WeatherHandler.output_path = output

    # ponytail: HTTPServer is one request at a time, which matches one station.
    server = HTTPServer(("0.0.0.0", port), WeatherHandler)
    print(f"listening on 0.0.0.0:{port} -> {output}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main(sys.argv)
