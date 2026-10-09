"""T-02: schema from Section 8.3 and C9 repo functions."""

import numpy as np
import pytest

from app.db import repo
from app.db.connection import connect, init_db, transaction

EMB = np.ones(4, dtype=np.float32).tobytes()


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "peekr.db"
    init_db(db)
    init_db(db)  # idempotent
    c = connect(db)
    yield c
    c.close()


def _file(conn, folder_id, path="C:/x/a.pdf", h="h1"):
    return repo.upsert_file(conn, folder_id=folder_id, path=path, name="a.pdf", extension=".pdf", size_bytes=10,
                            created_at="2026-01-01T00:00:00+00:00", modified_at="2026-01-02T00:00:00+00:00",
                            content_hash=h, category="School", status="indexed", status_reason=None,
                            indexed_at="2026-01-02T00:00:00+00:00")


def test_schema_and_pragmas(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table')")}
    assert {"folders", "excluded_paths", "files", "chunks", "chunks_fts", "summaries", "events", "categories",
            "settings"} <= tables
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert repo.get_setting(conn, "schema_version") == "1"


def test_fts_trigger_sync_and_search(conn):
    with transaction(conn):
        fid = repo.insert_folder(conn, "C:/x", "t")
        f = _file(conn, fid)
        repo.replace_chunks(conn, f, [(0, "page 1", "Meralco electric bill total due", EMB),
                                      (1, "page 2", "pay through GCash", EMB)])
    assert len(repo.fts_search(conn, '"gcash"', 10)) == 1
    with transaction(conn):
        repo.replace_chunks(conn, f, [(0, "page 1", "water bill only", EMB)])
    assert repo.fts_search(conn, '"gcash"', 10) == []
    assert len(repo.fts_search(conn, '"water"', 10)) == 1
    assert len(repo.all_indexed_embeddings(conn)) == 1


def test_upsert_reuses_row_and_cascade_delete(conn):
    with transaction(conn):
        fid = repo.insert_folder(conn, "C:/x", "t")
        f1 = _file(conn, fid)
        f2 = _file(conn, fid, h="h2")
        repo.replace_chunks(conn, f1, [(0, "part 1", "text", EMB)])
        repo.insert_event(conn, f1, "baseline", None, "C:/x/a.pdf", None, "h1", "t", "scan")
        repo.upsert_summary(conn, f1, "h2", "s", "m", "t")
    assert f1 == f2
    assert repo.list_folders(conn)[0]["file_count"] == 1
    assert repo.summary_cached_ids(conn, [f1], "m") == {f1}
    assert repo.summary_cached_ids(conn, [f1], "other") == set()
    with transaction(conn):
        repo.delete_folder(conn, fid)
    for t in ("files", "chunks", "events", "summaries", "chunks_fts"):
        assert conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0, t


def test_events_newest_first(conn):
    with transaction(conn):
        fid = repo.insert_folder(conn, "C:/x", "t")
        f = _file(conn, fid)
        repo.insert_event(conn, f, "baseline", None, "a", None, "h", "2026-01-01T00:00:00+00:00", "scan")
        repo.insert_event(conn, f, "modified", None, "a", "h", "h2", "2026-01-02T00:00:00+00:00", "watcher")
    assert [e["event_type"] for e in repo.list_events(conn, f)] == ["modified", "baseline"]
