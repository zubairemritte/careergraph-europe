"""Initialize an empty demonstration volume, then serve as the unprivileged user."""

import json
from pathlib import Path

import uvicorn

from careergraph.api import create_app
from careergraph.db import default_db
from careergraph.demo import seed_demo
from careergraph.pipeline import save_benchmark


def main() -> None:
    """Initialize only an absent demo database, then serve the local container app."""
    db: Path = default_db()
    if not db.exists():
        seed_demo(db)
        save_benchmark(db, json.loads(Path("examples/eurostat-context.json").read_text()))
    uvicorn.run(create_app(db), host="0.0.0.0", port=8000, access_log=False)


if __name__ == "__main__":
    main()
