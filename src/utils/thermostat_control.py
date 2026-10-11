import datetime
import logging

LOG = logging.getLogger(__name__)

class ThermostatControl:
    def __init__(self, device, config, temp_offset: int = 0):
        self._device = device
        self._temp_offset = temp_offset
        self._config = config

    def get_target_temp(self, temps: tuple) -> int:
        target_temp = self._device.current_heat_temp or self._device.temperature
        if self._device.temperature > temps[1] - self._temp_offset:
            target_temp = temps[0]
        elif self._device.temperature < temps[0] + self._temp_offset:
            target_temp = temps[1]
        return target_temp

    def get_ideal_action(self, target_temp: int, startup_temp=None, fan_startup_temp=None, fan_startup_time=None, cycle_end_temp=None) -> dict:
        force_fan = False
        end_fan = False
        mode = "heat" if target_temp > self._device.temperature else "cool"

        if self._config.use_fan():
            if fan_startup_temp is not None:
                if fan_startup_temp - self._config.max_temp_loss() >= self._device.temperature:
                    end_fan = True
                if fan_startup_time is not None:
                    mode = "off"
                    if (datetime.datetime.now() - fan_startup_time).total_seconds() >= self._config.end_fan_after():
                        end_fan = True
            elif startup_temp is not None:
                if startup_temp + self._config.min_temp_gain() <= self._device.temperature:
                    force_fan = True
                    mode = "off"

            if cycle_end_temp is not None:
                if cycle_end_temp - self._config.cycle_end_max_temp_loss() < self._device.temperature:
                    mode = "off"

        # Clamp target_temp to ranges
        heat_min, heat_max = self._device.heat_range
        cool_min, cool_max = self._device.cool_range
        if mode == "heat":
            target_temp = max(heat_min, min(heat_max, target_temp))
        elif mode == "cool":
            target_temp = max(cool_min, min(cool_max, target_temp))
        else:
            target_temp = 0  # Off mode

        if target_temp <= 0:
            mode = "off"

        return {
            "mode": mode,
            "target_temp": target_temp,
            "force_fan": force_fan,
            "end_fan": end_fan,
        }

    def temperature_control(self, startup_temp=None, fan_startup_temp=None, fan_startup_time=None, cycle_end_temp=None, modes=['off', 'cool', 'heat']):
        temps = self._config.is_current_datetime_in_night_range()
        if self._device.temperature is None:
            LOG.error("Cannot get temperature from thermostat")
            return {
                "startup_temp": startup_temp,
                "fan_startup_temp": fan_startup_temp,
                "fan_startup_time": fan_startup_time,
                "cycle_end_temp": cycle_end_temp
            }

        target_temp = self.get_target_temp(temps)
        action = self.get_ideal_action(target_temp, startup_temp, fan_startup_temp, fan_startup_time, cycle_end_temp)

        LOG.info(f"Temp={self._device.temperature}, Mode={action['mode']}, Force Fan={action['force_fan']}, End Fan={action['end_fan']}, Target={action['target_temp']}, Min/Max={temps}")

        if action["end_fan"]:
            self._device.set_circulating_fan("off", 100)
            cycle_end_temp = self._device.temperature
            startup_temp = None
            fan_startup_temp = None
            fan_startup_time = None
        elif action["force_fan"]:
            self._device.set_circulating_fan("on", 100)
            fan_startup_temp = self._device.temperature
            fan_startup_time = datetime.datetime.now()

        if action["mode"] != "off" and startup_temp is None:
            startup_temp = self._device.temperature
            cycle_end_temp = None

        if self._device.mode != action["mode"] and action["mode"] in modes:
            LOG.info(f"Setting mode to {action['mode']}")
            self._device.set_operating_mode(action["mode"])
        if action["target_temp"] > 0 and action["target_temp"] != self._device.current_heat_temp:
            LOG.info(f"Setting temperature to {action['target_temp']}")
            self._device.set_temperature(action["target_temp"])

        return {
            "startup_temp": startup_temp,
            "fan_startup_temp": fan_startup_temp,
            "fan_startup_time": fan_startup_time,
            "cycle_end_temp": cycle_end_temp
        }