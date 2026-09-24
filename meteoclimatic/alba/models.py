"""Observation model for the Meteoclimatic Alba API v3.

This model describes what Alba actually reports, and is deliberately independent
of the legacy RSS transport. The two report different information, so a shared
type would misrepresent both: Alba has a station time zone, a local civil day and
station quality categories, and reports no weather condition.

Values are grouped by family, and every value Alba returns is covered. Anything
not modelled here, including fields the provider may add later, stays reachable
through ``Observation.raw``.

Naming rules:

* a field whose API key begins with ``D`` is a **daily** value and carries a
  ``daily_`` prefix; daily values cover the station's local civil day and reset
  at local midnight;
* a field derived from ``avg_*`` is named ``average``, or ``average_<quantity>``
  when its group holds more than one quantity; and
* the absence of a period in a name means the period is **not known**, not that
  the value is current.

A value the station does not provide is ``None``. ``None`` never means zero, and
a real zero is preserved. Numeric values are floats, except counts.
"""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

__all__ = [
    "Station",
    "Webcam",
    "Sun",
    "Temperature",
    "Humidity",
    "Pressure",
    "Wind",
    "Precipitation",
    "Solar",
    "AirQuality",
    "SensorFlags",
    "Quality",
    "Observation",
]


class _Group:
    """Shared behaviour for the value groups."""

    __slots__ = ()

    def as_dict(self):
        """Return the group's values as a plain dictionary."""
        return {name: getattr(self, name) for name in self.__slots__}

    def __eq__(self, other):
        if type(self) is not type(other):
            return NotImplemented
        return self.as_dict() == other.as_dict()

    def __repr__(self):
        present = {k: v for k, v in self.as_dict().items() if v is not None}
        return "%s(%r)" % (type(self).__name__, present)


class Temperature(_Group):
    """Air temperature, in degrees Celsius.

    :param current: current temperature
    :param daily_max: highest temperature of the local civil day
    :param daily_min: lowest temperature of the local civil day
    :param average: mean temperature; the period is not confirmed
    :param delta_3h: change over the last three hours; not confirmed
    """

    __slots__ = ("current", "daily_max", "daily_min", "average", "delta_3h")

    def __init__(self, current=None, daily_max=None, daily_min=None,
                 average=None, delta_3h=None):
        """Initialize the class."""
        self.current = current
        self.daily_max = daily_max
        self.daily_min = daily_min
        self.average = average
        self.delta_3h = delta_3h


class Humidity(_Group):
    """Relative humidity, as a percentage.

    :param current: current relative humidity
    :param daily_max: highest value of the local civil day
    :param daily_min: lowest value of the local civil day
    :param average: mean value; the period is not confirmed
    :param delta_3h: change over the last three hours; not confirmed
    """

    __slots__ = ("current", "daily_max", "daily_min", "average", "delta_3h")

    def __init__(self, current=None, daily_max=None, daily_min=None,
                 average=None, delta_3h=None):
        """Initialize the class."""
        self.current = current
        self.daily_max = daily_max
        self.daily_min = daily_min
        self.average = average
        self.delta_3h = delta_3h


class Pressure(_Group):
    """Atmospheric pressure, in hectopascals.

    :param current: current pressure
    :param daily_max: highest pressure of the local civil day
    :param daily_min: lowest pressure of the local civil day
    :param average: mean pressure; the period is not confirmed
    :param mean_6h: six-hour mean; not confirmed
    :param delta_3h: change over the last three hours; not confirmed
    :param delta_6h: change over the last six hours; not confirmed
    :param trend: barometric trend, one of ``Steady``, ``Rising``,
        ``Rising Quickly``, ``Falling`` or ``Falling Quickly``
    """

    __slots__ = ("current", "daily_max", "daily_min", "average", "mean_6h",
                 "delta_3h", "delta_6h", "trend")

    def __init__(self, current=None, daily_max=None, daily_min=None,
                 average=None, mean_6h=None, delta_3h=None, delta_6h=None,
                 trend=None):
        """Initialize the class."""
        self.current = current
        self.daily_max = daily_max
        self.daily_min = daily_min
        self.average = average
        self.mean_6h = mean_6h
        self.delta_3h = delta_3h
        self.delta_6h = delta_6h
        self.trend = trend


