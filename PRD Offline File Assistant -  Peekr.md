# **Product Requirements Document: Offline File Assistant (Peekr)**

AppBuildersPH Hackathon 2026 · Theme: Local AI · Version 1.0 · October 9, 2026 · Status: Draft for team review

## **0\. Agent Guide**

This document is the single source of truth for building Peekr. It is written for an AI coding agent working with the team. Read this section first, then follow the task order in Section 12.1. If sections conflict, the order of precedence is: the hard rules below, then Section 9 (requirements), then Sections 7 and 8, then everything else.

**Product in one paragraph:** Peekr is a localhost web app (Python FastAPI backend, browser interface) that indexes documents in folders the user selects. The user searches by meaning in English, Filipino, or Taglish, and each result shows a summary on demand, the file location, a category, and a history of file events. All AI (embeddings and a small LLM through Ollama) runs on the user's laptop, and nothing is sent to the internet.

**Where to find things**

| Need | Go to |
| :---- | :---- |
| What to build and what not to build | Sections 6 and 9 (scope and FR-\* requirements) |
| How the parts fit together | Section 8.1 (diagram) and 8.2 (components C1 to C19) |
| What happens step by step | Section 7 (flows F1 to F7) |
| Exact data and interfaces | 8.3 (database), 8.8 (API), 8.9 (configuration) |
| Rules and algorithms | 8.10 and 8.11 |
| Which flow touches which component, endpoint, table, and requirement | 8.12 |
| Tech stack and models | 8.4 and 8.5 |
| How to run it | 8.6 |
| What to build first | 12.1 |
| How to prove it works | Sections 4.3 and 13 |

**ID conventions:** C\# is a component (Section 8.2), F\# is a flow (Section 7), FR-\# is a functional requirement (Section 9), T-\# is a build task (Section 12.1). API paths start with /api. Name code, tests, and commit messages after these IDs, for example a docstring that says Implements F3 step 4, FR-10.

**Hard rules for the build (never break these)**

1. Never write, move, rename, or delete a user's files. Access to indexed folders is read-only (FR-3). The app writes only inside its own data folder.  
2. Bind the server to 127.0.0.1 only (FR-24). Never 0.0.0.0.  
3. Make no outbound network calls at runtime: no telemetry, no CDN links, no cloud API (FR-22, FR-23). Bundle all frontend assets locally.  
4. Use local models only, through Ollama on 127.0.0.1:11434. Never use a :cloud model tag.  
5. Stay within the VRAM budget (Section 8.5): one LLM loaded at a time, LLM calls run one at a time, embeddings run on the CPU by default.  
6. Stay inside the MVP scope (Section 6.1). Stretch items start only after the Phase 5 exit criteria pass. Do not add video, audio, photo search, or whole-disk scanning.  
7. When a dependency, model, or major tool is added, add it to the disclosure table in Section 8.4 in the same change (hackathon rule).  
8. Report only real measurements. Never hard-code or invent benchmark numbers.  
9. A bad file must never crash indexing or the server. Catch the error, record the reason, and continue (Section 8.11).  
10. If a requirement is unclear, choose the simplest option that satisfies these rules, write the assumption in a code comment and the commit message, and flag it for the team instead of guessing silently.

**Coding conventions**

* Python 3.11 or 3.12, type hints on public functions, one module per component, layout as in Section 8.7.  
* Timestamps are stored as UTC ISO 8601 strings. File paths are stored as absolute paths normalized with pathlib.  
* Settings come from configuration (Section 8.9). Never hard-code them in modules.  
* Log to the data folder with Python logging. Log IDs, paths, and timings, never file contents.  
* Every API error returns a JSON body with error.code and error.message (Section 8.8).

**Definition of done for a task:** the code runs with the network off, meets the acceptance criteria of the FR-\* rows it covers, has at least one automated test or a scripted manual check, follows the hard rules above, and updates the disclosure table if a dependency changed.

## **1\. Product Summary**

**One-liner:** An offline AI assistant that finds documents by meaning, summarizes them without opening them, shows where they are saved, and records how they changed over time. All AI runs on the user's own laptop.

**Type:** Working prototype for the hackathon. It covers documents in folders the user selects, not the whole file manager.

**Platform:** Windows laptop, as a desktop or localhost app. Reference demo machine: RTX 2050 laptop with 4GB VRAM.

**Core promise:** It works with Wi-Fi turned off. No file content, file name, or search query leaves the device.

## **2\. Hackathon Alignment**

### **2.1 Theme and challenge**

| Hackathon asks | How this product meets it |
| :---- | :---- |
| Theme: an AI product that stays useful when the cloud disappears | Indexing, search, summaries, and history all work offline. The demo runs with Wi-Fi off. |
| A working product using AI that runs locally on the user's device | Embeddings, the language model, categorization, and OCR all run on the laptop. |
| Solve a real problem | People lose track of files and can't tell what is inside without opening them. |
| Show why local beats cloud-only | Privacy (personal, school, and work files are never uploaded), cost (no API fees), and speed (no folder uploads or network waits). |
| Any kind of product; what counts as Local AI | Fits Productivity, Personal assistants, and Privacy tools. Uses a local LLM, local embeddings and RAG, and local OCR. |

### **2.2 Rules compliance**

| Rule | How we comply |
| :---- | :---- |
| Only participants on the official list can compete | Every team member confirms they are on the official list before work starts. |
| Substantially built during the hackathon | The repository starts empty at kickoff, and the commit history is the evidence. No pre-existing project code is reused. |
| A meaningful part of AI inference runs locally; core functionality does not depend entirely on a cloud AI API | All AI inference is local, and no cloud AI API is used. |
| A working product, demonstrated | A scripted live demo with Wi-Fi off (Section 13). |
| Models, APIs, frameworks, and major tools disclosed | A disclosure list is kept from day one (Section 8.4). |
| One person, one team, one project; no outside help | Only registered members work on this single project. No outside developers and no copied project code. |
| No fake benchmarks | Only numbers measured by the team on the demo laptop are reported, with the method documented. |
| Allowed: open-source models and libraries, AI-assisted development | Used and disclosed, including which AI coding tools the team used. |

## **3\. Problem Statement**

Students and office workers collect hundreds of documents in Downloads, school folders, and chat attachments. File names such as 'Final\_v2 (1).pdf' do not describe the content, so people open files one by one to find the right one. Built-in search mostly matches names and exact words. It does not say what a document contains, where it fits, or how it changed.

**Problem statement:** People cannot quickly find a document, recall what it contains, or see how it changed, because common search tools match names and keywords instead of meaning, and cloud AI tools that could help require uploading private files.

**Gaps in current options**

* Name and keyword search misses meaning and handles Taglish phrasing poorly.  
* Checking content means opening each file.  
* There is no readable history of when a file was created, edited, moved, or renamed.  
* Cloud AI file tools need private documents (school records, IDs, payslips, contracts) uploaded to a server.

**Why local AI is the right answer**

* **Privacy:** documents never leave the device.  
* **Offline:** the product keeps working when the cloud is unavailable.  
* **Cost:** no per-use API fees, which matters for students.  
* **Speed:** no uploading of large folders and no network delay.

## **4\. Goals, Non-Goals, and Success Metrics**

### **4.1 Goals**

* G1. Find a document by describing it in natural language, including Taglish.  
* G2. Show a short summary so the user does not need to open the file.  
* G3. Show where the file is located (folder path and category).  
* G4. Show the file's history: creation, edits, moves, renames, deletion.  
* G5. Run fully offline on a 4GB VRAM laptop.

### **4.2 Non-goals (prototype)**

* Searching the whole computer or replacing the operating system's file manager.  
* Video, audio, and general photo search.  
* Mobile app, multi-user accounts, or cloud sync.  
* Moving, deleting, or renaming files on the user's behalf.

### **4.3 Success metrics (draft targets, to be confirmed after the first test run)**

