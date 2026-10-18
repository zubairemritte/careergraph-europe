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
    """Operational class coordinating one advert-to-database workflow.

    The instance stores a database Path. collect consumes an AdvertConnector, records the attempt and publishes only a complete successful ingestion. It does not implement provider field mappings.
    """

    def __init__(self, db: str | Path) -> None:
        """Select the database used by this collection service.

        Args:
            db: A local SQLite filename or Path.

        Returns:
            None; stores the target Path on this instance.

        Side effects:
            No database creation or source request until collect is called.
        """
        self.db: Path = Path(db)

    def collect(
        self, connector: AdvertConnector, *, country: str, queries: list[str], pages: int = 2
    ) -> JsonObject:
        """Audit and publish one complete source/country collection.

        Args:
            connector: AdvertConnector implementation that declares coverage and normalizes hits.
            country: Configured workplace code; the verified adapter currently accepts SE only.
            queries: One to eight nonempty search terms, each at most 100 characters.
            pages: Page budget per query, from one to five; each page requests at most 100 hits.

        Returns:
            A run report with run_id, input/accepted/duplicate/rejected counts, reasons and request metadata.

        Raises:
            ValueError: The country or connector request configuration is invalid.
            Exception: A fatal provider/storage error is recorded as failed, then re-raised.

        Side effects:
            Creates a run audit and requests a bounded batch. Only a fully successful transaction becomes current; a failed refresh preserves the previous successful sample.
        """
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
    """Copy the top level of an already-normalized fixture.

    Args:
        record: Offer-shaped dictionary used by the demo or direct ingestion.

    Returns:
        A shallow dictionary copy. Nested objects are not deep-copied.

    Side effects:
        Prevents ingestion's text-field cleanup from replacing values on the caller's dictionary.
    """
    return dict(record)


def now() -> str:
    """Create a timezone-aware collection-audit timestamp.

    Returns:
        Current UTC datetime formatted as an ISO string.

    Side effects:
        Reads the system clock; writes nothing.
    """
    return datetime.now(UTC).isoformat()


def begin_run(db: str | Path, source: str, kind: str, country: str, scope: JsonObject) -> str:
    """Initialize the schema and create a running collection audit.

    Args:
        db: Local SQLite target.
        source: Stable provider ID, such as jobtech or synthetic.
        kind: demo or live; these data origins must remain separate.
        country: Configured workplace code, or ALL for the multi-country demo.
        scope: Serializable query/page/sampling settings to retain with this attempt.

    Returns:
        A new opaque run ID used by ingest and fail_run.

    Raises:
        sqlite3.Error: The audit cannot be stored.
        TypeError: Scope contains values that JSON cannot serialize.

    Side effects:
        Creates the schema if required and commits a running audit before records are ingested.
    """
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
    """Record a failed attempt without exposing arbitrary provider error bodies.

    Args:
        db: Database containing the running audit.
        run_id: Identifier returned by begin_run.
        error: Fatal exception; only its type and a fixed safe message are retained.

    Returns:
        None. The audit becomes failed with a completion timestamp.

    Raises:
        sqlite3.Error: The audit update cannot be committed.

    Side effects:
        Updates the run report only. Does not publish partial adverts or replace an earlier successful sample.
    """
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
    """Validate, deduplicate and atomically store a complete offer sample.

    Args:
        db: Local SQLite target.
        run_id: Existing running audit; its mode and country define the permitted sample.
        records: Source observations or normalized demo fixtures.
        normalize: Record-to-Offer-input callable; the default copies normalized fixtures.
        metadata: Optional serializable request provenance included in the quality report.
        as_of: Calendar date for future/expiry checks; defaults to the current UTC date.

    Returns:
        The run ID and reconciliation report. input_records equals accepted_offers + duplicates_removed + rejected_records.

    Raises:
        ValueError: The audit does not exist or is not running.
        sqlite3.Error: A fatal storage error rolls back this sample.
        TypeError: Fatal report metadata cannot be serialized.

    Side effects:
        Stores sanitized observations and exact description evidence. Bad records are counted/quarantined; run success and all accepted rows commit together.
    """
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
    """Run the public advert workflow through its adapter and service.

    Args:
        db: Local SQLite target.
        country: Configured workplace code; the verified adapter currently accepts SE only.
        queries: One to eight nonempty search terms, each at most 100 characters.
        pages: Page budget per query, from one to five; each page requests at most 100 hits.
        fetch: Optional injected source fetcher; None selects the bounded HTTP client.

    Returns:
        The same validated collection report returned by CollectionService.collect.

    Raises:
        ValueError: Country or search configuration is invalid.
        Exception: Fatal source/storage failure is audited by the service and re-raised.

    Side effects:
        This is the CLI collect entry function. It constructs the two runtime objects; it does not duplicate their logic.
    """
    connector: JobTechConnector = (
        JobTechConnector(fetch) if fetch is not None else JobTechConnector()
    )
    service: CollectionService = CollectionService(db)
    return service.collect(connector, country=country, queries=queries, pages=pages)


def save_benchmark(db: str | Path, snapshot: BenchmarkSnapshot) -> str:
    """Store an already-validated official snapshot independently of adverts.

    Args:
        db: Local SQLite target.
        snapshot: BenchmarkSnapshot from EurostatConnector or a trusted exported snapshot.

    Returns:
        A content-derived snapshot ID. Saving the identical snapshot twice is idempotent.

    Raises:
        sqlite3.Error: The snapshot transaction cannot be committed.
        KeyError: A supplied file does not follow the documented snapshot contract.

    Side effects:
        Creates schema if needed and writes official snapshots/cells. No network request or offer-row insertion.
    """
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
