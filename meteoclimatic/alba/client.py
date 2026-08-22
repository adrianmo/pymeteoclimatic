"""Synchronous Meteoclimatic API v3 client, built on the standard library.

This is the default client. It adds no third-party dependency, so the library
remains usable in a plain script:

    from meteoclimatic.alba import Client

    client = Client(api_key)
    observation = client.get_current_data("T415")
    print(observation.weather.temp_current)

Asynchronous callers should use
:class:`meteoclimatic.alba.AsyncClient`, which requires the
optional ``async`` extra.

The credential is sent only as the ``APIkey`` request header, never in a URL, and
never appears in ``repr``, logs or exceptions.
"""

import json
import logging
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from meteoclimatic.version import __version__
from meteoclimatic.alba._http import (
    CURRENT_DATA_PATH,
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    RateLimitBlock,
    build_headers,
    raise_for_status,
    retry_after_seconds,
)
from meteoclimatic.alba.errors import MalformedResponseError, TransportError
from meteoclimatic.alba.parsing import parse_current_data

_LOGGER = logging.getLogger(__name__)

__all__ = ["Client"]


class Client:
    """Read-only synchronous client for the Meteoclimatic API v3.

    :param api_key: the user's API Identifier ("Identificador de API"). This is
        not the separate profile "Key" value, which the API rejects.
    :param base_url: override, mainly for testing
    :param timeout: per-request timeout in seconds
    """

    def __init__(self, api_key, base_url=DEFAULT_BASE_URL, timeout=DEFAULT_TIMEOUT):
        """Initialize the class."""
        if not api_key:
            raise ValueError("api_key cannot be empty")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._block = RateLimitBlock()

    @property
    def blocked_until(self):
        """Return when the current rate-limit block ends, or ``None``.

        Exposed so the state is inspectable rather than hidden.
        """
        return self._block.blocked_until

    def get_current_data(self, station_code):
        """Return the latest observation for *station_code*.

        :param station_code: the new short station code, e.g. ``T415``
        :rtype: meteoclimatic.alba.models.ApiObservation
        """
        payload, headers = self._get(CURRENT_DATA_PATH, station_code)
        return parse_current_data(
            payload, cache_directive=headers.get("Cache-Control")
        )

    def _get(self, path, station_code):
        """Perform a GET request and map failures to typed errors."""
        if not station_code:
            raise ValueError("station_code cannot be empty")

        # Never send while blocked: a request issued during a block extends it.
        self._block.raise_if_blocked()

        url = "%s%s?%s" % (
            self._base_url,
            path,
            urlencode({"stationcode": station_code}),
        )
        request = Request(
            url,
            headers=build_headers(
                self._api_key, "pymeteoclimatic/%s" % (__version__,)
            ),
        )

        try:
            with urlopen(request, timeout=self._timeout) as response:
                body = response.read()
                headers = response.headers
        except HTTPError as error:
            body = self._safe_read(error)
            retry_after = retry_after_seconds(
                error.headers.get("Retry-After") if error.headers else None, body
            )
            if error.code == 429:
                self._block.record(retry_after)
            _LOGGER.debug(
                "Meteoclimatic API returned HTTP %s for station %s",
                error.code, station_code,
            )
            raise_for_status(error.code, station_code, retry_after)
            raise  # pragma: no cover - raise_for_status always raises
        except socket.timeout as error:
            raise TransportError("request timed out") from error
        except URLError as error:
            # Deliberately excludes the URL and headers from the message.
            raise TransportError(
                "transport failure: %s" % (type(error).__name__,)
            ) from error

        _LOGGER.debug(
            "Meteoclimatic API request for station %s succeeded", station_code
        )
        return self._decode(body), headers

    @staticmethod
    def _decode(body):
        """Decode a JSON body, or raise a malformed-response error."""
        try:
            return json.loads(body)
        except (ValueError, TypeError) as error:
            raise MalformedResponseError(
                "response body is not valid JSON"
            ) from error

    @staticmethod
    def _safe_read(error):
        """Return the decoded error body, or ``None`` when unusable."""
        try:
            return json.loads(error.read())
        except Exception:  # noqa: BLE001 - error bodies are not guaranteed JSON
            return None

    def __repr__(self):
        """Return a representation that never discloses the credential."""
        return "%s(base_url=%r, api_key=<redacted>)" % (
            self.__class__.__name__,
            self._base_url,
        )

    __str__ = __repr__
