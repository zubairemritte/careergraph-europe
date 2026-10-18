"""Bounded GETs. Transport is injectable, so tests never need a public API."""

import json
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from careergraph.contracts import JsonObject


class SourceError(RuntimeError):
    """A safe provider or transport failure that must not publish partial data."""


class ResponseReader(Protocol):
    """Internal transport protocol describing read(size). Not a runtime object the project user needs to construct."""

    def read(self, size: int) -> bytes:
        """Describe the byte reader expected from an HTTP transport.

        Args:
            size: Maximum bytes the caller permits this read to return.

        Returns:
            Response bytes within the supplied read budget.

        Side effects:
            Protocol declaration only; the concrete transport implements the read.
        """
        ...


class Opener(Protocol):
    """Internal transport protocol describing timed context-managed response opening. Only transport tests replace it."""

    def __call__(
        self, request: Request, *, timeout: float
    ) -> AbstractContextManager[ResponseReader]:
        """Describe the injectable request-opening interface.

        Args:
            request: Prepared urllib Request with headers and the provider URL.
            timeout: Per-request timeout in seconds.

        Returns:
            A context manager exposing ResponseReader and closing the response on exit.

        Side effects:
            Protocol declaration only; implementations may perform one HTTP request.
        """
        ...


def retry_delay(value: str | None, attempt: int) -> float:
    """Interpret a provider delay without retrying earlier than requested.

    Args:
        value: Retry-After seconds or HTTP date; None uses exponential backoff.
        attempt: Zero-based retry attempt used for fallback delays.

    Returns:
        A nonnegative delay in seconds that fits the ten-second retry budget.

    Raises:
        SourceError: The requested wait exceeds the local retry budget; the run must stop.

    Side effects:
        Reads the UTC clock for an HTTP-date header; does not sleep.

    Example:
        retry_delay("2", 0) returns 2.0.
    """
    try:
        seconds: float = float(value) if value else 2**attempt
    except ValueError:
        try:
            seconds = (parsedate_to_datetime(value or "") - datetime.now(UTC)).total_seconds()
        except (ValueError, TypeError):
            seconds = 2**attempt
    if seconds > 10:
        raise SourceError("Source requests a longer retry delay; stop this run and try again later")
    return max(0.0, seconds)


def open_response(request: Request, *, timeout: float) -> AbstractContextManager[ResponseReader]:
    """Adapt urllib to the small response-reader contract.

    Args:
        request: Prepared GET request.
        timeout: Maximum wait in seconds for this transport call.

    Returns:
        A context manager around the urllib response.

    Raises:
        OSError: The underlying connection fails.
        urllib.error.HTTPError: The provider returns an HTTP error response.

    Side effects:
        Performs one HTTP request. Retry handling belongs to get_json.
    """
    return cast(AbstractContextManager[ResponseReader], urlopen(request, timeout=timeout))


def get_json(
    url: str, *, opener: Opener | None = None, sleep: Callable[[float], None] = time.sleep
) -> JsonObject:
    """Retrieve one bounded provider JSON object with transient retries.

    Args:
        url: Documented provider URL, including its explicit query parameters.
        opener: Optional urllib-compatible fake transport for offline tests.
        sleep: Delay callback; tests can record delays instead of sleeping.

    Returns:
        The decoded top-level JSON object.

    Raises:
        SourceError: Nonretryable HTTP error, exhausted retries, excessive size/delay, invalid JSON or a nonobject response.

    Side effects:
        Up to three GET attempts; timeout 25 seconds and response cap 10 MB. Sleeps only for bounded transient retries.
    """
    request: Request = Request(
        url, headers={"Accept": "application/json", "User-Agent": "CareerGraph-Europe/0.2"}
    )
    transport: Opener = opener if opener is not None else open_response
    for attempt in range(3):
        try:
            with transport(request, timeout=25) as response:
                body: bytes = response.read(10000001)
            if len(body) > 10000000:
                raise SourceError("Source response exceeds the 10 MB limit")
            data: object = json.loads(body)
            if not isinstance(data, dict):
                raise SourceError("Source response must be a JSON object")
            return cast(JsonObject, data)
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise SourceError(f"Source request failed (HTTP {exc.code})") from None
            sleep(retry_delay(exc.headers.get("Retry-After"), attempt))
        except (URLError, TimeoutError, OSError) as exc:
            if attempt == 2:
                raise SourceError(f"Source connection failed ({type(exc).__name__})") from None
            sleep(2**attempt)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise SourceError("Source returned invalid JSON") from None
    raise SourceError("Source retry budget exhausted")
