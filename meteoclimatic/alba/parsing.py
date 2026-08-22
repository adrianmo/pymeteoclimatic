"""Parsing of Alba API v3 payloads into the observation model.

Field mapping, units and semantics follow the agreed contract:

* units are fixed per field and no conversion is performed (°C, %, hPa, km/h,
  degrees, mm, W/m², µg/m³);
* an unavailable value arrives as ``null`` with the key retained, and maps to
  ``None`` - never to ``0.0``;
* a value may arrive as an integer or a float, so it is read as a JSON number
  and normalised to ``float``, except counts;
* every ``daily_`` value refers to the station's local civil day; and
* Alba exposes no current weather condition, so none is produced.

Unknown fields are ignored, which keeps the parser forward compatible, and the
untouched payload is kept on ``Observation.raw`` so nothing is lost. A missing or
unusable *required* structure raises
:class:`~meteoclimatic.alba.errors.MalformedResponseError` rather than being
silently treated as an absent measurement.
"""

from datetime import date, datetime, timezone

from meteoclimatic.alba.errors import MalformedResponseError
from meteoclimatic.alba.models import (
    AirQuality,
    Humidity,
    Observation,
    Precipitation,
    Pressure,
    Quality,
    SensorFlags,
    Solar,
    Station,
    Sun,
    Temperature,
    Webcam,
    Wind,
)

__all__ = ["parse_current_data", "FIELD_MAP"]


#: Group name -> {model attribute: Alba ``wxdata`` key}. Every key Alba returns
#: is covered; ``local_day`` is read separately onto the observation itself.
FIELD_MAP = {
    "temperature": {
        "current": "TMP",
        "daily_max": "DHTM",
        "daily_min": "DLTM",
        "average": "avg_TMP",
        "delta_3h": "temperature_delta_3h",
    },
    "humidity": {
        "current": "HUM",
        "daily_max": "DHHM",
        "daily_min": "DLHM",
        "average": "avg_HUM",
        "delta_3h": "humidity_delta_3h",
    },
    "pressure": {
        "current": "BAR",
        "daily_max": "DHBR",
        "daily_min": "DLBR",
        "average": "avg_BAR",
        "mean_6h": "pressure_mean_6h",
        "delta_3h": "pressure_delta_3h",
        "delta_6h": "pressure_delta_6h",
    },
    "wind": {
        "speed": "WND",
        "daily_gust": "DGST",
        "bearing": "AZI",
        "average_speed": "avg_WND",
        "average_bearing": "avg_AZI",
    },
    "precipitation": {
        "daily_total": "DPCP",
        "current": "PCP",
        "average": "avg_PCP",
        "intensity_max": "pcp_int_max",
    },
    "solar": {
        "radiation": "SUN",
        "daily_radiation": "DSUN",
        "average_radiation": "avg_SUN",
        "uv_index": "UVI",
        "daily_uv_index": "DUVI",
        "average_uv_index": "avg_UVI",
    },
    "air_quality": {
        "aqi": "AQI",
        "daily_aqi_max": "DHAQI",
        "daily_aqi_min": "DLAQI",
        "average_aqi": "avg_AQI",
        "pm1": "PM1",
        "pm10": "PM10",
        "pm25": "PM25",
        "daily_pm1_max": "DHPM1",
        "daily_pm10_max": "DHPM10",
        "daily_pm25_max": "DHPM25",
        "daily_pm1_min": "DLPM1",
        "daily_pm10_min": "DLPM10",
        "daily_pm25_min": "DLPM25",
        "average_pm1": "avg_PM1",
        "average_pm10": "avg_PM10",
        "average_pm25": "avg_PM25",
    },
}

_GROUP_TYPES = {
    "temperature": Temperature,
    "humidity": Humidity,
    "pressure": Pressure,
    "wind": Wind,
    "precipitation": Precipitation,
    "solar": Solar,
    "air_quality": AirQuality,
}


def _require_mapping(payload, what):
    """Return *payload* when it is a mapping, otherwise raise."""
    if not isinstance(payload, dict):
        raise MalformedResponseError(
            "expected a JSON object for %s, got %s" % (what, type(payload).__name__)
        )
    return payload


def _envelope_data(payload):
    """Return the ``data`` object from a read envelope."""
    body = _require_mapping(payload, "the response body")
    if "data" not in body:
        raise MalformedResponseError("response envelope has no 'data' object")
    return _require_mapping(body["data"], "'data'")


