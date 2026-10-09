"""C2 API layer. Implements F3. Covers FR-9, FR-10, FR-11, FR-12. Built in T-06.

Optional overrides for C1 (T-08): date_from/date_to replace the parsed date range (the
date menu), and ignore drops parsed filters (the X on a filter chip). Ignore wins over an
override. Dates must carry a time zone; they are stored as UTC ISO like the parser output.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api import ApiError, AppContext, get_ctx, require_embedder
from app.core.logging import get_logger
from app.search import query_parser

router = APIRouter(prefix="/api")
log = get_logger("search")


class SearchBody(BaseModel):
    query: str = Field(max_length=500)
    limit: int | None = Field(default=None, ge=1, le=100)
    date_from: str | None = None
    date_to: str | None = None
    ignore: list[Literal["extensions", "date", "folder"]] = Field(default_factory=list)


def _utc(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ApiError("invalid_request", "date_from and date_to must be ISO 8601 date-times.") from exc
    if dt.tzinfo is None:
        raise ApiError("invalid_request", "date_from and date_to must include a time zone.")
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def apply_overrides(pq: query_parser.ParsedQuery, body: SearchBody) -> None:
    if (body.date_from is None) != (body.date_to is None):
        raise ApiError("invalid_request", "Send both date_from and date_to, or neither.")
    if body.date_from is not None:
        df, dt = _utc(body.date_from), _utc(body.date_to)
        if df >= dt:
            raise ApiError("invalid_request", "date_from must be before date_to.")
        pq.date_from, pq.date_to = df, dt
    if "date" in body.ignore:
        pq.date_from = pq.date_to = None
    if "extensions" in body.ignore:
        pq.extensions = []
    if "folder" in body.ignore:
        pq.folder_hint = None


@router.post("/search")
def search(body: SearchBody, ctx: AppContext = Depends(get_ctx)) -> dict:
    t0 = time.perf_counter()
    pq = query_parser.parse(body.query)
    apply_overrides(pq, body)
    if pq.semantic_text:
        require_embedder(ctx)
    out = ctx.search.search(pq, body.limit)
    out["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
    log.info("search results=%d relaxed=%s in %dms", len(out["results"]), out["relaxed_filters"], out["elapsed_ms"])
    return out
