"""Transparent regression evaluation; an authored challenge set is not a market benchmark."""

import json
from pathlib import Path

from careergraph.text import extract_skills


def evaluate(path: str | Path) -> dict:
    cases = json.loads(Path(path).read_text(encoding="utf-8"))
    tp = fp = fn = exact = 0
    errors = []
    for case in cases:
        predicted = {m["skill"] for m in extract_skills(case["text"])}
        expected = set(case["skills"])
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
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
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