| Metric | Draft target | How it is measured |
| :---- | :---- | :---- |
| Search accuracy | Correct file in the top 3 results for at least 70% of test queries | About 30 fixed queries on the demo folder, results recorded as they are |
| Search response time | Under 3 seconds after indexing | Timed on the RTX 2050 laptop |
| Summary time | Under 20 seconds for a typical document, instant when cached | Timed on the RTX 2050 laptop |
| Indexing speed | About 100 documents in under 10 minutes | Timed on the demo folder |
| Offline operation | All core features pass with the network disabled | Demo script run with Wi-Fi off |
| History correctness | Every create, edit, move, and rename in the test script is recorded | Scripted file actions checked against the timeline |

Targets are goals, not claims. Report only measured results.

## **5\. Users and Use Cases**

**Primary user:** a Filipino college student with a messy laptop, school folders, and downloaded PDFs and slides. **Secondary user:** an office or barangay staff member who handles many forms and documents.

| ID | User story |
| :---- | :---- |
| US-1 | As a student, I want to type 'yung PDF about normalization na dinownload ko last month' and get the right file, so I do not have to open many files. |
| US-2 | As a user, I want a short summary of a file, so I can decide whether to open it. |
| US-3 | As a user, I want to see which folder a file is in and its category, so I can find it again. |
| US-4 | As a user, I want to see when a file was created, edited, moved, or renamed. |
| US-5 | As a user, I want to choose which folders are indexed, so my private folders stay untouched. |
| US-6 | As a user, I want the app to work without internet, so my files stay private and the tool is always available. |

## **6\. Scope**

### **6.1 In scope (MVP)**

* User-selected folders, indexed recursively.  
* File types: PDF, DOCX, PPTX, TXT.  
* Meaning-based and keyword search with Taglish support.  
* On-demand summaries, cached.  
* Location and category display, with open file and open folder buttons.  
* File history from a folder watcher.  
* Fully offline operation with no cloud AI API.

### **6.2 Stretch (only after the MVP is stable)**

* XLSX files.  
* Images and scanned documents through OCR, indexed like any other document.  
* Short AI note on what changed between two versions of a file.  
* User-editable categories.

### **6.3 Out of scope**

* Video, audio, and general photo search.  
* Whole-disk scanning, mobile, cloud sync, multi-user.  
* Automatic file organization or deletion.

### **6.4 Assumptions and constraints**

* Primary hardware: RTX 2050 with 4GB VRAM. Plan for about 3.5GB of usable VRAM and a short context window (2k to 4k tokens).  
* Windows is the primary target.  
* Models are downloaded before the demo, so no network is needed during it.  
* History starts when a folder is first indexed. The operating system does not keep a full change history, so earlier history is limited to file timestamps.

## **7\. System Flow**

