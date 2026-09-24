"""Synchronous Meteoclimatic API v3 client, built on the standard library.

This is the default client. It imports no third-party package, so the library
remains usable in a plain script:

    from meteoclimatic.alba import Client

    client = Client(api_key)
    observation = client.get_current_data("T415")
    print(observation.temperature.current)

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
from urllib.request import HTTPRedirectHandler, Request, build_opener

from meteoclimatic.version import __version__
from meteoclimatic.alba._http import (
    CURRENT_DATA_PATH,
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    RateLimitBlock,
    build_headers,
    raise_for_status,
    retry_after_seconds,
    validate_api_key,
    with_status,
)
from meteoclimatic.alba.errors import (
    ApiError,
    MalformedResponseError,
    TransportError,
)
from meteoclimatic.alba.parsing import parse_current_data

_LOGGER = logging.getLogger(__name__)


class _NoRedirects(HTTPRedirectHandler):
    """Refuse HTTP redirects instead of following them.

    ``urllib`` copies the original request headers onto a redirected request,
    so following a 3xx would send the ``APIkey`` header to whatever host the
    response names. Returning ``None`` here leaves the 3xx to surface as an
    error, which both clients then map to a transport failure.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Return ``None`` so that no redirect is ever followed."""
        return None


#: Opener used for every request. Built once, and deliberately not
#: ``urllib.request.urlopen``, whose default handler follows redirects.
_OPENER = build_opener(_NoRedirects)


def _urlopen(request, timeout):
    """Send *request* without following redirects."""
    return _OPENER.open(request, timeout=timeout)


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
        # Validated here so a malformed credential fails at construction
        # rather than inside the header encoder, which quotes the value it
        # rejects and would put the secret in a traceback.
        self._api_key = validate_api_key(api_key)
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
        :rtype: meteoclimatic.alba.models.Observation
        """
        payload, headers, status = self._get(CURRENT_DATA_PATH, station_code)
        try:
            return parse_current_data(
                payload, cache_directive=headers.get("Cache-Control")
            )
        except ApiError as error:
            # The response arrived with a status; a failure while interpreting
            # it should report that status rather than None.
            raise with_status(error, status) from None

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
            with _urlopen(request, self._timeout) as response:
                body = response.read()
                headers = response.headers
                status = response.status
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

        if status != 200:
            # urllib raises only for 4xx and 5xx, so a 201 or 204 arrives here
            # looking like success. The asynchronous client requires exactly
            # 200, and parsing an unexpected 2xx body would report it as
            # malformed rather than as the unexpected status it is.
            _LOGGER.debug(
                "Meteoclimatic API returned HTTP %s for station %s",
                status, station_code,
            )
            raise_for_status(status, station_code)

        _LOGGER.debug(
            "Meteoclimatic API request for station %s succeeded", station_code
        )
        return self._decode(body, status), headers, status

    @staticmethod
    def _decode(body, status=None):
        """Decode a JSON body, or raise a malformed-response error.

        The status is threaded through so that a malformed body reports the
        same metadata here as it does on the asynchronous client. Without it
        the two transports disagreed about ``ApiError.status`` for an
        identical failure.
        """
        try:
            return json.loads(body)
        except (ValueError, TypeError) as error:
            raise MalformedResponseError(
                "response body is not valid JSON", status=status
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
