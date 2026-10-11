import logging
from ..sensi.api import SensiApi
from ..sensi.thermostat import SensiThermostat
from ..utils.thermostat_control import ThermostatControl
from ..utils.config_parser import ConfigParser

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

class BaseRoutine:
    def __init__(self, config_path):
        self._config_path = config_path
        self._thermostats = {}
        self.device_id = None

    async def _control_temperature(self):
        if self.device_id is None:
            LOG.error("No device set")
            return

        if self.device_id not in self._thermostats:
            LOG.error("Device not found")
            return

        config = ConfigParser(self._config_path)
        device = self._thermostats[self.device_id]
        thermostat_control = ThermostatControl(device, config)
        # Subclasses override this to customize control logic
        raise NotImplementedError("Subclasses must implement _control_temperature")

    async def routine_callback(self, api_instance, parsed_response):
        if parsed_response:
            _type, _content = parsed_response
            if _type == "42" and "state" in _content:
                for device in _content[1]:
                    _id = device.get("icd_id")
                    if _id in self._thermostats:
                        self._thermostats[_id].update_state(device)
                    else:
                        self._thermostats[_id] = SensiThermostat(api_instance, device)
                await self._control_temperature()

    def run(self, refresh_token, device_id):
        self.device_id = device_id
        sensi_api = SensiApi(refresh_token)
        sensi_api.start(self.routine_callback)