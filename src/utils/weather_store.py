"""UTC 12-hour JSONL buckets shared by the collector and the HTTP server."""

import json
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone

_BUCKET_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})_(00|12)$")
_TIMESTAMP_FORMATS = ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S")
_ISO = "%Y-%m-%dT%H:%M:%SZ"


def format_timestamp(moment):
    """UTC `YYYY-MM-DDTHH:MM:SSZ` for an aware or naive datetime."""
    return moment.astimezone(timezone.utc).strftime(_ISO)


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


def bucket_path(history_dir, dateutc):
    """12-hour file for a UTC timestamp. 00:00 stays in _00; 12:00 starts _12."""
    hour = int(dateutc[11:13])
    slot = "00" if hour < 12 else "12"
    return history_dir / f"{dateutc[:10]}_{slot}.jsonl"


def latest_path(history_dir):
    return history_dir / "_latest.json"


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


def atomic_write(path, text):
    """Replace path with text. Readers see the previous file or this one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".atomic-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def write_latest(path, record):
    payload = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    atomic_write(path, payload)


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
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                stamp = record.get("dateutc", "")
                if start is not None and stamp < start:
                    continue
                if end is not None and stamp > end:
                    continue
                records.append(project_record(record, fields))
    return records, opened
