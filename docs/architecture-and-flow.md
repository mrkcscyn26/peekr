# Peekr: System Architecture and System Flow

Source: Peekr PRD v1.0 (AppBuildersPH Hackathon 2026, Theme: Local AI), Sections 7 and 8. Section numbers match the PRD so cross-references stay valid. This file is written for an AI coding agent: read Part 1 (architecture) first, then Part 2 (flow).

## How to use this file

- **IDs:** C# is a component (Section 8.2), F# is a flow (Part 2), FR-# is a functional requirement (index below), T-# is a build task (PRD Section 12.1).
- **Precedence if sections conflict:** the hard rules, then the FR requirements, then Section 8, then Section 7.
- **Keep it aligned:** if you change a flow, update its row in Section 8.12, the component table (8.2), and the API table (8.8) in the same change.
- **Stay in scope:** the MVP covers documents (PDF, DOCX, PPTX, TXT) in folders the user selects. Do not add video, audio, photo search, or whole-disk scanning.

## Product in one paragraph

Peekr is a localhost web app (Python FastAPI backend, browser interface) that indexes documents in folders the user selects. The user searches by meaning in English, Filipino, or Taglish, and each result shows a summary on demand, the file location, a category, and a history of file events. All AI (embeddings and a small LLM through Ollama) runs on the user's laptop, and nothing is sent to the internet. Reference hardware: Windows laptop with an RTX 2050 and 4GB VRAM.

## Hard rules for the build (never break these)

1. Never write, move, rename, or delete a user's files. Access to indexed folders is read-only (FR-3). The app writes only inside its own data folder.
2. Bind the server to 127.0.0.1 only (FR-24). Never 0.0.0.0.
3. Make no outbound network calls at runtime: no telemetry, no CDN links, no cloud API (FR-22, FR-23). Bundle all frontend assets locally.
4. Use local models only, through Ollama on 127.0.0.1:11434. Never use a :cloud model tag.
5. Stay within the VRAM budget (Section 8.5): one LLM loaded at a time, LLM calls run one at a time, embeddings run on the CPU by default.
6. Stay inside the MVP scope. Stretch items (OCR, XLSX, change notes, category edit) start only after the hardening task passes.
7. When a dependency, model, or major tool is added, add it to the disclosure table in Section 8.4 in the same change (hackathon rule).
8. Report only real measurements. Never hard-code or invent benchmark numbers.
9. A bad file must never crash indexing or the server. Catch the error, record the reason, and continue (Section 8.11).
10. If a requirement is unclear, choose the simplest option that satisfies these rules, write the assumption in a code comment and the commit message, and flag it for the team instead of guessing silently.

## Requirement index (FR-IDs used in this file)

Priority: M = Must, S = Should, C = Could. Full acceptance criteria are in PRD Section 9.

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | Add and remove indexed folders | M |
| FR-2 | Exclude subfolders | S |
| FR-3 | The app never modifies user files | M |
| FR-4 | Extract text from PDF, DOCX, PPTX, and TXT | M |
| FR-5 | Skip unreadable or protected files with a clear message | M |
| FR-6 | Show indexing progress | S |
| FR-7 | Re-index only new or changed files | M |
| FR-8 | OCR for images and scanned PDFs | C |
| FR-9 | Search by meaning in English, Filipino, and Taglish | M |
| FR-10 | Combine keyword and vector search | M |
| FR-11 | Understand date, file type, and folder clues | S |
| FR-12 | Results show name, path, category, modified date, and snippet | M |
| FR-13 | Open file and open folder buttons | M |
| FR-14 | Generate a short summary on demand | M |
| FR-15 | Cache summaries and refresh them when the file changes | M |
| FR-16 | Show folder path and an assigned category | M |
| FR-17 | User can change a category | C |
| FR-18 | Log create, edit, move, rename, and delete events | M |
| FR-19 | Reconciliation scan at startup | S |
| FR-20 | Per-file timeline view | M |
| FR-21 | Short AI note on what changed between versions | C |
| FR-22 | All core features work with the network disabled | M |
| FR-23 | No telemetry and no external requests | M |
| FR-24 | The backend only accepts local connections | M |
| FR-25 | On-screen indicator that processing is local | S |

---

# Part 1: System Architecture (PRD Section 8)

## 8.1 Overview

```
PROCESS VIEW (everything runs on one laptop, nothing leaves it)

[P1 Browser]  http://127.0.0.1:8000
   C1 UI (static HTML, CSS, JS, no CDN)
        |  JSON over HTTP (/api/*) and static files
        v
[P2 Backend]  one Python process (uvicorn + FastAPI)
   C2 API layer
     |-- /api/search ------------> C10 Query parser -> C7 Embedder -> C11 Hybrid search -> C9
     |-- /api/files/*/summary ---> C13 Summary service -> C12 LLM client -> [P3 Ollama]
     |-- /api/index, /api/folders -> C8 Indexer (job queue + worker thread)
     |        C8 uses: C4 Scanner, C5 Extractors, C6 Chunker, C7 Embedder,
     |                 C14 Category, C17 History service, C9 Database layer
     |-- /api/files/*/open* -----> C18 OS actions
     |-- /api/health ------------> C19 Health checks
   Background threads
     C15 Watcher (watchdog) ----events----> C8 queue
     C16 Reconciler (startup, rescan) ----> C8 queue
   Shared: C3 Core (config, logging), C9 Database layer

[Data folder]  data/peekr.db (SQLite, WAL): folders, files, chunks, chunks_fts,
               summaries, events, categories, settings. Also logs/
[P3 Ollama]    http://127.0.0.1:11434, local LLM (3B to 4B, 4-bit) on the GPU,
               called only by C12
[User folders] read-only access by C4, C5, C15, C16, C18
```

