"""Bounded GETs. Transport is injectable, so tests never need a public API."""

import json
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class SourceError(RuntimeError):
    pass


def retry_delay(value: str | None, attempt: int) -> float:
    try:
        seconds = float(value) if value else 2**attempt
    except ValueError:
        try:
            seconds = (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()
        except (ValueError, TypeError):
            seconds = 2**attempt
    if seconds > 10:
        raise SourceError("Source requests a longer retry delay; stop this run and try again later")
    return max(0.0, seconds)


def get_json(url: str, *, opener=urlopen, sleep=time.sleep) -> dict:
    request = Request(
        url, headers={"Accept": "application/json", "User-Agent": "CareerGraph-Europe/0.1"}
    )
    for attempt in range(3):
        try:
            with opener(request, timeout=25) as response:
                body = response.read(10_000_001)
            if len(body) > 10_000_000:
                raise SourceError("Source response exceeds the 10 MB limit")
            data = json.loads(body)
            if not isinstance(data, dict):
                raise SourceError("Source response must be a JSON object")
            return data
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
