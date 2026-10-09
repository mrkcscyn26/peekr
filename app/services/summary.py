"""C13 Summary service. Implements F4. Covers FR-14, FR-15. Built in T-09.

Chunk selection, prompt, cache keyed by file_id + content_hash + model_name, and an
extractive fallback when Ollama is down or times out (Section 8.10, F4).
Assumption (flagged): a file with no chunks (skipped, error or deleted) returns an
empty fallback summary instead of an error, since 8.8 defines no code for it.
Fallback summaries are not cached, so the next request retries the LLM.
"""

from __future__ import annotations

import time
from typing import Any

from app.ai.llm import LLMClient, LLMUnavailable
from app.core.config import Section, utc_now
from app.core.logging import get_logger
from app.db import repo
from app.db.connection import open_conn, transaction

log = get_logger("summary")

SYSTEM_PROMPT = (
    "You summarize documents for a file search tool. Write 3 to 5 sentences in the same language as the "
    "document (English, Filipino, or Taglish). Use only the text provided. Do not add advice or opinions."
)


def select_chunks(chunks: list[dict], budget: int) -> list[dict]:
    """First chunk, then chunks spread evenly across the file in file order, within the character budget."""
    if not chunks:
        return []
    n = len(chunks)
    avg = max(1, sum(len(c["text"]) for c in chunks) // n)
    k = max(1, min(n, budget // avg))
    idx = sorted({0, *(round(i * (n - 1) / (k - 1)) for i in range(k))} if k > 1 else {0})
    out, used = [], 0
    for i in idx:
        text = chunks[i]["text"]
        if not out:
            text = text[:budget]
        elif used + len(text) > budget:
            continue
        out.append({**chunks[i], "text": text})
        used += len(text)
    return out


def fallback_text(chunks: list[dict], limit: int) -> str:
    text = " ".join(c["text"] for c in chunks[:5]).replace("\n", " ")
    if len(text) <= limit:
        return text
    cut = text.rfind(" ", 0, limit)
    return text[: cut if cut > limit // 2 else limit].rstrip() + "..."


class SummaryService:
    def __init__(self, summary: Section, llm: LLMClient, db_path: str) -> None:
        self.budget = int(summary.char_budget)
        self.fallback_chars = int(summary.fallback_chars)
        self.llm = llm
        self.db_path = db_path

    def get(self, file_row: dict, force: bool = False) -> dict[str, Any]:
        t0 = time.perf_counter()
        fid, h = file_row["id"], file_row["content_hash"]
        with open_conn(self.db_path) as conn:
            cached = repo.get_summary(conn, fid)
            chunks = repo.get_chunks(conn, fid)
        if not force and cached and cached["content_hash"] == h and cached["model_name"] == self.llm.model:
            return self._result(cached["summary_text"], True, False, self.llm.model, t0)
        if not chunks:
            return self._result("", False, True, None, t0)
        selected = select_chunks(chunks, self.budget)
        user = f"Document name: {file_row['name']}\n\n" + "\n\n".join(c["text"] for c in selected)
        try:
            text = self.llm.chat(SYSTEM_PROMPT, user)
            if not text:
                raise LLMUnavailable("empty response")
        except LLMUnavailable:
            log.info("summary fallback file_id=%s", fid)
            return self._result(fallback_text(chunks, self.fallback_chars), False, True, None, t0)
        with open_conn(self.db_path) as conn, transaction(conn):
            current = repo.get_file(conn, fid)
            if current and current["content_hash"] == h:  # file did not change while the LLM ran
                repo.upsert_summary(conn, fid, h, text, self.llm.model, utc_now())
        log.info("summary generated file_id=%s in %.1fs", fid, time.perf_counter() - t0)
        return self._result(text, False, False, self.llm.model, t0)

    @staticmethod
    def _result(text: str, cached: bool, fallback: bool, model: str | None, t0: float) -> dict[str, Any]:
        return {"summary": text, "cached": cached, "fallback": fallback, "model": model,
                "elapsed_ms": int((time.perf_counter() - t0) * 1000)}
