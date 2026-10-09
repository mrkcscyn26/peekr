# Notes for coding agents

Read PRD (`docs/prd.md`) Section 0 and `docs/architecture-and-flow.md` first. The hard rules there override everything.

## Environment (Windows)
- Python 3.12 virtual environment in `.venv` (`.venv/Scripts/python.exe`). Install with `pip install -r requirements.txt`.
- Embedding model download (online, once): `python -m app.ai.embedder --download`. At runtime the app forces Hugging Face offline mode.
- Ollama runs on 127.0.0.1:11434. The configured model is in `config.yaml` (`llm.model`).

## Verify
- Tests: `.venv/Scripts/python.exe -m pytest -q`. Outbound sockets are blocked in conftest. Temp files go to `.pytest_tmp/`, because AppData is a blocked system folder for `POST /api/folders`.
- Demo data: `python tests/make_demo_data.py` (writes `tests/demo_data/`, git-ignored).
- Search benchmark: `python scripts/eval_search.py --runs 3`. LLM timing: `python scripts/bench_llm.py <model> ...`.
- Run the server: `python -m app.main --no-browser` (127.0.0.1:8000). Use `--preflight` to check the port and Ollama.
- Point the app at another config or data folder with the `PEEKR_CONFIG` and `PEEKR_DATA_DIR` env vars.

## Conventions
- Only `app/db/repo.py` contains SQL. The C8 worker thread is the only writer of files, chunks and events. Exceptions: folder delete cascades and C13 summary writes.
- Each module docstring says which component, flow and FR it implements, and lists flagged assumptions.
- Record real measurements only, in `docs/benchmarks.md`.
