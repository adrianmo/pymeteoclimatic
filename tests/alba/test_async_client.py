"""Offline tests for the asynchronous API v3 client.

No network and no credential are used: the aiohttp session is replaced by a stub
that returns canned responses. These tests assert the two properties that matter
most for safety - the credential never leaks, and every failure mode maps to a
typed error without falling back to RSS.
"""

import json
import os
import unittest

from meteoclimatic.alba import (
    AsyncClient,
    AuthenticationError,
    BadRequestError,
    MalformedResponseError,
    RateLimitError,
    StationNotFound,
    TransportError,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
SECRET = "super-secret-api-identifier"


def load(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return json.load(handle)


class FakeResponse:
    def __init__(self, status, payload, headers=None, raise_on_json=None):
        self.status = status
        self._payload = payload
        self.headers = headers or {}
        self._raise_on_json = raise_on_json

    async def json(self, content_type=None):
        if self._raise_on_json is not None:
            raise self._raise_on_json
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeSession:
    """Records the request so tests can assert on headers and URL."""

    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls = []
        self.closed = False

    def get(self, url, params=None, headers=None, timeout=None,
            allow_redirects=None):
        self.calls.append({
            "url": url,
            "params": params or {},
            "headers": headers or {},
            "allow_redirects": allow_redirects,
        })
        if self._error is not None:
            raise self._error
        return self._response

    async def close(self):
        self.closed = True


def make_client(session):
    return AsyncClient(SECRET, session=session)


class TestCredentialSafety(unittest.IsolatedAsyncioTestCase):

    async def test_key_is_sent_as_header_never_in_url_or_query(self):
        session = FakeSession(FakeResponse(200, load("currentdata_full.json")))
        await make_client(session).get_current_data("AA111")

        call = session.calls[0]
        self.assertEqual(call["headers"]["APIkey"], SECRET)
        self.assertNotIn(SECRET, call["url"])
        self.assertNotIn("apikey", {k.lower() for k in call["params"]})
        self.assertEqual(call["params"], {"stationcode": "AA111"})
        # Credential-bearing requests must not be redirected elsewhere.
        self.assertFalse(call["allow_redirects"])

    async def test_repr_and_str_never_disclose_the_key(self):
        client = make_client(FakeSession())
        self.assertNotIn(SECRET, repr(client))
        self.assertNotIn(SECRET, str(client))
        self.assertIn("redacted", repr(client))

    async def test_errors_never_carry_the_key(self):
        session = FakeSession(FakeResponse(401, load("error_401.json")))
        with self.assertRaises(AuthenticationError) as caught:
            await make_client(session).get_current_data("AA111")
        self.assertNotIn(SECRET, str(caught.exception))
        self.assertNotIn(SECRET, repr(caught.exception))

    async def test_empty_key_is_rejected(self):
        with self.assertRaises(ValueError):
            AsyncClient("")


class TestErrorMapping(unittest.IsolatedAsyncioTestCase):

    async def _raises(self, status, fixture, expected, headers=None):
        session = FakeSession(FakeResponse(status, load(fixture), headers))
        with self.assertRaises(expected) as caught:
            await make_client(session).get_current_data("AA111")
        return caught.exception

    async def test_401_maps_to_authentication_error(self):
        error = await self._raises(401, "error_401.json", AuthenticationError)
        self.assertEqual(error.status, 401)

    async def test_404_maps_to_station_not_found(self):
        error = await self._raises(404, "error_404.json", StationNotFound)
        self.assertEqual(error.station_code, "AA111")

    async def test_400_maps_to_bad_request(self):
        error = await self._raises(400, "error_400.json", BadRequestError)
        self.assertEqual(error.status, 400)

    async def test_429_reads_retry_after_header(self):
        error = await self._raises(
            429, "error_429.json", RateLimitError, {"Retry-After": "118"}
        )
        self.assertEqual(error.retry_after, 118)

    async def test_429_falls_back_to_body_retry_after(self):
        """The body repeats the value as 'Retry-After: N'."""
        error = await self._raises(429, "error_429.json", RateLimitError)
        self.assertEqual(error.retry_after, 118)

    async def test_500_maps_to_transport_error(self):
        session = FakeSession(FakeResponse(500, None))
        with self.assertRaises(TransportError):
            await make_client(session).get_current_data("AA111")

    async def test_client_error_maps_to_transport_error(self):
        import aiohttp
        session = FakeSession(error=aiohttp.ClientConnectionError("boom"))
        with self.assertRaises(TransportError):
            await make_client(session).get_current_data("AA111")

    async def test_timeout_maps_to_transport_error(self):
        import asyncio
        session = FakeSession(error=asyncio.TimeoutError())
        with self.assertRaises(TransportError):
            await make_client(session).get_current_data("AA111")

    async def test_invalid_json_maps_to_malformed_response(self):
        session = FakeSession(
            FakeResponse(200, None, raise_on_json=ValueError("no json"))
        )
        with self.assertRaises(MalformedResponseError):
            await make_client(session).get_current_data("AA111")

    async def test_no_rss_fallback_on_failure(self):
        """A failure must never reach the legacy RSS endpoint.

        Transport selection is the caller's explicit choice, so an Alba failure
        is reported rather than hidden behind data from somewhere else.
        """
        session = FakeSession(FakeResponse(500, None))
        with self.assertRaises(TransportError):
            await make_client(session).get_current_data("AA111")
        for call in session.calls:
            self.assertNotIn("meteoclimatic.net", call["url"])
            self.assertIn("api.m11c.net", call["url"])


class TestSessionOwnership(unittest.IsolatedAsyncioTestCase):

    async def test_injected_session_is_not_closed(self):
        """The host application owns an injected session."""
        session = FakeSession(FakeResponse(200, load("currentdata_full.json")))
        async with make_client(session) as client:
            await client.get_current_data("AA111")
        self.assertFalse(session.closed)

    async def test_owned_session_is_closed(self):
        client = AsyncClient(SECRET)
        client._session = FakeSession()
        client._owns_session = True
        await client.close()
        self.assertIsNone(client._session)


class TestRequestShape(unittest.IsolatedAsyncioTestCase):

    async def test_current_data_uses_the_expected_endpoint(self):
        session = FakeSession(FakeResponse(200, load("currentdata_full.json")))
        await make_client(session).get_current_data("AA111")
        self.assertEqual(session.calls[0]["url"],
                         "https://api.m11c.net/v3/station/currentdata")

    async def test_empty_station_code_is_rejected(self):
        session = FakeSession(FakeResponse(200, {}))
        with self.assertRaises(ValueError):
            await make_client(session).get_current_data("")


if __name__ == "__main__":
    unittest.main()
