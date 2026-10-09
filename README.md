# Peekr

**Peek inside any file without opening it.**

Peekr is an offline AI file assistant for Windows. Describe a document in English, Filipino, or Taglish and Peekr finds it, summarizes it, shows where it is saved, and tracks how it changed. All AI runs on your own laptop. Built for the AppBuildersPH Hackathon 2026 (Theme: Local AI).

- **Demo video:** [PASTE X / LINKEDIN VIDEO URL]
- **Team Triple-M:** Mark Allen Cascayan, Eugene Mariano, Meynard Mosquito, Jessah Quinal
- **Repository:** https://github.com/mrkcscyn26/peekr

---

## Problem

People collect hundreds of files with names like `Final_v2 (1).pdf`. Built-in search matches names and exact words, not meaning, so people open files one by one to find the right one. Cloud AI tools could help, but they require uploading private files such as school records, payslips, and contracts.

## Why does this product benefit from running AI locally?

- **Privacy:** file contents, file names, and search queries never leave the laptop.
- **Offline:** every core feature works with Wi-Fi turned off.
- **Cost:** no per-use API fees, which matters for students.
- **Latency:** no uploading of folders and no waiting on a network.
- **Local AI is the product:** local embeddings power meaning-based search (including Taglish), and a local LLM writes the summaries. Without them, Peekr would be only a filename and keyword search.

## What runs where

| Runs locally (no internet) | Needs internet |
|---|---|
| Embeddings, LLM summaries (Ollama), hybrid search, categories, file watcher and history, web UI (served on 127.0.0.1 only) | One-time setup only: `pip install`, `ollama pull`, embedding model download |

No cloud AI API. No telemetry. The server binds to `127.0.0.1` only. Hardware use: the LLM runs on the GPU and embeddings run on the CPU.

## Features

- **Search by meaning and keywords**, with date, file type, and folder clues, for example "yung PDF about normalization na dinownload ko last month"
- **On-demand summaries**, cached, with a plain-text fallback if Ollama is unavailable
- **Location and category** for every file, with Open file and Open folder buttons
- **History timeline:** created, edited, moved, renamed, and deleted events, tracked live by a folder watcher and by a rescan on startup
- **Folder management:** choose which folders are indexed, see indexing progress, skipped files, and errors
- Supports **PDF, DOCX, PPTX, and TXT**. Your files are read-only and never modified.

## Run it (to recreate)

Requirements: Windows 10 or 11, Python 3.11 or 3.12, Git, and [Ollama](https://ollama.com). An NVIDIA GPU is recommended (reference machine: RTX 2050, 4 GB VRAM); the app falls back to CPU.

1. Clone and enter the repo:
   ```
   git clone https://github.com/mrkcscyn26/peekr
   cd peekr
   ```
2. Create a virtual environment and install dependencies:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Pull the local model: `ollama pull qwen2.5:3b`
4. Download the embedding model: `python -m app.ai.embedder --download`
5. Make sure Ollama is running, then double-click `run.bat`.
6. Open http://127.0.0.1:8000, click **Add folder**, wait for indexing to finish, and search.

To verify offline operation, turn Wi-Fi off after step 4 and run the app again.

Sample data: `python tests/make_demo_data.py` generates fake demo files. Tests: `python -m pytest` (tests block outbound sockets, so any hidden network call fails the run).

## Tech

- **Models:** `qwen2.5:3b` via Ollama (summaries), `intfloat/multilingual-e5-small` (embeddings)
- **Stack:** Python, FastAPI, Uvicorn, SQLite (FTS5), NumPy, sentence-transformers, PyTorch (CPU), pypdfium2, python-docx, python-pptx, watchdog, dateparser, PyYAML, httpx, pytest, plain HTML/CSS/JavaScript
- Full list, versions, and licenses: [docs/disclosure.md](docs/disclosure.md)
- Architecture, flows, and API: [docs/architecture-and-flow.md](docs/architecture-and-flow.md)
- Product requirements: [docs/prd.md](docs/prd.md)

## Tested on

MSI Cyborg 15: Intel Core i5 (12th gen), NVIDIA RTX 2050 (4 GB VRAM), 16 GB DDR5 RAM, Windows.

Benchmarks: [docs/benchmarks.md](docs/benchmarks.md). Only numbers we measured ourselves are reported.

## Known limitations

- History starts when a folder is first indexed; earlier history is limited to file timestamps.
- Category labels are approximate (the category threshold is not fully tuned).
- 3B models may summarize Filipino imperfectly, and the first summary can be slow on a 4 GB GPU.
- Windows only. No OCR, XLSX, images, audio, or video yet.

## How it was built

The repository was created at the start of the hackathon. **Devin (Cognition, model: Claude Opus) was used as our full-stack development tool**, building both the backend (FastAPI, indexing, search, history) and the browser UI, committed through one shared GitHub account, so the commit count is low. The initial scaffold used Copilot in VS Code. Team Triple-M wrote the PRD, directed and reviewed the work, tested the app, and prepared the demo. No cloud AI API and no pre-existing project code were used.

## Hackathon compliance

- Core AI (embeddings and LLM) runs locally; no cloud AI API.
- No telemetry and no external requests at runtime.
- Models, libraries, frameworks, and AI development tools are disclosed in [docs/disclosure.md](docs/disclosure.md).
