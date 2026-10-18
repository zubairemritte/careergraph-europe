"""Start here: one command-line entry point for every local project operation.

Read main first. environment_report supports the read-only doctor command.
Collection, analysis and serving are delegated to their owning modules.
"""

import argparse
import json
import platform
import sqlite3
import sys
from importlib.metadata import PackageNotFoundError, distribution, version
from pathlib import Path

from packaging.requirements import Requirement

from careergraph.analysis import coverage, overview
from careergraph.connectors import EurostatConnector
from careergraph.contracts import BenchmarkSnapshot, JsonObject
from careergraph.db import default_db, init_db
from careergraph.demo import seed_demo
from careergraph.evaluation import evaluate
from careergraph.http import SourceError
from careergraph.pipeline import collect_jobtech, save_benchmark


def environment_report() -> JsonObject:
    """Inspect this installation without collecting data or creating a database.

    Returns:
        A JSON report with Python/OS/architecture, exact direct runtime-package
        versions, SQLite window-function support and bundled-resource checks.
        ok is true only when every installation check passes. It does not certify
        network access, a live source or the complete application's behaviour.

    Side effects:
        Reads installed distribution metadata and package resource paths. Opens
        and closes an in-memory SQLite connection; writes no filesystem database.
    """
    packages: list[JsonObject] = []
    for declaration in distribution("careergraph-europe").requires or []:
        requirement: Requirement = Requirement(declaration)
        if requirement.marker is not None and not requirement.marker.evaluate({"extra": ""}):
            continue
        name: str = requirement.name
        expected: str = str(requirement.specifier)
        installed: str | None
        try:
            installed = version(name)
        except PackageNotFoundError:
            installed = None
        packages.append(
            {
                "package": name,
                "expected": expected,
                "installed": installed,
                "ok": installed is not None
                and requirement.specifier.contains(installed, prereleases=True),
            }
        )
    root: Path = Path(__file__).parent
    resources: dict[str, bool] = {
        relative: (root / relative).is_file()
        for relative in [
            "config/countries.json",
            "config/roles.json",
            "config/skills.json",
            "sql/schema.sql",
            "static/index.html",
            "static/app.js",
            "static/style.css",
        ]
    }
    sqlite_ok: bool = False
    connection: sqlite3.Connection = sqlite3.connect(":memory:")
    try:
        sqlite_ok = connection.execute("SELECT ROW_NUMBER() OVER ()").fetchone()[0] == 1
    except sqlite3.DatabaseError:
        sqlite_ok = False
    finally:
        connection.close()
    python_ok: bool = (
        sys.version_info[:2] == (3, 12) and platform.python_implementation() == "CPython"
    )
    bits_ok: bool = sys.maxsize > 2**32
    return {
        "ok": python_ok
        and bits_ok
        and sqlite_ok
        and all(resources.values())
        and bool(packages)
        and all(p["ok"] for p in packages),
        "python": platform.python_version(),
        "python_ok": python_ok,
        "system": platform.system(),
        "system_release": platform.release(),
        "machine": platform.machine(),
        "64_bit": bits_ok,
        "sqlite_version": sqlite3.sqlite_version,
        "sqlite_window_functions": sqlite_ok,
        "runtime_packages": packages,
        "resources": resources,
        "scope": "Local installation checks only; no dataset, server or network request.",
    }


