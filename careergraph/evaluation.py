"""Transparent regression evaluation; an authored challenge set is not a market benchmark."""

import json
from pathlib import Path

from careergraph.contracts import JsonObject
from careergraph.text import extract_skills


def evaluate(path: str | Path) -> JsonObject:
    """Compare skill mentions with an authored regression-case file.

    Args:
        path: UTF-8 JSON array of cases containing id, text and expected local skill IDs.

    Returns:
        Label-level true/false positives and false negatives, micro precision/recall, exact matches and errors. Undefined precision/recall remain None.

    Raises:
        OSError: The case file cannot be read.
        ValueError: The file is not valid JSON.
        KeyError: A case is missing a required field.

    Side effects:
        Reads the case file and computes results in memory; this is not independent market-accuracy evidence.
    """
    cases: list[JsonObject] = json.loads(Path(path).read_text(encoding="utf-8"))
    tp: int = 0
    fp: int = 0
    fn: int = 0
    exact: int = 0
    errors: list[JsonObject] = []
    for case in cases:
        predicted: set[str] = {m["skill"] for m in extract_skills(case["text"])}
        expected: set[str] = set(case["skills"])
        tp += len(predicted & expected)
        fp += len(predicted - expected)
        fn += len(expected - predicted)
        exact += predicted == expected
        if predicted != expected:
            errors.append(
                {
                    "id": case["id"],
                    "extra": sorted(predicted - expected),
                    "missed": sorted(expected - predicted),
                }
            )
    precision: float | None = tp / (tp + fp) if tp + fp else None
    recall: float | None = tp / (tp + fn) if tp + fn else None
    return {
        "scope": "Authored regression cases only; not an independent multilingual job-ad evaluation.",
        "cases": len(cases),
        "true_positive_labels": tp,
        "false_positive_labels": fp,
        "false_negative_labels": fn,
        "micro_precision": precision,
        "micro_recall": recall,
        "exact_match_cases": exact,
        "errors": errors,
    }
