"""Append-only collection runs; only a successful run becomes visible to analysis."""

import hashlib
import json
import uuid
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import ValidationError

from careergraph.catalog import CATALOG_HASH
from careergraph.connectors import fetch_jobtech, normalize_jobtech
from careergraph.db import connect, init_db
from careergraph.models import Offer
from careergraph.text import clean_text, extract_skills


def now() -> str:
    return datetime.now(UTC).isoformat()


def begin_run(db, source: str, kind: str, country: str, scope: dict) -> str:
    init_db(db)
    run_id = uuid.uuid4().hex
    with connect(db) as conn:
        conn.execute(
            "INSERT INTO runs(run_id,source,kind,country,scope,started_at,status,catalog_hash) VALUES (?,?,?,?,?,?,?,?)",
            (
                run_id,
                source,
                kind,
                country,
                json.dumps(scope, sort_keys=True),
                now(),
                "running",
                CATALOG_HASH,
            ),
        )
    return run_id


def fail_run(db, run_id: str, error: Exception):
    # Never persist arbitrary source bodies or exception messages containing credentials.
    with connect(db) as conn:
        conn.execute(
            "UPDATE runs SET status='failed', completed_at=?, report=? WHERE run_id=?",
            (
                now(),
                json.dumps(
                    {
                        "error_type": type(error).__name__,
                        "message": "Collection failed. No partial data published. See local command output.",
                    }
                ),
                run_id,
            ),
        )


def ingest(
    db,
    run_id: str,
    records: list[dict],
    *,
    normalize=lambda x: x,
    metadata=None,
    as_of: date | None = None,
) -> dict:
    as_of = as_of or datetime.now(UTC).date()
    with connect(db) as conn:
        run = conn.execute(
            "SELECT * FROM runs WHERE run_id=? AND status='running'", (run_id,)
        ).fetchone()
        if not run:
            raise ValueError("The ingestion run must exist and be running")
        rejected, rejected_ids = Counter(), []
        seen_ids, seen_fingerprints = set(), set()
        duplicates = 0
        accepted = []
        for raw in records:
            try:
                record = normalize(raw)
                for key in ["title", "description", "company", "location"]:
                    record[key] = clean_text(record.get(key, ""))
                offer = Offer.model_validate(record)
                if offer.kind != run["kind"]:
                    raise ValueError("mixed_demo_and_live_data")
                if run["country"] != "ALL" and offer.country != run["country"]:
                    raise ValueError("outside_run_country")
                if offer.published_at > as_of:
                    raise ValueError("future_publication_date")
                if offer.expires_at and offer.expires_at < as_of:
                    raise ValueError("expired_offer")
            except (ValidationError, ValueError, TypeError, AttributeError) as exc:
                reasons = {
                    "outside_verified_country",
                    "removed_offer",
                    "mixed_demo_and_live_data",
                    "outside_run_country",
                    "future_publication_date",
                    "expired_offer",
                }
                reason = str(exc) if str(exc) in reasons else "invalid_record"
                rejected[reason] += 1
                if len(rejected_ids) < 20:
                    source_id = (
                        raw.get("id", raw.get("source_id", "unknown"))
                        if isinstance(raw, dict)
                        else "unknown"
                    )
                    rejected_ids.append({"source_id": str(source_id)[:200], "reason": reason})
                continue
            fingerprint_fields = [
                offer.country,
                offer.company,
                offer.location,
                offer.title,
                offer.published_at.isoformat(),
                offer.description,
            ]
            fingerprint = hashlib.sha256(
                json.dumps([v.casefold() for v in fingerprint_fields], ensure_ascii=False).encode()
            ).hexdigest()
            if offer.source_id in seen_ids or fingerprint in seen_fingerprints:
                duplicates += 1
                continue
            seen_ids.add(offer.source_id)
            seen_fingerprints.add(fingerprint)
            offer_id = hashlib.sha256(f"{run['source']}:{offer.source_id}".encode()).hexdigest()[
                :24
            ]
            conn.execute(
                "INSERT INTO offers VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    offer_id,
                    offer.source_id,
                    offer.country,
                    offer.role,
                    offer.title,
                    offer.company,
                    offer.location,
                    offer.description,
                    offer.published_at.isoformat(),
                    offer.expires_at.isoformat() if offer.expires_at else None,
                    offer.source_url,
                    fingerprint,
                ),
            )
            # Evidence offsets always refer to description, never to a concatenated title.
            mentions = extract_skills(offer.description)
            conn.executemany(
                "INSERT INTO skill_mentions VALUES (?,?,?,?,?,?,?)",
                [
                    (
                        run_id,
                        offer_id,
                        m["skill"],
                        m["start"],
                        m["end"],
                        m["matched_text"],
                        m["excerpt"],
                    )
                    for m in mentions
                ],
            )
            accepted.append((offer, mentions))
        report = {
            "input_records": len(records),
            "accepted_offers": len(accepted),
            "duplicates_removed": duplicates,
            "rejected_records": sum(rejected.values()),
            "rejection_reasons": dict(rejected),
            "rejection_examples": rejected_ids,
            "offers_with_skills": sum(bool(mentions) for _, mentions in accepted),
            "as_of": as_of.isoformat(),
            "collection": metadata or {},
        }
        assert (
            report["input_records"]
            == report["accepted_offers"] + duplicates + report["rejected_records"]
        )
        conn.execute(
            "UPDATE runs SET status='success', completed_at=?, report=? WHERE run_id=?",
            (now(), json.dumps(report), run_id),
        )
    return {"run_id": run_id, **report}


def collect_jobtech(db, *, country: str, queries: list[str], pages: int = 2, fetch=None) -> dict:
    from careergraph.catalog import country_code

    country = country_code(country)
    if country != "SE":
        raise ValueError(
            "No verified JobTech workplace connector for this country; JobTech currently supports SE."
        )
    run_id = begin_run(
        db,
        "jobtech",
        "live",
        country,
        {
            "queries": queries,
            "pages_per_query": pages,
            "page_size": 100,
            "sampling": "bounded keyword search; not a national census",
        },
    )
    try:
        records, metadata = fetch_jobtech(
            country, queries, pages, **({"fetch": fetch} if fetch else {})
        )
        return ingest(db, run_id, records, normalize=normalize_jobtech, metadata=metadata)
    except Exception as error:
        fail_run(db, run_id, error)
        raise


def save_benchmark(db: str | Path, snapshot: dict) -> str:
    init_db(db)
    snapshot_id = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()[:24]
    with connect(db) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO benchmark_snapshots VALUES (?,?,?,?,?,?)",
            (
                snapshot_id,
                snapshot["retrieved_at"],
                snapshot["metadata"].get("source_updated_at"),
                snapshot["request_url"],
                snapshot["payload_sha256"],
                json.dumps(snapshot["metadata"]),
            ),
        )
        conn.executemany(
            "INSERT OR IGNORE INTO benchmarks VALUES (?,?,?,?,?)",
            [
                (
                    snapshot_id,
                    row["country"],
                    row["quarter"],
                    row["vacancy_rate"],
                    row.get("status_flag"),
                )
                for row in snapshot["rows"]
            ],
        )
    return snapshot_id
