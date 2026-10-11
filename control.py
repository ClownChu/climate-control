import sys
import os
import tempfile
from src.routines.keep_temperature_in_range import KeepTemperatureInRangeRoutine
from src.routines.keep_temperature_in_range_spring import KeepTemperatureInRangeSpringRoutine
from src.routines.out_and_warm import OutAndWarmRoutine
from src.routines.keep_house_from_freezing import KeepHouseFromFreezingRoutine
from src.routines.always_heated import AlwaysHeatedRoutine

def to_pascal_case(text: str):
    if len(text) == 0:
        return text
    s = text.replace("-", " ").replace("_", " ").split()
    return ''.join(i.capitalize() for i in s)

def load_dotenv(path):
    try:
        with open(path) as stream:
            for raw in stream:
                line = raw.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    except FileNotFoundError:
        return

def resolve_run(argv, environ):
    args = argv[1:]
    if len(args) < 2 or len(args) > 3:
        return None
    refresh_token = environ.get('REFRESH_TOKEN') or (args[2] if len(args) == 3 else '')
    return refresh_token, args[0], args[1]

def _self_check():
    assert resolve_run(['c', 'profile', 'device'], {'REFRESH_TOKEN': 'from-env'}) == ('from-env', 'profile', 'device')
    assert resolve_run(['c', 'profile', 'device', 'from-cli'], {}) == ('from-cli', 'profile', 'device')
    assert resolve_run(['c', 'profile', 'device', 'from-cli'], {'REFRESH_TOKEN': 'from-env'}) == ('from-env', 'profile', 'device')
    assert resolve_run(['c', 'profile'], {}) is None
    key = 'DOTENV_SELF_CHECK'
    os.environ.pop(key, None)
    handle, path = tempfile.mkstemp()
    os.close(handle)
    with open(path, 'w') as stream:
        stream.write(f'{key}=from-file\n# comment\n\n')
    try:
        load_dotenv(path)
        assert os.environ.get(key) == 'from-file'
        os.environ[key] = 'already'
        load_dotenv(path)
        assert os.environ[key] == 'already'
    finally:
        os.remove(path)
        os.environ.pop(key, None)
    print('ok')

if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == '--self-check':
        _self_check()
    else:
        file_path = os.path.dirname(os.path.abspath(__file__))
        load_dotenv(os.path.join(file_path, '.env'))
        resolved = resolve_run(sys.argv, os.environ)
        if resolved is None:
            print("usage: python3 ./run.py <profile> <device-id> [refresh-token]", file=sys.stderr)
            sys.exit(2)
        refresh_token, profile, device_id = resolved
        routine_class = f'{to_pascal_case(profile)}Routine'
        routine = locals()[routine_class](file_path + '/src/config/' + profile + '_config.yml')
        routine.run(refresh_token, device_id)