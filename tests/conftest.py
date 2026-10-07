import pytest

from careergraph.db import init_db
from careergraph.demo import seed_demo


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    init_db(path)
    return path


@pytest.fixture
def demo_db(db):
    seed_demo(db)
    return db


@pytest.fixture
def jobtech_record():
    return {
        "id": "test-1",
        "headline": "Data Analyst",
        "removed": False,
        "publication_date": "2026-09-20T09:00:00",
        "application_deadline": "2099-10-31T23:59:59",
        "webpage_url": "https://arbetsformedlingen.se/platsbanken/annonser/test-1",
        "workplace_address": {
            "country_concept_id": "i46j_HmG_v64",
            "country_code": "199",
            "city": "Stockholm",
        },
        "employer": {"name": "Example Employer", "email": "do-not-store@example.invalid"},
        "description": {
            "text": "<p>Build products with Python and SQL. Contact someone@example.invalid.</p>"
        },
    }
