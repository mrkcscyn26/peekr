"""C14 Category service. Implements F2, F5. Covers FR-16. Built in T-09.

Labels (name plus description, passage prefix) are embedded once and stored in the
categories table. A file vector is the normalized mean of its first 5 chunk vectors;
the best label by cosine wins, below category.min_score the file gets Other (Section 8.10).
"""

from __future__ import annotations

import sqlite3
import threading

import numpy as np

from app.ai.embedder import Embedder, from_bytes, to_bytes
from app.core.config import Section
from app.db import repo

FALLBACK = "Other"
FILE_VECTOR_CHUNKS = 5


class CategoryService:
    def __init__(self, category: Section, embedder: Embedder) -> None:
        self.min_score = float(category.min_score)
        self.labels: dict[str, str] = dict(category.labels)
        self.embedder = embedder
        self._names: list[str] = []
        self._matrix: np.ndarray | None = None
        self._lock = threading.Lock()

    def ensure_labels(self, conn: sqlite3.Connection) -> None:
        """Embed labels (once per description change) and load them into memory. Called by the C8 writer thread."""
        stored = {r["name"]: r for r in repo.list_categories(conn)}
        names = list(self.labels)
        texts, todo = [], []
        for name in names:
            row = stored.get(name)
            if row is None or row["description"] != self.labels[name] or not row["embedding"]:
                todo.append(name)
                texts.append(f"{name}: {self.labels[name]}")
        if todo:
            vecs = self.embedder.embed_passages(texts)
            for name, vec in zip(todo, vecs):
                repo.upsert_category(conn, name, self.labels[name], to_bytes(vec))
        repo.delete_categories_except(conn, names)
        rows = {r["name"]: r for r in repo.list_categories(conn)}
        with self._lock:
            self._names = names
            self._matrix = np.vstack([from_bytes(rows[n]["embedding"]) for n in names])

    def assign(self, chunk_vectors: np.ndarray) -> str:
        with self._lock:
            if self._matrix is None or len(chunk_vectors) == 0:
                return FALLBACK
            v = np.asarray(chunk_vectors[:FILE_VECTOR_CHUNKS], dtype=np.float32).mean(axis=0)
            n = np.linalg.norm(v)
            if n == 0:
                return FALLBACK
            scores = self._matrix @ (v / n)
            best = int(np.argmax(scores))
            return self._names[best] if float(scores[best]) >= self.min_score else FALLBACK
