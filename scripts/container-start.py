"""Initialize an empty demonstration volume, then serve as the unprivileged user."""

import json
from pathlib import Path

import uvicorn

from careergraph.api import create_app
from careergraph.db import default_db
from careergraph.demo import seed_demo
from careergraph.pipeline import save_benchmark


def main() -> None:
    """Initialize a fresh demo volume, then run the container application.

    Returns:
        None while the server is running.

    Raises:
        Exception: Initialization or Uvicorn startup fails.

    Side effects:
        Only an absent database triggers the full demo and bundled benchmark load. Starts Uvicorn on 0.0.0.0:8000 inside the container; this script is not a smoke test.
    """
    db: Path = default_db()
    if not db.exists():
        seed_demo(db)
        save_benchmark(
            db, json.loads(Path("examples/eurostat-context.json").read_text(encoding="utf-8"))
        )
    uvicorn.run(create_app(db), host="0.0.0.0", port=8000, access_log=False)


if __name__ == "__main__":
    main()
