"""Asynchronous Meteoclimatic API v3 client.

Requires the optional ``async`` extra::

    pip install pymeteoclimatic[async]

Usage, letting the client own its session::

    from meteoclimatic.alba import AsyncClient

    async with AsyncClient(api_key) as client:
        observation = await client.get_current_data("T415")

An existing session can be injected instead, which is the recommended form for
any application that already maintains one. The caller then keeps ownership: the
session is never closed by this client, and its connector, timeouts and
cancellation apply.

    client = AsyncClient(api_key, session=my_session)

The credential is sent only as the ``APIkey`` request header, never in a URL, and
never appears in ``repr``, logs or exceptions.
"""

import asyncio
import logging

import aiohttp

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

__all__ = ["AsyncClient"]


class AsyncClient:
    """Read-only asynchronous client for the Meteoclimatic API v3.

    :param api_key: the user's API Identifier ("Identificador de API"). This is
        not the separate profile "Key" value, which the API rejects.
    :param session: an existing :class:`aiohttp.ClientSession` to reuse. When
        omitted the client creates and owns one, which the caller must close via
        ``async with`` or :meth:`close`.
    :param base_url: override, mainly for testing
    :param timeout: per-request timeout in seconds
    """

    def __init__(self, api_key, session=None, base_url=DEFAULT_BASE_URL,
                 timeout=DEFAULT_TIMEOUT):
        """Initialize the class."""
        if not api_key:
            raise ValueError("api_key cannot be empty")
        self._api_key = api_key
        self._session = session
        self._owns_session = session is None
        self._base_url = base_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._block = RateLimitBlock()

    @property
    def blocked_until(self):
        """Return when the current rate-limit block ends, or ``None``.

        Exposed so the state is inspectable rather than hidden.
        """
        return self._block.blocked_until

    async def __aenter__(self):
        """Enter the asynchronous context manager."""
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        """Close an owned session on exit."""
        await self.close()

    async def close(self):
        """Close the session if this client created it.

        An injected session belongs to the caller and is never closed here.
        """
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    def _ensure_session(self):
        """Return the session, creating an owned one on first use."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def get_current_data(self, station_code):
        """Return the latest observation for *station_code*.

        :param station_code: the new short station code, e.g. ``T415``
        :rtype: meteoclimatic.alba.models.ApiObservation
        """
        payload, headers = await self._get(CURRENT_DATA_PATH, station_code)
        return parse_current_data(
            payload, cache_directive=headers.get("Cache-Control")
        )

    async def _get(self, path, station_code):
        """Perform a GET request and map failures to typed errors."""
        if not station_code:
            raise ValueError("station_code cannot be empty")

        # Never send while blocked: a request issued during a block extends it.
        self._block.raise_if_blocked()

        session = self._ensure_session()
        url = "%s%s" % (self._base_url, path)

        try:
            async with session.get(
                url,
                params={"stationcode": station_code},
                headers=build_headers(
                    self._api_key, "pymeteoclimatic/%s" % (__version__,)
                ),
                timeout=self._timeout,
                allow_redirects=False,
            ) as response:
                status = response.status
                if status != 200:
                    # Error envelopes are documented for 4xx but not for 5xx,
                    # so a body is read defensively and never required.
                    body = await self._safe_json(response)
                    retry_after = retry_after_seconds(
                        response.headers.get("Retry-After"), body
                    )
                    if status == 429:
                        self._block.record(retry_after)
                    _LOGGER.debug(
                        "Meteoclimatic API returned HTTP %s for station %s",
                        status, station_code,
                    )
                    raise_for_status(status, station_code, retry_after)
                try:
                    payload = await response.json(content_type=None)
                except ValueError as error:
                    raise MalformedResponseError(
                        "response body is not valid JSON", status=status
                    ) from error
                _LOGGER.debug(
                    "Meteoclimatic API request for station %s succeeded",
                    station_code,
                )
                return payload, response.headers
        except asyncio.TimeoutError as error:
            raise TransportError("request timed out") from error
        except aiohttp.ClientError as error:
            # Deliberately excludes the URL and headers from the message.
            raise TransportError(
                "transport failure: %s" % (type(error).__name__,)
            ) from error

    @staticmethod
    async def _safe_json(response):
        """Return the decoded body, or ``None`` when it is not JSON."""
        try:
            return await response.json(content_type=None)
        except (ValueError, aiohttp.ClientError):
            return None

    def __repr__(self):
        """Return a representation that never discloses the credential."""
        return "%s(base_url=%r, api_key=<redacted>)" % (
            self.__class__.__name__,
            self._base_url,
        )

    __str__ = __repr__
