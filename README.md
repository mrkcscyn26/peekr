# 1. Peekr

An offline AI assistant that finds documents by meaning, summarizes them without opening them, shows where they are saved, and records how they changed over time.

**Core promise:** Peekr works with Wi-Fi off. Nothing leaves the device.

## 2. Why local AI

Documents stay private on the laptop. Local models avoid per-use API fees. Search and summaries do not wait for folders to upload or for a network response.

## 3. What it does

The MVP indexes folders selected by the user and supports PDF, DOCX, PPTX, and TXT. It searches by meaning and keywords, including Taglish queries. It provides on-demand cached summaries, file locations and categories, buttons to open a file or its folder, and a history timeline. Core features work fully offline.

## 4. Not included

Stretch items, only after the MVP is stable, are XLSX, OCR for images and scanned documents, change notes, and editable categories. Video, audio, and general photo search, whole-disk scanning, mobile, cloud sync, multi-user accounts, and automatic file organization or deletion are out of scope.

## 5. Requirements

- Windows 10 or 11 with an NVIDIA GPU and its driver.
- Python 3.11 or 3.12.
- Git and Ollama for Windows.
- Reference machine: an RTX 2050 laptop with 4GB VRAM.

## 6. First-time setup

With internet access, set up once:

1. Install the latest NVIDIA driver, Python 3.11 or 3.12, Git, and Ollama for Windows.
2. Clone this repository and create a virtual environment.
3. Install the dependencies from `requirements.txt`.
4. Pull the chosen local Ollama model and download the embedding model.
5. Run the app once, then turn off Wi-Fi and run it again to confirm offline operation.

## 7. Run

Every run, without internet:

1. Make sure Ollama is running.
2. Double-click `run.bat`.
3. The browser opens the app. Select folders and start indexing.
4. Close the console window to stop the app.

