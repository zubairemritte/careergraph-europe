"""Append-only collection runs; only a successful run becomes visible to analysis."""

import hashlib
import json
import sqlite3
import uuid
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import ValidationError

from careergraph.catalog import CATALOG_HASH
from careergraph.connectors import JobTechConnector
from careergraph.contracts import (
    AdvertConnector,
    BenchmarkSnapshot,
    CollectionBatch,
    JsonFetcher,
    JsonObject,
    Normalizer,
    SkillMention,
)
from careergraph.db import connect, init_db
from careergraph.models import Offer
from careergraph.text import clean_text, extract_skills


class CollectionService:
    """Own a database target and publish only complete validated provider samples."""

    def __init__(self, db: str | Path) -> None:
        """Select the local database without collecting or initializing data."""
        self.db: Path = Path(db)

    def collect(
        self, connector: AdvertConnector, *, country: str, queries: list[str], pages: int = 2
    ) -> JsonObject:
        """Audit a bounded collection; a failure leaves prior successful samples visible."""
        from careergraph.catalog import country_code

        code: str = country_code(country)
        if code not in connector.supported_countries:
            raise ValueError(f"No verified {connector.source_id} workplace connector for {code}")
        run_id: str = begin_run(
            self.db,
            connector.source_id,
            "live",
            code,
            {
                "queries": queries,
                "pages_per_query": pages,
                "page_size": 100,
                "sampling": "bounded keyword search; not a national census",
            },
        )
        try:
            batch: CollectionBatch = connector.collect(code, queries, pages)
            return ingest(
                self.db,
                run_id,
                batch.records,
                normalize=connector.normalize,
                metadata=batch.metadata,
            )
        except Exception as error:
            fail_run(self.db, run_id, error)
            raise


def identity_record(record: JsonObject) -> JsonObject:
    """Copy an already-normalized fixture so ingestion never edits its caller's data."""
    return dict(record)


def now() -> str:
    """Return a timezone-aware UTC timestamp for the collection audit."""
    return datetime.now(UTC).isoformat()


def begin_run(db: str | Path, source: str, kind: str, country: str, scope: JsonObject) -> str:
    """Create a running audit record before processing any provider observations."""
    init_db(db)
    run_id: str = uuid.uuid4().hex
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


def fail_run(db: str | Path, run_id: str, error: Exception) -> None:
    """Mark a run failed using a safe error category; never store arbitrary source errors."""
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
    db: str | Path,
    run_id: str,
    records: list[JsonObject],
    *,
    normalize: Normalizer = identity_record,
    metadata: JsonObject | None = None,
    as_of: date | None = None,
) -> JsonObject:
    """Validate, deduplicate and atomically publish a complete normalized offer sample."""
    as_of = as_of or datetime.now(UTC).date()
    with connect(db) as conn:
        run: sqlite3.Row | None = conn.execute(
            "SELECT * FROM runs WHERE run_id=? AND status='running'", (run_id,)
        ).fetchone()
        if not run:
            raise ValueError("The ingestion run must exist and be running")
        rejected: Counter[str]
        rejected_ids: list[JsonObject]
        rejected, rejected_ids = (Counter(), [])
        seen_ids: set[str]
        seen_fingerprints: set[str]
        seen_ids, seen_fingerprints = (set(), set())
        duplicates: int = 0
        accepted: list[tuple[Offer, list[SkillMention]]] = []
        for raw in records:
            try:
                record: JsonObject = normalize(raw)
                for key in ["title", "description", "company", "location"]:
                    record[key] = clean_text(record.get(key, ""))
                offer: Offer = Offer.model_validate(record)
                if offer.kind != run["kind"]:
                    raise ValueError("mixed_demo_and_live_data")
                if run["country"] != "ALL" and offer.country != run["country"]:
                    raise ValueError("outside_run_country")
                if offer.published_at > as_of:
                    raise ValueError("future_publication_date")
                if offer.expires_at and offer.expires_at < as_of:
                    raise ValueError("expired_offer")
            except (ValidationError, ValueError, TypeError, AttributeError) as exc:
                reasons: set[str] = {
                    "outside_verified_country",
                    "removed_offer",
                    "mixed_demo_and_live_data",
                    "outside_run_country",
                    "future_publication_date",
                    "expired_offer",
                }
                reason: str = str(exc) if str(exc) in reasons else "invalid_record"
                rejected[reason] += 1
                if len(rejected_ids) < 20:
                    source_id: object = (
                        raw.get("id", raw.get("source_id", "unknown"))
                        if isinstance(raw, dict)
                        else "unknown"
                    )
                    rejected_ids.append({"source_id": str(source_id)[:200], "reason": reason})
                continue
            fingerprint_fields: list[str] = [
                offer.country,
                offer.company,
                offer.location,
                offer.title,
                offer.published_at.isoformat(),
                offer.description,
            ]
            fingerprint: str = hashlib.sha256(
                json.dumps([v.casefold() for v in fingerprint_fields], ensure_ascii=False).encode()
            ).hexdigest()
            if offer.source_id in seen_ids or fingerprint in seen_fingerprints:
                duplicates += 1
                continue
            seen_ids.add(offer.source_id)
            seen_fingerprints.add(fingerprint)
            offer_id: str = hashlib.sha256(
                f"{run['source']}:{offer.source_id}".encode()
            ).hexdigest()[:24]
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
            mentions: list[SkillMention] = extract_skills(offer.description)
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
        report: JsonObject = {
            "input_records": len(records),
            "accepted_offers": len(accepted),
            "duplicates_removed": duplicates,
            "rejected_records": sum(rejected.values()),
            "rejection_reasons": dict(rejected),
            "rejection_examples": rejected_ids,
            "offers_with_skills": sum((bool(mentions) for _, mentions in accepted)),
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


def collect_jobtech(
    db: str | Path,
    *,
    country: str,
    queries: list[str],
    pages: int = 2,
    fetch: JsonFetcher | None = None,
) -> JsonObject:
    """Collect the verified provider through CollectionService with an injectable transport."""
    connector: JobTechConnector = (
        JobTechConnector(fetch) if fetch is not None else JobTechConnector()
    )
    service: CollectionService = CollectionService(db)
    return service.collect(connector, country=country, queries=queries, pages=pages)


def save_benchmark(db: str | Path, snapshot: BenchmarkSnapshot) -> str:
    """Store an attributed aggregate snapshot idempotently without creating advert rows."""
    init_db(db)
    snapshot_id: str = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()[
        :24
    ]
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