def main(argv: list[str] | None = None) -> None:
    """Dispatch one explicit local operation from the project's single entry point.

    Args:
        argv: Argument list without the executable name; None reads the terminal arguments.

    Returns:
        None. Most commands print a JSON result; serve runs until stopped.

    Raises:
        SystemExit: Parser errors, a failed doctor check or a handled source/file/value error produce a nonzero exit.

    Side effects:
        doctor reads installation state without creating a database. Other commands initialize the selected database; only demo/collect/benchmark write datasets, and only serve starts the local web server.

    Example:
        poetry run careergraph doctor; use poetry run careergraph --help to list all commands.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="CareerGraph Europe — sample-aware skills intelligence"
    )
    parser.add_argument(
        "--db", type=Path, default=default_db(), help="SQLite file (default: data/careergraph.db)"
    )
    sub: argparse._SubParsersAction[argparse.ArgumentParser] = parser.add_subparsers(
        dest="command", required=True
    )
    sub.add_parser("doctor", help="Check the local installation; no dataset or network request")
    sub.add_parser("demo", help="Load deterministic synthetic offers; no network")
    collect: argparse.ArgumentParser = sub.add_parser(
        "collect", help="Collect a bounded sample of actual offers"
    )
    collect.add_argument("--source", choices=["jobtech"], default="jobtech")
    collect.add_argument("--country", required=True, help="ISO alpha-2 workplace country")
    collect.add_argument(
        "--query",
        action="append",
        dest="queries",
        help="Repeat for each search term; defaults to four English data-role queries",
    )
    collect.add_argument("--pages", type=int, default=2, help="Maximum pages per query, 1–5")
    bench: argparse.ArgumentParser = sub.add_parser(
        "benchmark", help="Fetch official Eurostat economic context"
    )
    bench.add_argument("--from-file", type=Path, help="Load a previously exported snapshot offline")
    bench.add_argument("--export", type=Path, help="Write a shareable official-statistics snapshot")
    serve: argparse.ArgumentParser = sub.add_parser(
        "serve", help="Start the local, read-only web application"
    )
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    inspect: argparse.ArgumentParser = sub.add_parser(
        "inspect", help="Print an analytical cohort as JSON"
    )
    inspect.add_argument("--mode", choices=["demo", "live"], default="demo")
    inspect.add_argument("--country", default="ALL")
    inspect.add_argument("--role", default="all")
    inspect.add_argument("--skills", default="python,sql")
    sub.add_parser("coverage", help="Show configured versus actually collected countries")
    evaluation: argparse.ArgumentParser = sub.add_parser(
        "evaluate", help="Run skill-extraction regression evaluation"
    )
    evaluation.add_argument("--cases", type=Path, default=Path("tests/fixtures/skill_cases.json"))
    args: argparse.Namespace = parser.parse_args(argv)
    if args.command == "doctor":
        report: JsonObject = environment_report()
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if not report["ok"]:
            raise SystemExit(1)
        return
    init_db(args.db)
    try:
        if args.command == "demo":
            result: JsonObject | list[JsonObject] = seed_demo(args.db)
        elif args.command == "collect":
            result = collect_jobtech(
                args.db,
                country=args.country,
                queries=args.queries
                or ["data analyst", "data engineer", "data scientist", "analytics engineer"],
                pages=args.pages,
            )
        elif args.command == "benchmark":
            snapshot: BenchmarkSnapshot = (
                json.loads(args.from_file.read_text(encoding="utf-8"))
                if args.from_file
                else EurostatConnector().fetch_snapshot()
            )
            snapshot_id: str = save_benchmark(args.db, snapshot)
            if args.export:
                args.export.parent.mkdir(parents=True, exist_ok=True)
                args.export.write_text(
                    json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
                )
            result = {
                "snapshot_id": snapshot_id,
                "rows": len(snapshot["rows"]),
                "observed_values": sum(r["vacancy_rate"] is not None for r in snapshot["rows"]),
                "retrieved_at": snapshot["retrieved_at"],
            }
        elif args.command == "serve":
            import uvicorn

            from careergraph.api import create_app

            uvicorn.run(create_app(args.db), host=args.host, port=args.port, access_log=False)
            return
        elif args.command == "inspect":
            result = overview(
                args.db,
                mode=args.mode,
                country=args.country,
                role=args.role,
                known=args.skills.split(","),
            )
        elif args.command == "coverage":
            result = coverage(args.db)
        else:
            result = evaluate(args.cases)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (SourceError, ValueError, OSError) as exc:
        print(f"CareerGraph: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