The address is [http://127.0.0.1:8000](http://127.0.0.1:8000). The server binds to `127.0.0.1` only and never to `0.0.0.0`.

## 8. Verify offline

Turn Wi-Fi off, start the app again, then follow the offline demo flow from PRD Section 13: index the demo folder, try Taglish searches including a date clue, inspect a summary and timeline, and verify file changes appear in history. The demo uses fake or sample data only. The demo script and sample files are future work; they are not part of this scaffold.

## 9. Tech stack

| Layer | Choice |
|---|---|
| Language model | Local 3B to 4B instruct model through Ollama |
| Embeddings | multilingual-e5-small with sentence-transformers |
| Backend | Python, FastAPI, and Uvicorn |
| Text extraction | pypdfium2, python-docx, python-pptx, and plain TXT reads |
| Keyword search | SQLite FTS5 |
| Vector search | NumPy cosine similarity |
| Database | SQLite |
| File watching | watchdog |
| Query clues | dateparser and a hand-written Filipino phrase map |
| Frontend | HTML, CSS, and JavaScript served by FastAPI |
| Tests | pytest |

See [docs/disclosure.md](docs/disclosure.md) for the planned tools, models, license fields, and the AI coding tools used by the team.

## 10. Repository structure

This is one Git monorepo. The backend (`app/`) and browser UI (`web/`) are side by side.

```text
peekr/
  README.md
  run.bat
  requirements.txt
  config.yaml
  .gitignore
  app/                    # C2
    __init__.py
    main.py
    api/                    # C2
      __init__.py
      health.py
      folders.py
      index.py
      search.py
      files.py
    core/                   # C3, C18, C19
      __init__.py
      config.py
      logging.py
      os_actions.py
      health.py
    db/                     # C9
      __init__.py
      schema.sql
      connection.py
      repo.py
    indexing/               # C4, C5, C6, C8
      __init__.py
      scanner.py
      chunker.py
      pipeline.py
      extractors/           # C5
        __init__.py
        pdf.py
        docx.py
        pptx.py
        txt.py
    ai/                     # C7, C12
      __init__.py
      embedder.py
      llm.py
    search/                 # C10, C11
      __init__.py
      query_parser.py
      hybrid.py
    services/               # C13, C14
      __init__.py
      summary.py
      category.py
    history/                # C15, C16, C17
      __init__.py
      watcher.py
      reconciler.py
      events.py
  web/                      # C1
    index.html
    app.js
    style.css
  tests/                  # mirrors app/
    api/                  # C2
    core/                 # C3, C18, C19
    db/                   # C9
    indexing/             # C4, C5, C6, C8
    ai/                   # C7, C12
    search/               # C10, C11
    services/             # C13, C14
    history/              # C15, C16, C17
    demo_data/              # .gitkeep only; fake data comes later
  docs/
    prd.md
    architecture-and-flow.md
    disclosure.md
    benchmarks.md
```

Use Python 3.11 or 3.12, add type hints to public functions, keep one module per component, and avoid circular imports. Only the database layer (C9) contains SQL. The API layer (C2) calls services and database repository functions.

## 11. How it works

The browser UI (C1) talks to the local FastAPI backend (C2). The backend routes folder and indexing work through the scanner, extractors, chunker, embedder, indexer, category service, history service, and database. Search combines semantic and keyword results. Summary requests use the local Ollama model. Watcher and reconciliation events feed the indexer. User folders are read-only.

See [docs/architecture-and-flow.md](docs/architecture-and-flow.md) for components C1-C19, flows F1-F7, the API, and the data model.

## 12. Configuration

Defaults are in [config.yaml](config.yaml). `server.host` must remain `127.0.0.1`. These values are expected to be reviewed after testing:

| Setting | Final value |
|---|---|
| `llm.model` | TBD |
| `category.min_score` | TBD |
| Chunking sizes (`target_chars`, `overlap_chars`, `min_chunk_chars`) | TBD |

## 13. Testing and benchmarks

Run the tests with `python -m pytest`. The tests in this scaffold are placeholders.

All benchmark numbers must be measured by the team on the demo laptop. Record the method and hardware in [docs/benchmarks.md](docs/benchmarks.md); no results have been measured for this scaffold.

The following are **targets, not results**, from PRD Section 4.3:

- Search accuracy: correct file in the top 3 for at least 70% of about 30 fixed queries.
- Search response time: under 3 seconds after indexing.
- Summary time: under 20 seconds for a typical document; instant when cached.
- Indexing speed: about 100 documents in under 10 minutes.
- Offline operation: all core features pass with the network disabled.
- History correctness: scripted create, edit, move, and rename actions all appear in the timeline.

## 14. Known limitations

- History starts at the first scan of a folder; earlier history is limited to file timestamps.
- Small 3B-4B models may summarize Filipino imperfectly.
- The first summary can be slow on a 4GB GPU.
- Windows is the primary target.
- Judges cannot open a localhost app. A backup demo is needed.

## 15. Hackathon compliance

The PRD states that the repository started at kickoff. No cloud AI API or telemetry is used, and the app makes no external requests at runtime. Only registered team members should work on the project. Models, libraries, frameworks, and major tools belong in the [disclosure list](docs/disclosure.md).

## 16. Build status

All tasks are unchecked. Build order and completion criteria are in PRD Section 12.1.

- [ ] T-00 Environment and model test
- [ ] T-01 Skeleton, configuration, health
- [ ] T-02 Database
- [ ] T-03 Scanner and extractors
- [ ] T-04 Chunker and embedder
- [ ] T-05 Indexer, folder API, job API
- [ ] T-06 Query parser and hybrid search
- [ ] T-07 OS actions and file endpoints
- [ ] T-08 Interface: folders, search, results
- [ ] T-09 LLM client, summary, category
- [ ] T-10 History: events, watcher, reconciler
- [ ] T-11 Detail view and timeline
- [ ] T-12 Hardening and proof
- [ ] T-13 Stretch
- [ ] T-14 Submission

## 17. Team and demo

- Backend and indexing: TBD
- Search and AI models: TBD
- Interface and demo: TBD
- Testing, documentation, and disclosure: TBD
- Backup demo link: TBD

The roles are suggested in the PRD and remain open for the team to assign.
