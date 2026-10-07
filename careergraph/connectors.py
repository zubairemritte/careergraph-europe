"""Two distinct source contracts: individual adverts and aggregate official statistics."""

import hashlib
import json
import math
from datetime import UTC, date, datetime
from urllib.parse import urlencode

from careergraph.catalog import COUNTRIES, country_code
from careergraph.http import SourceError, get_json
from careergraph.text import clean_text, role_family

JOBTECH_URL = "https://jobsearch.api.jobtechdev.se/search"
EUROSTAT_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/jvs_q_r21"


def iso_date(value):
    return date.fromisoformat(str(value)[:10]).isoformat() if value else None


def normalize_jobtech(raw: dict) -> dict:
    address = raw.get("workplace_address") or {}
    # The feed also contains overseas jobs: never label every returned offer as Swedish.
    if address.get("country_concept_id") != "i46j_HmG_v64":
        raise ValueError("outside_verified_country")
    if raw.get("removed"):
        raise ValueError("removed_offer")
    title = clean_text(raw.get("headline") or "")
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
    country: str, queries: list[str], pages: int = 2, *, fetch=get_json
) -> tuple[list[dict], dict]:
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
    records, requests, totals, capped = [], [], {}, []
    for query in dict.fromkeys(queries):
        for page in range(pages):
            url = JOBTECH_URL + "?" + urlencode({"q": query, "offset": page * 100, "limit": 100})
            data = fetch(url)
            if not isinstance(data.get("hits"), list) or not isinstance(data.get("total"), dict):
                raise SourceError("JobTech schema changed: hits/total are missing")
            total = int(data["total"]["value"])
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
    return records, {
        "requests": requests,
        "reported_query_totals": totals,
        "capped_queries": capped,
        "query_totals_are_not_additive": True,
    }


def _ordered_codes(category: dict) -> list[str]:
    index = category["index"]
    if isinstance(index, list):
        return index
    return [key for key, _ in sorted(index.items(), key=lambda item: item[1])]


def parse_eurostat(data: dict) -> tuple[list[dict], dict]:
    expected = {
        "freq": "Q",
        "nace_r2_1": "B-T",
        "sizeclas": "TOTAL",
        "s_adj": "SA",
        "indic_em": "JVR",
    }
    ids, sizes = data.get("id", []), data.get("size", [])
    if set(ids) != set(expected) | {"geo", "time"} or len(ids) != len(sizes):
        raise SourceError("Eurostat dimensions changed; review the series contract")
    codes = {dim: _ordered_codes(data["dimension"][dim]["category"]) for dim in ids}
    for dim, value in expected.items():
        if codes[dim] != [value]:
            raise SourceError(f"Unexpected Eurostat filter: {dim}")
    for dim, size in zip(ids, sizes, strict=True):
        if len(codes[dim]) != size:
            raise SourceError("Inconsistent JSON-stat category size")
    values, flags = data.get("value", {}), data.get("status", {})

    def cell(container, index):
        if isinstance(container, list):
            return container[index] if index < len(container) else None
        return container.get(str(index))

    rows = []
    for country in COUNTRIES:
        for quarter in codes["time"]:
            index = 0
            present = country in codes["geo"]
            if present:
                for dim, size in zip(ids, sizes, strict=True):
                    value = country if dim == "geo" else quarter if dim == "time" else expected[dim]
                    index = index * size + codes[dim].index(value)
            value = cell(values, index) if present else None
            if value is not None and (
                not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0 <= value <= 100
            ):
                raise SourceError("Invalid Eurostat vacancy rate")
            rows.append(
                {
                    "country": country,
                    "quarter": quarter,
                    "vacancy_rate": value,
                    "status_flag": cell(flags, index) if present else None,
                }
            )
    return rows, {
        "dataset": "jvs_q_r21",
        "label": data.get("label"),
        "dimensions": expected,
        "quarters": codes["time"],
        "source_updated_at": data.get("updated"),
        "unit": "percent",
        "scope": "B–T economy; not a data-occupation series",
    }


def fetch_benchmark(*, fetch=get_json):
    url = (
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
    payload = fetch(url)
    rows, metadata = parse_eurostat(payload)
    return {
        "retrieved_at": datetime.now(UTC).isoformat(),
        "request_url": url,
        "payload_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
        "metadata": metadata,
        "rows": rows,
    }
