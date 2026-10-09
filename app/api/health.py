"""C2 API layer. Implements F1. Covers FR-16, FR-22, FR-24, FR-25. Built in T-01.

GET /api/health also reports the configured Ollama URL and embedding model so C1 can show
what runs locally. GET /api/categories returns the labels from config (category.labels),
not the categories table, because that table is only filled once indexing starts.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import AppContext, get_ctx

router = APIRouter(prefix="/api")


@router.get("/health")
def health(ctx: AppContext = Depends(get_ctx)) -> dict:
    return {**ctx.health.status(), "ollama_url": ctx.cfg.ollama.url, "embedding_model": ctx.cfg.embedding.model,
            "embedding_device": ctx.cfg.embedding.device}


@router.get("/categories")
def categories(ctx: AppContext = Depends(get_ctx)) -> dict:
    return {"categories": [{"name": n, "description": d} for n, d in ctx.cfg.category.labels.items()]}
