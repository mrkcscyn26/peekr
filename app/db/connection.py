"""C9 Database layer. Supports F1, F2, F3, F4, F5, F6, F7. Covers FR-1, FR-18, FR-20. Built in T-02."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
SCHEMA_VERSION = "1"


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a connection with WAL, foreign keys and busy_timeout (Section 8.11). One per thread."""
    conn = sqlite3.connect(str(db_path), timeout=5.0, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db(db_path: str | Path) -> None:
    """Create missing tables (F1 step 3)."""
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES ('schema_version', ?)", (SCHEMA_VERSION,)
        )
    finally:
        conn.close()


@contextmanager
def open_conn(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Short write transaction: commit on success, roll back on error."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
