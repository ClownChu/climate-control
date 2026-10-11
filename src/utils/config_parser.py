from datetime import datetime
import yaml
import logging

LOG = logging.getLogger(__name__)

class ConfigParser:
    def __init__(self, config_path: str):
        self._config_path = config_path
        try:
            with open(self._config_path) as stream:
                self._config = yaml.safe_load(stream)
        except Exception as e:
            LOG.error(f"Failed to load config {config_path}: {e}")
            raise

    def is_current_datetime_in_night_range(self, timenow: datetime = None) -> tuple:
        if timenow is None:
            timenow = datetime.now()
        closest_hour = timenow.hour
        while closest_hour not in self._config.get('temps', {}):
            closest_hour = (closest_hour - 1) % 24
        closest_temp = self._config['temps'][closest_hour]
        return closest_temp['min'], closest_temp['max']

    def use_fan(self) -> bool:
        return self._config.get("use_fan", False)

    def min_temp_gain(self) -> int:
        return int(self._config.get("min_temp_gain", 0))

    def max_temp_loss(self) -> int:
        return int(self._config.get("max_temp_loss", 0))

    def end_fan_after(self) -> int:
        return int(self._config.get("end_fan_after", 0))

    def cycle_end_max_temp_loss(self) -> int:
        return int(self._config.get("cycle_end_max_temp_loss", 0))