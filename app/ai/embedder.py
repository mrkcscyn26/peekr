"""C7 Embedder. Implements F2, F3, F5. Covers FR-9, FR-10. Built in T-04.

Loads the embedding model once (background thread, F1 step 5), adds the e5
'passage: ' / 'query: ' prefixes, returns L2-normalized float32 vectors. The
dimension is read from the model, never hard-coded (Section 8.10).

Offline: Hugging Face libraries are forced into offline mode before import so the
app never contacts the network at runtime (FR-23). The model must be downloaded once
during setup: python -m app.ai.embedder --download
"""

from __future__ import annotations

import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import threading  # noqa: E402
import time  # noqa: E402
from typing import Sequence  # noqa: E402

import numpy as np  # noqa: E402

from app.core.config import Section  # noqa: E402
from app.core.logging import get_logger  # noqa: E402

log = get_logger("embedder")


class EmbedderNotReady(RuntimeError):
    pass


class Embedder:
    def __init__(self, embedding: Section) -> None:
        self.model_name: str = embedding.model
        self.device: str = embedding.device
        self.batch_size: int = int(embedding.batch_size)
        self.dim: int | None = None
        self.error: str | None = None
        self.ready = threading.Event()
        self.done = threading.Event()  # set when loading finished, successfully or not
        self._model = None
        self._lock = threading.Lock()

    def load(self) -> None:
        t0 = time.perf_counter()
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(self.model_name, device=self.device)
            get_dim = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
            self.dim = int(get_dim())
            self._model = model
            self.ready.set()
            log.info("embedder loaded model=%s dim=%s device=%s in %.1fs", self.model_name, self.dim, self.device,
                     time.perf_counter() - t0)
        except Exception as exc:  # noqa: BLE001
            self.error = (f"Embedding model '{self.model_name}' could not be loaded ({type(exc).__name__}). "
                          "Run the setup step: python -m app.ai.embedder --download")
            log.error("embedder load failed: %s", type(exc).__name__)
        finally:
            self.done.set()

    def load_async(self) -> threading.Thread:
        t = threading.Thread(target=self.load, name="embedder-load", daemon=True)
        t.start()
        return t

    def _encode(self, texts: Sequence[str]) -> np.ndarray:
        if not self.ready.is_set():
            raise EmbedderNotReady(self.error or "embedding model is still loading")
        with self._lock:
            vecs = self._model.encode(list(texts), batch_size=self.batch_size, normalize_embeddings=True,
                                      convert_to_numpy=True, show_progress_bar=False)
        vecs = np.asarray(vecs, dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / np.where(norms == 0, 1, norms)

    def embed_passages(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim or 0), dtype=np.float32)
        return self._encode([f"passage: {t}" for t in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self._encode([f"query: {text}"])[0]


def to_bytes(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def from_bytes(data: bytes) -> np.ndarray:
    return np.frombuffer(data, dtype=np.float32)


if __name__ == "__main__":  # one-time setup with internet: download the model into the local cache
    import sys

    if "--download" in sys.argv:
        os.environ["HF_HUB_OFFLINE"] = "0"
        os.environ["TRANSFORMERS_OFFLINE"] = "0"
        from sentence_transformers import SentenceTransformer

        from app.core.config import load_config

        SentenceTransformer(load_config().embedding.model, device="cpu")
        print("embedding model downloaded")
