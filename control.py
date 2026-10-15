import sys
import os

from envfile import load_dotenv
from src.routines.catalog import ROUTINE_NAMES, routine_path
from src.utils.log import configure_logging
from src.utils.weather_config import load_app_config

USAGE = "usage: python3 ./run.py"


def resolve_run(environ, config):
    if not isinstance(config, dict):
        return None
    device_id = config.get("device_id")
    routine = config.get("routine")
    if not isinstance(device_id, str) or not device_id.strip():
        return None
    if routine not in ROUTINE_NAMES:
        return None
    return environ.get("REFRESH_TOKEN") or "", routine, device_id.strip()


def _self_check():
    env = {"REFRESH_TOKEN": "from-env"}
    good = {"device_id": "dev-9", "routine": "keep_temperature_in_range"}
    assert resolve_run(env, good) == ("from-env", "keep_temperature_in_range", "dev-9")
    assert resolve_run({}, good) == ("", "keep_temperature_in_range", "dev-9")
    assert resolve_run(env, {"device_id": "  ", "routine": "keep_temperature_in_range"}) is None
    assert resolve_run(env, {"device_id": "dev-9", "routine": "missing"}) is None
    assert resolve_run(env, {"routine": "keep_temperature_in_range"}) is None
    assert resolve_run(env, {"device_id": "dev-9"}) is None
    loaded = load_app_config()
    assert resolve_run(env, loaded) == ("from-env", loaded["routine"], loaded["device_id"])
    for name in ROUTINE_NAMES:
        assert routine_path(name).is_file()
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--self-check":
        _self_check()
    else:
        configure_logging()
        # Imported here so --self-check does not load websockets or api_config.yml.
        from src.routines.keep_temperature_in_range import KeepTemperatureInRangeRoutine
        from src.routines.keep_temperature_in_range_spring import KeepTemperatureInRangeSpringRoutine
        from src.routines.out_and_warm import OutAndWarmRoutine
        from src.routines.keep_house_from_freezing import KeepHouseFromFreezingRoutine
        from src.routines.always_heated import AlwaysHeatedRoutine

        file_path = os.path.dirname(os.path.abspath(__file__))
        load_dotenv(os.path.join(file_path, ".env"))
        resolved = resolve_run(os.environ, load_app_config())
        if resolved is None:
            print(USAGE, file=sys.stderr)
            sys.exit(2)
        refresh_token, profile, device_id = resolved
        routine_class = {
            "keep_temperature_in_range": KeepTemperatureInRangeRoutine,
            "keep_temperature_in_range_spring": KeepTemperatureInRangeSpringRoutine,
            "out_and_warm": OutAndWarmRoutine,
            "keep_house_from_freezing": KeepHouseFromFreezingRoutine,
            "always_heated": AlwaysHeatedRoutine,
        }[profile]
        routine = routine_class(str(routine_path(profile)))
        routine.run(refresh_token, device_id)
