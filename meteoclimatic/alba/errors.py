"""Typed errors for the Meteoclimatic API v3 transport.

Every exception subclasses :class:`meteoclimatic.exceptions.MeteoclimaticError`,
so existing callers that catch that base class keep catching every failure.

The mapping is keyed on the HTTP status rather than on the ``error`` or
``message`` text, because the provider has not confirmed that those strings are
stable enough to branch on.

Credential safety: no exception in this module ever carries the API key, an
authenticated URL, or a request header, so an error report or traceback cannot
leak the credential.
"""

from meteoclimatic.exceptions import MeteoclimaticError, StationNotFound

__all__ = [
    "MeteoclimaticError",
    "StationNotFound",
    "ApiError",
    "AuthenticationError",
    "BadRequestError",
    "RateLimitError",
    "TransportError",
    "MalformedResponseError",
]


class ApiError(MeteoclimaticError):
    """Base class for API v3 transport failures.

    :param message: human readable description, never containing a credential
    :param status: HTTP status code when one was received
    """

    def __init__(self, message, status=None):
        """Initialize the class."""
        self.status = status
        super().__init__(message)


class AuthenticationError(ApiError):
    """Raised on HTTP 401.

    The API key is missing, malformed, or not accepted. Note that the credential
    must be the user's API Identifier ("Identificador de API"), not the separate
    profile "Key" value.

    The offending credential is deliberately not stored on the exception.
    """

    def __init__(self, station_code=None):
        """Initialize the class."""
        self.station_code = station_code
        detail = "" if station_code is None else " for station %s" % (station_code,)
        super().__init__("API key was not accepted%s" % (detail,), status=401)


class BadRequestError(ApiError):
    """Raised on HTTP 400.

    Returned when the HTTP method is wrong, for example using GET where POST is
    expected or vice versa. This normally indicates a client bug rather than a
    recoverable condition, so it is not retried.
    """

    def __init__(self, message="Bad request"):
        """Initialize the class."""
        super().__init__(message, status=400)


class RateLimitError(ApiError):
    """Raised on HTTP 429.

    Limits apply per user for authenticated requests, across per-minute,
    per-hour and per-day windows.

    Callers MUST respect :attr:`retry_after` and must not retry earlier: the
    provider adds the exceeded window to the time still remaining when a client
    insists during a block (30 s left plus a retry becomes 90 s).

    :param retry_after: seconds to wait, taken from the ``Retry-After`` header
    """

    def __init__(self, retry_after=None):
        """Initialize the class."""
        self.retry_after = retry_after
        if retry_after is None:
            detail = "no Retry-After value was provided"
        else:
            detail = "retry after %s seconds" % (retry_after,)
        super().__init__("Rate limit exceeded; %s" % (detail,), status=429)


class TransportError(ApiError):
    """Raised on timeouts, connection failures, and server-side errors.

    Server error envelopes are not enumerated by the provider, so a 5xx body is
    never parsed as the documented read envelope.
    """


class MalformedResponseError(ApiError):
    """Raised when a response cannot be understood.

    This covers invalid JSON, a missing envelope, and a missing or unusable
    required field. It is deliberately distinct from a legitimately absent
    measurement: the API returns ``null`` with the key retained for a value the
    station does not provide, and that is normal data, not a malformed response.
    """
