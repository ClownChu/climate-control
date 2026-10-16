import os
import subprocess
import sys
import time

from src.utils.weather_config import control_fingerprint

HERE = os.path.dirname(os.path.abspath(__file__))
POLL_SECONDS = 1
STOP_WAIT_SECONDS = 5
USAGE = "usage: python3 ./run.py"
# ponytail: history retries inside src.weather.history, so a dead history
# process is left down. Restarting it here would loop every second on a bad
# weather_history_interval. Upgrade: restart history only when a signal killed it.
RESTART = {"control", "server"}


def commands(argv, executable):
    if argv[1:]:
        return None
    return [
        ("control", [executable, os.path.join(HERE, "control.py")]),
        ("server", [executable, "-m", "src.weather.server"]),
        ("history", [executable, "-m", "src.weather.history"]),
    ]


def eligible_to_restart(name, returncode):
    return name in RESTART and returncode is not None


def restart_exited(children, specs, popen):
    restarted = []
    for name, cmd in specs:
        child = children.get(name)
        if child is not None and eligible_to_restart(name, child.poll()):
            children[name] = popen(cmd, cwd=HERE)
            restarted.append(name)
    return restarted


def control_changed(child, started, current):
    """True when a live control child was started with different connection settings."""
    if child is None or started is None or current is None:
        return False
    if child.poll() is not None:
        return False
    return started != current


def stop_child(child):
    try:
        child.terminate()
    except OSError:
        pass


def read_control_identity():
    try:
        return control_fingerprint()
    except (OSError, ValueError, KeyError, TypeError):
        return None


def stop_children(children, wait_seconds=STOP_WAIT_SECONDS):
    alive = [child for child in children.values() if child.poll() is None]
    for child in alive:
        try:
            child.terminate()
        except OSError:
            pass
    for child in alive:
        try:
            child.wait(timeout=wait_seconds)
        except subprocess.TimeoutExpired:
            try:
                child.kill()
            except OSError:
                pass
            child.wait()


def supervise(specs, popen=subprocess.Popen, sleep=time.sleep, identity=None):
    if identity is None:
        identity = read_control_identity
    children = {}
    started = None
    try:
        for name, cmd in specs:
            children[name] = popen(cmd, cwd=HERE)
        started = identity()
        while True:
            sleep(POLL_SECONDS)
            current = identity()
            child = children.get("control")
            if control_changed(child, started, current):
                stop_child(child)
            restarted = restart_exited(children, specs, popen)
            if "control" in restarted:
                started = current
    except KeyboardInterrupt:
        stop_children(children)


def self_check():
    exe = sys.executable
    specs = commands(["run.py"], exe)
    assert specs == [
        ("control", [exe, os.path.join(HERE, "control.py")]),
        ("server", [exe, "-m", "src.weather.server"]),
        ("history", [exe, "-m", "src.weather.history"]),
    ]
    assert commands(["run.py", "spring", "dev-9"], exe) is None
    assert commands(["run.py", "only"], exe) is None

    assert eligible_to_restart("control", 1)
    assert eligible_to_restart("server", 0)
    assert not eligible_to_restart("control", None)
    assert not eligible_to_restart("history", 1)

    class Child:
        def __init__(self, code):
            self.code = code
            self.stops = 0

        def poll(self):
            return self.code

        def terminate(self):
            self.stops += 1
            self.code = 0

    children = {
        "control": Child(1),
        "server": Child(None),
        "history": Child(1),
    }
    spawned = []

    def popen(cmd, cwd=None):
        spawned.append((cmd, cwd))
        return Child(None)

    restarted = restart_exited(children, specs, popen)
    assert restarted == ["control"]
    assert spawned == [(specs[0][1], HERE)]
    assert children["control"].poll() is None
    assert children["history"].poll() == 1

    live = Child(None)
    children = {"control": live, "server": Child(None), "history": Child(None)}
    spawned.clear()
    started = ("dev", "keep_temperature_in_range")
    assert control_changed(live, started, started) is False
    assert control_changed(live, started, None) is False
    assert control_changed(live, started, ("dev", "always_heated")) is True
    assert control_changed(live, started, ("other-device", started[1])) is True
    current = ("other-device", "always_heated")
    if control_changed(children["control"], started, current):
        stop_child(children["control"])
    restarted = restart_exited(children, specs, popen)
    if "control" in restarted:
        started = current
    assert live.stops == 1
    assert started == current
    assert children["control"] is not live
    assert children["control"].poll() is None

    same = Child(None)
    if control_changed(same, started, started):
        stop_child(same)
    assert same.stops == 0

    identity = read_control_identity()
    assert identity[:2] == (
        "36-6f-92-ff-fe-0d-6c-d1",
        "keep_temperature_in_range",
    )
    assert identity[2].startswith("https://")
    assert identity[3].startswith("wss://")
    assert identity[4] == "fleet"
    assert "client_secret" not in identity
    print("self-check ok")


def main(argv):
    if argv[1:] == ["--self-check"]:
        self_check()
        return 0
    specs = commands(argv, sys.executable)
    if specs is None:
        print(USAGE, file=sys.stderr)
        return 2
    supervise(specs)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
