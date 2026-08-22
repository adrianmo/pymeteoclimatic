"""Offline tests for the synchronous API v3 client.

No network and no credential are used: ``urlopen`` is replaced by a stub. These
tests assert the same safety properties as the asynchronous client, so that both
clients demonstrably behave the same way.
"""

import io
import json
import os
import socket
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from meteoclimatic.alba import (
    AuthenticationError,
    BadRequestError,
    MalformedResponseError,
    Client,
    RateLimitError,
    StationNotFound,
    TransportError,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
SECRET = "super-secret-api-identifier"


def load(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return json.load(handle)


def raw(name):
    with open(os.path.join(FIXTURES, name), "rb") as handle:
        return handle.read()


class FakeResponse:
    """Minimal stand-in for the object returned by ``urlopen``."""

    def __init__(self, body, headers=None):
        self._body = body
        self.headers = headers or {}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def http_error(status, fixture, headers=None):
    return HTTPError(
        "https://api.m11c.net/v3/station/currentdata",
        status,
        "error",
        headers or {},
        io.BytesIO(raw(fixture)),
    )


class TestCredentialSafety(unittest.TestCase):

    @patch("meteoclimatic.alba.client.urlopen", autospec=True)
    def test_key_is_sent_as_header_never_in_url(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse(raw("currentdata_full.json"))

        Client(SECRET).get_current_data("AA111")

        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.get_header("Apikey"), SECRET)
        self.assertNotIn(SECRET, request.full_url)
        self.assertNotIn("apikey", request.full_url.lower())
        self.assertIn("stationcode=AA111", request.full_url)

    def test_repr_and_str_never_disclose_the_key(self):
        client = Client(SECRET)
        self.assertNotIn(SECRET, repr(client))
        self.assertNotIn(SECRET, str(client))
        self.assertIn("redacted", repr(client))

    @patch("meteoclimatic.alba.client.urlopen", autospec=True)
    def test_errors_never_carry_the_key(self, mock_urlopen):
        mock_urlopen.side_effect = http_error(401, "error_401.json")
        with self.assertRaises(AuthenticationError) as caught:
            Client(SECRET).get_current_data("AA111")
        self.assertNotIn(SECRET, str(caught.exception))

    def test_empty_key_is_rejected(self):
        with self.assertRaises(ValueError):
            Client("")


class TestErrorMapping(unittest.TestCase):

    def setUp(self):
        self.client = Client(SECRET)

    @patch("meteoclimatic.alba.client.urlopen", autospec=True)
    def test_401_maps_to_authentication_error(self, mock_urlopen):
        mock_urlopen.side_effect = http_error(401, "error_401.json")
        with self.assertRaises(AuthenticationError):
            self.client.get_current_data("AA111")

    @patch("meteoclimatic.alba.client.urlopen", autospec=True)
    def test_404_maps_to_station_not_found(self, mock_urlopen):
        mock_urlopen.side_effect = http_error(404, "error_404.json")
        with self.assertRaises(StationNotFound) as caught:
            self.client.get_current_data("AA111")
        self.assertEqual(caught.exception.station_code, "AA111")

    @patch("meteoclimatic.alba.client.urlopen", autospec=True)
    def test_400_maps_to_bad_request(self, mock_urlopen):
        mock_urlopen.side_effect = http_error(400, "error_400.json")
        with self.assertRaises(BadRequestError):
            self.client.get_current_data("AA111")

    @patch("meteoclimatic.alba.client.urlopen", autospec=True)
    def test_429_reads_retry_after_from_body(self, mock_urlopen):
        mock_urlopen.side_effect = http_error(429, "error_429.json")
        with self.assertRaises(RateLimitError) as caught:
            self.client.get_current_data("AA111")
        self.assertEqual(caught.exception.retry_after, 118)

    @patch("meteoclimatic.alba.client.urlopen", autospec=True)
    def test_500_maps_to_transport_error(self, mock_urlopen):
        mock_urlopen.side_effect = http_error(500, "error_401.json")
        with self.assertRaises(TransportError):
            self.client.get_current_data("AA111")

    @patch("meteoclimatic.alba.client.urlopen", autospec=True)
    def test_timeout_maps_to_transport_error(self, mock_urlopen):
        mock_urlopen.side_effect = socket.timeout()
        with self.assertRaises(TransportError):
            self.client.get_current_data("AA111")

    @patch("meteoclimatic.alba.client.urlopen", autospec=True)
    def test_connection_failure_maps_to_transport_error(self, mock_urlopen):
        mock_urlopen.side_effect = URLError("unreachable")
        with self.assertRaises(TransportError):
            self.client.get_current_data("AA111")

    @patch("meteoclimatic.alba.client.urlopen", autospec=True)
    def test_invalid_json_maps_to_malformed_response(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse(b"not json")
        with self.assertRaises(MalformedResponseError):
            self.client.get_current_data("AA111")

    @patch("meteoclimatic.alba.client.urlopen", autospec=True)
    def test_no_rss_fallback_on_failure(self, mock_urlopen):
        """A failure must never reach the legacy RSS feed."""
        mock_urlopen.side_effect = http_error(500, "error_401.json")
        with self.assertRaises(TransportError):
            self.client.get_current_data("AA111")
        for call in mock_urlopen.call_args_list:
            url = call[0][0].full_url
            self.assertNotIn("meteoclimatic.net", url)
            self.assertIn("api.m11c.net", url)


class TestRequests(unittest.TestCase):

    @patch("meteoclimatic.alba.client.urlopen", autospec=True)
    def test_current_data_is_parsed(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse(
            raw("currentdata_full.json"), {"Cache-Control": "no-store"}
        )
        observation = Client(SECRET).get_current_data("AA111")
        self.assertEqual(observation.temperature.current, 21.5)
        self.assertEqual(observation.cache_directive, "no-store")
        self.assertEqual(observation.station.timezone, "Europe/Madrid")

    def test_empty_station_code_is_rejected(self):
        with self.assertRaises(ValueError):
            Client(SECRET).get_current_data("")


if __name__ == "__main__":
    unittest.main()
