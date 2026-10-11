import datetime
from .base_routine import BaseRoutine
from ..utils.config_parser import ConfigParser
from ..utils.thermostat_control import ThermostatControl

class AlwaysHeatedRoutine(BaseRoutine):
    def __init__(self, config_path):
        super().__init__(config_path)
        self.startup_temp = None
        self.fan_startup_temp = None
        self.fan_startup_time = None
        self.cycle_end_temp = None

    async def _control_temperature(self):
        config = ConfigParser(self._config_path)
        device = self._thermostats[self.device_id]
        thermostat_control = ThermostatControl(device, config)
        result = thermostat_control.temperature_control(
            self.startup_temp, self.fan_startup_temp, self.fan_startup_time, self.cycle_end_temp
        )
        self.startup_temp = result["startup_temp"]
        self.fan_startup_temp = result["fan_startup_temp"]
        self.fan_startup_time = result["fan_startup_time"]
        self.cycle_end_temp = result["cycle_end_temp"]