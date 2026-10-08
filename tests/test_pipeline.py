import copy
from datetime import date
from pathlib import Path

import pytest

from careergraph.analysis import cohort, overview
from careergraph.connectors import normalize_jobtech
from careergraph.contracts import JsonObject
from careergraph.db import connect
from careergraph.demo import DEMO_DATE, demo_records, seed_demo
from careergraph.http import SourceError
from careergraph.pipeline import begin_run, collect_jobtech, ingest


def test_repeated_runs_preserve_history_without_double_counting(db: Path) -> None:
    """Verify repeated runs preserve history without double counting."""
    first = seed_demo(db)
    second = seed_demo(db)
    assert first["accepted_offers"] == second["accepted_offers"] == 768
    assert second["duplicates_removed"] == 2 and second["rejected_records"] == 3
    offers, runs = cohort(db)
    assert len(offers) == 768 and len(runs) == 1
    assert runs[0]["run_id"] == second["run_id"]
    with connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM offers").fetchone()[0] == 1536


def test_country_role_filters_have_explicit_denominator(demo_db: Path) -> None:
    """Verify country role filters have explicit denominator."""
    result = overview(demo_db, country="de", role="data_analyst", known=["sql"])
    assert result["sample"]["offers"] == 12
    assert result["sample"]["small_sample"]
    assert all(s["denominator"] == 12 for s in result["skills"])
    assert result["quality"]["accepted_offers"] == 768


def test_demo_never_populates_live_mode(demo_db: Path) -> None:
    """Verify demo never populates live mode."""
    result = overview(demo_db, mode="live", country="DE")
    assert result["sample"]["availability"] == "not_collected"
    assert result["sample"]["offers"] == 0


def test_unmatched_keywords_are_empty_sample_not_not_collected(db: Path) -> None:
    """Verify unmatched keywords are empty sample not not collected."""
    run = begin_run(db, "jobtech", "live", "SE", {})
    ingest(db, run, [])
    assert overview(db, mode="live", country="SE")["sample"]["availability"] == "empty_sample"


def test_mixed_origin_future_expired_invalid_are_quarantined(db: Path) -> None:
    """Verify mixed origin future expired invalid are quarantined."""
    records = demo_records()[:1]
    records += [{**records[0], "kind": "live"}, {**records[0], "description": "x"}, None]
    run = begin_run(db, "synthetic", "demo", "ALL", {})
    report = ingest(db, run, records, as_of=DEMO_DATE)
    assert report["accepted_offers"] == 1 and report["rejected_records"] == 3
    assert report["rejection_reasons"]["mixed_demo_and_live_data"] == 1


def test_external_country_is_not_relabelled(jobtech_record: JsonObject) -> None:
    """Verify external country is not relabelled."""
    raw = copy.deepcopy(jobtech_record)
    raw["workplace_address"]["country_concept_id"] = "another-country"
    with pytest.raises(ValueError, match="outside_verified_country"):
        normalize_jobtech(raw)


def test_contact_fields_are_not_carried_into_model(jobtech_record: JsonObject) -> None:
    """Verify contact fields are not carried into model."""
    record = normalize_jobtech(jobtech_record)
    assert "employer" not in record and "email" not in record
    assert "someone@example.invalid" not in record["description"]


def test_failed_collection_does_not_replace_successful_snapshot(
    db: Path, jobtech_record: JsonObject
) -> None:
    """Verify failed collection does not replace successful snapshot."""

    def good(url: str) -> JsonObject:
        """Provide one successful source fixture."""
        return {"hits": [jobtech_record], "total": {"value": 1}}

    first = collect_jobtech(db, country="SE", queries=["data"], fetch=good)

    def bad(url: str) -> JsonObject:
        """Simulate a source outage without network access."""
        raise SourceError("Source failed")

    with pytest.raises(SourceError):
        collect_jobtech(db, country="SE", queries=["data"], fetch=bad)
    rows, runs = cohort(db, mode="live", country="SE")
    assert len(rows) == 1 and runs[0]["run_id"] == first["run_id"]
    assert overview(db, mode="live", country="SE")["latest_attempts"][0]["status"] == "failed"
    with connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM runs WHERE status='failed'").fetchone()[0] == 1


def test_changed_offer_is_new_snapshot_not_second_current_offer(db: Path) -> None:
    """Verify changed offer is new snapshot not second current offer."""
    record = demo_records()[0]
    first = begin_run(db, "synthetic", "demo", "ALL", {})
    ingest(db, first, [record], as_of=DEMO_DATE)
    second = begin_run(db, "synthetic", "demo", "ALL", {})
    ingest(
        db,
        second,
        [
            {
                **record,
                "description": "Updated role requiring Python, SQL and Docker in a small example team.",
            }
        ],
        as_of=DEMO_DATE,
    )
    offers, _ = cohort(db)
    assert len(offers) == 1 and "docker" in offers[0]["skills"]


def test_future_and_expired_records_never_reach_analysis(db: Path) -> None:
    """Verify future and expired records never reach analysis."""
    record = demo_records()[0]
    run = begin_run(db, "synthetic", "demo", "ALL", {})
    result = ingest(
        db,
        run,
        [{**record, "published_at": "2030-01-01"}, {**record, "expires_at": "2020-01-01"}],
        as_of=date(2026, 10, 1),
    )
    assert result["accepted_offers"] == 0
    assert result["rejection_reasons"] == {"future_publication_date": 1, "expired_offer": 1}
