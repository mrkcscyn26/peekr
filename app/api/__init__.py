"""C2 API layer. Implements F1, F2, F3, F4, F5, F6, F7. Covers FR-1, FR-9, FR-13, FR-14, FR-18, FR-22, FR-24. Built in T-01.

Shared pieces for the routers: the application context, the error type and the
JSON error format {"error": {"code", "message"}} from Section 8.8.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator

from fastapi import Request

from app.db.connection import connect

if TYPE_CHECKING:
    from app.ai.embedder import Embedder
    from app.ai.llm import LLMClient
    from app.core.config import Config
    from app.core.health import HealthChecker
    from app.history.watcher import Watcher
    from app.indexing.pipeline import Indexer
    from app.search.hybrid import HybridSearch
    from app.services.summary import SummaryService

STATUS = {
    "invalid_request": 400, "invalid_path": 400, "already_added": 409, "folder_not_found": 404,
    "file_not_found": 404, "file_missing": 404, "forbidden_path": 403, "embedder_not_ready": 503,
    "llm_unavailable": 503, "os_error": 500, "internal": 500, "not_found": 404,
}


class ApiError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, STATUS[code]


def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


@dataclass
class AppContext:
    cfg: "Config"
    db_path: str
    embedder: "Embedder"
    llm: "LLMClient"
    health: "HealthChecker"
    search: "HybridSearch"
    summary: "SummaryService"
    indexer: "Indexer"
    watcher: "Watcher"


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def get_conn(request: Request) -> Iterator:
    """Each request reads with its own short-lived connection (Section 8.11)."""
    conn = connect(get_ctx(request).db_path)
    try:
        yield conn
    finally:
        conn.close()


def require_embedder(ctx: AppContext) -> None:
    if not ctx.embedder.ready.is_set():
        raise ApiError("embedder_not_ready", ctx.embedder.error or "The embedding model is still loading. Try again shortly.")
