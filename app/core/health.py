"""C19 Health checks. Implements F1. Covers FR-22, FR-24, FR-25. Built in T-01.

Checks Ollama reachable, model installed, embedder ready, data folder writable.
Results are cached briefly in memory; Ollama being down never stops startup.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

from app.ai.embedder import Embedder
from app.ai.llm import LLMClient, LLMUnavailable
from app.db.connection import open_conn

CACHE_SECONDS = 5.0


class HealthChecker:
    def __init__(self, llm: LLMClient, embedder: Embedder, db_path: str, data_dir: str) -> None:
        self.llm, self.embedder, self.db_path, self.data_dir = llm, embedder, db_path, data_dir
        self._ollama: tuple[float, bool, bool] | None = None
        self._lock = threading.Lock()

    def check_ollama(self, force: bool = False) -> tuple[bool, bool]:
        with self._lock:
            if not force and self._ollama and time.monotonic() - self._ollama[0] < CACHE_SECONDS:
                return self._ollama[1], self._ollama[2]
        try:
            names = self.llm.list_models()
            ok, ready = True, self.llm.model_installed(names)
        except LLMUnavailable:
            ok, ready = False, False
        with self._lock:
            self._ollama = (time.monotonic(), ok, ready)
        return ok, ready

    def db_ok(self) -> bool:
        try:
            with open_conn(self.db_path) as conn:
                conn.execute("SELECT 1 FROM settings LIMIT 1")
            return os.access(self.data_dir, os.W_OK)
        except Exception:  # noqa: BLE001
            return False

    def status(self) -> dict[str, Any]:
        ollama_ok, llm_ready = self.check_ollama()
        return {
            "ollama_ok": ollama_ok,
            "llm_model": self.llm.model,
            "llm_ready": llm_ready,
            "embedder_ready": self.embedder.ready.is_set(),
            "embedder_error": self.embedder.error,
            "db_ok": self.db_ok(),
            "local_only": True,
        }