No component calls an external network service.

## 8.2 Components

| ID | Component | Module | Responsibility | Depends on | Flows |
|---|---|---|---|---|---|
| C1 | UI | web/index.html, app.js, style.css | Folder management, search box, result cards, detail view with summary and timeline, indexing progress, status indicators | C2 over HTTP | F1 to F7 |
| C2 | API layer | app/api/*.py | FastAPI routers, request validation, error format, serves the web folder | C3, C8 to C19 | F1 to F7 |
| C3 | Core | app/core/config.py, logging.py | Load configuration, resolve data folder paths, set up logging | None | All |
| C4 | Scanner | app/indexing/scanner.py | Walk folders, filter files, return path, size, created and modified times | C3 | F2, F6 |
| C5 | Extractors | app/indexing/extractors/ | Text and locations from PDF, DOCX, PPTX, TXT. Classify failures (password protected, no text, unreadable). | None | F2, F5 |
| C6 | Chunker | app/indexing/chunker.py | Split text segments into overlapping chunks that keep their page or slide location | C3 | F2, F5 |
| C7 | Embedder | app/ai/embedder.py | Load the embedding model once, embed passages and queries, return normalized float32 vectors | C3 | F2, F3, F5 |
| C8 | Indexer | app/indexing/pipeline.py | Job queue, the single worker thread, end-to-end processing of one file, progress reporting, handling watcher events | C4 to C7, C9, C14, C17 | F2, F5, F6 |
| C9 | Database layer | app/db/schema.sql, connection.py, repo.py | SQLite connections (WAL), schema creation, all queries. One writer thread. | C3 | All |
| C10 | Query parser | app/search/query_parser.py | Extract file type, date range, and folder hint, and produce the semantic text | C3 | F3 |
| C11 | Hybrid search | app/search/hybrid.py | In-memory vector matrix, FTS5 search, rank fusion, filters, snippets | C7, C9 | F3 |
| C12 | LLM client | app/ai/llm.py | Ollama HTTP client, global lock, timeout, thinking mode off | C3 | F1, F4 |
| C13 | Summary service | app/services/summary.py | Select chunks, build the prompt, cache by content_hash and model, extractive fallback | C9, C12 | F4 |
| C14 | Category service | app/services/category.py | Embed category labels once, assign a category by cosine similarity | C7, C9 | F2, F5 |
| C15 | Watcher | app/history/watcher.py | watchdog observers, debounce, classify events, move detection buffer | C3, C8 | F5 |
| C16 | Reconciler | app/history/reconciler.py | Compare disk with the database, find created, modified, moved, renamed, and deleted files | C4, C8, C9, C17 | F1, F6 |
| C17 | History service | app/history/events.py | Write and read events, apply path changes for moves, renames, and deletes | C9 | F2, F4, F5, F6 |
| C18 | OS actions | app/core/os_actions.py | Native folder dialog, open a file, open a folder in Explorer | C3 | F2, F7 |
| C19 | Health checks | app/core/health.py | Ollama reachable, model installed, embedder ready, data folder writable | C3, C12 | F1 |

## 8.3 Data model

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS folders (
  id            INTEGER PRIMARY KEY,
  path          TEXT NOT NULL UNIQUE,      -- absolute path
  enabled       INTEGER NOT NULL DEFAULT 1,
  last_scan_at  TEXT,                      -- UTC ISO 8601
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS excluded_paths (
  id         INTEGER PRIMARY KEY,
  folder_id  INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
  path       TEXT NOT NULL,
  UNIQUE (folder_id, path)
);

CREATE TABLE IF NOT EXISTS files (
  id            INTEGER PRIMARY KEY,
  folder_id     INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
  current_path  TEXT NOT NULL UNIQUE,
  name          TEXT NOT NULL,
  extension     TEXT NOT NULL,             -- lowercase with dot, e.g. .pdf
  size_bytes    INTEGER NOT NULL,
  created_at    TEXT,                      -- file system times
  modified_at   TEXT NOT NULL,
  content_hash  TEXT,                      -- SHA-256 hex of the file bytes
  category      TEXT,
  status        TEXT NOT NULL,             -- pending | indexed | skipped | error | deleted
  status_reason TEXT,                      -- reason code, see Section 8.11
  indexed_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_files_hash   ON files(content_hash);
CREATE INDEX IF NOT EXISTS idx_files_folder ON files(folder_id, status);

CREATE TABLE IF NOT EXISTS chunks (
  id          INTEGER PRIMARY KEY,
  file_id     INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  location    TEXT,                        -- 'page 3', 'slide 5', 'part 2'
  text        TEXT NOT NULL,
  embedding   BLOB NOT NULL,               -- float32, L2-normalized
  UNIQUE (file_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file_id);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  text, content='chunks', content_rowid='id',
  tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;

CREATE TABLE IF NOT EXISTS summaries (
  file_id       INTEGER PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
  content_hash  TEXT NOT NULL,             -- hash the summary was made from
  summary_text  TEXT NOT NULL,
  model_name    TEXT NOT NULL,
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
  id           INTEGER PRIMARY KEY,
  file_id      INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  event_type   TEXT NOT NULL,              -- baseline | created | modified | moved | renamed | deleted
  old_path     TEXT,
  new_path     TEXT,
  hash_before  TEXT,
  hash_after   TEXT,
  occurred_at  TEXT NOT NULL,              -- detection time, UTC
  source       TEXT NOT NULL               -- scan | watcher | reconcile
);
CREATE INDEX IF NOT EXISTS idx_events_file ON events(file_id, occurred_at);

CREATE TABLE IF NOT EXISTS categories (
  name        TEXT PRIMARY KEY,
  description TEXT NOT NULL,
  embedding   BLOB                         -- float32, normalized
);

CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL                      -- e.g. embedding_model, embedding_dim, schema_version
);
```

**Schema rules.** Removing a folder deletes its files, chunks, summaries, and events (cascade). A deleted file keeps its files row (status deleted) and its events, but loses its chunks and summary, so it is no longer searchable and its timeline survives. Embeddings are raw float32 bytes with the dimension stored in settings.embedding_dim. If the embedding model changes, every chunk must be re-embedded. Timestamps are UTC ISO 8601 strings, and content_hash is a SHA-256 hex string.

## 8.4 Tech stack and disclosure list

These are the planned choices. Keep this list updated, since the rules require disclosure of models, frameworks, and major tools.

| Layer | Planned choice | Purpose | Alternative |
|---|---|---|---|
| Language model | 3B to 4B instruct model, 4-bit. Primary candidates: Qwen3 4B (thinking mode off) and Qwen2.5 3B | Summaries, plus a fallback for query parsing | Gemma 4 E2B or E4B, Llama 3.2 3B, Phi-4-mini |
| LLM runtime | Ollama, local models only, cloud features off | Runs the model on the GPU and offers a local API | llama.cpp |
| Embeddings | multilingual-e5-small with sentence-transformers | Meaning-based search in English and Filipino, can run on the CPU | bge-small |
| Backend | Python 3.11 or 3.12 with FastAPI and Uvicorn | Local API and the indexing and search pipelines | Flask |
| Text extraction | pypdfium2 or pdfplumber for PDF, python-docx, python-pptx, plain read for TXT | Pull out text and metadata | PyMuPDF (AGPL license, check first), openpyxl for XLSX (stretch) |
| Keyword search | SQLite FTS5 | Exact words and names | None |
| Vector search | NumPy cosine similarity over stored vectors | Simple, no extension to install, enough for a few thousand chunks | sqlite-vec or LanceDB |
| Database | SQLite through Python's sqlite3 | Files, chunks, summaries, events, and settings | None |
| File watching | watchdog with a short debounce | Live history events, ignoring temporary saves | Periodic rescan |
| Query clues | dateparser plus a small hand-written Filipino phrase map | Dates like last month or kahapon, with the LLM returning JSON as a fallback | LLM only |
| Hashing | hashlib SHA-256 (standard library) | Detect changes and match moved files | None |
| OCR (stretch) | Tesseract or RapidOCR | Text from scans and images | PaddleOCR |
| Frontend | HTML, CSS, and JavaScript served by FastAPI | Search page, results, detail view, timeline | React with Vite |
| Native actions | tkinter folder dialog, os.startfile, Windows Explorer | Pick folders and open files or folders from the backend | Paste a folder path |
| Run and packaging | Python virtual environment, requirements.txt, run.bat | Repeatable local start | uv |
| Testing and measuring | pytest, a timing script, nvidia-smi, Windows Resource Monitor | Check features, record real speeds, show no network traffic | Wireshark |
| Version control | Git and GitHub | Commit history shows the work started at the hackathon | None |
| Development tools | AI coding assistants as allowed by the rules, logged by the team | Faster development | None |

All planned components are free and open source, and none needs a subscription or an online account while the app runs. Record each model and library license in the disclosure list. Use local model tags only and turn on Ollama's local-only mode. Do not pull Ollama cloud models (names ending in :cloud), because the hackathon requires the AI to run on the user's device.

## 8.5 Model and VRAM budget (4GB)

| Item | Runs on | Approximate memory |
|---|---|---|
| 3B to 4B LLM at 4-bit | GPU | About 2 to 3GB |
| Embedding model | CPU or GPU | Well under 1GB |
| OCR | CPU | System RAM |
| Windows and display | GPU | About 0.3 to 0.5GB |

Keep the context window at 2k to 4k tokens. Models of 7B and up are not used, because they spill into system RAM and slow the demo. Confirm these figures by measuring on the actual laptop.

## 8.6 Localhost run

Peekr runs as a localhost app. The Python backend and the browser page run on the same laptop, and nothing is hosted online. The browser is only the screen, and all AI work happens on the laptop.

| Item | Setting |
|---|---|
| App address | http://127.0.0.1:8000, served by FastAPI (any free port works) |
| Binding | 127.0.0.1 only, never 0.0.0.0, so other devices on the network cannot reach the app |
| LLM runtime | Ollama on http://127.0.0.1:11434, local models only |
| Start command | `run.bat` starts the backend and opens the browser |
| Data location | A local data folder next to the app (SQLite index, summaries, history, logs) |
| Internet | Needed once to install libraries and download models, not needed while the app runs |

**First-time setup (once, with internet)**

1. Install the latest NVIDIA driver, Python 3.11 or 3.12, Git, and Ollama for Windows.
2. Clone the repository and create a virtual environment.
3. Install the dependencies from `requirements.txt`.
4. Pull the chosen model with Ollama (for example `ollama pull qwen3:4b`) and download the embedding model.
5. Run the app once, then turn off Wi-Fi and run it again to confirm it works offline.

**Every run (no internet needed)**

1. Make sure Ollama is running.
2. Double-click `run.bat`. It activates the virtual environment and starts the server on 127.0.0.1:8000.
3. The browser opens the app. Select folders and start indexing.
4. To stop the app, close the console window.

**Rules for the localhost setup**

- Do not deploy the app online or expose it through a public tunnel, because that would turn it into a cloud app.
- Keep the server bound to 127.0.0.1 (FR-24).
- Use local model tags only, with no :cloud models.
- Judges cannot open localhost, so prepare a backup demo video, a README with setup steps, and the repository. Run the live demo on the demo laptop.
- Optional later: wrap the same app in a desktop window with pywebview or Tauri. The localhost backend stays the same.

## 8.7 Repository structure

Create this layout. Each folder maps to the components in Section 8.2.

```
peekr/
  run.bat                 # check Ollama, activate venv, start uvicorn, open browser (F1)
  requirements.txt        # pinned versions
  config.yaml             # defaults, see Section 8.9
  README.md               # setup steps, scope, known limitations
  app/
    main.py               # FastAPI app, startup and shutdown hooks (F1)
    api/                  # C2: health.py, folders.py, index.py, search.py, files.py
    core/                 # C3, C18, C19: config.py, logging.py, os_actions.py, health.py
    db/                   # C9: schema.sql, connection.py, repo.py
    indexing/             # C4, C5, C6, C8: scanner.py, chunker.py, pipeline.py, extractors/
      extractors/         #   pdf.py, docx.py, pptx.py, txt.py (stretch: xlsx.py, ocr.py)
    ai/                   # C7, C12: embedder.py, llm.py
    search/               # C10, C11: query_parser.py, hybrid.py
    services/             # C13, C14: summary.py, category.py
    history/              # C15, C16, C17: watcher.py, reconciler.py, events.py
  web/                    # C1: index.html, app.js, style.css (no external CDN or fonts)
  tests/                  # pytest, mirrors app/. demo_data/ holds the sample files
  data/                   # created at runtime: peekr.db, logs/ (git-ignored)
  docs/                   # PRD export, disclosure list, benchmark notes
```

Rules: one component per module, no circular imports, the API layer (C2) calls services and C9 repo functions, and only the database layer (C9) contains SQL.

## 8.8 API specification

The backend (C2) serves the interface at GET / and static files from the web folder. All /api endpoints accept and return JSON. Only one indexing job runs at a time, and a second start request is queued. Errors return an HTTP 4xx or 5xx status with a body that contains error.code and error.message.

| Endpoint | Purpose | Request fields | Response fields | Flow | Requirements |
|---|---|---|---|---|---|
| GET /api/health | Status of the local stack | None | ollama_ok, llm_model, llm_ready, embedder_ready, db_ok, local_only (always true) | F1 | FR-22, FR-25 |
| GET /api/folders | List indexed folders | None | folders: id, path, enabled, available, last_scan_at, file_count | F1, F2 | FR-1 |
| POST /api/folders/pick | Open the native folder dialog | None | path, or null if cancelled | F2 | FR-1 |
| POST /api/folders | Add a folder | path | folder (same fields as the list) | F2 | FR-1 |
| DELETE /api/folders/{id} | Remove a folder and everything indexed from it | None | ok | F2 | FR-1 |
| POST /api/folders/{id}/exclusions | Exclude a subfolder (Should) | path | ok | F2 | FR-2 |
| POST /api/index/start | Start an indexing or rescan job | folder_id (optional, default all), kind (initial or rescan) | job_id | F2, F6 | FR-4 to FR-7, FR-19 |
| GET /api/index/status | Progress of the current or last job | None | state (idle, queued, running, done, failed), total, processed, skipped, errors, current_file, skipped_items (path, reason) | F2 | FR-5, FR-6 |
| POST /api/search | Search the index | query, limit (default 10) | results (file_id, name, extension, path, folder, category, modified_at, score, snippet, location, summary_cached), parsed (extensions, date_from, date_to, folder_hint), relaxed_filters, reason, elapsed_ms | F3 | FR-9 to FR-12, FR-16 |
| GET /api/files/{id} | File metadata | None | id, name, extension, path, folder, size_bytes, created_at, modified_at, category, status, summary_cached | F4 | FR-16 |
| POST /api/files/{id}/summary | Get or create the summary | force (optional boolean) | summary, cached, fallback, model, elapsed_ms | F4 | FR-14, FR-15 |
| GET /api/files/{id}/history | File timeline, newest first | None | events: event_type, old_path, new_path, occurred_at, source | F4, F5 | FR-18, FR-20 |
| POST /api/files/{id}/open | Open with the default app | None | ok | F7 | FR-13 |
| POST /api/files/{id}/open-folder | Show the file in Explorer | None | ok | F7 | FR-13 |
| PATCH /api/files/{id}/category | Change the category (Could) | category | file metadata | None | FR-17 |

**Error codes**

| Code | HTTP | Meaning |
|---|---|---|
| invalid_path | 400 | The path is missing, not a directory, a system folder, or nested in an added folder |
| already_added | 409 | The folder is already indexed |
| folder_not_found | 404 | Unknown folder id |
| file_not_found | 404 | Unknown file id |
| file_missing | 404 | The file is in the database but gone from disk (a reconciliation is queued) |
| forbidden_path | 403 | The path is outside every indexed folder |
| embedder_not_ready | 503 | The embedding model is still loading or missing |
| llm_unavailable | 503 | Ollama is down and no fallback is possible |
| os_error | 500 | The operating system refused to open the file or folder |
| internal | 500 | Unexpected error, logged without file contents |

## 8.9 Configuration

Store these defaults in config.yaml at the project root. They are starting points: tune them on the demo set and record the final values in the README.

```yaml
server:
  host: 127.0.0.1            # must stay 127.0.0.1 (FR-24)
  port: 8000
data_dir: ./data
ollama:
  url: http://127.0.0.1:11434
llm:
  model: qwen3:4b            # final choice after the Phase 0 tests
  temperature: 0.2
  num_ctx: 4096
  num_predict: 250
  timeout_seconds: 60
  disable_thinking: true
embedding:
  model: intfloat/multilingual-e5-small
  device: cpu
  batch_size: 32
indexing:
  supported_extensions: ['.pdf', '.docx', '.pptx', '.txt']
  max_file_size_mb: 50
  ignore_patterns: ['~$*', '*.tmp', '*.crdownload', '*.part', '.*']
chunking:
  target_chars: 1000
  overlap_chars: 150
  min_chunk_chars: 200
search:
  top_k_vector: 50
  top_k_keyword: 50
  rrf_k: 60
  default_limit: 10
  snippet_chars: 240
  query_llm_fallback: false  # rules only by default, keeps search fast
summary:
  char_budget: 8000          # about 2000 tokens of document text
  fallback_chars: 400
category:
  min_score: 0.75            # tune in Phase 3 on the demo set
  labels:
    School: classes, lessons, reports, assignments, research, notes
    Finance: receipts, bills, invoices, bank statements, budgets
    Work: office documents, memos, proposals, project files
    Personal: letters, resumes, personal notes, travel, family
    Government and Forms: forms, applications, permits, certificates
    Other: anything that does not fit the labels above
watcher:
  debounce_seconds: 1.5
  move_window_seconds: 5
```

Rules: modules read settings only through C3. server.host must not be changed to anything other than 127.0.0.1. Values that are expected to change after testing are llm.model, category.min_score, and the chunking sizes.

## 8.10 Core algorithms and rules

**Text extraction (C5)**

| Type | Library | Segments and locations | Notes |
|---|---|---|---|
| PDF | pypdfium2 or pdfplumber | One segment per page, location 'page N' | A password-protected file is skipped (password_protected). A file with no text on any page is skipped (no_text). OCR is a stretch item. |
| DOCX | python-docx | Paragraphs and table cells grouped into parts of about 3000 characters, location 'part N' | DOCX has no reliable page numbers |
| PPTX | python-pptx | One segment per slide (titles, text boxes, tables, speaker notes), location 'slide N' | None |
| TXT | Plain read | Parts of about 3000 characters, location 'part N' | Try utf-8, then utf-8-sig, then cp1252 |

Normalize whitespace and drop empty segments.

**Chunking (C6)**

- Chunks never cross a page or slide boundary.
- Inside a segment, split at paragraph or line breaks, then at sentences, and merge pieces up to chunking.target_chars. Carry chunking.overlap_chars into the next chunk.
- A segment shorter than the target becomes one chunk. Never create an empty chunk.
- chunk_index starts at 0 for each file, and each chunk keeps the location of its segment.

**Embedding (C7)**

- multilingual-e5 models expect prefixes: 'passage: ' before chunk text and 'query: ' before the search query.
- L2-normalize every vector and store it as float32 bytes. Read the vector dimension from the model at load time and save it in settings.embedding_dim. Do not hard-code it.
- Normalized vectors make cosine similarity equal to the dot product.
- Run on the CPU by default, in batches of embedding.batch_size, and truncate input to the model's maximum length.

**Query parsing (C10)**

| Clue | Examples | Result |
|---|---|---|
| File type | pdf, word or docx or document, ppt or pptx or slides or powerpoint, txt or text file | extensions |
| Relative date | today or ngayon, yesterday or kahapon, this week or ngayong linggo, last week or nakaraang linggo or noong isang linggo, this month or ngayong buwan, last month or nakaraang buwan or noong nakaraang buwan, last year or nakaraang taon, N days ago | date_from and date_to |
| Month name | January or Enero, with an optional year | date_from and date_to for that month |
| Folder hint | in Downloads, sa Documents, from the school folder | folder_hint |

- semantic_text is the query with the recognized clue words removed. If it is empty, F3 lists the matching files newest first.
- A date filter matches a file when created_at or modified_at falls inside the range, because downloaded files often keep an older modified time.
- Dates use the laptop's local time zone and are converted to UTC for comparison.
- folder_hint is a case-insensitive substring match against the parts of the file path.
- Use dateparser only for explicit dates such as 12 March 2026. Do not call the LLM unless search.query_llm_fallback is true.

**Search ranking (C11)**

- Keep a NumPy matrix of all chunk embeddings and a parallel array of chunk ids. Rebuild it from the database when the dirty flag is set. About 20,000 chunks of 384 float32 values is roughly 31 MB.
- Vector list: the top search.top_k_vector chunks by dot product. Keyword list: the top search.top_k_keyword chunks from FTS5 ranked by bm25, with the query terms joined by OR and special characters escaped.
- Reciprocal rank fusion: the score of a chunk is the sum over both lists of 1 / (rrf_k + rank), with rank starting at 1.
- Apply the filters, then group by file. A file's score is its best chunk score. Return the top files up to the limit, each with its best chunk.
- Snippet: the best chunk text centered on the first matched keyword if there is one, otherwise the start of the chunk, trimmed to search.snippet_chars.
- Only files with status indexed can appear in results.

**Summary (C13)**

- Chunk selection: take the first chunk, then chunks spread evenly across the file in file order, until summary.char_budget characters are used.
- System prompt: You summarize documents for a file search tool. Write 3 to 5 sentences in the same language as the document (English, Filipino, or Taglish). Use only the text provided. Do not add advice or opinions.
- User prompt: Document name: {name}, then the selected text.
- Call settings: llm.temperature, llm.num_ctx, llm.num_predict, and thinking mode off (use the Ollama think option, or the no_think switch for Qwen3 if the option is unavailable).
- Cache key: file_id plus content_hash plus model_name. A summary is stale when the hash or the model differs.
- Fallback: the first chunks joined and trimmed to summary.fallback_chars, returned with fallback true.

**Category (C14)**

- At startup, embed each label as its name plus its description (with the passage prefix) and store the result in the categories table.
- A file's vector is the normalized mean of its first 5 chunk vectors.
- The category is the label with the highest cosine similarity. If the best score is below category.min_score, use Other.
- Assign the category at index time and again when the file's content changes. A user override (stretch) is kept.

**Hashing and change detection**

- SHA-256 over the file bytes in 1 MB blocks.
- A file is unchanged when its size and modified time match the stored values. A different hash at the same path is a modification. The same hash at a different path is a move or rename.

**Event classification (C15, C16, C17)**

| Event type | When it is written | Change to the files row | Re-indexing |
|---|---|---|---|
| baseline | First scan of a newly added folder | Insert | Full |
| created | A new file appears (watcher or rescan) | Insert | Full |
| modified | The content hash changed | Update hash and times | Re-chunk and re-embed |
| moved | Same hash, parent folder changed | Update current_path | None |
| renamed | Same hash, same folder, name changed | Update name and current_path | None |
| deleted | File gone and no matching created event inside the move window | Status deleted, chunks removed | Remove chunks |

## 8.11 Runtime model, states, and error handling

**Threads and shared resources**

| Resource | Rule |
|---|---|
| FastAPI request handlers | Short calls only. They read the database with their own connections and call services. They never run indexing. |
| Index worker thread (C8) | The only writer of files, chunks, and events. It handles one job or watcher event at a time, in order. |
| Watcher thread (C15) | Receives file system events and only puts them on the queue. It never touches the database. |
| LLM lock (C12) | One global lock, so only one Ollama call runs at a time and the GPU is never overloaded. |
| Embedder (C7) | Loaded once. Calls are guarded by a lock if the library is not thread-safe. |
| Vector cache (C11) | Guarded by a lock. A dirty flag is set after any change to chunks and cleared after a rebuild. |
| SQLite (C9) | WAL mode, busy_timeout of 5000 ms, foreign keys on. Writes use short transactions. C13 writes only summaries. |

**File status**

| Status | Meaning | Searchable | Next |
|---|---|---|---|
| pending | Found and waiting to be processed | No | indexed, skipped, or error |
| indexed | Text extracted, chunks and embeddings stored | Yes | pending (when changed), deleted |
| skipped | Not indexable, with a reason code (no_text, password_protected, too_large) | No | pending (when the file changes) |
| error | Processing failed, with a reason code (extract_failed, file_locked, internal) | No | pending (on rescan or when the file changes) |
| deleted | The file is gone from disk. The row and its events are kept. | No | pending (if the same path reappears, the row is reused) |

**Job states:** idle, queued, running, then done or failed. A job fails only on a fatal error such as the database not being writable. Errors on single files never fail a job. The state is shown by GET /api/index/status.

**Error handling**

| Situation | Reason code | Behavior |
|---|---|---|
| Password-protected PDF | password_protected | Skip and list it in the interface |
| No extractable text | no_text | Skip and list it in the interface (OCR is a stretch item) |
| File larger than the limit | too_large | Skip |
| Corrupt or unreadable file | extract_failed | Mark error and continue |
| File locked by another program | file_locked | Retry once after 1 second, then mark error |
| Ollama down or timed out | llm_unavailable | Summary falls back to extractive text and a banner is shown |
| Embedding model missing or still loading | embedder_not_ready | Block indexing and search with a clear message |
| Folder missing or drive disconnected | folder_unavailable | Mark the folder unavailable. Never mark its files deleted. |
| Path outside every indexed folder | forbidden_path | Refuse with HTTP 403 |
| Unexpected exception | internal | Log the error type and ids, mark the file error, and continue |

**Logging:** write logs to data/logs. Log events, ids, paths, and timings. Never log file text, summaries, or search queries.

## 8.12 Traceability: flows, components, endpoints, tables, and requirements

Use this matrix to keep the architecture and the flows aligned. If you change a flow, update its row here, the component table (Section 8.2), and the API table (Section 8.8) in the same change.

| Flow | Purpose | Components | Endpoints | Tables | Requirements |
|---|---|---|---|---|---|
| F1 | App startup and health check | C1, C3, C7, C9, C12, C15, C16, C19 | GET /api/health, GET /api/folders | folders, settings | FR-22, FR-24, FR-25 |
| F2 | Add a folder and index it | C1, C2, C4, C5, C6, C7, C8, C9, C14, C15, C17, C18 | POST /api/folders/pick, POST /api/folders, DELETE /api/folders/{id}, POST /api/index/start, GET /api/index/status | folders, files, chunks, chunks_fts, events | FR-1, FR-3 to FR-7, FR-16 |
| F3 | Search | C1, C2, C7, C9, C10, C11 | POST /api/search | files, chunks, chunks_fts | FR-9 to FR-13 |
| F4 | File detail and summary | C1, C2, C9, C12, C13, C17 | GET /api/files/{id}, POST /api/files/{id}/summary, GET /api/files/{id}/history | files, chunks, summaries, events | FR-14 to FR-16, FR-20 |
| F5 | Live history tracking | C5, C6, C7, C8, C9, C11, C14, C15, C17 | None (the timeline is read with GET /api/files/{id}/history) | files, chunks, chunks_fts, events | FR-18 |
| F6 | Reconciliation | C4, C8, C9, C16, C17 | POST /api/index/start (kind rescan), GET /api/index/status | files, chunks, events | FR-19 |
| F7 | Open a file or its folder | C1, C2, C9, C18 | POST /api/files/{id}/open, POST /api/files/{id}/open-folder | files, folders | FR-13 |

**Requirements that apply everywhere:** FR-3 (read-only access to user files) and FR-23 (no external requests) apply to every component and are enforced by the hard rules at the top of this file. FR-2 and FR-17 are served by the optional endpoints in Section 8.8. FR-8 and FR-21 are stretch items that extend C5 and C13.

**Alignment checks before a task is marked done**

- Every component C1 to C19 appears in at least one flow.
- Every endpoint used by a flow exists in Section 8.8, with the same name and fields.
- Every table written by a flow exists in Section 8.3, with the columns the flow uses.
- Every FR-* row is covered by at least one flow, endpoint, or hard rule in this matrix.

---

# Part 2: System Flow (PRD Section 7)

Each flow lists its trigger, the components (C#, Section 8.2) and API endpoints (Section 8.8) involved, the tables it reads and writes (Section 8.3), numbered steps, and failure handling. Each step names the component that does the work. Section 8.12 summarizes all flows in one matrix.

## 7.1 F1: App startup and health check

| Item | Detail |
|---|---|
| Trigger | The user runs run.bat |
| Components | C3, C9, C7, C12, C15, C16, C19, C1 |
| API | GET /api/health, GET /api/folders |
| Tables | Reads folders and settings. Creates missing tables. |
| Requirements | FR-22, FR-24, FR-25 |

1. run.bat activates the virtual environment and starts uvicorn for app.main:app on 127.0.0.1:8000.
2. C3 loads the configuration (Section 8.9) and creates the data folder (database and logs) if it is missing.
3. C9 opens the SQLite database, enables WAL mode and foreign keys, and creates any missing tables (Section 8.3).
4. C19 checks that Ollama answers at the configured URL and that the configured LLM model is installed. It keeps the result in memory for the health endpoint and does not stop startup if Ollama is down.
5. C7 loads the embedding model in a background thread. Until it finishes, embedder_ready is false.
6. C8 starts the index worker thread, which processes one job or event at a time from a queue.
7. For every enabled folder, C15 starts a watcher, and C16 queues a reconciliation scan (F6).
8. The browser opens http://127.0.0.1:8000. C1 loads, calls GET /api/health and GET /api/folders, and shows the status of Ollama, the LLM model, the embedding model, the local-only indicator (FR-25), and the folder list.

**Failure handling:** Ollama down shows a banner, summaries use the extractive fallback (F4), and search still works. The embedding model missing blocks indexing and search with a message that points to the setup step. A busy port makes run.bat print a clear message and exit.

## 7.2 F2: Add a folder and index it

| Item | Detail |
|---|---|
| Trigger | The user clicks Add folder |
| Components | C1, C2, C18, C9, C4, C5, C6, C7, C14, C8, C17, C15 |
| API | POST /api/folders/pick, POST /api/folders, DELETE /api/folders/{id}, POST /api/index/start, GET /api/index/status |
| Tables | Reads files. Writes folders, files, chunks, chunks_fts, events. |
| Requirements | FR-1, FR-3 to FR-7, FR-16 |

1. C1 calls POST /api/folders/pick. C18 opens the native folder dialog on the laptop and returns the chosen path. The user may also paste a path.
2. C1 calls POST /api/folders with the path. C2 checks that the path exists, is a directory, is not already added or nested inside an added folder, and is not a Windows system folder. C9 inserts the folders row.
3. C1 calls POST /api/index/start with the folder id and kind initial. C8 creates a job (state queued) and returns job_id. The worker thread picks it up.
4. C4 walks the folder recursively and yields candidate files: supported extension, not hidden or temporary, not excluded, size at most the configured limit. Each candidate has path, size, created time, and modified time.
5. For each candidate, C8 compares with the files table by path. New files are processed. Files with the same size and modified time are skipped as unchanged (FR-7). Files that differ are hashed and processed only if the hash changed.
6. To process a file, C8 computes the SHA-256 hash, C5 extracts text segments with locations (page or slide), C6 splits them into chunks, C7 embeds the chunks in batches with the passage prefix, and C14 assigns a category. If C5 finds no text, the file is marked skipped with a reason.
7. C9 writes one transaction per file: upsert the files row, delete old chunks, insert the new chunks with embeddings (triggers keep chunks_fts in sync). C17 writes a baseline event for an initial scan, a created event for a new file in a rescan, or a modified event for changed content.
8. After each file, C8 updates the job progress. C1 polls GET /api/index/status every second and shows processed and total counts, the current file name, and the skipped and error counts.
9. When the job ends, C8 sets the state to done, updates folders.last_scan_at, marks the vector cache dirty (C11), and makes sure a watcher is running for the folder (C15).

**Failure handling:** a file that cannot be read, is password protected, has no text, or is too large is recorded with a reason code, listed in the interface, and skipped. The job continues (Section 8.11).

**Removing a folder:** C1 calls DELETE /api/folders/{id}. C15 stops the watcher for that folder, C9 deletes the folder together with its files, chunks, summaries, and events (cascade), and C11 marks the vector cache dirty. The user's files on disk are not touched.

## 7.3 F3: Search

| Item | Detail |
|---|---|
| Trigger | The user submits a search query |
| Components | C1, C2, C10, C7, C11, C9 |
| API | POST /api/search |
| Tables | Reads chunks, chunks_fts, files |
| Requirements | FR-9 to FR-13 |

1. C1 sends POST /api/search with the query text and a limit (default 10).
2. C10 parses the query into semantic_text, extensions, date_from, date_to, and folder_hint (Section 8.10).
3. C7 embeds semantic_text with the query prefix. If the embedding model is not ready, C2 returns the error embedder_not_ready.
4. C11 runs vector search: a dot product of the query vector against the in-memory matrix of chunk vectors (rebuilt from the database when marked dirty) returns the top 50 chunks.
5. C11 runs keyword search: an FTS5 MATCH on the sanitized query terms, ranked by bm25, returns the top 50 chunks.
6. C11 merges both lists with reciprocal rank fusion, applies the filters (extension, date range, folder hint, status indexed), keeps the best chunk per file, and keeps the top files up to the limit.
7. C11 builds each result: file id, name, extension, full path, parent folder, category, modified time, score, snippet, location, and whether a summary is cached.
8. C2 returns the results, the parsed filters, a relaxed_filters flag, and elapsed_ms. C1 shows result cards with filter chips and the Open file and Open folder buttons.

**Failure handling:** if filters produce no results, C11 retries without folder_hint, then without the date range, and sets relaxed_filters to true. If semantic_text is empty (for example only a file type and a date), C11 skips vector and keyword search and lists the matching files by newest first. An empty index returns an empty list with the reason no_indexed_files.

## 7.4 F4: View a file with its summary and history

| Item | Detail |
|---|---|
| Trigger | The user opens a search result |
| Components | C1, C2, C13, C12, C17, C9 |
| API | GET /api/files/{id}, POST /api/files/{id}/summary, GET /api/files/{id}/history |
| Tables | Reads files, chunks, summaries, events. Writes summaries. |
| Requirements | FR-14 to FR-16, FR-20 |

1. C1 calls GET /api/files/{id} for metadata and category, and GET /api/files/{id}/history for the timeline, at the same time.
2. C1 calls POST /api/files/{id}/summary.
3. C13 looks up the summaries row. If its content_hash equals files.content_hash and its model_name equals the configured model, C13 returns the cached text with cached true.
4. Otherwise C13 selects chunks within the character budget (Section 8.10), builds the prompt, and calls C12. C12 holds a global lock so only one LLM call runs at a time.
5. C13 stores the summary with the content_hash and model_name, and returns it with cached false and elapsed_ms.
6. C1 shows the summary, folder path, category, file times, and the timeline.

**Failure handling:** if Ollama is down or the call exceeds the timeout, C13 returns an extractive fallback (the first chunks, up to the configured number of characters) with fallback true, and C1 shows a notice.

## 7.5 F5: Live history tracking

| Item | Detail |
|---|---|
| Trigger | A file system event in an indexed folder while the app runs |
| Components | C15, C8, C17, C5, C6, C7, C14, C9, C11 |
| API | None for the background work. The timeline is read with GET /api/files/{id}/history. |
| Tables | Reads and writes files, chunks, events |
| Requirements | FR-18 |

1. C15 receives watchdog events for each enabled folder (recursive) and puts them on the event queue with the time received.
2. C15 ignores temporary and unsupported files and debounces per path for 1.5 seconds, so a save that fires several events becomes one.
3. C15 classifies each event and the worker thread (C8) handles the events in order.
4. Created: C8 hashes and indexes the file (F2 steps 6 and 7) and C17 writes a created event. If a deleted file with the same hash was seen in the last 5 seconds, it is treated as a move (step 6).
5. Modified: C8 computes the hash. If it equals files.content_hash, the event is ignored because only the timestamp changed. Otherwise C8 re-indexes the file, replaces its chunks, and updates content_hash, and C17 writes a modified event with hash_before and hash_after. The cached summary becomes stale because its content_hash no longer matches.
6. Moved or renamed: C17 updates files.current_path and name and writes a renamed event (same parent folder) or a moved event (different parent folder). No re-embedding is needed. If the new location is outside every indexed folder, treat it as deleted.
7. Deleted: C15 holds the deletion for 5 seconds, waiting for a created event with the same hash (some apps report a move as delete plus create). If none arrives, C17 sets files.status to deleted, deletes the file's chunks so it is no longer searchable, and writes a deleted event. The files row and its events are kept so the timeline survives.
8. After any change, C11 marks the vector cache dirty. The open detail view fetches the history again every 3 seconds (the MVP has no push updates).

**Failure handling:** a locked file is retried once after 1 second and then recorded as an error. An event for an unknown path inside an indexed folder is treated as created.

## 7.6 F6: Reconciliation (startup and rescan)

| Item | Detail |
|---|---|
| Trigger | F1 step 7, or the user clicks Rescan (POST /api/index/start with kind rescan) |
| Components | C16, C4, C8, C17, C9 |
| API | POST /api/index/start, GET /api/index/status |
| Tables | Reads and writes files, chunks, events |
| Requirements | FR-19 |

1. C16 uses C4 to walk each enabled folder and builds a map of path to size and modified time.
2. C16 compares the map with the files table (status not deleted). Same size and modified time means unchanged. Different means compute the hash.
3. A different hash is a modified file: re-index it and write a modified event. The same hash only updates the stored times.
4. Paths in the database but missing on disk are deleted candidates. Paths on disk but not in the database are created candidates.
5. C16 hashes the created candidates and matches them to deleted candidates by content_hash. A match is a moved event (parent folder changed) or a renamed event (same parent). C17 updates current_path without re-embedding.
6. Unmatched created candidates are indexed as new files with a created event. Unmatched deleted candidates are marked deleted, their chunks are removed, and a deleted event is written.
7. Every event written here uses source reconcile and occurred_at equal to the detection time. The timeline also shows the file's modified time, because the exact moment of a change made while the app was closed is unknown.

**Failure handling:** if a whole folder is missing (for example a disconnected drive), mark the folder unavailable in the interface and do not mark its files as deleted.

## 7.7 F7: Open a file or its folder

| Item | Detail |
|---|---|
| Trigger | The user clicks Open file or Open folder on a result |
| Components | C1, C2, C18, C9 |
| API | POST /api/files/{id}/open, POST /api/files/{id}/open-folder |
| Tables | Reads files, folders |
| Requirements | FR-13 |

1. C1 calls the endpoint with the file id.
2. C2 loads the files row and checks that the path is inside an enabled folder. The server never opens a path sent by the client.
3. If the file is missing on disk, C2 returns file_missing and queues a reconciliation for that folder.
4. C18 opens the file with the default application (os.startfile), or opens Explorer with the file selected.

**Failure handling:** an operating system error returns os_error with its message.

## 7.8 Demo flow

The offline demo is scripted in PRD Section 13. It uses F2, F3, F4, and F5 in that order, with Wi-Fi off.
