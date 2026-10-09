"""T-04 / T-06: index a fresh copy of the demo set, record embedding speed, run the 30 fixed
queries and print the top-3 rate. Results are printed unedited.

Usage: python scripts/eval_search.py [--runs 3]
Runs fully offline (Hugging Face offline mode, no LLM calls).
"""

from __future__ import annotations

import argparse
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from app.ai.embedder import Embedder  # noqa: E402
from app.core.config import load_config  # noqa: E402
from app.db import repo  # noqa: E402
from app.db.connection import init_db, open_conn, transaction  # noqa: E402
from app.core.config import utc_now  # noqa: E402
from app.indexing.pipeline import Indexer  # noqa: E402
from app.search import query_parser  # noqa: E402
from app.search.hybrid import HybridSearch  # noqa: E402
from app.services.category import CategoryService  # noqa: E402
from make_demo_data import QUERIES, build  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args()
    work = Path(tempfile.mkdtemp(prefix="peekr_eval_", dir=ROOT / ".pytest_tmp" if (ROOT / ".pytest_tmp").exists() else None))
    try:
        demo = work / "demo"
        build(demo)
        cfg = load_config(overrides={"data_dir": str(work / "data")})
        init_db(cfg.db_path)
        emb = Embedder(cfg.embedding)
        t0 = time.perf_counter()
        emb.load()
        print(f"embedder load: {time.perf_counter() - t0:.1f}s")

        texts = [f"Sample passage number {i} about bills, school reports and travel plans. " * 12 for i in range(256)]
        speeds = []
        for _ in range(args.runs):
            t0 = time.perf_counter()
            emb.embed_passages(texts)
            speeds.append(len(texts) / (time.perf_counter() - t0))
        print(f"embedding speed (256 passages x ~1000 chars, batch {cfg.embedding.batch_size}, {cfg.embedding.device}): "
              f"{', '.join(f'{s:.1f}' for s in speeds)} passages/s")

        idx_times = []
        for run in range(args.runs):
            if cfg.db_path.exists():
                for suffix in ("", "-wal", "-shm"):
                    Path(str(cfg.db_path) + suffix).unlink(missing_ok=True)
            init_db(cfg.db_path)
            with open_conn(cfg.db_path) as conn, transaction(conn):
                repo.insert_folder(conn, str(demo.resolve()), utc_now())
            search = HybridSearch(cfg.search, emb, str(cfg.db_path), cfg.llm.model)
            indexer = Indexer(cfg, str(cfg.db_path), emb, CategoryService(cfg.category, emb), on_change=search.mark_dirty)
            indexer.start()
            t0 = time.perf_counter()
            indexer.submit_job(None, "initial")
            indexer.wait_idle(600)
            idx_times.append(time.perf_counter() - t0)
            status = indexer.status()
            indexer.stop()
        print(f"index demo set ({status['total']} files): {', '.join(f'{t:.1f}' for t in idx_times)} s")

        hits, lat, lines = 0, [], []
        search.search(query_parser.parse("warm up"))
        for q, expected in QUERIES:
            t0 = time.perf_counter()
            out = search.search(query_parser.parse(q), 10)
            lat.append((time.perf_counter() - t0) * 1000)
            top = [r["name"] for r in out["results"][:3]]
            ok = expected in top
            hits += ok
            lines.append(f"{'HIT ' if ok else 'MISS'} {q!r} -> {top} (expected {expected})")
        print("\n".join(lines))
        print(f"top-3: {hits}/{len(QUERIES)} = {hits / len(QUERIES):.0%}")
        print(f"search latency ms: median {statistics.median(lat):.0f}, max {max(lat):.0f}")
        with open_conn(cfg.db_path) as conn:
            cats = conn.execute("SELECT category, COUNT(*) FROM files WHERE status='indexed' GROUP BY category").fetchall()
        print("categories:", {r[0]: r[1] for r in cats})
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
