# Disclosure list

Planned choices are from PRD Section 8.4. License values are marked TBD where the source documents do not specify them. The team should complete them as choices are finalized.

| Layer | Planned choice | Purpose | Alternative | License |
|---|---|---|---|---|
| Language model | 3B to 4B instruct model, 4-bit; primary candidates: Qwen3 4B (thinking mode off) and Qwen2.5 3B | Summaries, plus a fallback for query parsing | Gemma 4 E2B or E4B, Llama 3.2 3B, Phi-4-mini | TBD |
| LLM runtime | Ollama, local models only, cloud features off | Runs the model on the GPU and offers a local API | llama.cpp | TBD |
| Embeddings | multilingual-e5-small with sentence-transformers | Meaning-based search in English and Filipino, can run on the CPU | bge-small | TBD |
| Backend | Python 3.11 or 3.12 with FastAPI and Uvicorn | Local API and the indexing and search pipelines | Flask | TBD |
| Text extraction | pypdfium2 or pdfplumber for PDF, python-docx, python-pptx, plain read for TXT | Pull out text and metadata | PyMuPDF (AGPL license, check first), openpyxl for XLSX (stretch) | TBD |
| Keyword search | SQLite FTS5 | Exact words and names | None | TBD |
| Vector search | NumPy cosine similarity over stored vectors | Simple, no extension to install, enough for a few thousand chunks | sqlite-vec or LanceDB | TBD |
| Database | SQLite through Python's sqlite3 | Files, chunks, summaries, events, and settings | None | TBD |
| File watching | watchdog with a short debounce | Live history events, ignoring temporary saves | Periodic rescan | TBD |
| Query clues | dateparser plus a small hand-written Filipino phrase map | Dates like last month or kahapon, with the LLM returning JSON as a fallback | LLM only | TBD |
| Hashing | hashlib SHA-256 (standard library) | Detect changes and match moved files | None | Standard library |
| OCR (stretch) | Tesseract or RapidOCR | Text from scans and images | PaddleOCR | TBD |
| Frontend | HTML, CSS, and JavaScript served by FastAPI | Search page, results, detail view, timeline | React with Vite | TBD |
| Native actions | tkinter folder dialog, os.startfile, Windows Explorer | Pick folders and open files or folders from the backend | Paste a folder path | Standard library |
| Run and packaging | Python virtual environment, requirements.txt, run.bat | Repeatable local start | uv | TBD |
| Testing and measuring | pytest, a timing script, nvidia-smi, Windows Resource Monitor | Check features, record real speeds, show no network traffic | Wireshark | TBD |
| Version control | Git and GitHub | Commit history shows the work started at the hackathon | None | TBD |
| Development tools | AI coding assistants as allowed by the rules, logged by the team | Faster development | None | TBD |

## Added during the backend build (T-00 to T-10)

| Item | Version | Purpose | License |
|---|---|---|---|
| qwen2.5:3b (Ollama) | tag 357c53fb659c | Interim summary model (T-00) | TBD (check the Qwen2.5 3B license) |
| qwen3:4b (Ollama) | tag 359d7dd4bcda | Tested in T-00, not used: thinking-only build | Apache 2.0 (from `ollama show`) |
| intfloat/multilingual-e5-small | HF cache | Embeddings | MIT (per model card, verify) |
| PyYAML | 6.0.3 | Reads config.yaml (C3) | MIT |
| httpx | 0.28.1 | Local Ollama client (C12), FastAPI TestClient | BSD-3-Clause |
| torch (CPU build) | 2.14.1 | Runtime for sentence-transformers | BSD-3-Clause |
| reportlab | 5.0.1 | Dev only: writes the fake demo PDFs | BSD |
| pytest | 9.1.1 | Tests | MIT |

Pinned versions are in requirements.txt. The PRD names pypdfium2 and pdfplumber as PDF alternatives; pypdfium2 is used.

## Team disclosures

- AI coding tool used for the scaffold: Copilot SDK in VS Code.
- AI coding tool used for the backend build (T-00 to T-10): Devin (Cognition), model Claude Opus.
- Final model choices and their licenses: TBD.
- Final library and framework license details: TBD.
