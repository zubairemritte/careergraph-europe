"""Sample-based measures with explicit denominators; no employability score."""

import json
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from typing import Unpack

from careergraph.catalog import COUNTRIES, ROLES, SKILLS, country_code, validate_skills
from careergraph.contracts import CohortFilters, JsonObject, StoredSkillMention
from careergraph.db import connect


def latest_runs(conn: sqlite3.Connection, mode: str) -> list[JsonObject]:
    """Select one latest successful run per provider/workplace scope.

    Args:
        conn: An open row-enabled SQLite connection.
        mode: demo or live; callers validate this origin before selecting a cohort.

    Returns:
        Raw audit dictionaries including JSON-text scope/report and the internal row position.

    Raises:
        sqlite3.Error: The run query cannot be executed.

    Side effects:
        Reads only. Uses completion time and row order to break ties.
    """
    rows: list[sqlite3.Row] = conn.execute(
        """
        SELECT * FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY source, country ORDER BY completed_at DESC, rowid DESC
            ) AS position FROM runs WHERE status='success' AND kind=?
        ) WHERE position=1
    """,
        (mode,),
    ).fetchall()
    return [dict(row) for row in rows]


def cohort(
    db: str | Path,
    *,
    mode: str = "demo",
    country: str = "ALL",
    role: str = "all",
    since: str | None = None,
) -> tuple[list[JsonObject], list[JsonObject]]:
    """Load the current filtered offers and their exact evidence.

    Args:
        db: Initialized local database target.
        mode: demo or live; these cohorts are never combined.
        country: Configured country or ALL.
        role: Configured role family or all.
        since: Optional inclusive publication-date lower bound as YYYY-MM-DD.

    Returns:
        An (offers, runs) tuple. Offers contain their skill IDs, stored mentions and source. Runs remain raw audit dictionaries; they describe whole selected collections.

    Raises:
        ValueError: Mode, country or role is invalid.
        sqlite3.Error: The database cannot provide the requested cohort.

    Side effects:
        Reads only. Uses bulk evidence loading and the latest successful run per provider/country; does not merge historical snapshots.
    """
    if mode not in {"demo", "live"}:
        raise ValueError("Mode must be demo or live")
    country = country_code(country, allow_all=True)
    if role != "all" and role not in ROLES:
        raise ValueError("Unknown role")
    with connect(db) as conn:
        runs: list[JsonObject] = [
            r
            for r in latest_runs(conn, mode)
            if country == "ALL" or r["country"] in {country, "ALL"}
        ]
        if not runs:
            return ([], [])
        params: list[str] = [r["run_id"] for r in runs]
        where: str = "run_id IN (" + ",".join("?" for _ in params) + ")"
        if country != "ALL":
            where += " AND country=?"
            params.append(country)
        if role != "all":
            where += " AND role=?"
            params.append(role)
        if since:
            where += " AND published_at>=?"
            params.append(since)
        rows: list[sqlite3.Row] = conn.execute(
            "SELECT * FROM offers WHERE " + where + " ORDER BY published_at DESC, offer_id", params
        ).fetchall()
        mentions_by_offer: dict[tuple[str, str], list[StoredSkillMention]] = {}
        run_ids: list[str] = [r["run_id"] for r in runs]
        for match in conn.execute(
            "SELECT * FROM skill_mentions WHERE run_id IN ("
            + ",".join("?" for _ in run_ids)
            + ") ORDER BY skill",
            run_ids,
        ):
            key: tuple[str, str] = (match["run_id"], match["offer_id"])
            mention: StoredSkillMention = {
                "skill": match["skill"],
                "start_offset": match["start_offset"],
                "end_offset": match["end_offset"],
                "matched_text": match["matched_text"],
                "excerpt": match["excerpt"],
            }
            mentions_by_offer.setdefault(key, []).append(mention)
        sources: dict[str, str] = {r["run_id"]: r["source"] for r in runs}
        result: list[JsonObject] = []
        for row in rows:
            offer: JsonObject = dict(row)
            mentions: list[StoredSkillMention] = mentions_by_offer.get(
                (row["run_id"], row["offer_id"]), []
            )
            offer["mentions"] = mentions
            offer["skills"] = [m["skill"] for m in mentions]
            offer["source"] = sources[row["run_id"]]
            result.append(offer)
    return (result, runs)


