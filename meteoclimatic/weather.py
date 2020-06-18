from datetime import datetime
from enum import Enum, auto


class AutoName(Enum):
    def _generate_next_value_(name, start, count, last_values):
        return name.lower()


class Condition(AutoName):
    fog = auto()
    hazemoon = auto()
    hazesun = auto()
    lightning = auto()
    mist = auto()
    moon = auto()
    mooncloud = auto()
    rain = auto()
    sun = auto()
    suncloud = auto()
    storm = auto()


class Weather:
    """
    A class encapsulating raw weather data.

    :param reference_time: Timestamp of weather measurement
    :type reference_time: `datetime.datetime`
    :param condition: Single-word weather condition
    :type condition: `meteoclimatic.Condition` or `str`
    :param temp_current: Current temperature in Celsius
    :type temp_current: `float`
    :param temp_max: Maximum temperature in Celsius for the past 24 hours
    :type temp_max: `float`
    :param temp_min: Minimum temperature in Celsius for the past 24 hours
    :type temp_min: `float`
    :param humidity_current: Current humidity in percentage points
    :type humidity_current: `float`
    :param humidity_max: Maximum humidity in percentage points for the past 24 hours
    :type humidity_max: `float`
    :param humidity_min: Minimum humidity in percentage points for the past 24 hours
    :type humidity_min: `float`
    :param pressure_current: Current atmospheric pressure in hPa units
    :type pressure_current: `float`
    :param pressure_max: Maximum atmospheric pressure in hPa units for the past 24 hours
    :type pressure_max: `float`
    :param pressure_min: Minimum atmospheric pressure in hPa units for the past 24 hours
    :type pressure_min: `float`
    :param wind_current: Current wind speed in km/h units
    :type wind_current: `float`
    :param wind_max: Maximum wind speed in km/h units for the past 24 hours
    :type wind_max: `float`
    :param wind_bearing: Wind bearing in degree units
    :type wind_bearing: `float`
    :param rain: Precipitation in mm units for the past 24 hours
    :type rain: `float`
    :returns: a *Weather* instance
    :raises: *ValueError* when invalid values are provided for non-negative or ranged
        quantities
    """

    def __init__(self, reference_time: datetime, condition: Condition,
                 temp_current: float, temp_max: float, temp_min: float,
                 humidity_current: float, humidity_max: float, humidity_min: float,
                 pressure_current: float, pressure_max: float, pressure_min: float,
                 wind_current: float, wind_max: float, wind_bearing: float,
                 rain: float):
        """Initialize the class."""
        if not isinstance(reference_time, datetime):
            raise ValueError(
                "reference_time is not an instance of datetime.datetime")
        self.reference_time = reference_time

        self.condition = condition

        self.temp_current = temp_current
        self.temp_max = temp_max
        self.temp_min = temp_min

        for humidity in [humidity_current, humidity_max, humidity_min]:
            if humidity is not None and (humidity < 0.0 or humidity > 100.0):
                raise ValueError("humidity must be between 0 and 100")
        self.humidity_current = humidity_current
        self.humidity_max = humidity_max
        self.humidity_min = humidity_min

        self.pressure_current = pressure_current
        self.pressure_max = pressure_max
        self.pressure_min = pressure_min

        for wind in [wind_current, wind_max]:
            if wind is not None and wind < 0.0:
                raise ValueError("wind must be greatear than 0")
        self.wind_current = wind_current
        self.wind_max = wind_max

        if wind_bearing is not None and (wind_bearing < 0.0 or wind_bearing > 360.0):
            raise ValueError("wind bearing must be between 0 and 360")
        self.wind_bearing = wind_bearing

        if rain is not None and rain < 0.0:
            raise ValueError("rain must be greatear than 0")
        self.rain = rain

    def __eq__(self, other):
        if not isinstance(other, Weather):
            return NotImplemented
        prop_names = list(self.__dict__)
        for prop in prop_names:
            if self.__dict__[prop] != other.__dict__[prop]:
                return False
        return True

    def __repr__(self):
        return "%s(%r)" % (self.__class__, self.__dict__)
