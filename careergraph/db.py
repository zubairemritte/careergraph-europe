import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def default_db() -> Path:
    return Path(os.environ.get("CAREERGRAPH_DB", "data/careergraph.db"))


@contextmanager
def connect(path: str | Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path: str | Path):
    with connect(path) as conn:
        conn.executescript((Path(__file__).parent / "sql/schema.sql").read_text())