def skill_bridge(offers: list[JsonObject], known: set[str]) -> JsonObject:
    """Count the exact additional coverage from one skill.

    Args:
        offers: Selected offer dictionaries containing offer_id and detected skills.
        known: Validated local skill IDs currently selected by the user.

    Returns:
        Baseline coverage and ranked one-skill gains. Offers with no detected skills are excluded from this metric's eligible denominator.

    Side effects:
        Pure calculation; does not edit offers or known skills. Mentions are not qualifications or hiring probabilities.

    Example:
        With known={"python", "sql"}, an offer with python/sql/dbt contributes one gain to dbt.
    """
    eligible: list[JsonObject] = [o for o in offers if o["skills"]]
    covered: list[JsonObject] = [o for o in eligible if set(o["skills"]) <= known]
    gains: Counter[str] = Counter()
    examples: dict[str, list[str]] = {}
    for offer in eligible:
        missing: set[str] = set(offer["skills"]) - known
        if len(missing) == 1:
            skill: str = next(iter(missing))
            gains[skill] += 1
            examples.setdefault(skill, []).append(offer["offer_id"])
    ranked: list[JsonObject] = [
        {
            "skill": s,
            "label": SKILLS[s]["label"],
            "additional_offers": n,
            "share_of_eligible": n / len(eligible),
            "example_offer_ids": examples[s][:5],
        }
        for s, n in sorted(gains.items(), key=lambda pair: (-pair[1], pair[0]))
    ]
    return {
        "known_skills": sorted(known),
        "eligible_offers": len(eligible),
        "excluded_without_detected_skills": len(offers) - len(eligible),
        "covered_offers": len(covered),
        "covered_share": len(covered) / len(eligible) if eligible else None,
        "add_one_skill": ranked,
        "interpretation": "Coverage of detected skill mentions only. Not a hiring probability, qualification assessment or causal estimate.",
    }


def describe(
    offers: list[JsonObject], runs: list[JsonObject], *, known: set[str], min_support: int = 3
) -> JsonObject:
    """Summarize one cohort while preserving the caller's offers and audits.

    Args:
        offers: Filtered normalized offers returned by cohort.
        runs: Raw cohort audits; scope/report must still be JSON strings.
        known: Validated selected skill IDs.
        min_support: Minimum advert co-occurrence count for displayed skill pairs.

    Returns:
        Sample size/freshness, frequencies, pairs, bridge, whole-run quality totals and decoded audit copies. Frequency denominators include every selected advert.

    Raises:
        ValueError: A raw audit JSON value is invalid.
        TypeError: An audit was supplied already decoded instead of following cohort's contract.

    Side effects:
        Reads the clock for age. Does not modify either input; the same raw cohort can be summarized repeatedly.
    """
    counts: Counter[str] = Counter(skill for o in offers for skill in set(o["skills"]))
    n: int = len(offers)
    pairs: Counter[tuple[str, str]] = Counter(
        pair for o in offers for pair in combinations(sorted(set(o["skills"])), 2)
    )
    frequencies: list[JsonObject] = [
        {"skill": s, "label": SKILLS[s]["label"], "count": c, "denominator": n, "share": c / n}
        for s, c in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    ]
    relationships: list[JsonObject] = [
        {
            "left": a,
            "right": b,
            "support": c,
            "denominator": n,
            "jaccard": c / (counts[a] + counts[b] - c),
        }
        for (a, b), c in pairs.items()
        if c >= min_support
    ]
    relationships.sort(key=lambda p: (-p["support"], -p["jaccard"], p["left"], p["right"]))
    public_runs: list[JsonObject] = [
        {key: value for key, value in run.items() if key != "position"}
        | {"scope": json.loads(run["scope"]), "report": json.loads(run["report"])}
        for run in runs
    ]
    reports: list[JsonObject] = [run["report"] for run in public_runs]
    timestamps: list[datetime] = [datetime.fromisoformat(run["completed_at"]) for run in runs]
    age: float | None = (
        (datetime.now(UTC) - min(timestamps)).total_seconds() / 3600 if timestamps else None
    )
    return {
        "sample": {
            "offers": n,
            "offers_with_skills": sum(bool(o["skills"]) for o in offers),
            "countries": sorted({o["country"] for o in offers}),
            "sources": sorted({o["source"] for o in offers}),
            "publication_min": min((o["published_at"] for o in offers), default=None),
            "publication_max": max((o["published_at"] for o in offers), default=None),
            "small_sample": n < 30,
            "availability": "observed_sample" if n else "empty_sample" if runs else "not_collected",
            "collection_age_hours": round(age, 1) if age is not None else None,
            "stale": age is not None and age > 48 and any(r["kind"] == "live" for r in runs),
        },
        "skills": frequencies,
        "relationships": relationships[:20],
        "bridge": skill_bridge(offers, known),
        "quality": {
            "scope": "whole collection runs, before country/role/date filtering",
            "input_records": sum(r["input_records"] for r in reports),
            "accepted_offers": sum(r["accepted_offers"] for r in reports),
            "duplicates_removed": sum(r["duplicates_removed"] for r in reports),
            "rejected_records": sum(r["rejected_records"] for r in reports),
        },
        "runs": public_runs,
    }


