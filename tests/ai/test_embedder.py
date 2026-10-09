"""T-04: C7 embedder (normalized float32, dimension from the model, e5 prefixes) and C12 offline behaviour."""

import numpy as np

from app.ai.embedder import Embedder, from_bytes, to_bytes
from app.ai.llm import LLMClient, LLMUnavailable
from app.core.config import Section, load_config


def test_vectors_normalized_and_dim_from_model(embedder):
    v = embedder.embed_passages(["Meralco electric bill", "Adobong manok recipe"])
    assert v.dtype == np.float32 and v.shape == (2, embedder.dim)
    assert np.allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-5)
    assert np.allclose(from_bytes(to_bytes(v[0])), v[0])


def test_taglish_query_matches_meaning(embedder):
    docs = embedder.embed_passages(["Electric bill: total amount due PHP 3,482.50, pay at Meralco",
                                    "Recipe: chicken adobo with soy sauce and vinegar"])
    q = embedder.embed_query("magkano ang bayad sa kuryente")
    assert q @ docs[0] > q @ docs[1]


def test_missing_model_reports_not_ready():
    e = Embedder(Section(model="intfloat/does-not-exist-peekr", device="cpu", batch_size=4))
    e.load()
    assert not e.ready.is_set() and e.done.is_set() and "download" in e.error


def test_llm_client_down_raises_unavailable():
    cfg = load_config()
    client = LLMClient(Section(url="http://127.0.0.1:1"), cfg.llm)
    try:
        client.list_models(timeout=1)
        raise AssertionError("expected LLMUnavailable")
    except LLMUnavailable:
        pass
