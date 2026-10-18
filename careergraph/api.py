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
    """Assemble the local read-only API around one database.

    Args:
        db_path: SQLite target; None uses the configured default path.

    Returns:
        A FastAPI app with static assets, input validation, response headers and analytical endpoints.

    Raises:
        OSError: The database/resources are unavailable.
        sqlite3.Error: The local schema cannot be initialized.

    Side effects:
        Initializes schema and mounts bundled resources. Does not start a server or collect data; CLI serve starts Uvicorn separately.
    """
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
        """Translate an analytical parameter error to an HTTP response.

        Args:
            request: Incoming request, supplied by FastAPI.
            exc: Validation error raised by the analytical functions.

        Returns:
            HTTP 422 JSON with the explicit detail message.

        Side effects:
            HTTP exception callback; does not write to the database.
        """
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.middleware("http")
    async def response_headers(request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Apply local browser response policy to each request.

        Args:
            request: Incoming HTTP request; its path selects the appropriate headers.
            call_next: Middleware continuation that produces the endpoint response.

        Returns:
            The endpoint response with security headers and no-store for analytical API responses.

        Side effects:
            Changes response headers only; performs no collection or profile persistence.
        """
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
        """Serve the packaged English interface.

        Returns:
            A FileResponse for static/index.html.

        Side effects:
            Reads a bundled asset; does not start a server or query a provider.
        """
        return FileResponse(static / "index.html")

    @app.get("/health")
    def health() -> JsonObject:
        """Report that the local API process can answer a request.

        Returns:
            status=ok and the application version. This does not certify source freshness.

        Side effects:
            No source request or database write.
        """
        return {"status": "ok", "version": __version__}

    @app.get("/api/catalog")
    def catalog() -> JsonObject:
        """Expose the versioned UI configuration.

        Returns:
            Country labels, role families, local skill specifications and vocabulary/package versions.

        Side effects:
            Returns bundled configuration; no provider or database request.
        """
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
        """Serve GET /api/overview using the shared analytical calculation.

        Args:
            mode: demo or live.
            country: ISO country code or ALL.
            role: Configured role family or all.
            since: Optional inclusive publication date.
            skills: Comma-separated local skill IDs; at most 1,000 characters.
            min_support: Pair-support threshold from 1 to 1,000.

        Returns:
            The overview response for the selected cohort, including run provenance and latest attempts.

        Raises:
            ValueError: Invalid catalog filters are translated to HTTP 422 by the registered handler.

        Side effects:
            Read-only database query; no hidden collection or CV/profile storage.
        """
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
        """Serve the bounded advert-evidence drill-down.

        Args:
            mode: demo or live.
            country: ISO country code or ALL.
            role: Configured role family or all.
            since: Optional inclusive publication date.
            skills: Comma-separated local skill IDs; at most 1,000 characters.
            missing_skill: Optional one-missing-skill filter.
            limit: Returned page size from 1 to 100.
            offset: Nonnegative number of matching rows to skip.

        Returns:
            A paginated evidence response with source links, snippets and missing skill IDs.

        Raises:
            ValueError: Invalid IDs/filters become HTTP 422.

        Side effects:
            Read-only; does not expose full description bodies.
        """
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
        """Serve official context separately from observed skill demand.

        Args:
            country: Configured country or ALL.

        Returns:
            The latest local benchmark snapshot, or an explicit unavailable response.

        Raises:
            ValueError: An unsupported country becomes HTTP 422.

        Side effects:
            No network refresh; CLI benchmark performs collection explicitly.
        """
        return benchmark(db, country)

    @app.get("/api/coverage")
    def get_coverage() -> JsonObject:
        """Serve the country coverage ledger.

        Returns:
            A countries array describing actual advert and benchmark availability.

        Side effects:
            Reads existing run/snapshot state only.
        """
        return {"countries": coverage(db)}

    return app