def overview(
    db: str | Path,
    *,
    known: list[str] | None = None,
    min_support: int = 3,
    **filters: Unpack[CohortFilters],
) -> JsonObject:
    """Combine cohort metrics with the most recent collection attempts.

    Args:
        db: Initialized local SQLite target.
        known: Selected local skill IDs; None means an empty known set.
        min_support: Minimum pair support passed to describe.
        filters: Optional mode, country, role and since values accepted by cohort.

    Returns:
        The response used by CLI inspect and GET /api/overview, including latest failed attempts beside the current successful data.

    Raises:
        ValueError: A selected skill or cohort filter is invalid.
        sqlite3.Error: A read query fails.

    Side effects:
        Reads the database only. Does not collect, overwrite stored matches or fall back from live to demo.
    """
    known_ids: set[str] = validate_skills(known or [])
    offers: list[JsonObject]
    runs: list[JsonObject]
    offers, runs = cohort(db, **filters)
    with connect(db) as conn:
        attempts: list[JsonObject] = [
            dict(row)
            for row in conn.execute(
                """
            SELECT run_id,source,country,status,started_at,completed_at FROM (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY source,country ORDER BY started_at DESC,rowid DESC) AS position
                FROM runs WHERE kind=?
            ) WHERE position=1
        """,
                (filters.get("mode", "demo"),),
            )
        ]
    country: str = country_code(filters.get("country", "ALL"), allow_all=True)
    attempts = [r for r in attempts if country == "ALL" or r["country"] in {country, "ALL"}]
    return {
        "filters": filters,
        "latest_attempts": attempts,
        **describe(offers, runs, known=known_ids, min_support=min_support),
    }


