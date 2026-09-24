"""Transport-agnostic request and response rules for the API v3 read path.

This module contains everything both clients need except the HTTP call itself:
endpoint paths, header construction, the status-to-error mapping, and the
Retry-After extraction. It imports no third-party package.

Keeping these rules in one place is what makes a synchronous and an asynchronous
client behave identically without duplicating contract logic.
"""

import logging
import time
from datetime import datetime, timedelta, timezone

from meteoclimatic.alba.errors import (
    AuthenticationError,
    BadRequestError,
    MalformedResponseError,
    RateLimitError,
    StationNotFound,
    TransportError,
)

_LOGGER = logging.getLogger("meteoclimatic.alba")

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT",
    "RECOMMENDED_POLL_INTERVAL",
    "MINIMUM_BLOCK_SECONDS",
    "CURRENT_DATA_PATH",
    "RateLimitBlock",
    "build_headers",
    "raise_for_status",
    "with_status",
    "retry_after_seconds",
    "validate_api_key",
]

DEFAULT_BASE_URL = "https://api.m11c.net"
DEFAULT_TIMEOUT = 15.0

#: Suggested polling interval in seconds, derived from the provider's own
#: cadence: stations generally publish every five minutes, some every fifteen.
#: Prefer the ``ttl`` value carried by each response, which approximates the next
#: five-minute block.
RECOMMENDED_POLL_INTERVAL = 300

#: Smallest documented rate-limit window. Used when a 429 arrives without any
#: usable Retry-After value: waiting the minimum is safer than assuming the
#: client may continue, because a request issued during a block extends it.
MINIMUM_BLOCK_SECONDS = 60

CURRENT_DATA_PATH = "/v3/station/currentdata"


class RateLimitBlock:
    """Remembers an active rate-limit block so the client stops making it worse.

    Meteoclimatic applies its limits per user, and issuing a request while
    blocked **adds** the exceeded window to the time still remaining. A client
    that keeps sending therefore actively harms the caller, which is why this
    state lives in the library rather than being left to every consumer to
    rediscover.

    The deadline is tracked with a monotonic clock so a system time adjustment
    cannot end a block early. ``blocked_until`` is derived when the block is
    recorded and is informational only.

    This object never sleeps and never retries: it reports the remaining time and
    lets the caller decide.
    """

    def __init__(self):
        """Initialize the class."""
        self._deadline = None
        self._blocked_until = None

    @property
    def blocked_until(self):
        """Return the approximate wall-clock end of the block, or ``None``."""
        if self.remaining() is None:
            return None
        return self._blocked_until

    def remaining(self):
        """Return the seconds left in the block, or ``None`` when not blocked."""
        if self._deadline is None:
            return None
        left = self._deadline - time.monotonic()
        if left <= 0:
            self._deadline = None
            self._blocked_until = None
            return None
        return left

    def record(self, retry_after):
        """Start or extend a block after a 429 response.

        :param retry_after: seconds reported by the provider; when it is missing
            the smallest documented window is assumed
        """
        # Guard the value as well as parse it. A non-positive wait would put
        # the deadline in the past, so the next request would go straight out
        # during an active block -- and the provider adds the exceeded window
        # to the time still remaining, so that request makes the block longer.
        if not retry_after or retry_after <= 0:
            seconds = MINIMUM_BLOCK_SECONDS
        else:
            seconds = retry_after
        previous = self.remaining()
        # The provider's value already accounts for any penalty it applied, so
        # the longer of the two deadlines is the safe one to honor.
        if previous is not None and previous > seconds:
            seconds = previous
        self._deadline = time.monotonic() + seconds
        self._blocked_until = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        if previous is None:
            _LOGGER.warning(
                "Meteoclimatic API rate limit reached; blocking requests for "
                "%.0f s. Requests sent during a block extend it.", seconds
            )
        else:
            _LOGGER.warning(
                "Meteoclimatic API rate limit still active; block extended to "
                "%.0f s.", seconds
            )
        return seconds

    def raise_if_blocked(self):
        """Raise :class:`RateLimitError` without sending a request when blocked."""
        left = self.remaining()
        if left is None:
            return
        _LOGGER.debug(
            "Skipping Meteoclimatic API request: rate limited for another "
            "%.0f s.", left
        )
        raise RateLimitError(int(left) or 1)


