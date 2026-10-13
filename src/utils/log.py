"""One timestamped log line. Color only the bracketed logger name."""

import hashlib
import logging
import re
import sys
import tempfile
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"
_RESET = "\033[0m"
# Distinct greens, cyans, yellows, magentas, blues. sha256 picks one per name.
# ponytail: a finite palette can repeat once more loggers exist than colors.
# Upgrade: lengthen _PALETTE and the name list in self_check.
_PALETTE = tuple(
    f"\033[38;5;{code}m"
    for code in (
        22, 28, 34, 40, 46, 70,
        30, 37, 44, 51, 80, 123,
        178, 184, 214, 220, 226,
        127, 165, 171, 201, 213,
        27, 33, 39, 63, 69,
    )
)
_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ")
_NAMES = (
    "src.ambient.api",
    "src.routines.base_routine",
    "src.sensi.api",
    "src.sensi.thermostat",
    "src.utils.config_parser",
    "src.utils.thermostat_control",
    "src.weather.history",
    "src.weather.server",
)
LOG_NAMES = _NAMES
_LOG_BYTES = 256 * 1024
_TAIL_LINES = 200
LOG_DIR = Path(__file__).resolve().parents[2] / "data" / "logs"


def color_for(name):
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    return _PALETTE[int.from_bytes(digest[:4], "big") % len(_PALETTE)]


class ColorFormatter(logging.Formatter):
    def __init__(self, color=None):
        super().__init__(_FORMAT, datefmt=_DATEFMT)
        if color is None:
            color = sys.stderr.isatty()
        self.color = color

    def format(self, record):
        line = super().format(record)
        if not self.color:
            return line
        token = f"[{record.name}]"
        start = line.find(token)
        if start < 0:
            return line
        end = start + len(token)
        return line[:start] + color_for(record.name) + token + _RESET + line[end:]


def _log_file(directory, name):
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        return None
    return Path(directory) / f"{name}.log"


def trim_log(path, limit=_LOG_BYTES):
    """Keep the tail once a log passes the cap. The cut starts on a line."""
    size = path.stat().st_size
    if size <= limit:
        return
    with path.open("rb") as handle:
        handle.seek(size - limit)
        tail = handle.read()
    cut = tail.find(b"\n")
    if 0 <= cut < len(tail) - 1:
        tail = tail[cut + 1 :]
    path.write_bytes(tail)


def tail_lines(path, limit=_TAIL_LINES):
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) <= limit:
        return lines
    return lines[-limit:]


def service_logs(directory=None, names=None, limit=_TAIL_LINES):
    folder = LOG_DIR if directory is None else Path(directory)
    chosen = LOG_NAMES if names is None else tuple(names)
    return {
        "loggers": [
            {"name": name, "lines": tail_lines(folder / f"{name}.log", limit)}
            for name in chosen
        ]
    }


class PlainLogHandler(logging.Handler):
    """Append the uncolored line. One file per logger name."""

    def __init__(self, directory):
        super().__init__()
        self.directory = Path(directory)
        self.setFormatter(ColorFormatter(color=False))

    def emit(self, record):
        path = _log_file(self.directory, record.name)
        if path is None:
            return
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(self.format(record) + "\n")
            trim_log(path)
        except Exception:
            self.handleError(record)


def configure_logging(color=None, log_dir=None):
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    stream = logging.StreamHandler()
    stream.setFormatter(ColorFormatter(color))
    files = PlainLogHandler(LOG_DIR if log_dir is None else log_dir)
    root.handlers[:] = [stream, files]


def _render(name, message, color):
    record = logging.LogRecord(
        name, logging.INFO, __file__, 1, message, (), None
    )
    return ColorFormatter(color).format(record)


def self_check():
    line = _render("src.sensi.thermostat", "Updated state for Kitchen", True)
    assert _STAMP.match(line), line
    visible = re.sub(r"\x1b\[[0-9;]*m", "", line)
    assert "INFO [src.sensi.thermostat]" in visible, visible
    painted = color_for("src.sensi.thermostat") + "[src.sensi.thermostat]" + _RESET
    assert painted in line
    assert "\x1b" not in line.split(painted, 1)[0]
    assert "\x1b" not in line.split(_RESET, 1)[1]
    server = _render("src.weather.server", "listening", True)
    assert color_for("src.sensi.thermostat") != color_for("src.weather.server")
    assert color_for("src.weather.server") + "[src.weather.server]" in server
    plain = _render("src.sensi.thermostat", "Updated state for Kitchen", False)
    assert "\x1b" not in plain
    assert "INFO [src.sensi.thermostat]" in plain
    codes = [color_for(name) for name in _NAMES]
    assert len(codes) == len(set(codes)), codes

    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    try:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            configure_logging(color=True, log_dir=folder)
            stream = root.handlers[0]
            files = root.handlers[1]
            assert root.level == logging.INFO
            assert len(root.handlers) == 2
            assert stream.stream is sys.stderr
            assert stream.formatter.color is True
            assert files.formatter.color is False
            logging.getLogger("src.sensi.thermostat").info("Updated state for Kitchen")
            written = (folder / "src.sensi.thermostat.log").read_text(encoding="utf-8")
            assert "\x1b" not in written
            assert "INFO [src.sensi.thermostat] Updated state for Kitchen" in written
            assert not (folder / "src.weather.server.log").exists()
            small = folder / "small.log"
            small.write_text("one\ntwo\n", encoding="utf-8")
            trim_log(small)
            assert small.read_text(encoding="utf-8") == "one\ntwo\n"
            big = folder / "src.weather.server.log"
            line = b"2026-01-01 00:00:00 INFO [src.weather.server] x\n"
            with big.open("wb") as handle:
                while handle.tell() <= _LOG_BYTES:
                    handle.write(line)
                handle.write(b"2026-01-01 00:00:01 INFO [src.weather.server] tail-marker\n")
            trim_log(big)
            data = big.read_bytes()
            assert len(data) <= _LOG_BYTES
            assert data.endswith(b"tail-marker\n")
            assert data.startswith(b"2026-")
            many = folder / "src.ambient.api.log"
            many.write_text("".join(f"line-{i}\n" for i in range(250)), encoding="utf-8")
            kept = tail_lines(many, 200)
            assert kept[0] == "line-50" and kept[-1] == "line-249" and len(kept) == 200
            payload = service_logs(folder)
            assert [item["name"] for item in payload["loggers"]] == list(LOG_NAMES)
            thermostat = payload["loggers"][LOG_NAMES.index("src.sensi.thermostat")]
            assert any("Updated state for Kitchen" in row for row in thermostat["lines"])
            missing = payload["loggers"][LOG_NAMES.index("src.utils.config_parser")]
            assert missing["lines"] == []
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)
    print("self-check ok")


if __name__ == "__main__":
    self_check()
