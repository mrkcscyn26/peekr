"""C9 Database layer. Supports F1, F2, F3, F4, F5, F6, F7. Covers FR-1, FR-18, FR-20. Built in T-02.

All SQL in the app lives in this module. Functions take an open connection; writes
that must be atomic are wrapped by the caller in connection.transaction().
"""

from __future__ import annotations

import sqlite3
from typing import Any, Iterable, Sequence

Row = sqlite3.Row


def _d(row: Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


# ---- settings ----

def get_setting(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


# ---- folders ----

_FOLDER_COLS = """f.id, f.path, f.enabled, f.last_scan_at, f.created_at,
  (SELECT COUNT(*) FROM files x WHERE x.folder_id = f.id AND x.status != 'deleted') AS file_count"""


def insert_folder(conn: sqlite3.Connection, path: str, created_at: str) -> int:
    return conn.execute("INSERT INTO folders(path, created_at) VALUES (?, ?)", (path, created_at)).lastrowid


def list_folders(conn: sqlite3.Connection, enabled_only: bool = False) -> list[dict]:
    sql = f"SELECT {_FOLDER_COLS} FROM folders f"
    if enabled_only:
        sql += " WHERE f.enabled = 1"
    return [dict(r) for r in conn.execute(sql + " ORDER BY f.id")]


def get_folder(conn: sqlite3.Connection, folder_id: int) -> dict | None:
    return _d(conn.execute(f"SELECT {_FOLDER_COLS} FROM folders f WHERE f.id = ?", (folder_id,)).fetchone())


def delete_folder(conn: sqlite3.Connection, folder_id: int) -> bool:
    return conn.execute("DELETE FROM folders WHERE id = ?", (folder_id,)).rowcount > 0


def set_folder_scanned(conn: sqlite3.Connection, folder_id: int, at: str) -> None:
    conn.execute("UPDATE folders SET last_scan_at = ? WHERE id = ?", (at, folder_id))


def add_exclusion(conn: sqlite3.Connection, folder_id: int, path: str) -> None:
    conn.execute("INSERT OR IGNORE INTO excluded_paths(folder_id, path) VALUES (?, ?)", (folder_id, path))


def list_exclusions(conn: sqlite3.Connection, folder_id: int | None = None) -> list[dict]:
    if folder_id is None:
        return [dict(r) for r in conn.execute("SELECT folder_id, path FROM excluded_paths")]
    return [dict(r) for r in conn.execute("SELECT folder_id, path FROM excluded_paths WHERE folder_id = ?", (folder_id,))]


# ---- files ----

_FILE_COLS = """f.id, f.folder_id, f.current_path, f.name, f.extension, f.size_bytes, f.created_at,
  f.modified_at, f.content_hash, f.category, f.status, f.status_reason, f.indexed_at"""


def get_file(conn: sqlite3.Connection, file_id: int) -> dict | None:
    return _d(conn.execute(f"SELECT {_FILE_COLS} FROM files f WHERE f.id = ?", (file_id,)).fetchone())


def get_file_by_path(conn: sqlite3.Connection, path: str) -> dict | None:
    return _d(conn.execute(f"SELECT {_FILE_COLS} FROM files f WHERE f.current_path = ?", (path,)).fetchone())


def get_files(conn: sqlite3.Connection, ids: Iterable[int]) -> dict[int, dict]:
    ids = list(ids)
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    return {r["id"]: dict(r) for r in conn.execute(f"SELECT {_FILE_COLS} FROM files f WHERE f.id IN ({marks})", ids)}


def list_files(conn: sqlite3.Connection, folder_id: int | None = None, statuses: Sequence[str] | None = None,
               exclude_deleted: bool = False) -> list[dict]:
    sql, args = f"SELECT {_FILE_COLS} FROM files f WHERE 1=1", []
    if folder_id is not None:
        sql += " AND f.folder_id = ?"
        args.append(folder_id)
    if statuses:
        sql += f" AND f.status IN ({','.join('?' * len(statuses))})"
        args.extend(statuses)
    if exclude_deleted:
        sql += " AND f.status != 'deleted'"
    return [dict(r) for r in conn.execute(sql + " ORDER BY f.id", args)]


def find_live_files_by_hash(conn: sqlite3.Connection, content_hash: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        f"SELECT {_FILE_COLS} FROM files f WHERE f.content_hash = ? AND f.status != 'deleted'", (content_hash,))]


def upsert_file(conn: sqlite3.Connection, *, folder_id: int, path: str, name: str, extension: str,
                size_bytes: int, created_at: str | None, modified_at: str, content_hash: str | None,
                category: str | None, status: str, status_reason: str | None, indexed_at: str | None) -> int:
    """Insert or update the files row keyed by current_path (a deleted row at the same path is reused)."""
    conn.execute(
        """INSERT INTO files(folder_id, current_path, name, extension, size_bytes, created_at, modified_at,
                             content_hash, category, status, status_reason, indexed_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(current_path) DO UPDATE SET folder_id=excluded.folder_id, name=excluded.name,
             extension=excluded.extension, size_bytes=excluded.size_bytes, created_at=excluded.created_at,
             modified_at=excluded.modified_at, content_hash=excluded.content_hash, category=excluded.category,
             status=excluded.status, status_reason=excluded.status_reason, indexed_at=excluded.indexed_at""",
        (folder_id, path, name, extension, size_bytes, created_at, modified_at, content_hash, category,
         status, status_reason, indexed_at),
    )
    return conn.execute("SELECT id FROM files WHERE current_path = ?", (path,)).fetchone()["id"]


def update_file_times(conn: sqlite3.Connection, file_id: int, size_bytes: int, created_at: str | None,
                      modified_at: str) -> None:
    conn.execute("UPDATE files SET size_bytes = ?, created_at = ?, modified_at = ? WHERE id = ?",
                 (size_bytes, created_at, modified_at, file_id))


def update_file_path(conn: sqlite3.Connection, file_id: int, folder_id: int, path: str, name: str) -> None:
    # A stale deleted row may hold the target path; drop it so current_path stays unique.
    conn.execute("DELETE FROM files WHERE current_path = ? AND id != ? AND status = 'deleted'", (path, file_id))
    conn.execute("UPDATE files SET folder_id = ?, current_path = ?, name = ? WHERE id = ?",
                 (folder_id, path, name, file_id))


def delete_file(conn: sqlite3.Connection, file_id: int) -> None:
    """Remove a file row entirely (used when its path becomes excluded, FR-2)."""
    conn.execute("DELETE FROM files WHERE id = ?", (file_id,))


def set_file_status(conn: sqlite3.Connection, file_id: int, status: str, reason: str | None = None) -> None:
    conn.execute("UPDATE files SET status = ?, status_reason = ? WHERE id = ?", (status, reason, file_id))


def set_file_category(conn: sqlite3.Connection, file_id: int, category: str) -> None:
    conn.execute("UPDATE files SET category = ? WHERE id = ?", (category, file_id))


def reset_all_for_reembed(conn: sqlite3.Connection) -> int:
    """Embedding model changed: drop every chunk and mark indexed files pending (Section 8.3)."""
    conn.execute("DELETE FROM chunks")
    return conn.execute("UPDATE files SET status = 'pending', status_reason = 'reembed' WHERE status = 'indexed'").rowcount


def indexed_file_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) AS n FROM files WHERE status = 'indexed'").fetchone()["n"]