def validate_api_key(api_key):
    """Return the credential, cleaned, or raise without ever echoing it.

    A key is frequently read from a file or an environment variable and
    arrives with a trailing newline. Passing that to the header encoder makes
    the standard library raise ``ValueError: Invalid header value b'...'``,
    which puts the secret verbatim into the message and into every traceback
    and error report that carries it. The credential-safety contract says the
    key never appears in an exception, so it has to be checked before it can
    reach code that quotes it.

    Surrounding whitespace is stripped, because that accident is routine and
    the credential never meaningfully begins or ends with it. Anything the
    header encoder would reject is refused outright, and every message here is
    written so that it describes the fault without containing the value.
    """
    if not isinstance(api_key, str):
        raise ValueError("api_key must be a string")
    cleaned = api_key.strip()
    if not cleaned:
        raise ValueError("api_key cannot be empty")
    for character in cleaned:
        if ord(character) < 32 or ord(character) == 127:
            raise ValueError(
                "api_key contains a control character; it is most likely a "
                "stray newline from a file or environment variable"
            )
    try:
        cleaned.encode("latin-1")
    except UnicodeEncodeError:
        raise ValueError(
            "api_key contains characters that cannot be sent in an HTTP "
            "header"
        ) from None
    return cleaned


def build_headers(api_key, user_agent):
    """Return the request headers, carrying the credential in a header only.

    The credential is never placed in the URL or query string. Although the
    provider also accepts an ``apikey`` query parameter, a URL-borne secret
    leaks into shell history, proxy logs, browser history and monitoring, so it
    is deliberately not used.
    """
    return {
        "APIkey": validate_api_key(api_key),
        "Accept": "application/json",
        "User-Agent": user_agent,
    }


def retry_after_seconds(header_value, body):
    """Return the Retry-After value in seconds, or ``None``.

    The provider sends it as a response header and repeats it in the body as
    ``"Retry-After: N"``; the header is preferred and the body is a fallback.

    A non-positive value is treated as absent rather than as a short wait: it
    is discarded and the body is consulted, exactly as if the header had not
    been sent. Only when neither source yields a usable value does the caller
    fall back to the minimum block, instead of recording a deadline that has
    already passed.
    """
    if header_value is not None:
        try:
            seconds = int(header_value)
        except (TypeError, ValueError):
            pass
        else:
            if seconds > 0:
                return seconds
            # A zero or negative wait is unusable, not a shorter block, so it
            # is discarded. Discarding it means falling through to the body,
            # not giving up: a stale header alongside a usable body value
            # would otherwise cost us the real wait and let a request go out
            # early, which is what extends the server-side penalty.
    if isinstance(body, dict):
        message = body.get("message")
        if isinstance(message, str) and ":" in message:
            candidate = message.split(":", 1)[1].strip()
            if candidate.isdigit() and int(candidate) > 0:
                return int(candidate)
    return None


def raise_for_status(status, station_code, retry_after=None):
    """Map a non-200 HTTP status onto a typed error.

    The mapping is keyed on the status rather than on the ``error`` or
    ``message`` strings, because the provider has not confirmed that those are
    stable enough to branch on.

    A failure here never triggers a request to the legacy RSS feed: transport
    selection is always the caller's explicit choice.
    """
    if status == 401:
        raise AuthenticationError(station_code)
    if status == 404:
        raise StationNotFound(station_code)
    if status == 429:
        raise RateLimitError(retry_after)
    if status == 400:
        raise BadRequestError()
    if 300 <= status < 400:
        # Never followed. The credential travels in a request header, so
        # following a redirect would disclose it to whatever host the
        # response names. Surfacing it also makes a change of service
        # address visible instead of silently transparent.
        raise TransportError(
            "the service returned a redirect (HTTP %s), which is not "
            "followed because the credential is sent as a request header"
            % (status,),
            status=status,
        )
    raise TransportError("unexpected HTTP status %s" % (status,), status=status)


def with_status(error, status):
    """Attach *status* to *error* when it does not already carry one.

    Both clients funnel parser failures through this, so a malformed body
    reports the status it arrived with regardless of which stage rejected it
    and regardless of which client made the request. Threading the status at
    each call site instead is what let the JSON path and the schema path
    disagree while both were nominally fixed.
    """
    if getattr(error, "status", None) is None:
        error.status = status
    return error


def ensure_json(payload, status=None):
    """Return a decoded body, or raise when it could not be parsed."""
    if payload is None:
        raise MalformedResponseError("response body is not valid JSON", status=status)
    return payload