Each flow lists its trigger, the components (C\#, Section 8.2) and API endpoints (Section 8.8) involved, the tables it reads and writes (Section 8.3), numbered steps, and failure handling. Each step names the component that does the work. Section 8.12 summarizes all flows in one matrix.

### **7.1 F1: App startup and health check**

| Item | Detail |
| :---- | :---- |
| Trigger | The user runs run.bat |
| Components | C3, C9, C7, C12, C15, C16, C19, C1 |
| API | GET /api/health, GET /api/folders |
| Tables | Reads folders and settings. Creates missing tables. |
| Requirements | FR-22, FR-24, FR-25 |

1. run.bat activates the virtual environment and starts uvicorn for app.main:app on 127.0.0.1:8000.  
2. C3 loads the configuration (Section 8.9) and creates the data folder (database and logs) if it is missing.  
3. C9 opens the SQLite database, enables WAL mode and foreign keys, and creates any missing tables (Section 8.3).  
4. C19 checks that Ollama answers at the configured URL and that the configured LLM model is installed. It keeps the result in memory for the health endpoint and does not stop startup if Ollama is down.  
5. C7 loads the embedding model in a background thread. Until it finishes, embedder\_ready is false.  
6. C8 starts the index worker thread, which processes one job or event at a time from a queue.  
7. For every enabled folder, C15 starts a watcher, and C16 queues a reconciliation scan (F6).  
8. The browser opens http\://127.0.0.1:8000. C1 loads, calls GET /api/health and GET /api/folders, and shows the status of Ollama, the LLM model, the embedding model, the local-only indicator (FR-25), and the folder list.

**Failure handling:** Ollama down shows a banner, summaries use the extractive fallback (F4), and search still works. The embedding model missing blocks indexing and search with a message that points to the setup step. A busy port makes run.bat print a clear message and exit.

### **7.2 F2: Add a folder and index it**

| Item | Detail |
| :---- | :---- |
| Trigger | The user clicks Add folder |
| Components | C1, C2, C18, C9, C4, C5, C6, C7, C14, C8, C17, C15 |
| API | POST /api/folders/pick, POST /api/folders, DELETE /api/folders/{id}, POST /api/index/start, GET /api/index/status |
| Tables | Reads files. Writes folders, files, chunks, chunks\_fts, events. |
| Requirements | FR-1, FR-3 to FR-7, FR-16 |

1. C1 calls POST /api/folders/pick. C18 opens the native folder dialog on the laptop and returns the chosen path. The user may also paste a path.  
2. C1 calls POST /api/folders with the path. C2 checks that the path exists, is a directory, is not already added or nested inside an added folder, and is not a Windows system folder. C9 inserts the folders row.  
3. C1 calls POST /api/index/start with the folder id and kind initial. C8 creates a job (state queued) and returns job\_id. The worker thread picks it up.  
4. C4 walks the folder recursively and yields candidate files: supported extension, not hidden or temporary, not excluded, size at most the configured limit. Each candidate has path, size, created time, and modified time.  
5. For each candidate, C8 compares with the files table by path. New files are processed. Files with the same size and modified time are skipped as unchanged (FR-7). Files that differ are hashed and processed only if the hash changed.  
6. To process a file, C8 computes the SHA-256 hash, C5 extracts text segments with locations (page or slide), C6 splits them into chunks, C7 embeds the chunks in batches with the passage prefix, and C14 assigns a category. If C5 finds no text, the file is marked skipped with a reason.  
7. C9 writes one transaction per file: upsert the files row, delete old chunks, insert the new chunks with embeddings (triggers keep chunks\_fts in sync). C17 writes a baseline event for an initial scan, a created event for a new file in a rescan, or a modified event for changed content.  
8. After each file, C8 updates the job progress. C1 polls GET /api/index/status every second and shows processed and total counts, the current file name, and the skipped and error counts.  
9. When the job ends, C8 sets the state to done, updates folders.last\_scan\_at, marks the vector cache dirty (C11), and makes sure a watcher is running for the folder (C15).

**Failure handling:** a file that cannot be read, is password protected, has no text, or is too large is recorded with a reason code, listed in the interface, and skipped. The job continues (Section 8.11).

**Removing a folder:** C1 calls DELETE /api/folders/{id}. C15 stops the watcher for that folder, C9 deletes the folder together with its files, chunks, summaries, and events (cascade), and C11 marks the vector cache dirty. The user's files on disk are not touched.

### **7.3 F3: Search**

| Item | Detail |
| :---- | :---- |
| Trigger | The user submits a search query |
| Components | C1, C2, C10, C7, C11, C9 |
| API | POST /api/search |
| Tables | Reads chunks, chunks\_fts, files |
| Requirements | FR-9 to FR-13 |

1. C1 sends POST /api/search with the query text and a limit (default 10).  
2. C10 parses the query into semantic\_text, extensions, date\_from, date\_to, and folder\_hint (Section 8.10).  
3. C7 embeds semantic\_text with the query prefix. If the embedding model is not ready, C2 returns the error embedder\_not\_ready.  
4. C11 runs vector search: a dot product of the query vector against the in-memory matrix of chunk vectors (rebuilt from the database when marked dirty) returns the top 50 chunks.  
5. C11 runs keyword search: an FTS5 MATCH on the sanitized query terms, ranked by bm25, returns the top 50 chunks.  
6. C11 merges both lists with reciprocal rank fusion, applies the filters (extension, date range, folder hint, status indexed), keeps the best chunk per file, and keeps the top files up to the limit.  
7. C11 builds each result: file id, name, extension, full path, parent folder, category, modified time, score, snippet, location, and whether a summary is cached.  
8. C2 returns the results, the parsed filters, a relaxed\_filters flag, and elapsed\_ms. C1 shows result cards with filter chips and the Open file and Open folder buttons.

**Failure handling:** if filters produce no results, C11 retries without folder\_hint, then without the date range, and sets relaxed\_filters to true. If semantic\_text is empty (for example only a file type and a date), C11 skips vector and keyword search and lists the matching files by newest first. An empty index returns an empty list with the reason no\_indexed\_files.

### **7.4 F4: View a file with its summary and history**

| Item | Detail |
| :---- | :---- |
| Trigger | The user opens a search result |
| Components | C1, C2, C13, C12, C17, C9 |
| API | GET /api/files/{id}, POST /api/files/{id}/summary, GET /api/files/{id}/history |
| Tables | Reads files, chunks, summaries, events. Writes summaries. |
| Requirements | FR-14 to FR-16, FR-20 |

1. C1 calls GET /api/files/{id} for metadata and category, and GET /api/files/{id}/history for the timeline, at the same time.  
2. C1 calls POST /api/files/{id}/summary.  
3. C13 looks up the summaries row. If its content\_hash equals files.content\_hash and its model\_name equals the configured model, C13 returns the cached text with cached true.  
4. Otherwise C13 selects chunks within the character budget (Section 8.10), builds the prompt, and calls C12. C12 holds a global lock so only one LLM call runs at a time.  
5. C13 stores the summary with the content\_hash and model\_name, and returns it with cached false and elapsed\_ms.  
6. C1 shows the summary, folder path, category, file times, and the timeline.

**Failure handling:** if Ollama is down or the call exceeds the timeout, C13 returns an extractive fallback (the first chunks, up to the configured number of characters) with fallback true, and C1 shows a notice.

### **7.5 F5: Live history tracking**

| Item | Detail |
| :---- | :---- |
| Trigger | A file system event in an indexed folder while the app runs |
| Components | C15, C8, C17, C5, C6, C7, C14, C9, C11 |
| API | None for the background work. The timeline is read with GET /api/files/{id}/history. |
| Tables | Reads and writes files, chunks, events |
| Requirements | FR-18 |

1. C15 receives watchdog events for each enabled folder (recursive) and puts them on the event queue with the time received.  
2. C15 ignores temporary and unsupported files and debounces per path for 1.5 seconds, so a save that fires several events becomes one.  
3. C15 classifies each event and the worker thread (C8) handles the events in order.  
4. Created: C8 hashes and indexes the file (F2 steps 6 and 7\) and C17 writes a created event. If a deleted file with the same hash was seen in the last 5 seconds, it is treated as a move (step 6).  
5. Modified: C8 computes the hash. If it equals files.content\_hash, the event is ignored because only the timestamp changed. Otherwise C8 re-indexes the file, replaces its chunks, and updates content\_hash, and C17 writes a modified event with hash\_before and hash\_after. The cached summary becomes stale because its content\_hash no longer matches.  
6. Moved or renamed: C17 updates files.current\_path and name and writes a renamed event (same parent folder) or a moved event (different parent folder). No re-embedding is needed. If the new location is outside every indexed folder, treat it as deleted.  
7. Deleted: C15 holds the deletion for 5 seconds, waiting for a created event with the same hash (some apps report a move as delete plus create). If none arrives, C17 sets files.status to deleted, deletes the file's chunks so it is no longer searchable, and writes a deleted event. The files row and its events are kept so the timeline survives.  
8. After any change, C11 marks the vector cache dirty. The open detail view fetches the history again every 3 seconds (the MVP has no push updates).

**Failure handling:** a locked file is retried once after 1 second and then recorded as an error. An event for an unknown path inside an indexed folder is treated as created.

### **7.6 F6: Reconciliation (startup and rescan)**

| Item | Detail |
| :---- | :---- |
| Trigger | F1 step 7, or the user clicks Rescan (POST /api/index/start with kind rescan) |
| Components | C16, C4, C8, C17, C9 |
| API | POST /api/index/start, GET /api/index/status |
| Tables | Reads and writes files, chunks, events |
| Requirements | FR-19 |

1. C16 uses C4 to walk each enabled folder and builds a map of path to size and modified time.  
2. C16 compares the map with the files table (status not deleted). Same size and modified time means unchanged. Different means compute the hash.  
3. A different hash is a modified file: re-index it and write a modified event. The same hash only updates the stored times.  
4. Paths in the database but missing on disk are deleted candidates. Paths on disk but not in the database are created candidates.  
5. C16 hashes the created candidates and matches them to deleted candidates by content\_hash. A match is a moved event (parent folder changed) or a renamed event (same parent). C17 updates current\_path without re-embedding.  
6. Unmatched created candidates are indexed as new files with a created event. Unmatched deleted candidates are marked deleted, their chunks are removed, and a deleted event is written.  
7. Every event written here uses source reconcile and occurred\_at equal to the detection time. The timeline also shows the file's modified time, because the exact moment of a change made while the app was closed is unknown.

**Failure handling:** if a whole folder is missing (for example a disconnected drive), mark the folder unavailable in the interface and do not mark its files as deleted.

### **7.7 F7: Open a file or its folder**

| Item | Detail |
| :---- | :---- |
| Trigger | The user clicks Open file or Open folder on a result |
| Components | C1, C2, C18, C9 |
| API | POST /api/files/{id}/open, POST /api/files/{id}/open-folder |
| Tables | Reads files, folders |
| Requirements | FR-13 |

1. C1 calls the endpoint with the file id.  
2. C2 loads the files row and checks that the path is inside an enabled folder. The server never opens a path sent by the client.  
3. If the file is missing on disk, C2 returns file\_missing and queues a reconciliation for that folder.  
4. C18 opens the file with the default application (os.startfile), or opens Explorer with the file selected.

**Failure handling:** an operating system error returns os\_error with its message.

### **7.8 Demo flow**

The offline demo is scripted in Section 13\. It uses F2, F3, F4, and F5 in that order, with Wi-Fi off.

## **8\. System Architecture**

### **8.1 Overview**

PROCESS VIEW (everything runs on one laptop, nothing leaves it)

\[P1 Browser\]  http\://127.0.0.1:8000  
   C1 UI (static HTML, CSS, JS, no CDN)  
        |  JSON over HTTP (/api/\*) and static files  
        v  
\[P2 Backend\]  one Python process (uvicorn \+ FastAPI)  
   C2 API layer  
     |-- /api/search \------------\> C10 Query parser \-\> C7 Embedder \-\> C11 Hybrid search \-\> C9  
     |-- /api/files/\*/summary \---\> C13 Summary service \-\> C12 LLM client \-\> \[P3 Ollama\]  
     |-- /api/index, /api/folders \-\> C8 Indexer (job queue \+ worker thread)  
     |        C8 uses: C4 Scanner, C5 Extractors, C6 Chunker, C7 Embedder,  
     |                 C14 Category, C17 History service, C9 Database layer  
     |-- /api/files/\*/open\* \-----\> C18 OS actions  
     |-- /api/health \------------\> C19 Health checks  
   Background threads  
     C15 Watcher (watchdog) \----events----\> C8 queue  
     C16 Reconciler (startup, rescan) \----\> C8 queue  
   Shared: C3 Core (config, logging), C9 Database layer

\[Data folder\]  data/peekr.db (SQLite, WAL): folders, files, chunks, chunks\_fts,  
               summaries, events, categories, settings. Also logs/  
\[P3 Ollama\]    http\://127.0.0.1:11434, local LLM (3B to 4B, 4-bit) on the GPU,  
               called only by C12  
\[User folders\] read-only access by C4, C5, C15, C16, C18  
No component calls an external network service.

### **8.2 Components**

| ID | Component | Module | Responsibility | Depends on | Flows |
| :---- | :---- | :---- | :---- | :---- | :---- |
| C1 | UI | web/index.html, app.js, style.css | Folder management, search box, result cards, detail view with summary and timeline, indexing progress, status indicators | C2 over HTTP | F1 to F7 |
| C2 | API layer | app/api/\*.py | FastAPI routers, request validation, error format, serves the web folder | C3, C8 to C19 | F1 to F7 |
| C3 | Core | app/core/config.py, logging.py | Load configuration, resolve data folder paths, set up logging | None | All |
| C4 | Scanner | app/indexing/scanner.py | Walk folders, filter files, return path, size, created and modified times | C3 | F2, F6 |
| C5 | Extractors | app/indexing/extractors/ | Text and locations from PDF, DOCX, PPTX, TXT. Classify failures (password protected, no text, unreadable). | None | F2, F5 |
| C6 | Chunker | app/indexing/chunker.py | Split text segments into overlapping chunks that keep their page or slide location | C3 | F2, F5 |
| C7 | Embedder | app/ai/embedder.py | Load the embedding model once, embed passages and queries, return normalized float32 vectors | C3 | F2, F3, F5 |
| C8 | Indexer | app/indexing/pipeline.py | Job queue, the single worker thread, end-to-end processing of one file, progress reporting, handling watcher events | C4 to C7, C9, C14, C17 | F2, F5, F6 |
| C9 | Database layer | app/db/schema.sql, connection.py, repo.py | SQLite connections (WAL), schema creation, all queries. One writer thread. | C3 | All |
| C10 | Query parser | app/search/query\_parser.py | Extract file type, date range, and folder hint, and produce the semantic text | C3 | F3 |
| C11 | Hybrid search | app/search/hybrid.py | In-memory vector matrix, FTS5 search, rank fusion, filters, snippets | C7, C9 | F3 |
| C12 | LLM client | app/ai/llm.py | Ollama HTTP client, global lock, timeout, thinking mode off | C3 | F1, F4 |
| C13 | Summary service | app/services/summary.py | Select chunks, build the prompt, cache by content\_hash and model, extractive fallback | C9, C12 | F4 |
| C14 | Category service | app/services/category.py | Embed category labels once, assign a category by cosine similarity | C7, C9 | F2, F5 |
| C15 | Watcher | app/history/watcher.py | watchdog observers, debounce, classify events, move detection buffer | C3, C8 | F5 |
| C16 | Reconciler | app/history/reconciler.py | Compare disk with the database, find created, modified, moved, renamed, and deleted files | C4, C8, C9, C17 | F1, F6 |
| C17 | History service | app/history/events.py | Write and read events, apply path changes for moves, renames, and deletes | C9 | F2, F4, F5, F6 |
| C18 | OS actions | app/core/os\_actions.py | Native folder dialog, open a file, open a folder in Explorer | C3 | F2, F7 |
| C19 | Health checks | app/core/health.py | Ollama reachable, model installed, embedder ready, data folder writable | C3, C12 | F1 |

### **8.3 Data model**

PRAGMA journal\_mode \= WAL;  
PRAGMA foreign\_keys \= ON;  
PRAGMA busy\_timeout \= 5000;

CREATE TABLE IF NOT EXISTS folders (  
  id            INTEGER PRIMARY KEY,  
  path          TEXT NOT NULL UNIQUE,      \-- absolute path  
  enabled       INTEGER NOT NULL DEFAULT 1,  
  last\_scan\_at  TEXT,                      \-- UTC ISO 8601  
  created\_at    TEXT NOT NULL  
);

CREATE TABLE IF NOT EXISTS excluded\_paths (  
  id         INTEGER PRIMARY KEY,  
  folder\_id  INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,  
  path       TEXT NOT NULL,  
  UNIQUE (folder\_id, path)  
);

CREATE TABLE IF NOT EXISTS files (  
  id            INTEGER PRIMARY KEY,  
  folder\_id     INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,  
  current\_path  TEXT NOT NULL UNIQUE,  
  name          TEXT NOT NULL,  
  extension     TEXT NOT NULL,             \-- lowercase with dot, e.g. .pdf  
  size\_bytes    INTEGER NOT NULL,  
  created\_at    TEXT,                      \-- file system times  
  modified\_at   TEXT NOT NULL,  
  content\_hash  TEXT,                      \-- SHA-256 hex of the file bytes  
  category      TEXT,  
  status        TEXT NOT NULL,             \-- pending | indexed | skipped | error | deleted  
  status\_reason TEXT,                      \-- reason code, see Section 8.11  
  indexed\_at    TEXT  
);  
CREATE INDEX IF NOT EXISTS idx\_files\_hash   ON files(content\_hash);  
CREATE INDEX IF NOT EXISTS idx\_files\_folder ON files(folder\_id, status);

CREATE TABLE IF NOT EXISTS chunks (  
  id          INTEGER PRIMARY KEY,  
  file\_id     INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,  
  chunk\_index INTEGER NOT NULL,  
  location    TEXT,                        \-- 'page 3', 'slide 5', 'part 2'  
  text        TEXT NOT NULL,  
  embedding   BLOB NOT NULL,               \-- float32, L2-normalized  
  UNIQUE (file\_id, chunk\_index)  
);  
CREATE INDEX IF NOT EXISTS idx\_chunks\_file ON chunks(file\_id);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks\_fts USING fts5(  
  text, content='chunks', content\_rowid='id',  
  tokenize='unicode61 remove\_diacritics 2'  
);  
CREATE TRIGGER IF NOT EXISTS chunks\_ai AFTER INSERT ON chunks BEGIN  
  INSERT INTO chunks\_fts(rowid, text) VALUES (new.id, new.text);  
END;  
CREATE TRIGGER IF NOT EXISTS chunks\_ad AFTER DELETE ON chunks BEGIN  
  INSERT INTO chunks\_fts(chunks\_fts, rowid, text) VALUES ('delete', old.id, old.text);  
END;

CREATE TABLE IF NOT EXISTS summaries (  
  file\_id       INTEGER PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,  
  content\_hash  TEXT NOT NULL,             \-- hash the summary was made from  
  summary\_text  TEXT NOT NULL,  
  model\_name    TEXT NOT NULL,  
  created\_at    TEXT NOT NULL  
);

CREATE TABLE IF NOT EXISTS events (  
  id           INTEGER PRIMARY KEY,  
  file\_id      INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,  
  event\_type   TEXT NOT NULL,              \-- baseline | created | modified | moved | renamed | deleted  
  old\_path     TEXT,  
  new\_path     TEXT,  
  hash\_before  TEXT,  
  hash\_after   TEXT,  
  occurred\_at  TEXT NOT NULL,              \-- detection time, UTC  
  source       TEXT NOT NULL               \-- scan | watcher | reconcile  
);  
CREATE INDEX IF NOT EXISTS idx\_events\_file ON events(file\_id, occurred\_at);

CREATE TABLE IF NOT EXISTS categories (  
  name        TEXT PRIMARY KEY,  
  description TEXT NOT NULL,  
  embedding   BLOB                         \-- float32, normalized  
);

CREATE TABLE IF NOT EXISTS settings (  
  key   TEXT PRIMARY KEY,  
  value TEXT NOT NULL                      \-- e.g. embedding\_model, embedding\_dim, schema\_version  
);  
**Schema rules.** Removing a folder deletes its files, chunks, summaries, and events (cascade). A deleted file keeps its files row (status deleted) and its events, but loses its chunks and summary, so it is no longer searchable and its timeline survives. Embeddings are raw float32 bytes with the dimension stored in settings.embedding\_dim. If the embedding model changes, every chunk must be re-embedded. Timestamps are UTC ISO 8601 strings, and content\_hash is a SHA-256 hex string.

### **8.4 Tech stack and disclosure list**

These are the planned choices. Keep this list updated, since the rules require disclosure of models, frameworks, and major tools.

| Layer | Planned choice | Purpose | Alternative |
| :---- | :---- | :---- | :---- |
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

### **8.5 Model and VRAM budget (4GB)**

| Item | Runs on | Approximate memory |
| :---- | :---- | :---- |
| 3B to 4B LLM at 4-bit | GPU | About 2 to 3GB |
| Embedding model | CPU or GPU | Well under 1GB |
| OCR | CPU | System RAM |
| Windows and display | GPU | About 0.3 to 0.5GB |

Keep the context window at 2k to 4k tokens. Models of 7B and up are not used, because they spill into system RAM and slow the demo. Confirm these figures by measuring on the actual laptop.

### **8.6 Localhost run**

Peekr runs as a localhost app. The Python backend and the browser page run on the same laptop, and nothing is hosted online. The browser is only the screen, and all AI work happens on the laptop.

| Item | Setting |
| :---- | :---- |
| App address | http\://127.0.0.1:8000, served by FastAPI (any free port works) |
| Binding | 127.0.0.1 only, never 0.0.0.0, so other devices on the network cannot reach the app |
| LLM runtime | Ollama on http\://127.0.0.1:11434, local models only |
| Start command | run.bat starts the backend and opens the browser |
| Data location | A local data folder next to the app (SQLite index, summaries, history, logs) |
| Internet | Needed once to install libraries and download models, not needed while the app runs |

**First-time setup (once, with internet)**

1. Install the latest NVIDIA driver, Python 3.11 or 3.12, Git, and Ollama for Windows.  
2. Clone the repository and create a virtual environment.  
3. Install the dependencies from requirements.txt.  
4. Pull the chosen model with Ollama (for example ollama pull qwen3:4b) and download the embedding model.  
5. Run the app once, then turn off Wi-Fi and run it again to confirm it works offline.

**Every run (no internet needed)**

1. Make sure Ollama is running.  
2. Double-click run.bat. It activates the virtual environment and starts the server on 127.0.0.1:8000.  
3. The browser opens the app. Select folders and start indexing.  
4. To stop the app, close the console window.

**Rules for the localhost setup**

* Do not deploy the app online or expose it through a public tunnel, because that would turn it into a cloud app.  
* Keep the server bound to 127.0.0.1 (FR-24).  
* Use local model tags only, with no :cloud models.  
* Judges cannot open localhost, so prepare a backup demo video, a README with setup steps, and the repository. Run the live demo on the demo laptop.  
* Optional later: wrap the same app in a desktop window with pywebview or Tauri. The localhost backend stays the same.

### **8.7 Repository structure**

Create this layout. Each folder maps to the components in Section 8.2.

peekr/  
  run.bat                 \# check Ollama, activate venv, start uvicorn, open browser (F1)  
  requirements.txt        \# pinned versions  
  config.yaml             \# defaults, see Section 8.9  
  README.md               \# setup steps, scope, known limitations  
  app/  
    main.py               \# FastAPI app, startup and shutdown hooks (F1)  
    api/                  \# C2: health.py, folders.py, index.py, search.py, files.py  
    core/                 \# C3, C18, C19: config.py, logging.py, os\_actions.py, health.py  
    db/                   \# C9: schema.sql, connection.py, repo.py  
    indexing/             \# C4, C5, C6, C8: scanner.py, chunker.py, pipeline.py, extractors/  
      extractors/         \#   pdf.py, docx.py, pptx.py, txt.py (stretch: xlsx.py, ocr.py)  
    ai/                   \# C7, C12: embedder.py, llm.py  
    search/               \# C10, C11: query\_parser.py, hybrid.py  
    services/             \# C13, C14: summary.py, category.py  
    history/              \# C15, C16, C17: watcher.py, reconciler.py, events.py  
  web/                    \# C1: index.html, app.js, style.css (no external CDN or fonts)  
  tests/                  \# pytest, mirrors app/. demo\_data/ holds the sample files  
  data/                   \# created at runtime: peekr.db, logs/ (git-ignored)  
  docs/                   \# PRD export, disclosure list, benchmark notes  
Rules: one component per module, no circular imports, the API layer (C2) calls services and C9 repo functions, and only the database layer (C9) contains SQL.

### **8.8 API specification**

The backend (C2) serves the interface at GET / and static files from the web folder. All /api endpoints accept and return JSON. Only one indexing job runs at a time, and a second start request is queued. Errors return an HTTP 4xx or 5xx status with a body that contains error.code and error.message.

| Endpoint | Purpose | Request fields | Response fields | Flow | Requirements |
| :---- | :---- | :---- | :---- | :---- | :---- |
| GET /api/health | Status of the local stack | None | ollama\_ok, llm\_model, llm\_ready, embedder\_ready, db\_ok, local\_only (always true), ollama\_url, embedding\_model, embedding\_device | F1 | FR-22, FR-25 |
| GET /api/categories | Category labels from config | None | categories: name, description | F1 | FR-16 |
| GET /api/folders | List indexed folders | None | folders: id, path, enabled, available, last\_scan\_at, file\_count, exclusions (paths) | F2 | FR-1 |
| POST /api/folders/pick | Open the native folder dialog | None | path, or null if cancelled | F2 | FR-1 |
| POST /api/folders | Add a folder | path | folder (same fields as the list) | F2 | FR-1 |
| DELETE /api/folders/{id} | Remove a folder and everything indexed from it | None | ok | F2 | FR-1 |
| POST /api/folders/{id}/exclusions | Exclude a subfolder (Should) | path | ok | F2 | FR-2 |
| POST /api/index/start | Start an indexing or rescan job | folder\_id (optional, default all), kind (initial or rescan) | job\_id | F2, F6 | FR-4 to FR-7, FR-19 |
| GET /api/index/status | Progress of the current or last job | None | state (idle, queued, running, done, failed), total, processed, skipped, errors, current\_file, skipped\_items (path, reason) | F2 | FR-5, FR-6 |
| POST /api/search | Search the index | query, limit (default 10\), date\_from and date\_to (optional, ISO with time zone, both or neither; replace the parsed date range), ignore (optional list of extensions, date, folder; drops those parsed filters) | results (file\_id, name, extension, path, folder, category, modified\_at, score, snippet, location, summary\_cached), parsed (extensions, date\_from, date\_to, folder\_hint; the filters actually used), relaxed\_filters, reason, elapsed\_ms | F3 | FR-9 to FR-12, FR-16 |
| GET /api/files | List files by status | status (optional comma list of pending, indexed, skipped, error, deleted; default indexed) | files: id, folder\_id, name, extension, path, folder, size\_bytes, created\_at, modified\_at, category, status, status\_reason | F2, F3 | FR-5, FR-16 |
| GET /api/files/{id} | File metadata | None | id, folder\_id, name, extension, path, folder, size\_bytes, created\_at, modified\_at, category, status, status\_reason, summary\_cached | F4 | FR-16 |
| POST /api/files/{id}/summary | Get or create the summary | force (optional boolean) | summary, cached, fallback, model, elapsed\_ms | F4 | FR-14, FR-15 |
| GET /api/files/{id}/history | File timeline, newest first | None | events: event\_type, old\_path, new\_path, occurred\_at, source | F4, F5 | FR-18, FR-20 |
| GET /api/events | Recent events across all files, newest first | limit (optional, 1 to 1000, default 200\), type (optional event type) | events: id, file\_id, name, path, file\_status, event\_type, old\_path, new\_path, occurred\_at, source | F5 | FR-18, FR-20 |
| POST /api/files/{id}/open | Open with the default app | None | ok | F7 | FR-13 |
| POST /api/files/{id}/open-folder | Show the file in Explorer | None | ok | F7 | FR-13 |
| PATCH /api/files/{id}/category | Change the category (Could) | category | file metadata | None | FR-17 |

**Error codes**

| Code | HTTP | Meaning |
| :---- | :---- | :---- |
| invalid\_path | 400 | The path is missing, not a directory, a system folder, or nested in an added folder |
| already\_added | 409 | The folder is already indexed |
| folder\_not\_found | 404 | Unknown folder id |
| file\_not\_found | 404 | Unknown file id |
| file\_missing | 404 | The file is in the database but gone from disk (a reconciliation is queued) |
| forbidden\_path | 403 | The path is outside every indexed folder |
| embedder\_not\_ready | 503 | The embedding model is still loading or missing |
| llm\_unavailable | 503 | Ollama is down and no fallback is possible |
| os\_error | 500 | The operating system refused to open the file or folder |
| internal | 500 | Unexpected error, logged without file contents |

### **8.9 Configuration**

Store these defaults in config.yaml at the project root. They are starting points: tune them on the demo set and record the final values in the README.

server:  
  host: 127.0.0.1            \# must stay 127.0.0.1 (FR-24)  
  port: 8000  
data\_dir: ./data  
ollama:  
  url: http\://127.0.0.1:11434  
llm:  
  model: qwen3:4b            \# final choice after the Phase 0 tests  
  temperature: 0.2  
  num\_ctx: 4096  
  num\_predict: 250  
  timeout\_seconds: 60  
  disable\_thinking: true  
embedding:  
  model: intfloat/multilingual-e5-small  
  device: cpu  
  batch\_size: 32  
indexing:  
  supported\_extensions: \['.pdf', '.docx', '.pptx', '.txt'\]  
  max\_file\_size\_mb: 50  
  ignore\_patterns: \['\~\$\*', '\*.tmp', '\*.crdownload', '\*.part', '.\*'\]  
chunking:  
  target\_chars: 1000  
  overlap\_chars: 150  
  min\_chunk\_chars: 200  
search:  
  top\_k\_vector: 50  
  top\_k\_keyword: 50  
  rrf\_k: 60  
  default\_limit: 10  
  snippet\_chars: 240  
  query\_llm\_fallback: false  \# rules only by default, keeps search fast  
summary:  
  char\_budget: 8000          \# about 2000 tokens of document text  
  fallback\_chars: 400  
category:  
  min\_score: 0.75            \# tune in Phase 3 on the demo set  
  labels:  
    School: classes, lessons, reports, assignments, research, notes  
    Finance: receipts, bills, invoices, bank statements, budgets  
    Work: office documents, memos, proposals, project files  
    Personal: letters, resumes, personal notes, travel, family  
    Government and Forms: forms, applications, permits, certificates  
    Other: anything that does not fit the labels above  
watcher:  
  debounce\_seconds: 1.5  
  move\_window\_seconds: 5  
Rules: modules read settings only through C3. server.host must not be changed to anything other than 127.0.0.1. Values that are expected to change after testing are llm.model, category.min\_score, and the chunking sizes.

### **8.10 Core algorithms and rules**

**Text extraction (C5)**

| Type | Library | Segments and locations | Notes |
| :---- | :---- | :---- | :---- |
| PDF | pypdfium2 or pdfplumber | One segment per page, location 'page N' | A password-protected file is skipped (password\_protected). A file with no text on any page is skipped (no\_text). OCR is a stretch item. |
| DOCX | python-docx | Paragraphs and table cells grouped into parts of about 3000 characters, location 'part N' | DOCX has no reliable page numbers |
| PPTX | python-pptx | One segment per slide (titles, text boxes, tables, speaker notes), location 'slide N' | None |
| TXT | Plain read | Parts of about 3000 characters, location 'part N' | Try utf-8, then utf-8-sig, then cp1252 |

Normalize whitespace and drop empty segments.

**Chunking (C6)**

* Chunks never cross a page or slide boundary.  
* Inside a segment, split at paragraph or line breaks, then at sentences, and merge pieces up to chunking.target\_chars. Carry chunking.overlap\_chars into the next chunk.  
* A segment shorter than the target becomes one chunk. Never create an empty chunk.  
* chunk\_index starts at 0 for each file, and each chunk keeps the location of its segment.

**Embedding (C7)**

* multilingual-e5 models expect prefixes: 'passage: ' before chunk text and 'query: ' before the search query.  
* L2-normalize every vector and store it as float32 bytes. Read the vector dimension from the model at load time and save it in settings.embedding\_dim. Do not hard-code it.  
* Normalized vectors make cosine similarity equal to the dot product.  
* Run on the CPU by default, in batches of embedding.batch\_size, and truncate input to the model's maximum length.

**Query parsing (C10)**

| Clue | Examples | Result |
| :---- | :---- | :---- |
| File type | pdf, word or docx or document, ppt or pptx or slides or powerpoint, txt or text file | extensions |
| Relative date | today or ngayon, yesterday or kahapon, this week or ngayong linggo, last week or nakaraang linggo or noong isang linggo, this month or ngayong buwan, last month or nakaraang buwan or noong nakaraang buwan, last year or nakaraang taon, N days ago | date\_from and date\_to |
| Month name | January or Enero, with an optional year | date\_from and date\_to for that month |
| Folder hint | in Downloads, sa Documents, from the school folder | folder\_hint |

* semantic\_text is the query with the recognized clue words removed. If it is empty, F3 lists the matching files newest first.  
* A date filter matches a file when created\_at or modified\_at falls inside the range, because downloaded files often keep an older modified time.  
* Dates use the laptop's local time zone and are converted to UTC for comparison.  
* folder\_hint is a case-insensitive substring match against the parts of the file path.  
* Use dateparser only for explicit dates such as 12 March 2026\. Do not call the LLM unless search.query\_llm\_fallback is true.

**Search ranking (C11)**

* Keep a NumPy matrix of all chunk embeddings and a parallel array of chunk ids. Rebuild it from the database when the dirty flag is set. About 20,000 chunks of 384 float32 values is roughly 31 MB.  
* Vector list: the top search.top\_k\_vector chunks by dot product. Keyword list: the top search.top\_k\_keyword chunks from FTS5 ranked by bm25, with the query terms joined by OR and special characters escaped.  
* Reciprocal rank fusion: the score of a chunk is the sum over both lists of 1 / (rrf\_k \+ rank), with rank starting at 1\.  
* Apply the filters, then group by file. A file's score is its best chunk score. Return the top files up to the limit, each with its best chunk.  
* Snippet: the best chunk text centered on the first matched keyword if there is one, otherwise the start of the chunk, trimmed to search.snippet\_chars.  
* Only files with status indexed can appear in results.

**Summary (C13)**

* Chunk selection: take the first chunk, then chunks spread evenly across the file in file order, until summary.char\_budget characters are used.  
* System prompt: You summarize documents for a file search tool. Write 3 to 5 sentences in the same language as the document (English, Filipino, or Taglish). Use only the text provided. Do not add advice or opinions.  
* User prompt: Document name: {name}, then the selected text.  
* Call settings: llm.temperature, llm.num\_ctx, llm.num\_predict, and thinking mode off (use the Ollama think option, or the no\_think switch for Qwen3 if the option is unavailable).  
* Cache key: file\_id plus content\_hash plus model\_name. A summary is stale when the hash or the model differs.  
* Fallback: the first chunks joined and trimmed to summary.fallback\_chars, returned with fallback true.

**Category (C14)**

* At startup, embed each label as its name plus its description (with the passage prefix) and store the result in the categories table.  
* A file's vector is the normalized mean of its first 5 chunk vectors.  
* The category is the label with the highest cosine similarity. If the best score is below category.min\_score, use Other.  
* Assign the category at index time and again when the file's content changes. A user override (stretch) is kept.

**Hashing and change detection**

* SHA-256 over the file bytes in 1 MB blocks.  
* A file is unchanged when its size and modified time match the stored values. A different hash at the same path is a modification. The same hash at a different path is a move or rename.

**Event classification (C15, C16, C17)**

| Event type | When it is written | Change to the files row | Re-indexing |
| :---- | :---- | :---- | :---- |
| baseline | First scan of a newly added folder | Insert | Full |
| created | A new file appears (watcher or rescan) | Insert | Full |
| modified | The content hash changed | Update hash and times | Re-chunk and re-embed |
| moved | Same hash, parent folder changed | Update current\_path | None |
| renamed | Same hash, same folder, name changed | Update name and current\_path | None |
| deleted | File gone and no matching created event inside the move window | Status deleted, chunks removed | Remove chunks |

### **8.11 Runtime model, states, and error handling**

**Threads and shared resources**

| Resource | Rule |
| :---- | :---- |
| FastAPI request handlers | Short calls only. They read the database with their own connections and call services. They never run indexing. |
| Index worker thread (C8) | The only writer of files, chunks, and events. It handles one job or watcher event at a time, in order. |
| Watcher thread (C15) | Receives file system events and only puts them on the queue. It never touches the database. |
| LLM lock (C12) | One global lock, so only one Ollama call runs at a time and the GPU is never overloaded. |
| Embedder (C7) | Loaded once. Calls are guarded by a lock if the library is not thread-safe. |
| Vector cache (C11) | Guarded by a lock. A dirty flag is set after any change to chunks and cleared after a rebuild. |
| SQLite (C9) | WAL mode, busy\_timeout of 5000 ms, foreign keys on. Writes use short transactions. C13 writes only summaries. |

**File status**

| Status | Meaning | Searchable | Next |
| :---- | :---- | :---- | :---- |
| pending | Found and waiting to be processed | No | indexed, skipped, or error |
| indexed | Text extracted, chunks and embeddings stored | Yes | pending (when changed), deleted |
| skipped | Not indexable, with a reason code (no\_text, password\_protected, too\_large) | No | pending (when the file changes) |
| error | Processing failed, with a reason code (extract\_failed, file\_locked, internal) | No | pending (on rescan or when the file changes) |
| deleted | The file is gone from disk. The row and its events are kept. | No | pending (if the same path reappears, the row is reused) |

**Job states:** idle, queued, running, then done or failed. A job fails only on a fatal error such as the database not being writable. Errors on single files never fail a job. The state is shown by GET /api/index/status.

**Error handling**

| Situation | Reason code | Behavior |
| :---- | :---- | :---- |
| Password-protected PDF | password\_protected | Skip and list it in the interface |
| No extractable text | no\_text | Skip and list it in the interface (OCR is a stretch item) |
| File larger than the limit | too\_large | Skip |
| Corrupt or unreadable file | extract\_failed | Mark error and continue |
| File locked by another program | file\_locked | Retry once after 1 second, then mark error |
| Ollama down or timed out | llm\_unavailable | Summary falls back to extractive text and a banner is shown |
| Embedding model missing or still loading | embedder\_not\_ready | Block indexing and search with a clear message |
| Folder missing or drive disconnected | folder\_unavailable | Mark the folder unavailable. Never mark its files deleted. |
| Path outside every indexed folder | forbidden\_path | Refuse with HTTP 403 |
| Unexpected exception | internal | Log the error type and ids, mark the file error, and continue |

**Logging:** write logs to data/logs. Log events, ids, paths, and timings. Never log file text, summaries, or search queries.

### **8.12 Traceability: flows, components, endpoints, tables, and requirements**

Use this matrix to keep the architecture and the flows aligned. If you change a flow, update its row here, the component table (Section 8.2), and the API table (Section 8.8) in the same change.

| Flow | Purpose | Components | Endpoints | Tables | Requirements |
| :---- | :---- | :---- | :---- | :---- | :---- |
| F1 | App startup and health check | C1, C3, C7, C9, C12, C15, C16, C19 | GET /api/health, GET /api/categories, GET /api/folders | folders, settings | FR-22, FR-24, FR-25 |
| F2 | Add a folder and index it | C1, C2, C4, C5, C6, C7, C8, C9, C14, C15, C17, C18 | POST /api/folders/pick, POST /api/folders, DELETE /api/folders/{id}, POST /api/index/start, GET /api/index/status, GET /api/files | folders, files, chunks, chunks\_fts, events | FR-1, FR-3 to FR-7, FR-16 |
| F3 | Search | C1, C2, C7, C9, C10, C11 | POST /api/search | files, chunks, chunks\_fts | FR-9 to FR-13 |
| F4 | File detail and summary | C1, C2, C9, C12, C13, C17 | GET /api/files/{id}, POST /api/files/{id}/summary, GET /api/files/{id}/history | files, chunks, summaries, events | FR-14 to FR-16, FR-20 |
| F5 | Live history tracking | C5, C6, C7, C8, C9, C11, C14, C15, C17 | GET /api/events (the timeline is read with GET /api/files/{id}/history) | files, chunks, chunks\_fts, events | FR-18 |
| F6 | Reconciliation | C4, C8, C9, C16, C17 | POST /api/index/start (kind rescan), GET /api/index/status | files, chunks, events | FR-19 |
| F7 | Open a file or its folder | C1, C2, C9, C18 | POST /api/files/{id}/open, POST /api/files/{id}/open-folder | files, folders | FR-13 |

**Requirements that apply everywhere:** FR-3 (read-only access to user files) and FR-23 (no external requests) apply to every component and are enforced by the hard rules in Section 0\. FR-2 and FR-17 are served by the optional endpoints in Section 8.8. FR-8 and FR-21 are stretch items that extend C5 and C13.

**Alignment checks before a task is marked done**

* Every component C1 to C19 appears in at least one flow.  
* Every endpoint used by a flow exists in Section 8.8, with the same name and fields.  
* Every table written by a flow exists in Section 8.3, with the columns the flow uses.  
* Every FR-\* row in Section 9 is covered by at least one flow, endpoint, or hard rule in this matrix.

## **9\. Functional Requirements**

Priority: M \= Must, S \= Should, C \= Could.

### **9.1 Folders and indexing**

| ID | Requirement | Priority | Acceptance criteria |
| :---- | :---- | :---- | :---- |
| FR-1 | Add and remove indexed folders | M | Only added folders are scanned |
| FR-2 | Exclude subfolders | S | Excluded paths are never read |
| FR-3 | The app never modifies user files | M | No write, move, or delete calls on user files |
| FR-4 | Extract text from PDF, DOCX, PPTX, and TXT | M | Text is extracted for the demo set, failures are logged |
| FR-5 | Skip unreadable or protected files with a clear message | M | The app does not crash, and skipped files are listed |
| FR-6 | Show indexing progress | S | Progress and file count are visible |
| FR-7 | Re-index only new or changed files | M | Unchanged files are not processed again |
| FR-8 | OCR for images and scanned PDFs | C | Test scans return searchable text |

### **9.2 Search**

| ID | Requirement | Priority | Acceptance criteria |
| :---- | :---- | :---- | :---- |
| FR-9 | Search by meaning in English, Filipino, and Taglish | M | Test queries return the expected file in the top results |
| FR-10 | Combine keyword and vector search | M | Exact-term and descriptive queries both work |
| FR-11 | Understand date, file type, and folder clues | S | 'last month' and 'PDF' filter results correctly |
| FR-12 | Results show name, path, category, modified date, and snippet | M | All fields are shown |
| FR-13 | Open file and open folder buttons | M | The default app or Explorer opens the item |

### **9.3 Summary and location**

| ID | Requirement | Priority | Acceptance criteria |
| :---- | :---- | :---- | :---- |
| FR-14 | Generate a short summary on demand | M | Summary appears in the detail view without opening the file |
| FR-15 | Cache summaries and refresh them when the file changes | M | A second request is instant, and an edited file gets a new summary |
| FR-16 | Show folder path and an assigned category | M | Both appear on every result |
| FR-17 | User can change a category | C | The change is saved |

### **9.4 History**

| ID | Requirement | Priority | Acceptance criteria |
| :---- | :---- | :---- | :---- |
| FR-18 | Log create, edit, move, rename, and delete events | M | Scripted actions appear on the timeline |
| FR-19 | Reconciliation scan at startup | S | Changes made while the app was closed are detected |
| FR-20 | Per-file timeline view | M | Events appear in order with timestamps and paths |
| FR-21 | Short AI note on what changed between versions | C | A one-line change note is shown |

### **9.5 Offline and privacy**

| ID | Requirement | Priority | Acceptance criteria |
| :---- | :---- | :---- | :---- |
| FR-22 | All core features work with the network disabled | M | Full demo passes with Wi-Fi off |
| FR-23 | No telemetry and no external requests | M | A network monitor shows no outbound traffic from the app |
| FR-24 | The backend only accepts local connections | M | The service listens on 127.0.0.1 |
| FR-25 | On-screen indicator that processing is local | S | The indicator is visible in the main view |

## **10\. Non-Functional Requirements**

| Area | Requirement |
| :---- | :---- |
| Performance | Meet the draft targets in Section 4.3 on the RTX 2050 laptop. |
| Privacy | The index and caches stay on the device. No file content, file name, or query is sent anywhere. |
| Reliability | One bad file must not stop indexing. The app recovers cleanly if closed during indexing. |
| Usability | A new user can index a folder and run a search within a few minutes, with clear loading messages for slow steps. |
| Resource use | Stay within the 4GB VRAM budget and keep the laptop usable while indexing. |
| Compatibility | Windows 10 or 11 with an NVIDIA GPU, falling back to CPU if the GPU is unavailable. |
| Transparency | Results show why a file matched, through the snippet and its source location. |

## **11\. Risks and Mitigations**

| Risk | Mitigation |
| :---- | :---- |
| A small 3B model summarizes poorly or struggles with Filipino | Test two or three models early on real Taglish samples, and use short structured prompts. |
| Summaries are slow on the RTX 2050 | Generate on demand, cache, cap input size, and pre-generate for the demo set. |
| Search quality looks poor on real files | Use hybrid search, a realistic test folder, and tune with the 30-query test set. |
| History looks incomplete | State clearly that history is recorded from the first scan, and show the reconciliation scan. |
| Scope grows into images and video | Hold the MVP scope. Stretch items start only after the MVP passes its tests. |
| Looks like an existing file search tool | Lead with Taglish queries, the file timeline, and the privacy and offline proof. |
| Setup fails on demo day | Install everything in advance, test on the demo laptop, and keep a recorded backup demo. |
| Rule violation (pre-existing code, outside help, fake numbers) | Start from an empty repository, work only as the registered team, and log real measurements only. |

## **12\. Build Plan**

The hackathon schedule is not in the screenshots, so phases are listed by order and exit criteria. Add dates once the official schedule is confirmed.

| Phase | Work | Exit criteria |
| :---- | :---- | :---- |
| 0\. Setup | Confirm the team is on the official list, create the repository, install Ollama and models, test model speed on the RTX 2050 laptop, pick the final models | Models run locally and speeds are recorded |
| 1\. Indexing core | Folder selection, scanner, extractors, chunker, embeddings, SQLite storage | The demo folder is indexed offline |
| 2\. Search | Hybrid search, query parser, results view | At least 70% top-3 on the test queries, or a clear plan to improve |
| 3\. Summary and location | On-demand summaries, caching, categories, open file and folder buttons | Detail view works for every demo file |
| 4\. History | Watcher, event log, reconciliation scan, timeline view | Scripted file actions show correctly |
| 5\. Polish and proof | Offline indicator, error handling, progress messages, benchmark runs, demo script | Full demo passes with Wi-Fi off, twice in a row |
| 6\. Stretch | OCR, XLSX, change notes, category editing | Only if phase 5 is complete |
| 7\. Submission | Disclosure list, README, backup demo recording, final test | All items in Section 14 checked |

**Suggested roles (adjust to the team):** backend and indexing, search and AI models, interface and demo, and one member responsible for testing, documentation, and the disclosure list.

### **12.1 Implementation task order**

Build in this order. The Phase column matches the table above. Do not start a task until the previous task meets its done criteria.

| Task | Phase | Build | Modules | Done when | Covers |
| :---- | :---- | :---- | :---- | :---- | :---- |
| T-00 | 0 | Environment and model test | Ollama, requirements.txt | Qwen3 4B, Qwen2.5 3B, and one more model are tested on 10 Taglish samples. Speeds and VRAM use are recorded and the final models are chosen. | Section 15 |
| T-01 | 1 | Skeleton, configuration, health | main.py, core/config.py, core/logging.py, core/health.py, api/health.py, run.bat | run.bat starts the app on 127.0.0.1 and GET /api/health works with Ollama stopped. FastAPI's default /docs and /redoc pages are disabled because they load assets from a CDN. | FR-24, FR-25 |
| T-02 | 1 | Database | db/ | The schema from Section 8.3 is created on startup and the repo functions have tests | Section 8.3 |
| T-03 | 1 | Scanner and extractors | indexing/scanner.py, indexing/extractors/ | The demo folder returns text with locations, and bad files return reason codes | FR-4, FR-5 |
| T-04 | 1 | Chunker and embedder | indexing/chunker.py, ai/embedder.py | Chunks follow Section 8.10, embeddings are stored, and embedding speed is recorded | FR-4 |
| T-05 | 1 | Indexer, folder API, job API | indexing/pipeline.py, api/folders.py, api/index.py | The demo folder is indexed offline with progress, and a re-run skips unchanged files | FR-1, FR-3, FR-6, FR-7 |
| T-06 | 2 | Query parser and hybrid search | search/, api/search.py | The 30-query test set runs and the top-3 rate is recorded. Date, file type, and folder clues work. | FR-9 to FR-12 |
| T-07 | 2 | OS actions and file endpoints | core/os\_actions.py, api/files.py | Open file and open folder work, and the path check is enforced | FR-13 |
| T-08 | 2 | Interface: folders, search, results | web/ | F2 and F3 work in the browser with no external requests | FR-12, FR-13 |
| T-09 | 3 | LLM client, summary, category | ai/llm.py, services/summary.py, services/category.py | A summary appears and is cached, becomes stale after an edit, and falls back with Ollama stopped. Categories are assigned. | FR-14 to FR-16 |
| T-10 | 4 | History: events, watcher, reconciler | history/ | Scripted create, edit, move, rename, and delete appear on the timeline. Changes made while the app was closed are found. | FR-18, FR-19 |
| T-11 | 4 | Detail view and timeline | web/ | The detail view shows summary, path, category, and timeline | FR-20, FR-25 |
| T-12 | 5 | Hardening and proof | All | Every case in Section 8.11 is handled, the demo script passes twice with Wi-Fi off, a network monitor shows no outbound traffic, and benchmarks are recorded | FR-22, FR-23 |
| T-13 | 6 | Stretch | indexing/extractors/ocr.py, xlsx.py, category edit, change notes | Only after T-12 is done | FR-8, FR-17, FR-21 |
| T-14 | 7 | Submission | README.md, docs/ | The Section 14 checklist is complete and a backup demo is recorded | Section 14 |

**Rules for every task**

* Test T-01 to T-07 through pytest and curl before the interface exists.  
* After each task, run the tests and the offline check (Wi-Fi off), and confirm earlier tasks still work.  
* Update the disclosure table in Section 8.4 whenever a dependency, model, or tool is added.  
* Record real measurements in docs/benchmarks.md with the hardware and settings used. Never invent numbers.  
* Keep commits small and name them after the task and requirement IDs, for example T-06: hybrid search (FR-9, FR-10).

## **13\. Test and Demo Plan**

**Demo dataset:** 50 to 100 realistic files across School, Finance, and Personal categories, including similar-looking files, files with unhelpful names, and a few Taglish documents. Use fake or sample data only, never real IDs or personal records.

**Test set:** about 30 queries written before tuning, with the expected file for each. Record the top-3 results and report them unedited.

**Demo script**

1. State the problem and the 'why local' argument in the first 10 seconds.  
2. Turn Wi-Fi off on screen.  
3. Index the demo folder and show the progress.  
4. Ask two or three Taglish questions, including one with a date clue.  
5. Open a result to show the summary, folder path, category, and timeline.  
6. Edit, rename, and move a file live, and show the timeline update.  
7. Show the network monitor with no outbound traffic, then state what is built and what is future work, such as photos and video.

**Benchmark method:** Run each measurement at least three times on the demo laptop, note the model and settings used, and write down the hardware.

## **14\. Submission Checklist**

* All team members confirmed on the official list.  
* Repository history shows work started at the hackathon.  
* Disclosure list complete: models, frameworks, libraries, major tools, and AI coding assistants used.  
* No cloud AI API in the core features.  
* Working demo shown with Wi-Fi off.  
* Benchmarks are real, with the method and hardware written down.  
* README with setup steps, scope, and known limitations.  
* Backup demo recording ready.

## **15\. Open Items**

* Confirm the official schedule, deadlines, and submission format from the event page.  
* Confirm the judging criteria and their weights.  
* Final product name.  
* Final choice of language model and embedding model after testing on the RTX 2050 laptop.  
* Team roles and who owns each phase.  
* Desktop window or localhost browser app for the final demo.