# ---- chunks ----

def replace_chunks(conn: sqlite3.Connection, file_id: int, chunks: Sequence[tuple[int, str | None, str, bytes]]) -> None:
    """chunks: (chunk_index, location, text, embedding_bytes). Triggers keep chunks_fts in sync."""
    conn.execute("DELETE FROM chunks WHERE file_id = ?", (file_id,))
    conn.executemany(
        "INSERT INTO chunks(file_id, chunk_index, location, text, embedding) VALUES (?, ?, ?, ?, ?)",
        [(file_id, i, loc, text, emb) for i, loc, text, emb in chunks],
    )


def delete_chunks(conn: sqlite3.Connection, file_id: int) -> None:
    conn.execute("DELETE FROM chunks WHERE file_id = ?", (file_id,))


def get_chunks(conn: sqlite3.Connection, file_id: int, with_embedding: bool = False) -> list[dict]:
    cols = "id, chunk_index, location, text" + (", embedding" if with_embedding else "")
    return [dict(r) for r in conn.execute(
        f"SELECT {cols} FROM chunks WHERE file_id = ? ORDER BY chunk_index", (file_id,))]


def get_chunks_by_ids(conn: sqlite3.Connection, ids: Iterable[int]) -> dict[int, dict]:
    ids = list(ids)
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    return {r["id"]: dict(r) for r in conn.execute(
        f"SELECT id, file_id, chunk_index, location, text FROM chunks WHERE id IN ({marks})", ids)}


def first_chunk(conn: sqlite3.Connection, file_id: int) -> dict | None:
    return _d(conn.execute(
        "SELECT id, file_id, chunk_index, location, text FROM chunks WHERE file_id = ? ORDER BY chunk_index LIMIT 1",
        (file_id,)).fetchone())


