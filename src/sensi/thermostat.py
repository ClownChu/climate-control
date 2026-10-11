import json
import logging

LOG = logging.getLogger(__name__)

class SensiThermostat:
    def __init__(self, api_instance, state_json):
        self.api = api_instance
        self.state = {}
        self._temperature = None
        self._current_heat_temp = None
        self._humidity = None
        self._mode = None
        self._cool_allowed = False
        self._heat_allowed = False
        self._fan_allowed = False
        self._unit_type = None
        self._duty_cycle = None
        self.update_state(state_json)

    @property
    def id(self) -> str:
        return self.state.get("icd_id", "")

    @property
    def name(self) -> str:
        return self.state.get("registration", {}).get("name", "Sensi Thermostat")

    @property
    def cool_range(self) -> tuple:
        caps = self.state.get("capabilities", {})
        return (caps.get("min_cool_setpoint", 45), caps.get("max_cool_setpoint", 99))

    @property
    def heat_range(self) -> tuple:
        caps = self.state.get("capabilities", {})
        return (caps.get("min_heat_setpoint", 45), caps.get("max_heat_setpoint", 99))

    @property
    def modes(self) -> list:
        modes = []
        try:
            for mode, enabled in self.state.get("capabilities", {}).get("operating_mode_settings", {}).items():
                if enabled == "yes":
                    modes.append(mode)
        except Exception as e:
            LOG.warning(f"Error parsing modes: {e}")
        return modes

    @property
    def fan_modes(self) -> list:
        modes = []
        try:
            for mode, enabled in self.state.get("capabilities", {}).get("fan_mode_settings", {}).items():
                if enabled == "yes":
                    modes.append(mode)
        except Exception as e:
            LOG.warning(f"Error parsing fan modes: {e}")
        return modes

    @property
    def temperature(self) -> int | None:
        temp = self.state.get("state", {}).get("display_temp")
        if temp is not None:
            self._temperature = temp
        return self._temperature

    @property
    def current_heat_temp(self) -> int | None:
        temp = self.state.get("state", {}).get("current_heat_temp")
        if temp is not None:
            self._current_heat_temp = temp
        return self._current_heat_temp

    @property
    def humidity(self) -> int | None:
        hum = self.state.get("state", {}).get("humidity")
        if hum is not None:
            self._humidity = hum
        return self._humidity

    @property
    def mode(self) -> str | None:
        m = self.state.get("state", {}).get("current_operating_mode")
        if m is not None:
            self._mode = m
        return self._mode

    @property
    def allowed_modes(self) -> list:
        allowed = ['off']
        if self.cool_allowed:
            allowed.append('cool')
        if self.heat_allowed:
            allowed.append('heat')
        return allowed

    @property
    def cool_allowed(self) -> bool:
        caps = self.state.get("capabilities", {})
        self._cool_allowed = caps.get("cool_cycle_rate") == "yes"
        return self._cool_allowed

    @property
    def heat_allowed(self) -> bool:
        caps = self.state.get("capabilities", {})
        self._heat_allowed = caps.get("heat_cycle_rate") == "yes"
        return self._heat_allowed

    @property
    def unit_type(self) -> str | None:
        unit = self.state.get("state", {}).get("display_scale")
        if unit is not None:
            self._unit_type = unit
        return self._unit_type

    @property
    def duty_cycle(self) -> int | None:
        dc = self.state.get("state", {}).get('circulating_fan', {}).get("duty_cycle")
        if dc is not None:
            self._duty_cycle = dc
        return self._duty_cycle

    def refresh_state(self):
        self.api.send(["state", {"icd_id": self.id}])

    def set_temperature(self, temperature: int, mode: str = None):
        if mode is None:
            mode = self.mode
        self.api.send(["set_temperature", {"icd_id": self.id, "target_temp": temperature, "mode": mode, "scale": self.unit_type}])

    def set_operating_mode(self, mode: str):
        self.api.send(["set_operating_mode", {"icd_id": self.id, "value": mode}])

    def set_circulating_fan(self, state: str, duty_cycle: int = None):
        if duty_cycle is None:
            duty_cycle = self.duty_cycle
        self.api.send(["set_circulating_fan", {"icd_id": self.id, "value": {"duty_cycle": duty_cycle, "enabled": state}}])

    def update_state(self, state_json: dict):
        self.state = state_json
        LOG.info(f"Updated state for {self.name} ({self.id}): Temp={self.temperature}, Humidity={self.humidity}, Mode={self.mode}")