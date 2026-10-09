"""C2 API layer. Implements F5. Covers FR-18, FR-20. Built in T-11.

GET /api/events: recent history events across all files, newest first, for the C1
Activity view. The per-file timeline stays at GET /api/files/{id}/history.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from app.api import ApiError, get_conn
from app.db import repo
from app.history.events import EVENT_TYPES

router = APIRouter(prefix="/api")


@router.get("/events")
def recent_events(limit: int = Query(default=200, ge=1, le=1000), type: str | None = None,
                  conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    if type is not None and type not in EVENT_TYPES:
        raise ApiError("invalid_request", f"type must be one of: {', '.join(sorted(EVENT_TYPES))}")
    return {"events": [
        {"id": e["id"], "file_id": e["file_id"], "name": e["name"], "path": e["current_path"],
         "file_status": e["status"], "event_type": e["event_type"], "old_path": e["old_path"],
         "new_path": e["new_path"], "occurred_at": e["occurred_at"], "source": e["source"]}
        for e in repo.list_recent_events(conn, limit, type)]}