class Wind(_Group):
    """Wind speed, gust and direction.

    Speed and gust are metres per second. The unit was established by
    measurement, not from a published figure: three stations compared
    against the RSS feed at the same instant gave a constant ratio of
    3.600, 3.582 and 3.636, and the km/h-to-m/s factor is exactly 3.6.
    No conversion is applied here, so a consumer displaying km/h must
    convert.

    :param speed: current wind speed, in m/s
    :param daily_gust: strongest gust of the local civil day, in m/s
    :param bearing: current wind bearing, in degrees from 0 to 360
    :param average_speed: mean speed; the period is not confirmed
    :param average_bearing: mean bearing; the period is not confirmed
    """

    __slots__ = ("speed", "daily_gust", "bearing", "average_speed",
                 "average_bearing")

    def __init__(self, speed=None, daily_gust=None, bearing=None,
                 average_speed=None, average_bearing=None):
        """Initialize the class."""
        self.speed = speed
        self.daily_gust = daily_gust
        self.bearing = bearing
        self.average_speed = average_speed
        self.average_bearing = average_bearing


class Precipitation(_Group):
    """Precipitation, in millimetres.

    :param daily_total: accumulated since local midnight
    :param current: current precipitation; whether this is a rate or an interval
        accumulation is not confirmed
    :param average: mean value; the period is not confirmed
    :param intensity_max: peak intensity; the unit is not confirmed
    :param drought_days: consecutive days without precipitation, as a count; not
        confirmed
    """

    __slots__ = ("daily_total", "current", "average", "intensity_max",
                 "drought_days")

    def __init__(self, daily_total=None, current=None, average=None,
                 intensity_max=None, drought_days=None):
        """Initialize the class."""
        self.daily_total = daily_total
        self.current = current
        self.average = average
        self.intensity_max = intensity_max
        self.drought_days = drought_days


class Solar(_Group):
    """Solar radiation and ultraviolet index.

    :param radiation: current solar radiation, in W/m²
    :param daily_radiation: daily radiation value; whether this is a maximum or
        an accumulation is not confirmed, so the name does not claim either
    :param average_radiation: mean radiation; the period is not confirmed
    :param uv_index: current UV index. The scale is 0-2 very low, 3-5 low, 6-7
        moderate, 8-10 high, above 10 extreme.
    :param daily_uv_index: daily UV index value; maximum or accumulation is not
        confirmed
    :param average_uv_index: mean UV index; the period is not confirmed
    """

    __slots__ = ("radiation", "daily_radiation", "average_radiation",
                 "uv_index", "daily_uv_index", "average_uv_index")

    def __init__(self, radiation=None, daily_radiation=None,
                 average_radiation=None, uv_index=None, daily_uv_index=None,
                 average_uv_index=None):
        """Initialize the class."""
        self.radiation = radiation
        self.daily_radiation = daily_radiation
        self.average_radiation = average_radiation
        self.uv_index = uv_index
        self.daily_uv_index = daily_uv_index
        self.average_uv_index = average_uv_index


class AirQuality(_Group):
    """Air quality index and particulate matter.

    Particulate values are in µg/m³. The ``aqi`` scale is still being defined by
    Meteoclimatic, and the period covered by the ``average_`` values is not
    confirmed. The ``daily_`` values cover the station's local civil day, as
    every ``daily_`` value in this model does.

    Not every station has air-quality hardware; those report ``None``.
    """

    __slots__ = (
        "aqi", "daily_aqi_max", "daily_aqi_min", "average_aqi",
        "pm1", "pm10", "pm25",
        "daily_pm1_max", "daily_pm10_max", "daily_pm25_max",
        "daily_pm1_min", "daily_pm10_min", "daily_pm25_min",
        "average_pm1", "average_pm10", "average_pm25",
    )

    def __init__(self, aqi=None, daily_aqi_max=None, daily_aqi_min=None,
                 average_aqi=None, pm1=None, pm10=None, pm25=None,
                 daily_pm1_max=None, daily_pm10_max=None, daily_pm25_max=None,
                 daily_pm1_min=None, daily_pm10_min=None, daily_pm25_min=None,
                 average_pm1=None, average_pm10=None, average_pm25=None):
        """Initialize the class."""
        self.aqi = aqi
        self.daily_aqi_max = daily_aqi_max
        self.daily_aqi_min = daily_aqi_min
        self.average_aqi = average_aqi
        self.pm1 = pm1
        self.pm10 = pm10
        self.pm25 = pm25
        self.daily_pm1_max = daily_pm1_max
        self.daily_pm10_max = daily_pm10_max
        self.daily_pm25_max = daily_pm25_max
        self.daily_pm1_min = daily_pm1_min
        self.daily_pm10_min = daily_pm10_min
        self.daily_pm25_min = daily_pm25_min
        self.average_pm1 = average_pm1
        self.average_pm10 = average_pm10
        self.average_pm25 = average_pm25