def _optional_number(container, key):
    """Return a numeric value as a float, or ``None`` when absent or null.

    A present ``null`` and an absent key are both "no value". A non-numeric value
    is a contract violation and is reported rather than silently dropped.
    """
    value = container.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        raise MalformedResponseError("field %s is a boolean, expected a number" % (key,))
    if isinstance(value, (int, float)):
        return float(value)
    raise MalformedResponseError(
        "field %s is %s, expected a number" % (key, type(value).__name__)
    )


def _optional_count(container, key):
    """Return an integer count, or ``None`` when absent or null."""
    value = container.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def _optional_int(container, key):
    """Return an integer identifier, or ``None`` when absent or null."""
    value = container.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _optional_text(container, key):
    """Return a string value, or ``None`` when absent, null or not a string."""
    value = container.get(key)
    return value if isinstance(value, str) and value else None


def _parse_datetime(value, field):
    """Parse an ISO 8601 timestamp that carries an explicit offset."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise MalformedResponseError(
            "field %s is %s, expected an ISO 8601 string" % (field, type(value).__name__)
        )
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise MalformedResponseError(
            "field %s is not a valid ISO 8601 timestamp" % (field,)
        ) from error


def _parse_optional_datetime(value):
    """Parse a timestamp, returning ``None`` when it is unusable."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _parse_date(value, field):
    """Parse a plain ``YYYY-MM-DD`` local civil date."""
    if value is None or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise MalformedResponseError(
            "field %s is not a valid ISO 8601 date" % (field,)
        ) from error


def _parse_sensors(data):
    """Return the per-sensor flags, which are carried but never acted upon."""
    sensors = data.get("sensors")
    if not isinstance(sensors, dict):
        return {}
    return {
        key: SensorFlags(
            status=value.get("status"),
            quality=value.get("quality"),
            params=value.get("params"),
        )
        for key, value in sensors.items()
        if isinstance(value, dict)
    }


def _parse_groups(wxdata):
    """Build every measurement group from ``wxdata``."""
    groups = {}
    for group, fields in FIELD_MAP.items():
        values = {
            attribute: _optional_number(wxdata, key)
            for attribute, key in fields.items()
        }
        groups[group] = _GROUP_TYPES[group](**values)
    # Values that are not plain measurements.
    groups["pressure"].trend = _optional_text(wxdata, "bar_trend")
    groups["precipitation"].drought_days = _optional_count(wxdata, "droughtdays")
    return groups


def _parse_station(data):
    """Build a :class:`Station` from a ``data`` object."""
    code = data.get("stationCode")
    if not code:
        raise MalformedResponseError("'data' has no usable stationCode")

    webcam = data.get("webcam")
    if isinstance(webcam, dict):
        webcam = Webcam(
            url=_optional_text(webcam, "URL"),
            visible=webcam.get("show"),
        )
    else:
        webcam = None

    return Station(
        code=code,
        name=data.get("name"),
        timezone=data.get("timezone"),
        latitude=_optional_number(data, "coord_Y"),
        longitude=_optional_number(data, "coord_X"),
        elevation=_optional_number(data, "elevation"),
        webcam=webcam,
    )


def _parse_sun(data):
    """Build a :class:`Sun` from the provider's extra block."""
    extra = data.get("extra")
    if not isinstance(extra, dict):
        return Sun()
    return Sun(
        sunrise=_parse_optional_datetime(extra.get("sunrise")),
        sunset=_parse_optional_datetime(extra.get("sunset")),
        day_length=_optional_text(extra, "sunlength"),
    )


def parse_current_data(payload, fetched_at=None, cache_directive=None):
    """Parse a ``currentdata`` response into an :class:`Observation`.

    :param payload: the decoded JSON body
    :param fetched_at: when the response was received; defaults to now in UTC
    :param cache_directive: the HTTP ``Cache-Control`` header value
    :raises MalformedResponseError: if a required structure is missing or unusable
    """
    data = _envelope_data(payload)
    wxdata = _require_mapping(data.get("wxdata"), "'data.wxdata'")

    extra = data.get("extra")
    forecast = (
        _optional_text(extra, "forecast") if isinstance(extra, dict) else None
    )

    return Observation(
        station=_parse_station(data),
        updated=_parse_datetime(data.get("updated"), "data.updated"),
        fetched_at=fetched_at or datetime.now(timezone.utc),
        local_day=_parse_date(wxdata.get("local_day"), "wxdata.local_day"),
        ttl=_optional_int(data, "ttl"),
        quality=Quality(
            main=_optional_int(data, "mainQuality"),
            additional=_optional_int(data, "additionalQuality"),
            transitional=_optional_int(data, "transitionalQuality"),
            sensors=_parse_sensors(data),
        ),
        sun=_parse_sun(data),
        forecast=forecast,
        cache_directive=cache_directive,
        raw=data,
        **_parse_groups(wxdata)
    )
