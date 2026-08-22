"""Migration-only comparison between the legacy RSS transport and Alba.

This helper exists to verify, during the migration, that Alba reports the same
values as the RSS feed for the same station. It lives in the test suite on
purpose: the two transports model their own data and the library offers no
public conversion between them, because a shared shape would misrepresent both.

It is not shipped with the package.
"""

#: Legacy RSS attribute -> dotted path into an Alba observation.
#:
#: Writing the correspondence out makes it reviewable. Two entries deserve
#: attention:
#:
#: * ``wind_max`` is compared against Alba's daily *gust*. The provider has not
#:   confirmed that the RSS value was also a gust, so this pairing is an
#:   assumption, not a verified equivalence.
#: * ``rain`` is compared against the total accumulated since local midnight.
#:   The RSS feed never documented its own window, so a mismatch here may mean
#:   the periods differ rather than that a value is wrong.
FIELD_PAIRS = {
    "temp_current": "temperature.current",
    "temp_max": "temperature.daily_max",
    "temp_min": "temperature.daily_min",
    "humidity_current": "humidity.current",
    "humidity_max": "humidity.daily_max",
    "humidity_min": "humidity.daily_min",
    "pressure_current": "pressure.current",
    "pressure_max": "pressure.daily_max",
    "pressure_min": "pressure.daily_min",
    "wind_current": "wind.speed",
    "wind_max": "wind.daily_gust",
    "wind_bearing": "wind.bearing",
    "rain": "precipitation.daily_total",
}

#: Pairings that rest on an unverified assumption rather than a confirmed one.
ASSUMED_PAIRS = ("wind_max",)


def _resolve(observation, path):
    """Return the value at a dotted *path* inside an Alba observation."""
    value = observation
    for part in path.split("."):
        value = getattr(value, part)
    return value


def compare(rainbow_weather, alba_observation, tolerance=0.0):
    """Return the fields that disagree between the two transports.

    :param rainbow_weather: a ``meteoclimatic.rainbow.Weather``
    :param alba_observation: a ``meteoclimatic.alba.Observation``
    :param tolerance: absolute tolerance for numeric comparison
    :returns: a dict of legacy field name to ``(rss_value, alba_value)`` for
        every field that differs; empty when the two agree

    The weather condition is deliberately not compared: Alba does not report
    one, so a difference there is a known gap rather than a discrepancy.
    """
    differences = {}
    for legacy_field, path in FIELD_PAIRS.items():
        left = getattr(rainbow_weather, legacy_field, None)
        right = _resolve(alba_observation, path)
        if left is None and right is None:
            continue
        if left is None or right is None:
            differences[legacy_field] = (left, right)
            continue
        if abs(left - right) > tolerance:
            differences[legacy_field] = (left, right)
    return differences