class Sun(_Group):
    """Sunrise, sunset and day length for the station.

    :param sunrise: sunrise time, with an explicit UTC offset
    :param sunset: sunset time, with an explicit UTC offset
    :param day_length: day length as a human-readable string, not a number
    """

    __slots__ = ("sunrise", "sunset", "day_length")

    def __init__(self, sunrise=None, sunset=None, day_length=None):
        """Initialize the class."""
        self.sunrise = sunrise
        self.sunset = sunset
        self.day_length = day_length


class Webcam(_Group):
    """Webcam associated with a station.

    :param url: webcam address
    :param visible: whether the station publishes it
    """

    __slots__ = ("url", "visible")

    def __init__(self, url=None, visible=None):
        """Initialize the class."""
        self.url = url
        self.visible = visible


class Station:
    """A station as described by Alba.

    :param code: the Alba station code, e.g. ``T415``
    :param name: station name
    :param timezone: IANA time-zone name, e.g. ``Europe/Madrid``. Stations span
        several zones, so this must not be assumed.
    :param latitude: latitude in decimal degrees
    :param longitude: longitude in decimal degrees
    :param elevation: station elevation; the unit is not confirmed
    :param webcam: a :class:`Webcam`, when the station has one

    Consumers must not re-key their own storage on ``code``. An application that
    already identifies a station by another identifier should keep doing so and
    treat ``code`` as an additional attribute; re-keying would break history that
    is keyed on the old one.
    """

    def __init__(self, code, name=None, timezone=None,
                 latitude=None, longitude=None, elevation=None, webcam=None):
        """Initialize the class."""
        if not code:
            raise ValueError("station code cannot be empty")
        self.code = code
        self.name = name
        self.timezone = timezone
        self.latitude = latitude
        self.longitude = longitude
        self.elevation = elevation
        self.webcam = webcam

    @property
    def tzinfo(self):
        """Return the station time zone as a ``ZoneInfo``, or ``None``.

        Returns ``None`` when no zone was reported or the name is unknown to the
        local tz database, rather than guessing one.
        """
        if not self.timezone:
            return None
        try:
            return ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            # TypeError covers a zone of the wrong type entirely. The parser
            # now rejects that at the boundary, but the documented promise of
            # this property is None for an unusable zone, and a Station can
            # also be constructed directly.
            return None

    def __eq__(self, other):
        if not isinstance(other, Station):
            return NotImplemented
        return self.__dict__ == other.__dict__

    def __repr__(self):
        return "%s(code=%r, name=%r, timezone=%r)" % (
            type(self).__name__, self.code, self.name, self.timezone,
        )


class SensorFlags(_Group):
    """Per-sensor flags reported by Alba.

    .. warning::
       These are carried but **not acted upon**, and consumers should do the
       same for now. Their meaning is undefined by the provider: a real station
       reported ``status=True`` with ``quality=False`` on every one of its
       sensors while returning perfectly valid measurements, so treating
       ``quality=False`` as invalid would discard everything.

       Membership of the sensor map is not an availability signal either:
       stations with no ``SUN`` or ``UVI`` sensor still report values for those
       fields. Availability is decided solely by a value being present and not
       ``None``.
    """

    __slots__ = ("status", "quality", "params")

    def __init__(self, status=None, quality=None, params=None):
        """Initialize the class."""
        self.status = status
        self.quality = quality
        self.params = params


class Quality:
    """Station quality classification, plus the raw per-sensor flags.

    :param main: integer category identifier, ``0`` when none is assigned
    :param additional: integer category identifier, ``0`` when none
    :param transitional: integer category identifier, ``0`` when none
    :param sensors: mapping of sensor key to :class:`SensorFlags`

    The three identifiers classify the *station*, for example "Destacada" or
    "Termopluviométrica". They are not per-reading validity and must not be used
    to filter measurements.
    """

    def __init__(self, main=None, additional=None, transitional=None,
                 sensors=None):
        """Initialize the class."""
        self.main = main
        self.additional = additional
        self.transitional = transitional
        self.sensors = dict(sensors) if sensors else {}

    def __eq__(self, other):
        if not isinstance(other, Quality):
            return NotImplemented
        return self.__dict__ == other.__dict__

    def __repr__(self):
        return "%s(main=%r, additional=%r, transitional=%r)" % (
            type(self).__name__, self.main, self.additional, self.transitional,
        )


