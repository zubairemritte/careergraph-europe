import argparse
import json
import sys
from pathlib import Path

from careergraph.analysis import coverage, overview
from careergraph.connectors import fetch_benchmark
from careergraph.db import default_db, init_db
from careergraph.demo import seed_demo
from careergraph.evaluation import evaluate
from careergraph.http import SourceError
from careergraph.pipeline import collect_jobtech, save_benchmark


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="CareerGraph Europe — sample-aware skills intelligence"
    )
    parser.add_argument(
        "--db", type=Path, default=default_db(), help="SQLite file (default: data/careergraph.db)"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="Load deterministic synthetic offers; no network")
    collect = sub.add_parser("collect", help="Collect a bounded sample of actual offers")
    collect.add_argument("--source", choices=["jobtech"], default="jobtech")
    collect.add_argument("--country", required=True, help="ISO alpha-2 workplace country")
    collect.add_argument(
        "--query",
        action="append",
        dest="queries",
        help="Repeat for each search term; defaults to four English data-role queries",
    )
    collect.add_argument("--pages", type=int, default=2, help="Maximum pages per query, 1–5")
    bench = sub.add_parser("benchmark", help="Fetch official Eurostat economic context")
    bench.add_argument("--from-file", type=Path, help="Load a previously exported snapshot offline")
    bench.add_argument("--export", type=Path, help="Write a shareable official-statistics snapshot")
    serve = sub.add_parser("serve", help="Start the local, read-only web application")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    inspect = sub.add_parser("inspect", help="Print an analytical cohort as JSON")
    inspect.add_argument("--mode", choices=["demo", "live"], default="demo")
    inspect.add_argument("--country", default="ALL")
    inspect.add_argument("--role", default="all")
    inspect.add_argument("--skills", default="python,sql")
    sub.add_parser("coverage", help="Show configured versus actually collected countries")
    evaluation = sub.add_parser("evaluate", help="Run skill-extraction regression evaluation")
    evaluation.add_argument("--cases", type=Path, default=Path("tests/fixtures/skill_cases.json"))
    args = parser.parse_args(argv)
    init_db(args.db)
    try:
        if args.command == "demo":
            result = seed_demo(args.db)
        elif args.command == "collect":
            result = collect_jobtech(
                args.db,
                country=args.country,
                queries=args.queries
                or ["data analyst", "data engineer", "data scientist", "analytics engineer"],
                pages=args.pages,
            )
        elif args.command == "benchmark":
            snapshot = (
                json.loads(args.from_file.read_text()) if args.from_file else fetch_benchmark()
            )
            snapshot_id = save_benchmark(args.db, snapshot)
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
