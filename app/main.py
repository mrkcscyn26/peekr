"""C2 API layer. Implements F1. Covers FR-24, FR-25. Built in T-01.

FastAPI app with startup and shutdown hooks (F1). The default /docs, /redoc and
/openapi.json pages are disabled because they load assets from a CDN (T-01).
Run: python -m app.main  (binds to 127.0.0.1 only, FR-24).
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import webbrowser
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.ai.embedder import Embedder
from app.ai.llm import LLMClient
from app.api import ApiError, AppContext, error_body
from app.api import events, files, folders, health, index, search
from app.core.config import PROJECT_ROOT, Config, load_config
from app.core.health import HealthChecker
from app.core.logging import get_logger, setup_logging
from app.db import repo
from app.db.connection import init_db, open_conn
from app.history.watcher import Watcher
from app.indexing.pipeline import Indexer
from app.search.hybrid import HybridSearch
from app.services.category import CategoryService
from app.services.summary import SummaryService

log = get_logger("main")
WEB_DIR = PROJECT_ROOT / "web"


def build_context(cfg: Config, embedder: Embedder | None = None, llm: LLMClient | None = None) -> AppContext:
    db_path = str(cfg.db_path)
    embedder = embedder or Embedder(cfg.embedding)
    llm = llm or LLMClient(cfg.ollama, cfg.llm)
    search_svc = HybridSearch(cfg.search, embedder, db_path, llm.model)
    category = CategoryService(cfg.category, embedder)
    watcher_holder: dict = {}
    indexer = Indexer(cfg, db_path, embedder, category, on_change=search_svc.mark_dirty,
                      on_folder_scanned=lambda f: watcher_holder["w"].watch(f["id"], f["path"]))
    watcher = Watcher(cfg, indexer.submit_event)
    watcher_holder["w"] = watcher
    return AppContext(cfg=cfg, db_path=db_path, embedder=embedder, llm=llm,
                      health=HealthChecker(llm, embedder, db_path, str(cfg.data_path)), search=search_svc,
                      summary=SummaryService(cfg.summary, llm, db_path), indexer=indexer, watcher=watcher)


def start_context(ctx: AppContext) -> None:
    """F1 steps 2-7."""
    setup_logging(ctx.cfg.logs_path)
    init_db(ctx.db_path)
    if not ctx.embedder.done.is_set():
        ctx.embedder.load_async()
    threading.Thread(target=ctx.health.check_ollama, kwargs={"force": True}, daemon=True).start()
    ctx.indexer.start()
    ctx.watcher.start()
    with open_conn(ctx.db_path) as conn:
        enabled = repo.list_folders(conn, enabled_only=True)
    for f in enabled:
        ctx.watcher.watch(f["id"], f["path"])
    if enabled:
        ctx.indexer.submit_job(None, "rescan")  # startup reconciliation (F6)
    log.info("startup done host=%s port=%s folders=%d", ctx.cfg.server.host, ctx.cfg.server.port, len(enabled))


def stop_context(ctx: AppContext) -> None:
    ctx.watcher.stop()
    ctx.indexer.stop()


def create_app(cfg: Config | None = None, embedder: Embedder | None = None, llm: LLMClient | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        ctx = build_context(cfg or load_config(), embedder, llm)
        app.state.ctx = ctx
        start_context(ctx)
        try:
            yield
        finally:
            stop_context(ctx)

    app = FastAPI(title="Peekr", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(error_body(exc.code, exc.message), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        if any(e.get("type") == "json_invalid" for e in errors):
            return JSONResponse(error_body("invalid_request", "The request body is not valid JSON."), status_code=400)
        fields = ", ".join(".".join(str(p) for p in e.get("loc", [])[1:]) or "body" for e in errors)
        return JSONResponse(error_body("invalid_request", f"Invalid request fields: {fields}"), status_code=400)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "invalid_request"
        return JSONResponse(error_body(code, str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _internal(request: Request, exc: Exception) -> JSONResponse:
        log.error("internal error path=%s type=%s", request.url.path, type(exc).__name__)
        return JSONResponse(error_body("internal", "Unexpected error."), status_code=500)

    for module in (health, folders, index, search, files, events):
        app.include_router(module.router)
    if WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
    return app


def port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def preflight(cfg: Config) -> int:
    """Used by run.bat: warn if Ollama is down, fail if the port is busy (F1 failure handling)."""
    llm = LLMClient(cfg.ollama, cfg.llm)
    try:
        names = llm.list_models()
        if not llm.model_installed(names):
            print(f"WARNING: model {llm.model} is not installed in Ollama. Run: ollama pull {llm.model}")
    except Exception:  # noqa: BLE001
        print("WARNING: Ollama is not running. Search works; summaries will use the short text fallback.")
    if not port_free(cfg.server.host, int(cfg.server.port)):
        print(f"ERROR: port {cfg.server.port} on {cfg.server.host} is busy. Close the other program or change "
              "server.port in config.yaml.")
        return 1
    return 0


def _open_browser_when_ready(host: str, port: int) -> None:
    for _ in range(120):
        time.sleep(0.5)
        with socket.socket() as s:
            if s.connect_ex((host, port)) == 0:
                webbrowser.open(f"http://{host}:{port}")
                return


def main(argv: list[str] | None = None) -> int:
    import uvicorn

    ap = argparse.ArgumentParser(prog="python -m app.main")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)
    cfg = load_config()
    if args.preflight:
        return preflight(cfg)
    host, port = cfg.server.host, int(cfg.server.port)
    if not args.no_browser:
        threading.Thread(target=_open_browser_when_ready, args=(host, port), daemon=True).start()
    uvicorn.run(create_app(cfg), host=host, port=port, log_level="info", server_header=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
