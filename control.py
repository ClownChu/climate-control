import sys
import os
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

if len(sys.argv) != 4:
    print("usage: python3 ./run.py <refresh-token> <profile> <device-id>", file=sys.stderr)
    sys.exit(2)

file_path = os.path.dirname(os.path.abspath(__file__))
refresh_token, profile, device_id = sys.argv[1], sys.argv[2], sys.argv[3]

routine_class = f'{to_pascal_case(profile)}Routine'
routine = locals()[routine_class](file_path + '/src/config/' + profile + '_config.yml')
routine.run(refresh_token, device_id)