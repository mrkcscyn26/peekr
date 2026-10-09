"""C17 History service. Implements F2, F4, F5, F6. Covers FR-18, FR-20. Built in T-10.

Writes and reads events and applies path changes for moves, renames and deletes
(Section 8.10 event classification). Callers wrap writes in a transaction.
"""

from __future__ import annotations

import os
import sqlite3

from app.core.config import utc_now
from app.db import repo

EVENT_TYPES = {"baseline", "created", "modified", "moved", "renamed", "deleted"}
SOURCES = {"scan", "watcher", "reconcile"}


def record(conn: sqlite3.Connection, file_id: int, event_type: str, *, source: str, old_path: str | None = None,
           new_path: str | None = None, hash_before: str | None = None, hash_after: str | None = None) -> int:
    assert event_type in EVENT_TYPES and source in SOURCES, (event_type, source)
    return repo.insert_event(conn, file_id, event_type, old_path, new_path, hash_before, hash_after, utc_now(), source)


def timeline(conn: sqlite3.Connection, file_id: int) -> list[dict]:
    """Events newest first, in the API shape of GET /api/files/{id}/history."""
    return [{k: e[k] for k in ("event_type", "old_path", "new_path", "occurred_at", "source")}
            for e in repo.list_events(conn, file_id)]


def move_kind(old_path: str, new_path: str) -> str:
    same_parent = os.path.normcase(os.path.dirname(old_path)) == os.path.normcase(os.path.dirname(new_path))
    return "renamed" if same_parent else "moved"


def apply_move(conn: sqlite3.Connection, file_row: dict, new_path: str, new_folder_id: int, source: str) -> str:
    """Update current_path and name without re-embedding, write a moved or renamed event."""
    kind = move_kind(file_row["current_path"], new_path)
    repo.update_file_path(conn, file_row["id"], new_folder_id, new_path, os.path.basename(new_path))
    record(conn, file_row["id"], kind, source=source, old_path=file_row["current_path"], new_path=new_path,
           hash_before=file_row["content_hash"], hash_after=file_row["content_hash"])
    return kind


def apply_delete(conn: sqlite3.Connection, file_row: dict, source: str) -> None:
    """Status deleted, chunks and summary removed, row and events kept (Section 8.3)."""
    repo.delete_chunks(conn, file_row["id"])
    repo.delete_summary(conn, file_row["id"])
    repo.set_file_status(conn, file_row["id"], "deleted", None)
    record(conn, file_row["id"], "deleted", source=source, old_path=file_row["current_path"],
           hash_before=file_row["content_hash"])
