"""Dew point, feels-like, and last rain for a station reading."""

import math
from decimal import Decimal, ROUND_HALF_UP

_A = 17.27
_B = 237.7


def _round_half_up(value, places):
    quant = Decimal(1).scaleb(-places)
    return float(Decimal(value).quantize(quant, rounding=ROUND_HALF_UP))


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def dew_point(temp_f, humidity):
    """Magnus dew point in °F. `humidity` must be above 0."""
    temp_c = (temp_f - 32.0) * 5.0 / 9.0
    gamma = math.log(humidity / 100.0) + (_A * temp_c) / (_B + temp_c)
    dew_c = (_B * gamma) / (_A - gamma)
    return dew_c * 9.0 / 5.0 + 32.0


def _wind_chill(temp_f, wind_mph):
    powered = wind_mph ** 0.16
    return 35.74 + 0.6215 * temp_f - 35.75 * powered + 0.4275 * temp_f * powered


def _heat_index(temp_f, humidity):
    temperature = temp_f
    relative = humidity
    index = (
        -42.379
        + 2.04901523 * temperature
        + 10.14333127 * relative
        - 0.22475541 * temperature * relative
        - 0.00683783 * temperature * temperature
        - 0.05481717 * relative * relative
        + 0.00122874 * temperature * temperature * relative
        + 0.00085282 * temperature * relative * relative
        - 0.00000199 * temperature * temperature * relative * relative
    )
    if relative < 13 and 80 <= temperature <= 112:
        index -= ((13 - relative) / 4) * math.sqrt((17 - abs(temperature - 95)) / 17)
    if relative > 85 and 80 <= temperature <= 87:
        index += ((relative - 85) / 10) * ((87 - temperature) / 5)
    return index


def _simple_heat_index(temp_f, humidity):
    return 0.5 * (temp_f + 61.0 + (temp_f - 68.0) * 1.2 + humidity * 0.094)


def _feels_like(temp_f, humidity, wind_mph):
    wind = 0.0 if wind_mph is None else float(wind_mph)
    temp = float(temp_f)
    relative = float(humidity)
    if temp < 50 and wind >= 3:
        return _wind_chill(temp, wind), True
    if temp >= 80:
        return _heat_index(temp, relative), True
    if temp > 68:
        return _simple_heat_index(temp, relative), True
    return temp, False


def feels_like(temp_f, humidity, wind_mph=0):
    """Feels-like °F before display rounding. Missing wind counts as calm."""
    value, _computed = _feels_like(temp_f, humidity, wind_mph)
    return value


def _put(reading, key, value):
    if value is None:
        reading.pop(key, None)
    else:
        reading[key] = value


def _side(reading, temp_key, humidity_key, feels_key, dew_key, wind, places):
    temp = _number(reading.get(temp_key))
    humidity = _number(reading.get(humidity_key))
    if temp is None or humidity is None:
        reading.pop(feels_key, None)
        reading.pop(dew_key, None)
        return
    value, computed = _feels_like(temp, humidity, wind)
    if computed:
        value = _round_half_up(value, places)
    reading[feels_key] = value
    if humidity <= 0:
        reading.pop(dew_key, None)
    else:
        reading[dew_key] = _round_half_up(dew_point(temp, humidity), places)


def _floor_minute(dateutc):
    if isinstance(dateutc, str) and len(dateutc) >= 17:
        return dateutc[:17] + "00Z"
    return None


def _last_rain(reading, previous):
    chosen = None
    if isinstance(previous, dict):
        prior = previous.get("lastRain")
        if isinstance(prior, str) and prior:
            chosen = prior
    rain = _number(reading.get("hourlyrainin"))
    if rain is not None and rain > 0:
        minute = _floor_minute(reading.get("dateutc"))
        if minute is not None and (chosen is None or minute >= chosen):
            chosen = minute
    _put(reading, "lastRain", chosen)


def apply_derived(reading, previous):
    """Set feels-like, dew point, and last rain. Skip a field whose inputs are missing."""
    wind = _number(reading.get("windspeedmph"))
    if wind is None:
        wind = 0.0
    _side(reading, "tempf", "humidity", "feelsLike", "dewPoint", wind, 2)
    _side(reading, "tempinf", "humidityin", "feelsLikein", "dewPointin", 0.0, 1)
    _last_rain(reading, previous)
    return reading
