import io
import json
from urllib.error import HTTPError

import pytest

from careergraph.connectors import fetch_jobtech, parse_eurostat
from careergraph.http import SourceError, get_json


def eurostat_fixture(dense=False):
    # Deliberately reordered axes: parsers must decode id/size, not assume geo/time positions.
    codes = {
        "time": ["2026-Q1", "2026-Q2"],
        "geo": ["DE", "FR"],
        "freq": ["Q"],
        "indic_em": ["JVR"],
        "sizeclas": ["TOTAL"],
        "nace_r2_1": ["B-T"],
        "s_adj": ["SA"],
    }
    return {
        "id": list(codes),
        "size": [len(c) for c in codes.values()],
        "dimension": {
            d: {"category": {"index": {code: i for i, code in enumerate(values)}}}
            for d, values in codes.items()
        },
        "value": [1.1, None, 1.3, 2.4] if dense else {"0": 1.1, "2": 1.3, "3": 2.4},
        "status": {"3": "p"},
        "label": "Test fixture",
    }


@pytest.mark.parametrize("dense", [False, True])
def test_sparse_missing_values_dimensions_and_flags(dense):
    rows, _ = parse_eurostat(eurostat_fixture(dense))
    cells = {(r["country"], r["quarter"]): r for r in rows}
    assert cells["DE", "2026-Q2"]["vacancy_rate"] == 1.3
    assert cells["FR", "2026-Q1"]["vacancy_rate"] is None
    assert cells["FR", "2026-Q2"]["status_flag"] == "p"
    assert cells["GB", "2026-Q2"]["vacancy_rate"] is None


def test_series_mismatch_fails_closed():
    data = eurostat_fixture()
    data["dimension"]["s_adj"]["category"]["index"] = {"NSA": 0}
    with pytest.raises(SourceError, match="filter"):
        parse_eurostat(data)


def test_unsupported_country_makes_no_network_call():
    def forbidden(url):
        pytest.fail("Should not access the network")

    with pytest.raises(ValueError, match="SE only"):
        fetch_jobtech("DE", ["data"], fetch=forbidden)


def test_pagination_is_bounded_and_truncation_is_visible():
    requests = []

    def fetch(url):
        requests.append(url)
        return {"hits": [{"id": str(n)} for n in range(100)], "total": {"value": 901}}

    records, report = fetch_jobtech("SE", ["data"], pages=2, fetch=fetch)
    assert len(records) == 200 and len(requests) == 2
    assert "offset=100" in requests[1]
    assert report["capped_queries"] == ["data"]


def test_transient_429_respects_retry_after():
    calls, sleeps = [], []

    def opener(request, timeout):
        calls.append(request)
        if len(calls) == 1:
            raise HTTPError(request.full_url, 429, "busy", {"Retry-After": "2"}, None)
        return io.BytesIO(json.dumps({"ok": True}).encode())

    assert get_json("https://example.invalid", opener=opener, sleep=sleeps.append) == {"ok": True}
    assert sleeps == [2] and len(calls) == 2


def test_long_retry_after_stops_instead_of_retrying_too_soon():
    def opener(request, timeout):
        raise HTTPError(request.full_url, 429, "busy", {"Retry-After": "120"}, None)

    with pytest.raises(SourceError, match="longer retry delay"):
        get_json(
            "https://example.invalid", opener=opener, sleep=lambda seconds: pytest.fail("Must stop")
        )


def test_non_retryable_http_and_invalid_json():
    def opener(request, timeout):
        raise HTTPError(request.full_url, 403, "denied", {}, None)

    with pytest.raises(SourceError, match="403"):
        get_json("https://example.invalid", opener=opener)
    with pytest.raises(SourceError, match="invalid JSON"):
        get_json(
            "https://example.invalid", opener=lambda *a, **k: io.BytesIO(b"<html>not JSON</html>")
        )
