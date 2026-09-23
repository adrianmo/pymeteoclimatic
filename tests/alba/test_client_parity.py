"""The two clients must fail identically for identical responses.

Three separate divergences have been found between the synchronous and the
asynchronous client: the synchronous one followed redirects while the
asynchronous one refused them, it dropped the HTTP status when a 200 body was
malformed while the asynchronous one reported it, and it accepted any 2xx
while the asynchronous one required exactly 200.

Each was fixed individually, which does nothing to stop a fourth. The two
clients duplicate their request and response handling, so the duplication is
what invites divergence. This module drives both through one table of
scenarios and asserts they agree on the exception type and on the status
carried with it, so a future divergence fails here rather than in a review.
"""

import asyncio
import io
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from meteoclimatic.alba import (
    ApiError,
    AuthenticationError,
    BadRequestError,
    Client,
    MalformedResponseError,
    RateLimitError,
    StationNotFound,
    TransportError,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
SECRET = "super-secret-api-identifier"
URL = "https://api.m11c.net/v3/station/currentdata"


def load(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return json.load(handle)


#: (label, HTTP status, body fixture, expected exception)
CASES = [
    ("unauthorized", 401, "error_401.json", AuthenticationError),
    ("not found", 404, "error_404.json", StationNotFound),
    ("bad request", 400, "error_400.json", BadRequestError),
    ("throttled", 429, "error_429.json", RateLimitError),
    ("server error", 500, "error_404.json", TransportError),
    ("redirect", 302, "error_404.json", TransportError),
    ("no content", 204, "error_404.json", TransportError),
    ("created", 201, "error_404.json", TransportError),
]


class _SyncResponse:
    def __init__(self, body, status):
        self._body = body
        self.headers = {}
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _AsyncResponse:
    def __init__(self, status, payload):
        self.status = status
        self._payload = payload
        self.headers = {}

    async def json(self, content_type=None):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _AsyncSession:
    def __init__(self, response):
        self._response = response

    def get(self, url, params=None, headers=None, timeout=None,
            allow_redirects=None):
        return self._response

    async def close(self):
        return None


def _sync_failure(status, payload):
    """Return the exception the synchronous client raises, or None."""
    body = json.dumps(payload).encode("utf-8")
    if status >= 400:
        side_effect = HTTPError(URL, status, "error", {}, io.BytesIO(body))
        patched = patch("meteoclimatic.alba.client._urlopen",
                        side_effect=side_effect)
    else:
        patched = patch("meteoclimatic.alba.client._urlopen",
                        return_value=_SyncResponse(body, status))
    with patched:
        try:
            Client(SECRET).get_current_data("AA111")
        except ApiError as error:
            return error
    return None


def _async_failure(status, payload):
    """Return the exception the asynchronous client raises, or None."""
    from meteoclimatic.alba import AsyncClient

    async def run():
        session = _AsyncSession(_AsyncResponse(status, payload))
        client = AsyncClient(SECRET, session=session)
        try:
            await client.get_current_data("AA111")
        except ApiError as error:
            return error
        return None

    return asyncio.run(run())


class TestBothClientsFailIdentically(unittest.TestCase):

    def test_exception_type_and_status_agree(self):
        for label, status, fixture, expected in CASES:
            with self.subTest(case=label, status=status):
                payload = load(fixture)
                sync_error = _sync_failure(status, payload)
                async_error = _async_failure(status, payload)

                self.assertIsNotNone(sync_error, "sync client did not raise")
                self.assertIsNotNone(async_error, "async client did not raise")
                self.assertIsInstance(sync_error, expected)
                self.assertIsInstance(async_error, expected)
                self.assertIs(
                    type(sync_error), type(async_error),
                    "clients disagree on the exception type",
                )
                self.assertEqual(
                    sync_error.status, async_error.status,
                    "clients disagree on ApiError.status",
                )

    def test_neither_client_leaks_the_credential(self):
        for label, status, fixture, expected in CASES:
            with self.subTest(case=label, status=status):
                payload = load(fixture)
                for error in (_sync_failure(status, payload),
                              _async_failure(status, payload)):
                    self.assertNotIn(SECRET, str(error))