class Observation:
    """A single reading of a station through the Alba API.

    Measurements are grouped by family::

        observation.temperature.daily_max
        observation.wind.daily_gust
        observation.precipitation.daily_total
        observation.air_quality.pm25

    :param station: the :class:`Station` this reading belongs to
    :param temperature: a :class:`Temperature`
    :param humidity: a :class:`Humidity`
    :param pressure: a :class:`Pressure`
    :param wind: a :class:`Wind`
    :param precipitation: a :class:`Precipitation`
    :param solar: a :class:`Solar`
    :param air_quality: an :class:`AirQuality`
    :param updated: the provider's observation timestamp, with an explicit UTC
        offset that follows the station's zone and daylight saving
    :param fetched_at: when the client received the response
    :param local_day: the station's local civil day, which defines the period
        covered by every ``daily_`` value
    :param ttl: seconds approximating the next update, for scheduling
    :param quality: the :class:`Quality` metadata
    :param sun: a :class:`Sun` with sunrise, sunset and day length
    :param forecast: the provider's forecast text. This is **not** a current
        weather condition and must not be used as one.
    :param cache_directive: the response ``Cache-Control`` value
    :param raw: the untouched ``data`` object, so anything not modelled here,
        including fields added by the provider later, stays reachable
    """

    def __init__(self, station, temperature=None, humidity=None, pressure=None,
                 wind=None, precipitation=None, solar=None, air_quality=None,
                 updated=None, fetched_at=None, local_day=None, ttl=None,
                 quality=None, sun=None, forecast=None, cache_directive=None,
                 raw=None):
        """Initialize the class."""
        if not isinstance(station, Station):
            raise ValueError("station is not a meteoclimatic.alba.Station")
        if updated is not None and not isinstance(updated, datetime):
            raise ValueError("updated is not an instance of datetime.datetime")
        if local_day is not None and not isinstance(local_day, date):
            raise ValueError("local_day is not an instance of datetime.date")
        # fetched_at and ttl are the two inputs to expires_at, and neither was
        # checked while updated and local_day were. A naive fetched_at, which
        # is what datetime.now() gives, produced a naive expires_at and made
        # seconds_until_refresh raise deep inside arithmetic instead of at the
        # point the bad value entered.
        if fetched_at is not None:
            if not isinstance(fetched_at, datetime):
                raise ValueError(
                    "fetched_at is not an instance of datetime.datetime")
            if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
                raise ValueError(
                    "fetched_at must be timezone aware; use "
                    "datetime.now(timezone.utc) rather than datetime.now()")
        if ttl is not None:
            if isinstance(ttl, bool) or not isinstance(ttl, (int, float)):
                raise ValueError("ttl is not a number of seconds")
            if ttl < 0:
                raise ValueError("ttl cannot be negative")
        self.station = station
        self.temperature = temperature if temperature is not None else Temperature()
        self.humidity = humidity if humidity is not None else Humidity()
        self.pressure = pressure if pressure is not None else Pressure()
        self.wind = wind if wind is not None else Wind()
        self.precipitation = (
            precipitation if precipitation is not None else Precipitation()
        )
        self.solar = solar if solar is not None else Solar()
        self.air_quality = air_quality if air_quality is not None else AirQuality()
        self.updated = updated
        self.fetched_at = fetched_at or datetime.now(timezone.utc)
        self.local_day = local_day
        self.ttl = ttl
        self.quality = quality if quality is not None else Quality()
        self.sun = sun if sun is not None else Sun()
        self.forecast = forecast
        self.cache_directive = cache_directive
        self.raw = raw if raw is not None else {}

    @property
    def expires_at(self):
        """Return when this reading is expected to be superseded, or ``None``."""
        if self.ttl is None:
            return None
        return self.fetched_at + timedelta(seconds=self.ttl)

    def seconds_until_refresh(self, now=None, minimum=0):
        """Return how long to wait before polling again, in seconds.

        This is a hint, not a schedule: the library never polls by itself. An
        application with its own scheduler can use it to set a dynamic interval
        instead of a fixed one.

        :param now: reference time, defaulting to the current UTC time
        :param minimum: floor applied to the result, so a small or stale ttl
            cannot turn into a busy loop
        :returns: ``None`` when no ttl was reported
        """
        if self.ttl is None:
            return None
        reference = now or datetime.now(timezone.utc)
        return max((self.expires_at - reference).total_seconds(), minimum)

    def __getattr__(self, name):
        """Explain the absent weather condition rather than failing opaquely."""
        if name == "condition":
            raise AttributeError(
                "Alba does not report a weather condition, so there is no "
                "'condition' attribute. The value is not missing or unobserved: "
                "the API has no such field. Do not derive it from the forecast "
                "text. The legacy RSS transport does provide one."
            )
        raise AttributeError(
            "%r object has no attribute %r" % (type(self).__name__, name)
        )

    def __eq__(self, other):
        if not isinstance(other, Observation):
            return NotImplemented
        return self.__dict__ == other.__dict__

    def __repr__(self):
        return "%s(station=%r, updated=%r)" % (
            type(self).__name__, self.station, self.updated,
        )
