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
    """Operational class for the advert provider.

    Read collect, then normalize. The instance keeps one injectable fetcher and declares verified workplace coverage. It does not own a database; CollectionService owns publication.
    """

    source_id: str = "jobtech"
    supported_countries: frozenset[str] = frozenset({"SE"})

    def __init__(self, fetch: JsonFetcher = get_json) -> None:
        """Configure the official advert adapter without collecting anything.

        Args:
            fetch: URL-to-JSON callable; production uses get_json, tests inject a fixture.

        Returns:
            None; stores the transport callable on this adapter.

        Side effects:
            No network or database work during construction.
        """
        self.fetch: JsonFetcher = fetch

    def collect(self, country: str, queries: list[str], pages: int = 2) -> CollectionBatch:
        """Retrieve a bounded advert batch and its source-request audit.

        Args:
            country: Configured workplace code; the verified adapter currently accepts SE only.
            queries: One to eight nonempty search terms, each at most 100 characters.
            pages: Page budget per query, from one to five; each page requests at most 100 hits.

        Returns:
            CollectionBatch containing provider records and request hashes, overlapping reported totals and visibly capped queries.

        Raises:
            ValueError: Country or search budget is unsupported.
            SourceError: The HTTP request fails or the provider hits/total contract changes.

        Side effects:
            Makes bounded source requests through the injected fetcher; writes no database. Country is checked before any request.
        """
        if country_code(country) != "SE":
            raise ValueError(
                "JobTech supports verified workplace coverage for SE only; choose another approved connector for this country."
            )
        if (
            not 1 <= pages <= 5
            or not 1 <= len(queries) <= 8
            or any(not q.strip() or len(q) > 100 for q in queries)
        ):
            raise ValueError(
                "Use 1–8 nonempty queries (100 characters max) and 1–5 pages per query."
            )
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
                data: JsonObject = self.fetch(url)
                if not isinstance(data.get("hits"), list) or not isinstance(
                    data.get("total"), dict
                ):
                    raise SourceError("JobTech schema changed: hits/total are missing")
                total: int = int(data["total"]["value"])
                requests.append(
                    {
                        "url": url,
                        "records": len(data["hits"]),
                        "sha256": hashlib.sha256(
                            json.dumps(data, sort_keys=True).encode()
                        ).hexdigest(),
                    }
                )
                totals[query] = total
                records.extend(data["hits"])
                if len(data["hits"]) < 100 or (page + 1) * 100 >= total:
                    break
            else:
                if pages * 100 < total:
                    capped.append(query)
        return CollectionBatch(
            records=records,
            metadata={
                "requests": requests,
                "reported_query_totals": totals,
                "capped_queries": capped,
                "query_totals_are_not_additive": True,
            },
        )

    def normalize(self, raw: JsonObject) -> JsonObject:
        """Map one provider advert into the application's Offer input fields.

        Args:
            raw: One provider hit, including its workplace concept, description and source link.

        Returns:
            A new normalized dictionary with country/role/kind and calendar-date strings, ready for Offer validation.

        Raises:
            ValueError: Workplace coverage is unverified, the advert is removed, or a provided date is invalid.

        Side effects:
            Sanitizes textual fields and omits provider contact objects; does not store, fetch or change the input record.
        """
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


class EurostatConnector:
    """Operational class for official aggregate statistics.

    The instance keeps a fetcher and returns BenchmarkSnapshot. It is separate from JobTechConnector because a country/quarter rate is not an individual advert.
    """

    def __init__(self, fetch: JsonFetcher = get_json) -> None:
        """Configure the official-statistics adapter independently of adverts.

        Args:
            fetch: URL-to-JSON callable; replace it with a fixture to avoid network access.

        Returns:
            None; stores the transport on this statistics adapter.

        Side effects:
            No collection, storage or network work during construction.
        """
        self.fetch: JsonFetcher = fetch

    def fetch_snapshot(self) -> BenchmarkSnapshot:
        """Retrieve the pinned quarterly official vacancy-rate series.

        Returns:
            An attributed BenchmarkSnapshot: retrieval time, request URL, payload hash, metadata and country/quarter rows preserving null values and flags.

        Raises:
            SourceError: Transport fails or series dimensions/values violate the expected contract.

        Side effects:
            Makes one JSON request through the fetcher. Does not store rows or create job adverts.
        """
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
        payload: JsonObject = self.fetch(url)
        rows: list[BenchmarkRow]
        metadata: JsonObject
        rows, metadata = parse_eurostat(payload)
        return {
            "retrieved_at": datetime.now(UTC).isoformat(),
            "request_url": url,
            "payload_sha256": hashlib.sha256(
                json.dumps(payload, sort_keys=True).encode()
            ).hexdigest(),
            "metadata": metadata,
            "rows": rows,
        }


