from pathlib import Path

import pytest

from careergraph.analysis import describe, evidence, skill_bridge
from careergraph.catalog import country_code


def test_skill_bridge_hand_calculated_and_empty_skill_exclusion() -> None:
    """Verify skill bridge hand calculated and empty skill exclusion."""
    offers = [
        {"offer_id": "A", "skills": ["python", "sql"]},
        {"offer_id": "B", "skills": ["python", "sql", "dbt"]},
        {"offer_id": "C", "skills": ["sql", "dbt"]},
        {"offer_id": "D", "skills": ["python", "docker", "aws"]},
        {"offer_id": "E", "skills": []},
    ]
    result = skill_bridge(offers, {"python", "sql"})
    assert result["eligible_offers"] == 4
    assert result["covered_offers"] == 1 and result["covered_share"] == 0.25
    assert result["excluded_without_detected_skills"] == 1
    assert result["add_one_skill"] == [
        {
            "skill": "dbt",
            "label": "dbt",
            "additional_offers": 2,
            "share_of_eligible": 0.5,
            "example_offer_ids": ["B", "C"],
        }
    ]


def test_adding_a_skill_cannot_reduce_coverage() -> None:
    """Verify adding a skill cannot reduce coverage."""
    offers = [{"offer_id": "a", "skills": ["sql", "python"]}, {"offer_id": "b", "skills": ["sql"]}]
    assert (
        skill_bridge(offers, {"sql", "python"})["covered_offers"]
        >= skill_bridge(offers, {"sql"})["covered_offers"]
    )


def test_pair_support_jaccard_and_denominator() -> None:
    """Verify pair support jaccard and denominator."""
    offers = [
        {
            "offer_id": str(i),
            "skills": skills,
            "country": "DE",
            "source": "synthetic",
            "published_at": "2026-09-01",
        }
        for i, skills in enumerate([["python", "sql"], ["python", "sql"], ["python"], []])
    ]
    result = describe(offers, [], known=set(), min_support=2)
    edge = result["relationships"][0]
    assert edge["support"] == 2 and edge["jaccard"] == pytest.approx(2 / 3)
    assert result["skills"][0]["share"] == 0.75
    assert describe(offers, [], known=set(), min_support=3)["relationships"] == []


def test_evidence_drilldown_reconciles_with_bridge(demo_db: Path) -> None:
    """Verify evidence drilldown reconciles with bridge."""
    from careergraph.analysis import overview

    result = overview(demo_db, known=["python", "sql"])
    for item in result["bridge"]["add_one_skill"]:
        rows = evidence(demo_db, known=["python", "sql"], missing_skill=item["skill"], limit=100)
        assert rows["total"] == item["additional_offers"]
        assert all(o["missing_skills"] == [item["skill"]] for o in rows["offers"])


def test_country_codes_are_not_silently_guessed() -> None:
    """Verify country codes are not silently guessed."""
    assert country_code(" de ") == "DE"
    with pytest.raises(ValueError):
        country_code("UK")
