"""Read-only local application. Collection is an explicit CLI operation."""

from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from careergraph import __version__
from careergraph.analysis import benchmark, coverage, evidence, overview
from careergraph.catalog import COUNTRIES, ROLES, SKILLS, VOCABULARY
from careergraph.contracts import JsonObject
from careergraph.db import default_db, init_db


def create_app(db_path: str | Path | None = None) -> FastAPI:
    """Build the local read-only API around one database; never trigger collection."""
    db: Path = Path(db_path) if db_path is not None else default_db()
    init_db(db)
    app: FastAPI = FastAPI(
        title="CareerGraph Europe",
        version=__version__,
        description="Observed job samples, explainable skill coverage and separate official economic context. Read-only API.",
    )
    static: Path = Path(__file__).parent / "static"
    app.mount("/assets", StaticFiles(directory=static), name="assets")

    @app.exception_handler(ValueError)
    async def invalid_value(request: Request, exc: ValueError) -> JSONResponse:
        """Translate invalid analytical parameters into an explicit HTTP 422 response."""
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.middleware("http")
    async def response_headers(request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Add browser security headers and prevent caching of personal skill query results."""
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path == "/":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
            )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/", include_in_schema=False)
    def home() -> FileResponse:
        """Serve the English local interface from bundled static assets."""
        return FileResponse(static / "index.html")

    @app.get("/health")
    def health() -> JsonObject:
        """Report process health and package version, independently from source freshness."""
        return {"status": "ok", "version": __version__}

    @app.get("/api/catalog")
    def catalog() -> JsonObject:
        """Expose English labels and versioned country, role and skill configuration."""
        return {
            "countries": COUNTRIES,
            "roles": ROLES,
            "skills": list(SKILLS.values()),
            "vocabulary_version": VOCABULARY["version"],
            "version": __version__,
        }

    @app.get("/api/overview")
    def get_overview(
        mode: Literal["demo", "live"] = "demo",
        country: str = "ALL",
        role: str = "all",
        since: date | None = None,
        skills: str = Query(default="", max_length=1000),
        min_support: int = Query(default=3, ge=1, le=1000),
    ) -> JsonObject:
        """Validate HTTP filters and return the selected analytical sample with its audit."""
        return overview(
            db,
            mode=mode,
            country=country,
            role=role,
            since=since.isoformat() if since else None,
            known=skills.split(","),
            min_support=min_support,
        )

    @app.get("/api/evidence")
    def get_evidence(
        mode: Literal["demo", "live"] = "demo",
        country: str = "ALL",
        role: str = "all",
        since: date | None = None,
        skills: str = Query(default="", max_length=1000),
        missing_skill: str | None = None,
        limit: int = Query(default=12, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> JsonObject:
        """Return bounded advert evidence and the exact missing-skill explanation."""
        return evidence(
            db,
            mode=mode,
            country=country,
            role=role,
            since=since.isoformat() if since else None,
            known=skills.split(","),
            missing_skill=missing_skill,
            limit=limit,
            offset=offset,
        )

    @app.get("/api/benchmark")
    def get_benchmark(country: str = "ALL") -> JsonObject:
        """Return the separately attributed official statistical context for a country filter."""
        return benchmark(db, country)

    @app.get("/api/coverage")
    def get_coverage() -> JsonObject:
        """Expose the country coverage ledger without inferring unconnected market data."""
        return {"countries": coverage(db)}

    return app
