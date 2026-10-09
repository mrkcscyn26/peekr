"""C11 Hybrid search. Implements F3. Covers FR-9, FR-10, FR-12. Built in T-06.

In-memory vector matrix (rebuilt when dirty) + FTS5 bm25, reciprocal rank fusion,
filters, best chunk per file, snippets (Section 8.10, F3).
Assumption (flagged): when filters are present, the vector top-k runs over chunks of
files that pass the filters, and the keyword list is fetched 4x deeper before
filtering, so a narrow filter does not empty the candidate lists.
"""

from __future__ import annotations

import os
import re
import threading
import time
from typing import Any

import numpy as np

from app.ai.embedder import Embedder, from_bytes
from app.core.config import Section
from app.db import repo
from app.db.connection import open_conn
from app.search.query_parser import ParsedQuery

_WORD = re.compile(r"\w+", re.UNICODE)


def fts_query(text: str) -> str:
    """Query terms joined by OR, each quoted so FTS5 special characters are escaped."""
    terms = []
    for t in _WORD.findall(text.lower()):
        if len(t) >= 2 and t not in terms:
            terms.append(t)
    return " OR ".join('"' + t.replace('"', '""') + '"' for t in terms)


def make_snippet(text: str, terms: list[str], limit: int) -> str:
    flat = re.sub(r"\s+", " ", text).strip()
    if len(flat) <= limit:
        return flat
    pos = -1
    low = flat.lower()
    for t in terms:
        m = re.search(rf"\b{re.escape(t)}", low)
        if m and (pos < 0 or m.start() < pos):
            pos = m.start()
    start = 0 if pos < 0 else max(0, min(pos - limit // 2, len(flat) - limit))
    if start > 0:
        sp = flat.find(" ", start)
        start = sp + 1 if 0 <= sp < start + 30 else start
    out = flat[start:start + limit].strip()
    return ("..." if start > 0 else "") + out + ("..." if start + limit < len(flat) else "")


class HybridSearch:
    def __init__(self, search: Section, embedder: Embedder, db_path: str, llm_model: str) -> None:
        self.cfg = search
        self.embedder = embedder
        self.db_path = db_path
        self.llm_model = llm_model
        self._lock = threading.Lock()
        self._dirty = True
        self._matrix = np.zeros((0, 0), dtype=np.float32)
        self._chunk_ids = np.zeros(0, dtype=np.int64)
        self._file_ids = np.zeros(0, dtype=np.int64)

    def mark_dirty(self) -> None:
        with self._lock:
            self._dirty = True

    def _ensure_matrix(self, conn) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        with self._lock:
            if self._dirty:
                rows = repo.all_indexed_embeddings(conn)
                if rows:
                    self._matrix = np.vstack([from_bytes(r[2]) for r in rows])
                    self._chunk_ids = np.array([r[0] for r in rows], dtype=np.int64)
                    self._file_ids = np.array([r[1] for r in rows], dtype=np.int64)
                else:
                    self._matrix = np.zeros((0, self.embedder.dim or 0), dtype=np.float32)
                    self._chunk_ids = self._file_ids = np.zeros(0, dtype=np.int64)
                self._dirty = False
            return self._matrix, self._chunk_ids, self._file_ids

    @staticmethod
    def _passes(f: dict, exts: list[str], date_from: str | None, date_to: str | None, folder_hint: str | None) -> bool:
        if f["status"] != "indexed":
            return False
        if exts and f["extension"] not in exts:
            return False
        if date_from:
            in_range = any(t and date_from <= t < date_to for t in (f["created_at"], f["modified_at"]))
            if not in_range:
                return False
        if folder_hint:
            parts = [p.lower() for p in re.split(r"[\\/]", os.path.dirname(f["current_path"])) if p]
            if not any(folder_hint in p for p in parts):
                return False
        return True

    def search(self, pq: ParsedQuery, limit: int | None = None) -> dict[str, Any]:
        t0 = time.perf_counter()
        limit = int(limit or self.cfg.default_limit)
        with open_conn(self.db_path) as conn:
            if repo.indexed_file_count(conn) == 0:
                return self._out([], pq, False, "no_indexed_files", t0)
            files = {f["id"]: f for f in repo.list_files(conn, statuses=["indexed"])}
            attempts = [(pq.extensions, pq.date_from, pq.date_to, pq.folder_hint)]
            if pq.folder_hint:
                attempts.append((pq.extensions, pq.date_from, pq.date_to, None))
            if pq.date_from:
                attempts.append((pq.extensions, None, None, None))
            qvec = self.embedder.embed_query(pq.semantic_text) if pq.semantic_text else None
            results: list[dict] = []
            relaxed = False
            for n, (exts, df, dt, fh) in enumerate(attempts):
                allowed = {fid for fid, f in files.items() if self._passes(f, exts, df, dt, fh)}
                if not allowed:
                    continue
                if qvec is None:
                    results = self._list_newest(conn, files, allowed, limit)
                else:
                    results = self._ranked(conn, files, allowed, qvec, pq.semantic_text, limit,
                                           filtered=len(allowed) < len(files))
                if results:
                    relaxed = n > 0
                    break
            cached = repo.summary_cached_ids(conn, [r["file_id"] for r in results], self.llm_model)
        for r in results:
            r["summary_cached"] = r["file_id"] in cached
        return self._out(results, pq, relaxed, None if results else "no_results", t0)

    def _list_newest(self, conn, files: dict, allowed: set, limit: int) -> list[dict]:
        ordered = sorted(allowed, key=lambda fid: files[fid]["modified_at"], reverse=True)[:limit]
        out = []
        for fid in ordered:
            ch = repo.first_chunk(conn, fid) or {"text": "", "location": None}
            out.append(self._result(files[fid], ch, 0.0, []))
        return out

    def _ranked(self, conn, files: dict, allowed: set, qvec: np.ndarray, text: str, limit: int,
                filtered: bool) -> list[dict]:
        k_vec, k_kw, rrf_k = int(self.cfg.top_k_vector), int(self.cfg.top_k_keyword), int(self.cfg.rrf_k)
        matrix, chunk_ids, file_ids = self._ensure_matrix(conn)
        scores: dict[int, float] = {}
        if len(chunk_ids):
            sims = matrix @ qvec
            if filtered:
                mask = np.isin(file_ids, np.fromiter(allowed, dtype=np.int64))
                sims = np.where(mask, sims, -np.inf)
            k = min(k_vec, int(np.isfinite(sims).sum()))
            if k > 0:
                top = np.argpartition(-sims, k - 1)[:k]
                top = top[np.argsort(-sims[top])]
                for rank, i in enumerate(top, 1):
                    scores[int(chunk_ids[i])] = scores.get(int(chunk_ids[i]), 0.0) + 1.0 / (rrf_k + rank)
        match = fts_query(text)
        if match:
            kw_ids = repo.fts_search(conn, match, k_kw * 4 if filtered else k_kw)
            chunk_rows = repo.get_chunks_by_ids(conn, kw_ids)
            kw_ids = [c for c in kw_ids if chunk_rows[c]["file_id"] in allowed][:k_kw]
            for rank, cid in enumerate(kw_ids, 1):
                scores[cid] = scores.get(cid, 0.0) + 1.0 / (rrf_k + rank)
        if not scores:
            return []
        chunks = repo.get_chunks_by_ids(conn, scores)
        best: dict[int, tuple[float, dict]] = {}
        for cid, s in scores.items():
            ch = chunks.get(cid)
            if ch is None or ch["file_id"] not in allowed:
                continue
            if ch["file_id"] not in best or s > best[ch["file_id"]][0]:
                best[ch["file_id"]] = (s, ch)
        terms = [t for t in _WORD.findall(text.lower()) if len(t) >= 3]
        ranked = sorted(best.items(), key=lambda kv: kv[1][0], reverse=True)[:limit]
        return [self._result(files[fid], ch, s, terms) for fid, (s, ch) in ranked]

    def _result(self, f: dict, chunk: dict, score: float, terms: list[str]) -> dict:
        return {
            "file_id": f["id"], "name": f["name"], "extension": f["extension"], "path": f["current_path"],
            "folder": os.path.dirname(f["current_path"]), "category": f["category"], "modified_at": f["modified_at"],
            "score": round(float(score), 6), "snippet": make_snippet(chunk["text"], terms, int(self.cfg.snippet_chars)),
            "location": chunk["location"],
        }

    @staticmethod
    def _out(results: list, pq: ParsedQuery, relaxed: bool, reason: str | None, t0: float) -> dict[str, Any]:
        return {"results": results, "parsed": pq.as_dict(), "relaxed_filters": relaxed, "reason": reason,
                "elapsed_ms": int((time.perf_counter() - t0) * 1000)}
