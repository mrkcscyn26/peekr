"""C2 API layer. Implements F2. Covers FR-1, FR-3, FR-16. Built in T-05.

Assumptions (flagged):
- A folder that contains an already added folder is rejected like a nested one.
- Drive roots, Windows, Program Files, ProgramData, AppData and Peekr's own data folder
  count as system folders (whole-disk scanning is out of scope).
- Folder removal runs in the request thread as one cascading delete; the C8 worker is
  told to skip any queued work for that folder.
- Adding an exclusion queues a rescan of the folder so excluded files leave the index.
Each folder in the response lists its excluded paths (exclusions) for C1 (T-08).
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api import ApiError, AppContext, get_conn, get_ctx
from app.core import os_actions
from app.core.config import is_within, norm_path, utc_now
from app.db import repo
from app.db.connection import transaction

router = APIRouter(prefix="/api/folders")


class PathBody(BaseModel):
    path: str


def _folder_out(f: dict, exclusions: list[str]) -> dict:
    return {"id": f["id"], "path": f["path"], "enabled": bool(f["enabled"]), "available": os.path.isdir(f["path"]),
            "last_scan_at": f["last_scan_at"], "file_count": f["file_count"], "exclusions": exclusions}


def _system_folders(data_dir: str) -> list[str]:
    env = os.environ
    names = [env.get("SystemRoot", r"C:\Windows"), env.get("ProgramFiles"), env.get("ProgramFiles(x86)"),
             env.get("ProgramData"), env.get("APPDATA"), env.get("LOCALAPPDATA"), data_dir]
    return [norm_path(n) for n in names if n]


def validate_new_folder(raw: str, existing: list[dict], data_dir: str) -> str:
    if not raw or not raw.strip():
        raise ApiError("invalid_path", "The path is missing.")
    p = Path(os.path.expandvars(raw.strip().strip('"')))
    if not p.is_absolute() or not p.is_dir():
        raise ApiError("invalid_path", "The path does not exist or is not a folder.")
    path = norm_path(p)
    if Path(path).parent == Path(path):
        raise ApiError("invalid_path", "A whole drive cannot be added. Choose a folder.")
    for sys_dir in _system_folders(data_dir):
        if is_within(path, sys_dir) or is_within(sys_dir, path):
            raise ApiError("invalid_path", "System folders cannot be added.")
    for f in existing:
        if os.path.normcase(f["path"]) == os.path.normcase(path):
            raise ApiError("already_added", "This folder is already added.")
        if is_within(path, f["path"]) or is_within(f["path"], path):
            raise ApiError("invalid_path", "This folder is inside, or contains, a folder that is already added.")
    return path


@router.get("")
def list_folders(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    excl: dict[int, list[str]] = {}
    for e in repo.list_exclusions(conn):
        excl.setdefault(e["folder_id"], []).append(e["path"])
    return {"folders": [_folder_out(f, sorted(excl.get(f["id"], []))) for f in repo.list_folders(conn)]}


@router.post("/pick")
def pick_folder() -> dict:
    try:
        return {"path": os_actions.pick_folder()}
    except os_actions.OsActionError as exc:
        raise ApiError("os_error", str(exc)) from exc


@router.post("")
def add_folder(body: PathBody, conn: sqlite3.Connection = Depends(get_conn), ctx: AppContext = Depends(get_ctx)) -> dict:
    path = validate_new_folder(body.path, repo.list_folders(conn), str(ctx.cfg.data_path))
    with transaction(conn):
        fid = repo.insert_folder(conn, path, utc_now())
    return {"folder": _folder_out(repo.get_folder(conn, fid), [])}


@router.delete("/{folder_id}")
def remove_folder(folder_id: int, conn: sqlite3.Connection = Depends(get_conn),
                  ctx: AppContext = Depends(get_ctx)) -> dict:
    if repo.get_folder(conn, folder_id) is None:
        raise ApiError("folder_not_found", "Unknown folder id.")
    ctx.watcher.unwatch(folder_id)
    ctx.indexer.forget_folder(folder_id)
    with transaction(conn):
        repo.delete_folder(conn, folder_id)
    ctx.search.mark_dirty()
    return {"ok": True}


@router.post("/{folder_id}/exclusions")
def add_exclusion(folder_id: int, body: PathBody, conn: sqlite3.Connection = Depends(get_conn),
                  ctx: AppContext = Depends(get_ctx)) -> dict:
    folder = repo.get_folder(conn, folder_id)
    if folder is None:
        raise ApiError("folder_not_found", "Unknown folder id.")
    raw = body.path.strip().strip('"') if body.path else ""
    if not raw:
        raise ApiError("invalid_path", "The path is missing.")
    path = norm_path(Path(folder["path"]) / raw)
    if not is_within(path, folder["path"]) or os.path.normcase(path) == os.path.normcase(folder["path"]):
        raise ApiError("invalid_path", "The excluded path must be a subfolder of the indexed folder.")
    with transaction(conn):
        repo.add_exclusion(conn, folder_id, path)
    ctx.indexer.submit_job([folder_id], "rescan")
    return {"ok": True}
