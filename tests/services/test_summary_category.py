"""T-09: C13 chunk selection and fallback, C14 category assignment."""

import numpy as np

from app.core.config import load_config
from app.db.connection import connect, init_db
from app.services.category import CategoryService
from app.services.summary import fallback_text, select_chunks


def test_select_chunks_first_then_spread_within_budget():
    chunks = [{"text": f"{i:02d}" + "x" * 998} for i in range(40)]
    sel = select_chunks(chunks, 8000)
    assert sel[0]["text"].startswith("00")
    assert sum(len(c["text"]) for c in sel) <= 8000
    idx = [int(c["text"][:2]) for c in sel]
    assert idx == sorted(idx) and idx[-1] == 39 and len(idx) == 8


def test_select_chunks_trims_huge_first_chunk():
    sel = select_chunks([{"text": "a" * 20000}], 8000)
    assert len(sel) == 1 and len(sel[0]["text"]) == 8000


def test_fallback_trimmed():
    out = fallback_text([{"text": "word " * 200}], 400)
    assert len(out) <= 403 and out.endswith("...")


def test_category_assignment(tmp_path, embedder):
    cfg = load_config(overrides={"data_dir": str(tmp_path)})
    init_db(cfg.db_path)
    conn = connect(cfg.db_path)
    svc = CategoryService(cfg.category, embedder)
    svc.ensure_labels(conn)
    assert {r["name"] for r in conn.execute("SELECT name FROM categories")} == set(cfg.category.labels)
    bill = embedder.embed_passages(["Electric bill statement. Total amount due PHP 3,482.50. Pay before due date."])
    assert svc.assign(bill) in ("Finance", "Other")
    strict = CategoryService(load_config(overrides={"data_dir": str(tmp_path), "category.min_score": 0.99}).category,
                             embedder)
    strict.ensure_labels(conn)
    assert strict.assign(bill) == "Other"
    assert svc.assign(np.zeros((0, embedder.dim), dtype=np.float32)) == "Other"
    conn.close()