def iso_date(value: str | None) -> str | None:
    """Convert a provided source timestamp to its calendar date.

    Args:
        value: ISO source date/timestamp, or None for a missing date.

    Returns:
        YYYY-MM-DD, or None when the value is absent. No timezone conversion is inferred.

    Raises:
        ValueError: A supplied nonempty value has an invalid ISO date prefix.
    """
    return date.fromisoformat(str(value)[:10]).isoformat() if value else None


def normalize_jobtech(raw: JsonObject) -> JsonObject:
    """Retain the original function shortcut for advert normalization.

    Args:
        raw: One provider hit.

    Returns:
        The result of JobTechConnector.normalize.

    Raises:
        ValueError: The adapter rejects the workplace, removal flag or date.

    Side effects:
        No network request. New application code calls the adapter method directly.
    """
    return JobTechConnector().normalize(raw)


def fetch_jobtech(
    country: str, queries: list[str], pages: int = 2, *, fetch: JsonFetcher = get_json
) -> tuple[list[JsonObject], JsonObject]:
    """Retain the original tuple-returning collection shortcut.

    Args:
        country: Configured workplace code; the verified adapter currently accepts SE only.
        queries: One to eight nonempty search terms, each at most 100 characters.
        pages: Page budget per query, from one to five; each page requests at most 100 hits.
        fetch: Injectable provider fetcher, identical to the adapter constructor argument.

    Returns:
        A (records, metadata) tuple. The active service uses CollectionBatch instead.

    Raises:
        ValueError: The adapter rejects the country or request budget.
        SourceError: The adapter cannot retrieve a valid source response.

    Side effects:
        Delegates network work to JobTechConnector.collect; do not implement another collector here.
    """
    batch: CollectionBatch = JobTechConnector(fetch).collect(country, queries, pages)
    return batch.records, batch.metadata


def _ordered_codes(category: JsonObject) -> list[str]:
    """Decode category positions from a JSON-stat dimension.

    Args:
        category: Category object whose index is an ordered list or a code-to-position mapping.

    Returns:
        Codes ordered by their source positions.

    Side effects:
        Internal parser helper; does not fetch or write data.
    """
    index: Any = category["index"]
    if isinstance(index, list):
        return cast(list[str], index)
    return [key for key, _ in sorted(index.items(), key=lambda item: item[1])]


def parse_eurostat(data: JsonObject) -> tuple[list[BenchmarkRow], JsonObject]:
    """Validate and reshape official JSON-stat cells into analytical rows.

    Args:
        data: Decoded jvs_q_r21 payload with the pinned quarterly/sector/adjustment filters.

    Returns:
        A (rows, metadata) tuple. Rows cover configured countries and returned quarters, including missing country/cell observations as None.

    Raises:
        SourceError: Dimensions, filter values, category sizes, rates or flags violate the series contract.

    Side effects:
        Pure transformation. Does not impute missing rates or interpret the economy-wide series as data-job demand.
    """
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
        """Read one dense or sparse JSON-stat cell.

        Args:
            container: A source value/status list or a mapping keyed by flat-index strings.
            index: Zero-based flattened position decoded from dimension order and sizes.

        Returns:
            The stored cell value, or None when the cell is absent.

        Side effects:
            Nested parser helper; no collection or mutation.
        """
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
    """Retain the original official-snapshot function shortcut.

    Args:
        fetch: Injectable source fetcher, identical to the statistics adapter constructor argument.

    Returns:
        The result of EurostatConnector.fetch_snapshot.

    Raises:
        SourceError: Transport or series validation fails.

    Side effects:
        Delegates its request to the statistics adapter; new CLI code uses that class directly.
    """
    return EurostatConnector(fetch).fetch_snapshot()
