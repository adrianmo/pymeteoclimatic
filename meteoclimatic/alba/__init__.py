"""Meteoclimatic Alba API v3 read path.

This package is independent of any particular consumer or HTTP stack, and has
three layers:

* :mod:`meteoclimatic.alba.models` and :mod:`meteoclimatic.alba.parsing` are the
  model and the parser. They have **no third-party dependency**, so an
  application can drive them with whatever HTTP client it already uses.
* :class:`Client` is a synchronous client built on the standard library. It is
  the default and adds no dependency.
* :class:`AsyncClient` is the asynchronous alternative, built on aiohttp. It
  requires the optional extra ``pymeteoclimatic[async]`` and resolves lazily, so
  importing this package never requires aiohttp.

Usage::

    from meteoclimatic.alba import Client

    client = Client(api_key)
    observation = client.get_current_data("T415")
    observation.temperature.current
    observation.temperature.daily_max
    observation.station.timezone

An API key is required: both read endpoints are authenticated.

Transport selection is always explicit. A failure here never falls back to the
legacy RSS feed in :mod:`meteoclimatic.rainbow`.
"""

from meteoclimatic.alba._http import (  # noqa: F401
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    RECOMMENDED_POLL_INTERVAL,
)
from meteoclimatic.alba.client import Client  # noqa: F401
from meteoclimatic.alba.errors import (  # noqa: F401
    ApiError,
    AuthenticationError,
    BadRequestError,
    MalformedResponseError,
    RateLimitError,
    StationNotFound,
    TransportError,
)
from meteoclimatic.alba.models import (  # noqa: F401
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
from meteoclimatic.alba.parsing import (  # noqa: F401
    FIELD_MAP,
    parse_current_data,
)

__all__ = [
    "Client",
    "AsyncClient",
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT",
    "RECOMMENDED_POLL_INTERVAL",
    "ApiError",
    "AuthenticationError",
    "BadRequestError",
    "MalformedResponseError",
    "RateLimitError",
    "StationNotFound",
    "TransportError",
    "AirQuality",
    "Humidity",
    "Observation",
    "Precipitation",
    "Pressure",
    "Quality",
    "SensorFlags",
    "Solar",
    "Station",
    "Sun",
    "Temperature",
    "Webcam",
    "Wind",
    "FIELD_MAP",
    "parse_current_data",
]


def __getattr__(name):
    """Resolve the asynchronous client lazily.

    Importing it eagerly would make aiohttp a hard requirement of this package,
    defeating the dependency-free core. Callers that never touch the
    asynchronous client never need the extra installed.
    """
    if name == "AsyncClient":
        try:
            from meteoclimatic.alba.async_client import AsyncClient
        except ImportError as error:  # pragma: no cover - depends on install
            raise ImportError(
                "AsyncClient requires the optional 'async' extra. Install it "
                "with: pip install pymeteoclimatic[async]"
            ) from error
        return AsyncClient
    raise AttributeError("module %r has no attribute %r" % (__name__, name))


def __dir__():
    """Include the lazily resolved names in ``dir()``."""
    return sorted(set(globals()) | set(__all__))