def all_indexed_embeddings(conn: sqlite3.Connection) -> list[tuple[int, int, bytes]]:
    """(chunk_id, file_id, embedding) for every chunk of an indexed file, for the C11 vector cache."""
    return [(r[0], r[1], r[2]) for r in conn.execute(
        "SELECT c.id, c.file_id, c.embedding FROM chunks c JOIN files f ON f.id = c.file_id "
        "WHERE f.status = 'indexed' ORDER BY c.id")]


def fts_search(conn: sqlite3.Connection, match: str, limit: int) -> list[int]:
    """Chunk ids from FTS5 ranked by bm25 (best first), indexed files only."""
    return [r[0] for r in conn.execute(
        "SELECT c.id FROM chunks_fts JOIN chunks c ON c.id = chunks_fts.rowid JOIN files f ON f.id = c.file_id "
        "WHERE chunks_fts MATCH ? AND f.status = 'indexed' ORDER BY bm25(chunks_fts) LIMIT ?",
        (match, limit))]


# ---- summaries ----

def get_summary(conn: sqlite3.Connection, file_id: int) -> dict | None:
    return _d(conn.execute(
        "SELECT file_id, content_hash, summary_text, model_name, created_at FROM summaries WHERE file_id = ?",
        (file_id,)).fetchone())


def summary_cached_ids(conn: sqlite3.Connection, ids: Iterable[int], model_name: str) -> set[int]:
    ids = list(ids)
    if not ids:
        return set()
    marks = ",".join("?" * len(ids))
    return {r[0] for r in conn.execute(
        f"SELECT s.file_id FROM summaries s JOIN files f ON f.id = s.file_id "
        f"WHERE s.file_id IN ({marks}) AND s.content_hash = f.content_hash AND s.model_name = ?",
        [*ids, model_name])}


def upsert_summary(conn: sqlite3.Connection, file_id: int, content_hash: str, text: str, model: str, at: str) -> None:
    conn.execute(
        """INSERT INTO summaries(file_id, content_hash, summary_text, model_name, created_at) VALUES (?,?,?,?,?)
           ON CONFLICT(file_id) DO UPDATE SET content_hash=excluded.content_hash,
             summary_text=excluded.summary_text, model_name=excluded.model_name, created_at=excluded.created_at""",
        (file_id, content_hash, text, model, at),
    )


def delete_summary(conn: sqlite3.Connection, file_id: int) -> None:
    conn.execute("DELETE FROM summaries WHERE file_id = ?", (file_id,))


# ---- events ----

def insert_event(conn: sqlite3.Connection, file_id: int, event_type: str, old_path: str | None,
                 new_path: str | None, hash_before: str | None, hash_after: str | None,
                 occurred_at: str, source: str) -> int:
    return conn.execute(
        "INSERT INTO events(file_id, event_type, old_path, new_path, hash_before, hash_after, occurred_at, source) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (file_id, event_type, old_path, new_path, hash_before, hash_after, occurred_at, source),
    ).lastrowid


def list_events(conn: sqlite3.Connection, file_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT id, event_type, old_path, new_path, hash_before, hash_after, occurred_at, source "
        "FROM events WHERE file_id = ? ORDER BY occurred_at DESC, id DESC", (file_id,))]


def list_recent_events(conn: sqlite3.Connection, limit: int, event_type: str | None = None) -> list[dict]:
    """Events across all files, newest first, with the file's current name, path and status."""
    sql = ("SELECT e.id, e.file_id, e.event_type, e.old_path, e.new_path, e.occurred_at, e.source, "
           "f.name, f.current_path, f.status FROM events e JOIN files f ON f.id = e.file_id")
    args: list = []
    if event_type:
        sql += " WHERE e.event_type = ?"
        args.append(event_type)
    return [dict(r) for r in conn.execute(sql + " ORDER BY e.occurred_at DESC, e.id DESC LIMIT ?", [*args, limit])]


# ---- categories ----

def upsert_category(conn: sqlite3.Connection, name: str, description: str, embedding: bytes) -> None:
    conn.execute(
        """INSERT INTO categories(name, description, embedding) VALUES (?,?,?)
           ON CONFLICT(name) DO UPDATE SET description=excluded.description, embedding=excluded.embedding""",
        (name, description, embedding),
    )


def list_categories(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT name, description, embedding FROM categories ORDER BY name")]


def delete_categories_except(conn: sqlite3.Connection, names: Sequence[str]) -> None:
    conn.execute(f"DELETE FROM categories WHERE name NOT IN ({','.join('?' * len(names))})", list(names))
