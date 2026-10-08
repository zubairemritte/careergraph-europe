"""Two distinct source contracts: individual adverts and aggregate official statistics."""

import hashlib
import json
import math
from datetime import UTC, date, datetime
from typing import Any, cast
from urllib.parse import urlencode

from careergraph.catalog import COUNTRIES, country_code
from careergraph.contracts import (
    BenchmarkRow,
    BenchmarkSnapshot,
    CollectionBatch,
    JsonFetcher,
    JsonObject,
)
from careergraph.http import SourceError, get_json
from careergraph.text import clean_text, role_family

JOBTECH_URL: str = "https://jobsearch.api.jobtechdev.se/search"
EUROSTAT_URL: str = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/jvs_q_r21"


class JobTechConnector:
    """An injectable official advert adapter with verified workplace coverage."""

    source_id: str = "jobtech"
    supported_countries: frozenset[str] = frozenset({"SE"})

    def __init__(self, fetch: JsonFetcher = get_json) -> None:
        """Keep the transport injectable so a fixture can replace every HTTP call."""
        self.fetch: JsonFetcher = fetch

    def collect(self, country: str, queries: list[str], pages: int = 2) -> CollectionBatch:
        """Return records and request provenance after enforcing the bounded search."""
        records: list[JsonObject]
        metadata: JsonObject
        records, metadata = fetch_jobtech(country, queries, pages, fetch=self.fetch)
        return CollectionBatch(records=records, metadata=metadata)

    def normalize(self, raw: JsonObject) -> JsonObject:
        """Map verified workplace adverts to the Offer contract; reject foreign jobs."""
        return normalize_jobtech(raw)


class EurostatConnector:
    """An aggregate-statistics adapter; it never produces individual job offers."""

    def __init__(self, fetch: JsonFetcher = get_json) -> None:
        """Use a separate injectable transport for the official statistics layer."""
        self.fetch: JsonFetcher = fetch

    def fetch_snapshot(self) -> BenchmarkSnapshot:
        """Retrieve and validate the pinned series, preserving flags and null cells."""
        return fetch_benchmark(fetch=self.fetch)


def iso_date(value: str | None) -> str | None:
    """Keep the source calendar date; leave a missing source date unset."""
    return date.fromisoformat(str(value)[:10]).isoformat() if value else None


def normalize_jobtech(raw: JsonObject) -> JsonObject:
    """Map provider fields to Offer input and reject removed or unverified workplace records."""
    address: JsonObject = raw.get("workplace_address") or {}
    if address.get("country_concept_id") != "i46j_HmG_v64":
        raise ValueError("outside_verified_country")
    if raw.get("removed"):
        raise ValueError("removed_offer")
    title: str = clean_text(raw.get("headline") or "")
    return {
        "source_id": str(raw.get("id") or ""),
        "country": "SE",
        "title": title,
        "company": clean_text((raw.get("employer") or {}).get("name") or "Unknown employer"),
        "location": clean_text(address.get("city") or address.get("municipality") or ""),
        "description": clean_text((raw.get("description") or {}).get("text") or ""),
        "published_at": iso_date(raw.get("publication_date")),
        "expires_at": iso_date(raw.get("application_deadline")),
        "source_url": raw.get("webpage_url") or "",
        "role": role_family(title),
        "kind": "live",
    }


def fetch_jobtech(
    country: str, queries: list[str], pages: int = 2, *, fetch: JsonFetcher = get_json
) -> tuple[list[JsonObject], JsonObject]:
    """Collect capped keyword pages with request hashes and visible truncation metadata."""
    if country_code(country) != "SE":
        raise ValueError(
            "JobTech supports verified workplace coverage for SE only; choose another approved connector for this country."
        )
    if (
        not 1 <= pages <= 5
        or not 1 <= len(queries) <= 8
        or any(not q.strip() or len(q) > 100 for q in queries)
    ):
        raise ValueError("Use 1–8 nonempty queries (100 characters max) and 1–5 pages per query.")
    records: list[JsonObject]
    requests: list[JsonObject]
    totals: dict[str, int]
    capped: list[str]
    records, requests, totals, capped = ([], [], {}, [])
    for query in dict.fromkeys(queries):
        for page in range(pages):
            url: str = (
                JOBTECH_URL + "?" + urlencode({"q": query, "offset": page * 100, "limit": 100})
            )
            data: JsonObject = fetch(url)
            if not isinstance(data.get("hits"), list) or not isinstance(data.get("total"), dict):
                raise SourceError("JobTech schema changed: hits/total are missing")
            total: int = int(data["total"]["value"])
            requests.append(
                {
                    "url": url,
                    "records": len(data["hits"]),
                    "sha256": hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest(),
                }
            )
            totals[query] = total
            records.extend(data["hits"])
            if len(data["hits"]) < 100 or (page + 1) * 100 >= total:
                break
        else:
            if pages * 100 < total:
                capped.append(query)
    return (
        records,
        {
            "requests": requests,
            "reported_query_totals": totals,
            "capped_queries": capped,
            "query_totals_are_not_additive": True,
        },
    )


