from fastapi.testclient import TestClient

from careergraph.api import create_app


def test_application_contract_and_country_selection(demo_db):
    with TestClient(create_app(demo_db)) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/").status_code == 200
        assert len(client.get("/api/catalog").json()["countries"]) == 16
        response = client.get(
            "/api/overview",
            params={"country": "DE", "role": "data_analyst", "skills": "python,sql"},
        )
        assert response.status_code == 200
        assert response.json()["sample"]["offers"] == 12
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/api/evidence?country=DE&limit=1").json()["offers"][0]["country"] == "DE"
        assert client.get("/api/benchmark").json()["available"] is False


def test_invalid_filters_cannot_turn_into_unbounded_or_injected_queries(demo_db):
    with TestClient(create_app(demo_db)) as client:
        for query in [
            "country=UK",
            "role=unknown",
            "skills=unrecognised",
            "since=not-a-date",
            "mode=mixed",
            "min_support=0",
            "country=%27%3Bdrop%20table%20offers",
        ]:
            assert client.get("/api/overview?" + query).status_code == 422
        assert client.get("/api/evidence?limit=100000").status_code == 422
        assert client.get("/api/evidence?offset=-1").status_code == 422
        assert client.post("/api/collect").status_code == 404


def test_live_unavailable_is_not_demo_fallback(demo_db):
    with TestClient(create_app(demo_db)) as client:
        result = client.get("/api/overview?mode=live&country=FR").json()
        assert result["sample"]["availability"] == "not_collected"
        assert not result["skills"]
        coverage = client.get("/api/coverage").json()["countries"]
        assert next(c for c in coverage if c["country"] == "FR")["offer_status"] == "not_connected"
