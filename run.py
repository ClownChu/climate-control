import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
POLL_SECONDS = 1
STOP_WAIT_SECONDS = 5
USAGE = "usage: python3 ./run.py <profile> <device-id> [refresh-token]"
# ponytail: history retries inside src.weather.history, so a dead history
# process is left down. Restarting it here would loop every second on a bad
# WEATHER_HISTORY_INTERVAL. Upgrade: restart history only when a signal killed it.
RESTART = {"control", "server"}


def commands(argv, executable):
    args = argv[1:]
    if len(args) < 2 or len(args) > 3:
        return None
    return [
        ("control", [executable, os.path.join(HERE, "control.py"), *args]),
        ("server", [executable, "-m", "src.weather.server"]),
        ("history", [executable, "-m", "src.weather.history"]),
    ]


def eligible_to_restart(name, returncode):
    return name in RESTART and returncode is not None


def restart_exited(children, specs, popen):
    for name, cmd in specs:
        child = children.get(name)
        if child is not None and eligible_to_restart(name, child.poll()):
            children[name] = popen(cmd, cwd=HERE)


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


def supervise(specs, popen=subprocess.Popen, sleep=time.sleep):
    children = {}
    try:
        for name, cmd in specs:
            children[name] = popen(cmd, cwd=HERE)
        while True:
            sleep(POLL_SECONDS)
            restart_exited(children, specs, popen)
    except KeyboardInterrupt:
        stop_children(children)


def self_check():
    exe = sys.executable
    specs = commands(["run.py", "spring", "dev-9", "token"], exe)
    assert specs == [
        ("control", [exe, os.path.join(HERE, "control.py"), "spring", "dev-9", "token"]),
        ("server", [exe, "-m", "src.weather.server"]),
        ("history", [exe, "-m", "src.weather.history"]),
    ]
    short = commands(["run.py", "spring", "dev-9"], exe)
    assert short[0][1] == [exe, os.path.join(HERE, "control.py"), "spring", "dev-9"]
    assert commands(["run.py"], exe) is None
    assert commands(["run.py", "only"], exe) is None

    assert eligible_to_restart("control", 1)
    assert eligible_to_restart("server", 0)
    assert not eligible_to_restart("control", None)
    assert not eligible_to_restart("history", 1)

    class Child:
        def __init__(self, code):
            self.code = code

        def poll(self):
            return self.code

    children = {
        "control": Child(1),
        "server": Child(None),
        "history": Child(1),
    }
    spawned = []

    def popen(cmd, cwd=None):
        spawned.append((cmd, cwd))
        return Child(None)

    restart_exited(children, specs, popen)
    assert spawned == [(specs[0][1], HERE)]
    assert children["control"].poll() is None
    assert children["history"].poll() == 1
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
