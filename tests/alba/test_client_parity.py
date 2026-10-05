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

That table could not see the fourth. Every case in it is a response that
already has a status, so a connection that fails before a status exists was
outside its reach. The synchronous client let a dropped connection, a reset,
a truncated body or a garbled status line escape as ``http.client`` or
``OSError`` exceptions, while the asynchronous client reported each as a
``TransportError``. A second table below covers those failures, and it drives
both clients over a real socket, because mocking the transport would only
exercise the exception types the test author already thought of.
"""

import asyncio
import io
import json
import os
import socket
import struct
import threading
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
    # A 200 whose body is valid JSON but not a valid payload. Both clients
    # must agree that this is malformed AND that it happened on a 200.
    ("schema failure on 200", 200, "error_404.json", MalformedResponseError),
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


def _chain(error):
    """Return every exception reachable from *error*, *error* included.

    An exception can carry both an explicit cause and an implicit context, and
    they differ when one exception is raised ``from`` another while a third is
    being handled. The links therefore form a tree, not a list, and following
    one of them at each step would skip a whole branch. Both are followed,
    including a context that ``from None`` hides from tracebacks: hiding it
    from display does not make it unreachable.
    """
    found = []
    pending = [error]
    while pending:
        link = pending.pop()
        if link is None or any(link is other for other in found):
            continue
        found.append(link)
        pending.extend((link.__cause__, link.__context__))
    return found


def _assert_credential_absent(test, error):
    """Fail if the key is in *error* or in any exception chained to it.

    The message is not the only place a secret can travel. An exception keeps
    the one it was raised from, and an HTTP library's exception can hold the
    request it failed on, headers included. Anything that prints or serialises
    the chain, such as a debugger, a test runner or an error reporter, would
    then show the key even though the message itself is clean. So every
    exception reachable through either link is checked, in both its ``str``
    and its ``repr``.
    """
    for link in _chain(error):
        for text in (str(link), repr(link)):
            test.assertNotIn(
                SECRET, text,
                "the key is reachable through %s in the chain of %r"
                % (type(link).__name__, type(error).__name__),
            )


class TestTheCredentialCheckWalksTheWholeChain(unittest.TestCase):
    """The credential check is only as good as the chain it walks.

    In every scenario in this module, an exception's cause and context turn
    out to be the same object, so none of them can show whether both links
    are followed. These cases build the chains directly.
    """

    @staticmethod
    def _caught(build):
        try:
            build()
        except Exception as error:  # noqa: BLE001 - the chain is under test
            return error
        raise AssertionError("the chain was not built")

    def test_a_key_held_only_by_the_context_is_found(self):
        def build():
            try:
                raise RuntimeError("holds %s" % SECRET)
            except RuntimeError:
                raise TransportError("clean") from ValueError("clean")

        error = self._caught(build)
        self.assertIsNot(error.__cause__, error.__context__)
        with self.assertRaises(AssertionError):
            _assert_credential_absent(self, error)

    def test_a_key_hidden_by_from_none_is_found(self):
        def build():
            try:
                raise RuntimeError("holds %s" % SECRET)
            except RuntimeError:
                raise TransportError("clean") from None

        error = self._caught(build)
        self.assertTrue(error.__suppress_context__)
        with self.assertRaises(AssertionError):
            _assert_credential_absent(self, error)


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
                    _assert_credential_absent(self, error)


def _close_without_response(connection):
    """Read the request, then hang up without answering."""


def _reset(connection):
    """Read the request, then abort the connection with a TCP reset."""
    connection.setsockopt(
        socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0)
    )


def _cut_off_body(connection):
    """Promise a longer body than is sent, then hang up."""
    connection.sendall(
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
        b"Content-Length: 500\r\n\r\n{\"status\":200,"
    )


def _garbled_status_line(connection):
    """Answer with something that is not an HTTP status line."""
    connection.sendall(b"NOT-HTTP garbage\r\n\r\n")


def _invalid_content_length(connection):
    """Send a Content-Length that is not a number."""
    connection.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: abc\r\n\r\n{}")


#: (label, server behaviour). Each fails before a usable response exists, so
#: each must surface as a TransportError from both clients.
TRANSPORT_FAILURES = [
    ("closed without a response", _close_without_response),
    ("connection reset", _reset),
    ("body cut off", _cut_off_body),
    ("garbled status line", _garbled_status_line),
]


class _MisbehavingServer:
    """Loopback server that answers every connection the same broken way.

    Every connection gets the behaviour, not only the first, because an HTTP
    client may retry an idempotent request on a fresh connection. A one-shot
    server would refuse that retry, and the test would then observe "connection
    refused" instead of the failure it set out to produce.
    """

    def __init__(self, behaviour):
        self._behaviour = behaviour
        self._server = socket.create_server(("127.0.0.1", 0))
        self._server.settimeout(0.2)
        self._stop = threading.Event()
        self.connections = 0
        self._thread = threading.Thread(target=self._run, daemon=True)

    @property
    def base_url(self):
        return "http://127.0.0.1:%d" % self._server.getsockname()[1]

    def _run(self):
        while not self._stop.is_set():
            try:
                connection, _ = self._server.accept()
            except (socket.timeout, OSError):
                continue
            self.connections += 1
            with connection:
                connection.settimeout(10)
                try:
                    connection.recv(65536)
                    self._behaviour(connection)
                except OSError:
                    pass

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(10)
        self._server.close()
        return False


def _sync_transport_failure(behaviour):
    """Return whatever the synchronous client raises, of any type."""
    with _MisbehavingServer(behaviour) as server:
        try:
            Client(SECRET, base_url=server.base_url,
                   timeout=10).get_current_data("AA111")
        except Exception as error:  # noqa: BLE001 - the type is under test
            return error
    return None


def _async_transport_failure(behaviour):
    """Return whatever the asynchronous client raises, of any type."""
    from meteoclimatic.alba import AsyncClient

    async def run(base_url):
        try:
            async with AsyncClient(SECRET, base_url=base_url,
                                   timeout=10) as client:
                await client.get_current_data("AA111")
        except Exception as error:  # noqa: BLE001 - the type is under test
            return error
        return None

    with _MisbehavingServer(behaviour) as server:
        return asyncio.run(run(server.base_url))


#: Every real-socket case, including the one where the clients disagree on
#: the exception type, for the checks that hold regardless of type.
_ALL_TRANSPORT_CASES = TRANSPORT_FAILURES + [
    ("invalid Content-Length", _invalid_content_length),
]


class TestBothClientsReportTransportFailuresAsApiError(unittest.TestCase):
    """A connection that fails before a usable response is a TransportError.

    The README promises that a single ``except ApiError`` catches every error
    a request can raise. These cases run over a real loopback socket so that
    each client's own HTTP stack decides which exception it raises; a mock
    would only raise the types the test already expects.
    """

    def test_both_clients_raise_transport_error(self):
        for label, behaviour in TRANSPORT_FAILURES:
            with self.subTest(case=label):
                sync_error = _sync_transport_failure(behaviour)
                async_error = _async_transport_failure(behaviour)
                for name, error in (("sync", sync_error),
                                    ("async", async_error)):
                    self.assertIsInstance(
                        error, TransportError,
                        "%s client raised %r instead of TransportError"
                        % (name, error),
                    )
                self.assertEqual(
                    sync_error.status, async_error.status,
                    "clients disagree on ApiError.status",
                )

    def test_a_header_only_one_stack_rejects_is_still_an_api_error(self):
        """The one known divergence, kept visible rather than left out.

        http.client ignores a Content-Length that is not a number and reads
        to the end of the connection, while aiohttp rejects the response. The
        same bytes therefore give MalformedResponseError from the synchronous
        client and TransportError from the asynchronous one. Both are
        ApiError, which is what the README promises. Making one HTTP stack
        imitate the other's parser is not worth it, so only that is asserted.
        """
        for name, error in (
            ("sync", _sync_transport_failure(_invalid_content_length)),
            ("async", _async_transport_failure(_invalid_content_length)),
        ):
            self.assertIsInstance(
                error, ApiError,
                "%s client raised %r, not an ApiError" % (name, error),
            )

    def test_neither_client_leaks_the_credential(self):
        for label, behaviour in _ALL_TRANSPORT_CASES:
            with self.subTest(case=label):
                for error in (_sync_transport_failure(behaviour),
                              _async_transport_failure(behaviour)):
                    _assert_credential_absent(self, error)

    def test_neither_client_chains_an_aiohttp_exception(self):
        """Check the rule itself, not only one symptom of breaking it.

        The key check catches a chained aiohttp exception only when that
        exception's ``repr`` happens to print the request. Which aiohttp
        exceptions keep the request can't be known from here, so none may be
        chained at all.
        """
        for label, behaviour in _ALL_TRANSPORT_CASES:
            with self.subTest(case=label):
                for error in (_sync_transport_failure(behaviour),
                              _async_transport_failure(behaviour)):
                    for link in _chain(error):
                        module = type(link).__module__
                        self.assertNotEqual(
                            module.partition(".")[0], "aiohttp",
                            "%r chains %s.%s"
                            % (error, module, type(link).__qualname__),
                        )
