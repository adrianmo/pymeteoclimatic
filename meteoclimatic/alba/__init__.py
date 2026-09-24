"""Meteoclimatic Alba API v3 read path.

This package is independent of any particular consumer or HTTP stack, and has
three layers:

* :mod:`meteoclimatic.alba.models` and :mod:`meteoclimatic.alba.parsing` are the
  model and the parser. They **import** no third-party package, so an
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

An API key is required: the read endpoint is authenticated.

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

# ``AsyncClient`` is deliberately absent from ``__all__``. It resolves lazily
# through ``__getattr__`` and needs the optional ``async`` extra, so listing it
# would make ``from meteoclimatic.alba import *`` require aiohttp in order to
# import the synchronous surface. An explicit
# ``from meteoclimatic.alba import AsyncClient`` still works.
__all__ = [
    "Client",
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


#: Names resolved on demand by ``__getattr__``. Kept out of ``__all__`` so a
#: wildcard import never needs the optional extra, and listed in ``__dir__``
#: so the surface stays discoverable.
_LAZY = ("AsyncClient",)


def __getattr__(name):
    """Resolve the asynchronous client lazily.

    Importing it eagerly would make aiohttp a hard requirement of this package,
    making aiohttp an import-time requirement of this package. Callers that
    never touch the
    asynchronous client never need the extra installed.
    """
    if name in _LAZY:
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
    """Include the lazily resolved names in ``dir()``.

    ``_LAZY`` is deliberately outside ``__all__`` so that a wildcard import
    does not drag in the optional extra, but leaving it out of ``dir()`` as
    well would make the asynchronous client undiscoverable by introspection.
    Discoverability and wildcard safety are separate concerns.
    """
    return sorted(set(globals()) | set(__all__) | set(_LAZY))
