"""Rate-limit self-protection, TTL hints and logging.

The scenario that matters most here is the one a real deployment hits: several
stations polled with the same API key. Meteoclimatic applies its limits per user
and *extends* a block when a request arrives during it, so a client that keeps
sending makes the situation worse rather than merely failing.
"""

import io
import json
import logging
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.error import HTTPError

from meteoclimatic.alba import (
    Client,
    RateLimitError,
    parse_current_data,
)
from meteoclimatic.alba._http import (
    MINIMUM_BLOCK_SECONDS,
    RateLimitBlock,
    retry_after_seconds,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
SECRET = "super-secret-api-identifier"


def raw(name):
    with open(os.path.join(FIXTURES, name), "rb") as handle:
        return handle.read()


def load(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return json.load(handle)


class FakeResponse:
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


def rate_limited(retry_after="118"):
    return HTTPError(
        "https://api.m11c.net/v3/station/currentdata",
        429,
        "Too Many Requests",
        {"Retry-After": retry_after},
        io.BytesIO(raw("error_429.json")),
    )


class TestBlockPreventsFurtherRequests(unittest.TestCase):

    @patch("meteoclimatic.alba.client._urlopen", autospec=True)
    def test_second_request_does_not_reach_the_network(self, mock_urlopen):
        client = Client(SECRET)
        mock_urlopen.side_effect = rate_limited()

        with self.assertRaises(RateLimitError):
            client.get_current_data("AA111")
        self.assertEqual(mock_urlopen.call_count, 1)

        # The second call must fail fast, without sending anything.
        with self.assertRaises(RateLimitError) as caught:
            client.get_current_data("AA111")
        self.assertEqual(mock_urlopen.call_count, 1)
        self.assertGreater(caught.exception.retry_after, 0)

    @patch("meteoclimatic.alba.client._urlopen", autospec=True)
    def test_multiple_stations_sharing_one_client_are_protected(self, mock_urlopen):
        """The scenario of several stations configured with the same API key.

        The client is scoped to a credential, not to a station, so reusing one
        client across stations gives coordinated protection: once any station
        triggers a block, no other station is allowed to extend it.
        """
        client = Client(SECRET)
        mock_urlopen.side_effect = rate_limited()

        with self.assertRaises(RateLimitError):
            client.get_current_data("AA111")
        self.assertEqual(mock_urlopen.call_count, 1)

        for station in ("BB222", "CC333", "DD444"):
            with self.assertRaises(RateLimitError):
                client.get_current_data(station)

        # None of the other stations sent a request.
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch("meteoclimatic.alba.client._urlopen", autospec=True)
    def test_separate_clients_do_not_share_a_block(self, mock_urlopen):
        """Honest limitation: one client per station protects only that station.

        This is why the recommended usage is one client per API key. If a
        consumer creates a client per station instead, each one still stops
        harming itself, but it cannot know about another client's block.
        """
        first = Client(SECRET)
        second = Client(SECRET)
        mock_urlopen.side_effect = rate_limited()

        with self.assertRaises(RateLimitError):
            first.get_current_data("AA111")
        with self.assertRaises(RateLimitError):
            second.get_current_data("BB222")

        self.assertEqual(mock_urlopen.call_count, 2)

    @patch("meteoclimatic.alba.client._urlopen", autospec=True)
    def test_requests_resume_once_the_block_expires(self, mock_urlopen):
        client = Client(SECRET)
        mock_urlopen.side_effect = rate_limited("1")

        with self.assertRaises(RateLimitError):
            client.get_current_data("AA111")

        # Expire the block without sleeping.
        client._block._deadline = None
        mock_urlopen.side_effect = None
        mock_urlopen.return_value = FakeResponse(raw("currentdata_full.json"))

        observation = client.get_current_data("AA111")
        self.assertEqual(observation.temperature.current, 21.5)
        self.assertIsNone(client.blocked_until)

    @patch("meteoclimatic.alba.client._urlopen", autospec=True)
    def test_blocked_until_is_inspectable(self, mock_urlopen):
        client = Client(SECRET)
        self.assertIsNone(client.blocked_until)
        mock_urlopen.side_effect = rate_limited()
        with self.assertRaises(RateLimitError):
            client.get_current_data("AA111")
        self.assertIsNotNone(client.blocked_until)
        self.assertGreater(client.blocked_until, datetime.now(timezone.utc))


class TestRateLimitBlock(unittest.TestCase):

    def test_missing_retry_after_falls_back_to_minimum_window(self):
        block = RateLimitBlock()
        self.assertEqual(block.record(None), MINIMUM_BLOCK_SECONDS)
        self.assertIsNotNone(block.remaining())

    def test_block_is_never_shortened(self):
        """A later, smaller value must not cut an existing longer block."""
        block = RateLimitBlock()
        block.record(600)
        block.record(5)
        self.assertGreater(block.remaining(), 100)

    def test_not_blocked_by_default(self):
        block = RateLimitBlock()
        self.assertIsNone(block.remaining())
        self.assertIsNone(block.blocked_until)
        block.raise_if_blocked()  # must not raise


class TestLogging(unittest.TestCase):

    @patch("meteoclimatic.alba.client._urlopen", autospec=True)
    def test_rate_limit_is_logged_as_a_warning(self, mock_urlopen):
        """A 429 is otherwise invisible to the operator."""
        mock_urlopen.side_effect = rate_limited()
        with self.assertLogs("meteoclimatic.alba", level="WARNING") as logs:
            with self.assertRaises(RateLimitError):
                Client(SECRET).get_current_data("AA111")
        joined = "\n".join(logs.output)
        self.assertIn("rate limit", joined.lower())

    @patch("meteoclimatic.alba.client._urlopen", autospec=True)
    def test_logs_never_contain_the_credential(self, mock_urlopen):
        mock_urlopen.side_effect = rate_limited()
        with self.assertLogs("meteoclimatic", level="DEBUG") as logs:
            with self.assertRaises(RateLimitError):
                Client(SECRET).get_current_data("AA111")
        self.assertNotIn(SECRET, "\n".join(logs.output))

    @patch("meteoclimatic.alba.client._urlopen", autospec=True)
    def test_successful_request_logs_only_at_debug(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse(raw("currentdata_full.json"))
        logger = logging.getLogger("meteoclimatic.alba.client")
        with self.assertLogs(logger, level="DEBUG") as logs:
            Client(SECRET).get_current_data("AA111")
        self.assertTrue(all(record.levelno <= logging.DEBUG
                            for record in logs.records))


class TestTtlHint(unittest.TestCase):

    def setUp(self):
        self.fetched_at = datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc)
        self.observation = parse_current_data(
            load("currentdata_full.json"), fetched_at=self.fetched_at
        )

    def test_expires_at_is_derived_from_ttl(self):
        self.assertEqual(self.observation.ttl, 226)
        self.assertEqual(
            self.observation.expires_at, self.fetched_at + timedelta(seconds=226)
        )

    def test_seconds_until_refresh_counts_down(self):
        halfway = self.fetched_at + timedelta(seconds=100)
        self.assertAlmostEqual(
            self.observation.seconds_until_refresh(now=halfway), 126.0
        )

    def test_seconds_until_refresh_respects_a_floor(self):
        """A stale or tiny ttl must not turn into a busy loop."""
        late = self.fetched_at + timedelta(seconds=10000)
        self.assertEqual(
            self.observation.seconds_until_refresh(now=late, minimum=60), 60
        )

    def test_absent_ttl_yields_no_hint(self):
        payload = load("currentdata_full.json")
        del payload["data"]["ttl"]
        observation = parse_current_data(payload)
        self.assertIsNone(observation.ttl)
        self.assertIsNone(observation.expires_at)
        self.assertIsNone(observation.seconds_until_refresh())

    def test_library_never_schedules_by_itself(self):
        """The hint is data; polling remains the consumer's decision."""
        self.assertFalse(hasattr(self.observation, "sleep"))
        self.assertFalse(hasattr(Client, "poll"))


if __name__ == "__main__":
    unittest.main()


class TestUnusableRetryAfterDoesNotDefeatTheBlock(unittest.TestCase):
    """A non-positive Retry-After must not become a block that has expired.

    This is the failure that matters most here. The provider adds the exceeded
    window to the time still remaining when a request arrives during a block,
    so a client that mistakes a bad header for "wait -30 seconds" does not
    merely fail to protect itself: the request it then sends makes the block
    longer. One malformed header would defeat the whole mechanism.
    """

    def test_negative_header_is_treated_as_absent(self):
        self.assertIsNone(retry_after_seconds("-30", None))

    def test_zero_header_is_treated_as_absent(self):
        self.assertIsNone(retry_after_seconds("0", None))

    def test_negative_value_in_the_body_is_treated_as_absent(self):
        self.assertIsNone(
            retry_after_seconds(None, {"message": "Retry-After: -5"}))

    def test_positive_header_is_still_honoured(self):
        self.assertEqual(retry_after_seconds("30", None), 30)

    def test_recording_a_negative_wait_falls_back_to_the_minimum(self):
        block = RateLimitBlock()
        block.record(-30)
        self.assertGreater(block.remaining(), 0)
        self.assertAlmostEqual(block.remaining(), MINIMUM_BLOCK_SECONDS, delta=2)

    def test_recording_a_zero_wait_falls_back_to_the_minimum(self):
        block = RateLimitBlock()
        block.record(0)
        self.assertAlmostEqual(block.remaining(), MINIMUM_BLOCK_SECONDS, delta=2)

    def test_a_short_positive_wait_is_not_inflated(self):
        # The guard must not turn every block into the minimum; a genuine
        # five-second wait is information, not a malformed value.
        block = RateLimitBlock()
        block.record(5)
        self.assertAlmostEqual(block.remaining(), 5, delta=2)

    def test_a_negative_wait_leaves_the_client_actually_blocked(self):
        client = Client(SECRET)
        client._block.record(-30)
        with self.assertRaises(RateLimitError):
            client.get_current_data("AA111")



class TestUnusableHeaderStillConsultsTheBody(unittest.TestCase):
    """Discarding a bad header must not mean discarding the body value.

    The service repeats Retry-After in the response body. An earlier fix made
    a non-positive header return immediately, which threw the body away with
    it: a stale ``Retry-After: 0`` alongside a body value of 118 produced the
    60-second fallback, so a request would go out 58 seconds early. Since the
    service adds the exceeded window to the time remaining, that early request
    lengthens the block -- the exact harm the fix was written to prevent.
    """

    def test_zero_header_falls_through_to_the_body(self):
        self.assertEqual(
            retry_after_seconds("0", {"message": "Retry-After: 118"}), 118)

    def test_negative_header_falls_through_to_the_body(self):
        self.assertEqual(
            retry_after_seconds("-30", {"message": "Retry-After: 118"}), 118)

    def test_unparseable_header_falls_through_to_the_body(self):
        self.assertEqual(
            retry_after_seconds("soon", {"message": "Retry-After: 118"}), 118)

    def test_a_usable_header_still_wins_over_the_body(self):
        self.assertEqual(
            retry_after_seconds("45", {"message": "Retry-After: 118"}), 45)

    def test_both_unusable_yields_nothing_so_the_caller_uses_the_minimum(self):
        self.assertIsNone(
            retry_after_seconds("0", {"message": "Retry-After: -5"}))
        self.assertIsNone(retry_after_seconds("0", None))

    def test_the_resulting_block_honours_the_body_value(self):
        block = RateLimitBlock()
        block.record(retry_after_seconds("0", {"message": "Retry-After: 118"}))
        self.assertAlmostEqual(block.remaining(), 118, delta=2)
