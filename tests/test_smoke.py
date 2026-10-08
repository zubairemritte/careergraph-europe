"""Small, network-free checks for the 0.2 refactor; no full demo is generated."""

import ast
import copy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from careergraph.analysis import overview
from careergraph.api import create_app
from careergraph.connectors import EurostatConnector, JobTechConnector
from careergraph.contracts import JsonObject
from careergraph.http import SourceError
from careergraph.pipeline import CollectionService


def test_small_batch_reconciles_and_exposes_evidence(db: Path, jobtech_record: JsonObject) -> None:
    """Four input records exercise success, duplicate and country quarantine paths."""
    second: JsonObject = copy.deepcopy(jobtech_record)
    second["id"] = "test-2"
    second["description"]["text"] = "Build reliable analytical products with Python, SQL and dbt."
    foreign: JsonObject = copy.deepcopy(jobtech_record)
    foreign["id"] = "foreign"
    foreign["workplace_address"]["country_concept_id"] = "unverified-country"

    def fixture_fetch(url: str) -> JsonObject:
        """Supply four authored records instead of requesting a public API."""
        return {"hits": [jobtech_record, second, jobtech_record, foreign], "total": {"value": 4}}

    report: JsonObject = CollectionService(db).collect(
        JobTechConnector(fixture_fetch), country="SE", queries=["data analyst"], pages=1
    )
    assert report["input_records"] == 4
    assert report["accepted_offers"] == 2
    assert report["duplicates_removed"] == 1
    assert report["rejected_records"] == 1
    assert report["rejection_reasons"] == {"outside_verified_country": 1}
    with TestClient(create_app(db)) as client:
        result: JsonObject = client.get(
            "/api/overview?mode=live&country=SE&role=data_analyst&skills=python,sql"
        ).json()
        assert result["sample"]["offers"] == 2
        assert result["bridge"]["covered_offers"] == 1
        assert result["bridge"]["add_one_skill"][0]["skill"] == "dbt"
        evidence: JsonObject = client.get(
            "/api/evidence?mode=live&country=SE&skills=python,sql&missing_skill=dbt"
        ).json()
        assert evidence["total"] == 1
        assert evidence["offers"][0]["missing_skills"] == ["dbt"]
        match = next(m for m in evidence["offers"][0]["mentions"] if m["skill"] == "dbt")
        assert second["description"]["text"][match["start_offset"] : match["end_offset"]] == "dbt"
        assert client.get("/api/overview?country=DE&mode=live").json()["sample"]["offers"] == 0
        assert "someone@example.invalid" not in str(evidence)


def test_failed_refresh_preserves_the_one_record_sample(
    db: Path, jobtech_record: JsonObject
) -> None:
    """An injected source failure must preserve the previous successful cohort."""
    service: CollectionService = CollectionService(db)

    def good(url: str) -> JsonObject:
        """Return one valid authored advert."""
        return {"hits": [jobtech_record], "total": {"value": 1}}

    first: JsonObject = service.collect(JobTechConnector(good), country="SE", queries=["data"])

    def bad(url: str) -> JsonObject:
        """Simulate a provider outage without network access."""
        raise SourceError("fixture outage")

    with pytest.raises(SourceError):
        service.collect(JobTechConnector(bad), country="SE", queries=["data"])
    result: JsonObject = overview(db, mode="live", country="SE")
    assert result["sample"]["offers"] == 1
    assert result["runs"][0]["run_id"] == first["run_id"]
    assert result["latest_attempts"][0]["status"] == "failed"


def test_unsupported_country_stops_before_transport(db: Path) -> None:
    """A country selector must never silently relabel another market's adverts."""

    def forbidden(url: str) -> JsonObject:
        """Fail immediately if the service attempts a transport call."""
        pytest.fail("No HTTP request is permitted in this check")

    with pytest.raises(ValueError, match="No verified"):
        CollectionService(db).collect(JobTechConnector(forbidden), country="DE", queries=["data"])


def test_eurostat_class_retains_missingness_and_flags() -> None:
    """A four-cell source fixture checks reordered axes and the separate snapshot contract."""
    axes: dict[str, list[str]] = {
        "time": ["2026-Q1", "2026-Q2"],
        "geo": ["DE", "FR"],
        "freq": ["Q"],
        "indic_em": ["JVR"],
        "sizeclas": ["TOTAL"],
        "nace_r2_1": ["B-T"],
        "s_adj": ["SA"],
    }

    def fixture_fetch(url: str) -> JsonObject:
        """Return a sparse official-series fixture with one missing observation."""
        return {
            "id": list(axes),
            "size": [len(codes) for codes in axes.values()],
            "dimension": {axis: {"category": {"index": codes}} for axis, codes in axes.items()},
            "value": {"0": 1.1, "2": 1.3, "3": 2.4},
            "status": {"3": "p"},
        }

    snapshot = EurostatConnector(fixture_fetch).fetch_snapshot()
    cells = {(row["country"], row["quarter"]): row for row in snapshot["rows"]}
    assert cells["FR", "2026-Q1"]["vacancy_rate"] is None
    assert cells["DE", "2026-Q2"]["vacancy_rate"] == 1.3
    assert cells["FR", "2026-Q2"]["status_flag"] == "p"


def test_public_functions_have_docstrings_and_typed_signatures() -> None:
    """Protect the explanatory function contracts, including nested HTTP handlers."""
    root: Path = Path(__file__).resolve().parents[1]
    for path in [
        *root.joinpath("careergraph").rglob("*.py"),
        *root.joinpath("scripts").glob("*.py"),
    ]:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert ast.get_docstring(node), f"Missing docstring: {path.name}:{node.name}"
                assert node.returns is not None, f"Missing return type: {node.name}"
                arguments = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
                arguments += [a for a in [node.args.vararg, node.args.kwarg] if a is not None]
                assert all(a.annotation is not None or a.arg in {"self", "cls"} for a in arguments)
