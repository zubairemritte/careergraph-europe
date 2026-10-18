"""Authored fixtures, not simulated estimates of any country's labour market."""

import random
from datetime import date
from pathlib import Path

from careergraph.catalog import COUNTRIES, ROLES, SKILLS
from careergraph.contracts import JsonObject
from careergraph.pipeline import begin_run, fail_run, ingest

DEMO_DATE: date = date(2026, 10, 1)
BUNDLES: dict[str, list[str]] = {
    "data_analyst": [
        "sql",
        "excel",
        "power_bi",
        "python",
        "statistics",
        "experimentation",
        "data_quality",
        "tableau",
    ],
    "analytics_engineer": [
        "sql",
        "dbt",
        "git",
        "bigquery",
        "snowflake",
        "data_quality",
        "python",
        "airflow",
    ],
    "data_engineer": ["python", "sql", "airflow", "docker", "spark", "aws", "terraform", "azure"],
    "data_scientist": [
        "python",
        "statistics",
        "sql",
        "scikit_learn",
        "experimentation",
        "causal_inference",
        "mlflow",
        "pytorch",
    ],
}


def demo_records(seed: int = 17) -> list[JsonObject]:
    """Build the deterministic fictional software dataset.

    Args:
        seed: Seed used by a local Random instance; default 17 preserves the demo contract.

    Returns:
        773 normalized fixture dictionaries: 768 distinct adverts plus intentional duplicate and rejected-record cases.

    Side effects:
        Creates in-memory fictional records only; no global random-state change, network request or database write.
    """
    randomizer: random.Random = random.Random(seed)
    records: list[JsonObject] = []
    for country in sorted(COUNTRIES):
        for role, pool in BUNDLES.items():
            for number in range(12):
                skills: list[str] = sorted(randomizer.sample(pool, randomizer.randint(2, 5)))
                text: str = ", ".join(SKILLS[s]["aliases"][0] for s in skills)
                source_id: str = f"demo-{country}-{role}-{number:02}"
                records.append(
                    {
                        "source_id": source_id,
                        "country": country,
                        "title": ROLES[role]["label"],
                        "company": f"Example Studio {number + 1:02}",
                        "location": "Illustrative location",
                        "description": f"Synthetic portfolio fixture. This fictional team uses {text}. Build reliable analyses and explain your decisions to colleagues. No actual vacancy is advertised.",
                        "published_at": f"2026-09-{number + 10:02}",
                        "expires_at": None,
                        "source_url": f"https://example.invalid/{source_id}",
                        "role": role,
                        "kind": "demo",
                    }
                )
    records.extend([dict(records[0]), {**records[1], "source_id": "demo-duplicate-id"}])
    records.extend(
        [
            {**records[2], "source_id": "demo-invalid", "description": "Too short"},
            {**records[3], "source_id": "demo-future", "published_at": "2099-01-01"},
            {**records[4], "source_id": "demo-expired", "expires_at": "2020-01-01"},
        ]
    )
    return records


def seed_demo(db: str | Path) -> JsonObject:
    """Store the authored demo using its fixed fixture calendar date.

    Args:
        db: Local SQLite target.

    Returns:
        The ingestion report, normally 773 input / 768 accepted / 2 duplicates / 3 rejected.

    Raises:
        Exception: Fatal storage failure is marked failed and re-raised.

    Side effects:
        Writes a new demo run; existing history remains. Uses DEMO_DATE, not today, so the fixture does not expire with time.
    """
    run_id: str = begin_run(
        db,
        "synthetic",
        "demo",
        "ALL",
        {
            "seed": 17,
            "fixture_date": DEMO_DATE.isoformat(),
            "purpose": "software demonstration only",
        },
    )
    try:
        return ingest(db, run_id, demo_records(), as_of=DEMO_DATE)
    except Exception as error:
        fail_run(db, run_id, error)
        raise
