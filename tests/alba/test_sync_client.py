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

from meteoclimatic.alba.client import _NoRedirects, _OPENER
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

    def __init__(self, body, headers=None, status=200):
        self._body = body
        self.headers = headers or {}
        # The real response carries the HTTP status; the client reads it so
        # that a malformed body reports the same metadata as the async path.
        self.status = status

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

    @patch("meteoclimatic.alba.client._urlopen", autospec=True)
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

    @patch("meteoclimatic.alba.client._urlopen", autospec=True)
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

    @patch("meteoclimatic.alba.client._urlopen", autospec=True)
    def test_401_maps_to_authentication_error(self, mock_urlopen):
        mock_urlopen.side_effect = http_error(401, "error_401.json")
        with self.assertRaises(AuthenticationError):
            self.client.get_current_data("AA111")

    @patch("meteoclimatic.alba.client._urlopen", autospec=True)
    def test_404_maps_to_station_not_found(self, mock_urlopen):
        mock_urlopen.side_effect = http_error(404, "error_404.json")
        with self.assertRaises(StationNotFound) as caught:
            self.client.get_current_data("AA111")
        self.assertEqual(caught.exception.station_code, "AA111")

    @patch("meteoclimatic.alba.client._urlopen", autospec=True)
    def test_400_maps_to_bad_request(self, mock_urlopen):
        mock_urlopen.side_effect = http_error(400, "error_400.json")
        with self.assertRaises(BadRequestError):
            self.client.get_current_data("AA111")

    @patch("meteoclimatic.alba.client._urlopen", autospec=True)
    def test_429_reads_retry_after_from_body(self, mock_urlopen):
        mock_urlopen.side_effect = http_error(429, "error_429.json")
        with self.assertRaises(RateLimitError) as caught:
            self.client.get_current_data("AA111")
        self.assertEqual(caught.exception.retry_after, 118)

    @patch("meteoclimatic.alba.client._urlopen", autospec=True)
    def test_500_maps_to_transport_error(self, mock_urlopen):
        mock_urlopen.side_effect = http_error(500, "error_401.json")
        with self.assertRaises(TransportError):
            self.client.get_current_data("AA111")

    @patch("meteoclimatic.alba.client._urlopen", autospec=True)
    def test_timeout_maps_to_transport_error(self, mock_urlopen):
        mock_urlopen.side_effect = socket.timeout()
        with self.assertRaises(TransportError):
            self.client.get_current_data("AA111")

    @patch("meteoclimatic.alba.client._urlopen", autospec=True)
    def test_connection_failure_maps_to_transport_error(self, mock_urlopen):
        mock_urlopen.side_effect = URLError("unreachable")
        with self.assertRaises(TransportError):
            self.client.get_current_data("AA111")

    @patch("meteoclimatic.alba.client._urlopen", autospec=True)
    def test_invalid_json_maps_to_malformed_response(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse(b"not json")
        with self.assertRaises(MalformedResponseError):
            self.client.get_current_data("AA111")

    @patch("meteoclimatic.alba.client._urlopen", autospec=True)
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

    @patch("meteoclimatic.alba.client._urlopen", autospec=True)
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


class TestRedirectsAreRefused(unittest.TestCase):
    """A redirect must never carry the credential to another host.

    ``urllib`` copies request headers onto a redirected request, so following
    a 3xx would disclose the ``APIkey`` header to the host named by the
    response. The asynchronous client already refuses redirects; these tests
    pin the same property for the synchronous one.
    """

    def test_opener_never_follows_a_redirect(self):
        handler = _NoRedirects()
        self.assertIsNone(
            handler.redirect_request(
                None, None, 302, "Found", {},
                "https://elsewhere.invalid/v3/station/currentdata",
            )
        )

    def test_opener_is_built_with_the_non_redirecting_handler(self):
        self.assertTrue(
            any(isinstance(h, _NoRedirects) for h in _OPENER.handlers),
            "the module opener must install the non-redirecting handler",
        )

    def test_redirect_surfaces_as_a_transport_error(self):
        client = Client(SECRET)
        with patch(
            "meteoclimatic.alba.client._urlopen",
            side_effect=http_error(302, "error_404.json"),
        ):
            with self.assertRaises(TransportError) as caught:
                client.get_current_data("AA111")
        message = str(caught.exception)
        self.assertIn("redirect", message)
        self.assertNotIn(SECRET, message)


class TestErrorMetadataMatchesTheAsyncClient(unittest.TestCase):
    """Both transports must report the same metadata for the same failure.

    ``ApiError.status`` is documented as the HTTP status that was received.
    The synchronous client used to drop it when a 200 response carried
    invalid JSON, so the same fault produced ``status=None`` here and
    ``status=200`` on the asynchronous client, and a caller branching on it
    behaved differently depending on which client it happened to use.
    """

    def test_malformed_body_on_a_200_reports_that_status(self):
        client = Client(SECRET)
        with patch("meteoclimatic.alba.client._urlopen",
                   return_value=FakeResponse(b"{not json", status=200)):
            with self.assertRaises(MalformedResponseError) as caught:
                client.get_current_data("AA111")
        self.assertEqual(caught.exception.status, 200)

    def test_the_credential_is_still_absent_from_that_error(self):
        client = Client(SECRET)
        with patch("meteoclimatic.alba.client._urlopen",
                   return_value=FakeResponse(b"{not json", status=200)):
            with self.assertRaises(MalformedResponseError) as caught:
                client.get_current_data("AA111")
        self.assertNotIn(SECRET, str(caught.exception))



class TestOnlyTwoHundredIsSuccess(unittest.TestCase):
    """urllib raises only for 4xx and 5xx, so a 2xx must be checked here.

    A 201 or 204 arrives looking like success. Parsing its body would report
    an unexpected status as a malformed response, and the asynchronous client
    already required exactly 200, so the two clients disagreed about the same
    response.
    """

    def _status(self, status, body=b'{"status":200,"data":{}}'):
        client = Client(SECRET)
        with patch("meteoclimatic.alba.client._urlopen",
                   return_value=FakeResponse(body, status=status)):
            with self.assertRaises(TransportError) as caught:
                client.get_current_data("AA111")
        return caught.exception

    def test_no_content_is_not_success(self):
        self.assertEqual(self._status(204, b"").status, 204)

    def test_created_is_not_success(self):
        self.assertEqual(self._status(201).status, 201)

    def test_the_message_names_the_status(self):
        self.assertIn("204", str(self._status(204, b"")))

    def test_the_credential_is_absent_from_that_error(self):
        self.assertNotIn(SECRET, str(self._status(204, b"")))

    def test_two_hundred_is_still_success(self):
        client = Client(SECRET)
        with patch("meteoclimatic.alba.client._urlopen",
                   return_value=FakeResponse(raw("currentdata_full.json"),
                                             status=200)):
            observation = client.get_current_data("AA111")
        self.assertEqual(observation.station.code, "AA111")
