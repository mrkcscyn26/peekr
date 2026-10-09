"""C2 API layer. Implements F2, F6. Covers FR-4, FR-5, FR-6, FR-7, FR-19. Built in T-05.

Assumption (flagged): while the embedding model is still loading, a start request is
queued (the worker waits for the model); only a failed model load returns embedder_not_ready.
"""

from __future__ import annotations

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api import ApiError, AppContext, get_conn, get_ctx
from app.db import repo

router = APIRouter(prefix="/api/index")


class StartBody(BaseModel):
    folder_id: int | None = None
    kind: Literal["initial", "rescan"] = "initial"


@router.post("/start")
def start(body: StartBody | None = None, conn: sqlite3.Connection = Depends(get_conn),
          ctx: AppContext = Depends(get_ctx)) -> dict:
    body = body or StartBody()
    if body.folder_id is not None and repo.get_folder(conn, body.folder_id) is None:
        raise ApiError("folder_not_found", "Unknown folder id.")
    if ctx.embedder.done.is_set() and not ctx.embedder.ready.is_set():
        raise ApiError("embedder_not_ready", ctx.embedder.error or "The embedding model is missing.")
    job_id = ctx.indexer.submit_job([body.folder_id] if body.folder_id is not None else None, body.kind)
    return {"job_id": job_id}


@router.get("/status")
def status(ctx: AppContext = Depends(get_ctx)) -> dict:
    return ctx.indexer.status()
