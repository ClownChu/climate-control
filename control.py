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

file_path = os.path.dirname(os.path.abspath(__file__))

routine_class = f'{to_pascal_case(sys.argv[3])}Routine'
routine = c = locals()[routine_class](file_path + '/src/config/'+ sys.argv[3] +'_config.yml')
routine.run(sys.argv[1], sys.argv[2], sys.argv[4])