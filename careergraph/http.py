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
    """The minimal byte-reading interface needed from an HTTP response."""

    def read(self, size: int) -> bytes:
        """Read at most the response-size budget supplied by the caller."""
        ...


class Opener(Protocol):
    """Injectable urllib-compatible transport, including its response lifecycle."""

    def __call__(
        self, request: Request, *, timeout: float
    ) -> AbstractContextManager[ResponseReader]:
        """Open one timed request; callers close the returned context manager."""
        ...


def retry_delay(value: str | None, attempt: int) -> float:
    """Decode Retry-After; stop instead of violating a delay beyond the retry budget."""
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
    """Adapt urllib's dynamic response to the minimal typed read-and-close contract."""
    return cast(AbstractContextManager[ResponseReader], urlopen(request, timeout=timeout))


def get_json(
    url: str, *, opener: Opener | None = None, sleep: Callable[[float], None] = time.sleep
) -> JsonObject:
    """GET a JSON object within the timeout, response-size and transient-retry budgets."""
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