def evidence(
    db: str | Path,
    *,
    known: list[str] | None = None,
    missing_skill: str | None = None,
    limit: int = 25,
    offset: int = 0,
    **filters: Unpack[CohortFilters],
) -> JsonObject:
    """Page the adverts behind a selected skill result.

    Args:
        db: Initialized local SQLite target.
        known: Selected local skill IDs; None means no known skills.
        missing_skill: Optional local skill ID; retain adverts with exactly this one missing detected skill.
        limit: Maximum returned rows; the HTTP layer enforces 1-100.
        offset: Rows to skip; the HTTP layer enforces a nonnegative value.
        filters: Optional mode, country, role and since values accepted by cohort.

    Returns:
        Total matching adverts plus the page, stored evidence snippets and missing skill IDs. Full descriptions are not exposed.

    Raises:
        ValueError: A skill ID or cohort filter is invalid.
        sqlite3.Error: The selected sample cannot be read.

    Side effects:
        Read-only drill-down. Direct Python callers should supply valid pagination bounds.
    """
    known_ids: set[str] = validate_skills(known or [])
    offers: list[JsonObject]
    if missing_skill and missing_skill not in SKILLS:
        raise ValueError("Unknown missing skill")
    offers, _ = cohort(db, **filters)
    if missing_skill:
        offers = [o for o in offers if set(o["skills"]) - known_ids == {missing_skill}]
    result: list[JsonObject] = []
    for offer in offers[offset : offset + limit]:
        missing: list[str] = sorted(set(offer["skills"]) - known_ids)
        result.append(
            {
                k: offer[k]
                for k in [
                    "offer_id",
                    "source_id",
                    "source",
                    "country",
                    "role",
                    "title",
                    "company",
                    "location",
                    "published_at",
                    "source_url",
                    "skills",
                    "mentions",
                ]
            }
            | {"missing_skills": missing}
        )
    return {"total": len(offers), "offset": offset, "limit": limit, "offers": result}


def benchmark(db: str | Path, country: str = "ALL") -> JsonObject:
    """Read the latest attributed official snapshot for a country filter.

    Args:
        db: Initialized local SQLite target.
        country: Configured country or ALL.

    Returns:
        Availability, metadata, hashes, attribution and country/quarter cells; an absent snapshot gives available=False and no rows.

    Raises:
        ValueError: The country parameter is invalid.
        sqlite3.Error: The snapshot query fails.

    Side effects:
        Reads only. Missing cells remain None; no refresh or alternate-series substitution occurs.
    """
    country = country_code(country, allow_all=True)
    with connect(db) as conn:
        snapshot: sqlite3.Row | None = conn.execute(
            "SELECT * FROM benchmark_snapshots ORDER BY retrieved_at DESC, rowid DESC LIMIT 1"
        ).fetchone()
        if not snapshot:
            return {
                "available": False,
                "reason": "No official benchmark snapshot loaded",
                "rows": [],
            }
        params: list[str] = [snapshot["snapshot_id"]]
        query: str = (
            "SELECT country,quarter,vacancy_rate,status_flag FROM benchmarks WHERE snapshot_id=?"
        )
        if country != "ALL":
            query += " AND country=?"
            params.append(country)
        rows: list[JsonObject] = [
            dict(r) for r in conn.execute(query + " ORDER BY country,quarter", params)
        ]
    return {
        "available": True,
        "retrieved_at": snapshot["retrieved_at"],
        "source_updated_at": snapshot["source_updated_at"],
        "request_url": snapshot["request_url"],
        "payload_sha256": snapshot["payload_sha256"],
        "metadata": json.loads(snapshot["metadata"]),
        "rows": rows,
        "attribution": "Source: Eurostat, jvs_q_r21. Selected and reshaped by CareerGraph Europe. Eurostat is not responsible for this analysis.",
    }


def coverage(db: str | Path) -> list[JsonObject]:
    """Report the difference between configured and connected markets.

    Args:
        db: Initialized local SQLite target.

    Returns:
        One row per configured country with offer-connector/run status and latest-quarter official-statistics availability.

    Raises:
        sqlite3.Error: The local availability queries fail.

    Side effects:
        Reads only. A ready connector is distinct from an actual successful collection.
    """
    with connect(db) as conn:
        runs: list[JsonObject] = latest_runs(conn, "live")
    official: JsonObject = benchmark(db)
    quarter: str | None = max((r["quarter"] for r in official["rows"]), default=None)
    available: set[str] = {
        r["country"]
        for r in official["rows"]
        if r["quarter"] == quarter and r["vacancy_rate"] is not None
    }
    return [
        {
            "country": code,
            "name": name,
            "live_offer_source": "jobtech" if code == "SE" else None,
            "offer_status": "collected"
            if any(r["country"] == code for r in runs)
            else "connector_ready"
            if code == "SE"
            else "not_connected",
            "benchmark_status": "available" if code in available else "unavailable",
            "benchmark_quarter": quarter,
        }
        for code, name in COUNTRIES.items()
    ]
