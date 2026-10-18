import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def default_db() -> Path:
    """Choose the configured local database filename.

    Returns:
        CAREERGRAPH_DB as a Path, or data/careergraph.db when unset.

    Side effects:
        Reads an environment value only; does not create the directory or database.
    """
    return Path(os.environ.get("CAREERGRAPH_DB", "data/careergraph.db"))


@contextmanager
def connect(path: str | Path) -> Iterator[sqlite3.Connection]:
    """Open one SQLite transaction and always close its connection.

    Args:
        path: Filesystem target; a missing parent directory is created.

    Returns:
        A context-managed iterator yielding a row-enabled SQLite connection. Commit occurs on successful exit; any exception triggers rollback.

    Raises:
        sqlite3.Error: SQLite cannot open, execute, commit or roll back.
        OSError: The parent directory cannot be created.

    Side effects:
        May create a database and WAL files. Enables foreign keys and write-ahead logging.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn: sqlite3.Connection = sqlite3.connect(path, timeout=15)
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


def init_db(path: str | Path) -> None:
    """Create the versioned tables and indexes if they are absent.

    Args:
        path: Local database target.

    Returns:
        None. Existing application rows are preserved.

    Raises:
        sqlite3.Error: The schema cannot be applied.
        OSError: The database directory or bundled schema cannot be read.

    Side effects:
        Writes schema objects to SQLite; does not collect or generate a dataset.
    """
    with connect(path) as conn:
        conn.executescript((Path(__file__).parent / "sql/schema.sql").read_text(encoding="utf-8"))
