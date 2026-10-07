import json
from pathlib import Path

import pytest

from careergraph.text import clean_text, extract_skills, role_family

CASES = json.loads((Path(__file__).parent / "fixtures/skill_cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_mention_contract(case):
    matches = extract_skills(case["text"])
    assert {m["skill"] for m in matches} == set(case["skills"])
    for match in matches:
        assert case["text"][match["start"] : match["end"]] == match["matched_text"]


def test_html_and_contact_minimization():
    text = clean_text(
        "<p>Python <strong>and SQL</strong></p><script>alert(1)</script> Contact a.b@example.org or +46 70 123 45 67."
    )
    assert "Python and SQL" in text
    assert "alert" not in text and "example.org" not in text and "123" not in text


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Senior Analytics Engineer", "analytics_engineer"),
        ("Dataanalytiker", "data_analyst"),
        ("Ingénieur données", "data_engineer"),
        ("Científico de datos", "data_scientist"),
        ("Analyst", "other"),
    ],
)
def test_role_boundary(title, expected):
    assert role_family(title) == expected
