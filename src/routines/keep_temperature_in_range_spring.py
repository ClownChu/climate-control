from .base_routine import BaseRoutine
from ..utils.config_parser import ConfigParser
from ..utils.thermostat_control import ThermostatControl

class KeepTemperatureInRangeSpringRoutine(BaseRoutine):
    async def _control_temperature(self):
        config = ConfigParser(self._config_path)
        device = self._thermostats[self.device_id]
        temps = config.is_current_datetime_in_night_range()
        thermostat_control = ThermostatControl(device, config, temp_offset=1)
        thermostat_control.temperature_control(modes=['off', 'heat'])