def _ordered_codes(category: JsonObject) -> list[str]:
    """Decode JSON-stat category positions from either a dense list or indexed mapping."""
    index: Any = category["index"]
    if isinstance(index, list):
        return cast(list[str], index)
    return [key for key, _ in sorted(index.items(), key=lambda item: item[1])]


def parse_eurostat(data: JsonObject) -> tuple[list[BenchmarkRow], JsonObject]:
    """Validate series dimensions and decode rates, missing cells and source flags."""
    expected: dict[str, str] = {
        "freq": "Q",
        "nace_r2_1": "B-T",
        "sizeclas": "TOTAL",
        "s_adj": "SA",
        "indic_em": "JVR",
    }
    ids: list[str]
    sizes: list[int]
    ids, sizes = (data.get("id", []), data.get("size", []))
    if set(ids) != set(expected) | {"geo", "time"} or len(ids) != len(sizes):
        raise SourceError("Eurostat dimensions changed; review the series contract")
    codes: dict[str, list[str]] = {
        dim: _ordered_codes(data["dimension"][dim]["category"]) for dim in ids
    }
    for dim, value in expected.items():
        if codes[dim] != [value]:
            raise SourceError(f"Unexpected Eurostat filter: {dim}")
    for dim, size in zip(ids, sizes, strict=True):
        if len(codes[dim]) != size:
            raise SourceError("Inconsistent JSON-stat category size")
    values: list[Any] | JsonObject
    flags: list[Any] | JsonObject
    values, flags = (data.get("value", {}), data.get("status", {}))

    def cell(container: list[Any] | JsonObject, index: int) -> Any:
        """Read one dense or sparse JSON-stat cell without replacing missingness with zero."""
        if isinstance(container, list):
            return container[index] if index < len(container) else None
        return container.get(str(index))

    rows: list[BenchmarkRow] = []
    for country in COUNTRIES:
        for quarter in codes["time"]:
            index: int = 0
            present: bool = country in codes["geo"]
            if present:
                for dim, size in zip(ids, sizes, strict=True):
                    coordinate: str = (
                        country if dim == "geo" else quarter if dim == "time" else expected[dim]
                    )
                    index = index * size + codes[dim].index(coordinate)
            rate_value: object = cell(values, index) if present else None
            if rate_value is not None and (
                isinstance(rate_value, bool)
                or not isinstance(rate_value, (int, float))
                or not math.isfinite(rate_value)
                or not 0 <= rate_value <= 100
            ):
                raise SourceError("Invalid Eurostat vacancy rate")
            rate: float | None = float(rate_value) if isinstance(rate_value, (int, float)) else None
            flag_value: object = cell(flags, index) if present else None
            if flag_value is not None and not isinstance(flag_value, str):
                raise SourceError("Invalid Eurostat status flag")
            rows.append(
                {
                    "country": country,
                    "quarter": quarter,
                    "vacancy_rate": rate,
                    "status_flag": flag_value,
                }
            )
    return (
        rows,
        {
            "dataset": "jvs_q_r21",
            "label": data.get("label"),
            "dimensions": expected,
            "quarters": codes["time"],
            "source_updated_at": data.get("updated"),
            "unit": "percent",
            "scope": "B–T economy; not a data-occupation series",
        },
    )


def fetch_benchmark(*, fetch: JsonFetcher = get_json) -> BenchmarkSnapshot:
    """Retrieve an attributed official-statistics snapshot independently from advert collection."""
    url: str = (
        EUROSTAT_URL
        + "?"
        + urlencode(
            {
                "lang": "EN",
                "freq": "Q",
                "nace_r2_1": "B-T",
                "sizeclas": "TOTAL",
                "s_adj": "SA",
                "indic_em": "JVR",
                "lastTimePeriod": 8,
            }
        )
    )
    payload: JsonObject = fetch(url)
    rows: list[BenchmarkRow]
    metadata: JsonObject
    rows, metadata = parse_eurostat(payload)
    return {
        "retrieved_at": datetime.now(UTC).isoformat(),
        "request_url": url,
        "payload_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
        "metadata": metadata,
        "rows": rows,
    }
