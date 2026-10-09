"""C2 API layer. Implements F2, F4, F7. Covers FR-5, FR-13, FR-14, FR-15, FR-16, FR-20. Built in T-07.

The server never opens a path sent by the client: open endpoints load the stored path
and check it is inside an enabled indexed folder (F7 step 2).
GET /api/files lists file rows by status so C1 can browse the library, build the folder
tree and list skipped or error files across restarts (T-08).
PATCH /api/files/{id}/category (FR-17, Could) is a stretch item and not implemented.
"""

from __future__ import annotations

import os
import sqlite3

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api import ApiError, AppContext, get_conn, get_ctx
from app.core import os_actions
from app.core.config import is_within
from app.db import repo
from app.history import events as history

router = APIRouter(prefix="/api/files")

FILE_STATUSES = ("pending", "indexed", "skipped", "error", "deleted")


class SummaryBody(BaseModel):
    force: bool = False


def _file(conn: sqlite3.Connection, file_id: int) -> dict:
    row = repo.get_file(conn, file_id)
    if row is None:
        raise ApiError("file_not_found", "Unknown file id.")
    return row


def _meta(f: dict) -> dict:
    return {
        "id": f["id"], "folder_id": f["folder_id"], "name": f["name"], "extension": f["extension"],
        "path": f["current_path"], "folder": os.path.dirname(f["current_path"]), "size_bytes": f["size_bytes"],
        "created_at": f["created_at"], "modified_at": f["modified_at"], "category": f["category"],
        "status": f["status"], "status_reason": f["status_reason"],
    }


@router.get("")
def list_files(status: str = "indexed", conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    statuses = [s.strip() for s in status.split(",") if s.strip()]
    if not statuses or any(s not in FILE_STATUSES for s in statuses):
        raise ApiError("invalid_request", f"status must be a comma list of: {', '.join(FILE_STATUSES)}")
    return {"files": [_meta(f) for f in repo.list_files(conn, statuses=statuses)]}


@router.get("/{file_id}")
def get_file(file_id: int, conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)) -> dict:
    f = _file(conn, file_id)
    return {**_meta(f), "summary_cached": file_id in repo.summary_cached_ids(conn, [file_id], ctx.llm.model)}


@router.post("/{file_id}/summary")
def summary(file_id: int, body: SummaryBody | None = None, conn: sqlite3.Connection = Depends(get_conn),
            ctx: AppContext = Depends(get_ctx)) -> dict:
    return ctx.summary.get(_file(conn, file_id), force=bool(body and body.force))


@router.get("/{file_id}/history")
def file_history(file_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    _file(conn, file_id)
    return {"events": history.timeline(conn, file_id)}


def _checked_path(conn: sqlite3.Connection, ctx: AppContext, file_id: int) -> str:
    f = _file(conn, file_id)
    path = f["current_path"]
    folder = next((x for x in repo.list_folders(conn, enabled_only=True) if is_within(path, x["path"])), None)
    if folder is None:
        raise ApiError("forbidden_path", "The file is outside every indexed folder.")
    if f["status"] == "deleted" or not os.path.isfile(path):
        ctx.indexer.submit_job([folder["id"]], "rescan")
        raise ApiError("file_missing", "The file is no longer on disk. A rescan was queued.")
    return path


@router.post("/{file_id}/open")
def open_file(file_id: int, conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)) -> dict:
    path = _checked_path(conn, ctx, file_id)
    try:
        os_actions.open_file(path)
    except os_actions.OsActionError as exc:
        raise ApiError("os_error", str(exc)) from exc
    return {"ok": True}


@router.post("/{file_id}/open-folder")
def open_folder(file_id: int, conn: sqlite3.Connection = Depends(get_conn),
                ctx: AppContext = Depends(get_ctx)) -> dict:
    path = _checked_path(conn, ctx, file_id)
    try:
        os_actions.open_folder(path)
    except os_actions.OsActionError as exc:
        raise ApiError("os_error", str(exc)) from exc
    return {"ok": True}
