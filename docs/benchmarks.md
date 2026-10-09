# Benchmarks

Real measurements only. These runs were on a **development laptop, not the RTX 2050 reference laptop**, so they do not show reference-hardware speed. Re-run on the demo laptop.

**Dev hardware:** Intel Core i3-1215U, 15.7 GB RAM, Intel UHD Graphics (no NVIDIA GPU, so Ollama runs on the CPU), Windows 11 Home, Python 3.12.10, Ollama 0.40.2.

## T-00 LLM model test (2026-10-09)

Method: `python scripts/bench_llm.py qwen3:4b qwen2.5:3b` runs 10 short Taglish samples once per model. It uses the summary system prompt (Section 8.10), `think: false`, temperature 0.2, num_ctx 4096 and num_predict 250. Wall time is per request and includes the model load on the first call. Raw output is in `data/bench_llm.json` (git-ignored). Each model was run 1 time, not 3, so these are preliminary numbers.

| Hardware | Model | Settings | Method | Runs | Result |
|---|---|---|---|---|---|
| i3-1215U, CPU only | qwen3:4b (Q4_K_M, 3.2 GB loaded, 100% CPU) | think false, ctx 4096, predict 250 | 10 Taglish samples | 1 | First call 48.5 s, warm median 40.5 s, median 6.9 tok/s. **No usable summary.** See note. |
| i3-1215U, CPU only | qwen2.5:3b (2.2 GB loaded, 100% CPU) | think false, ctx 4096, predict 250 | 10 Taglish samples | 1 | First call 15.6 s, warm median 10.6 s, median 10.1 tok/s. 53-90 output tokens. |

**Findings**

- The current Ollama `qwen3:4b` tag is the thinking-only Qwen3-4B-2507 build (262k context, thinking on by default). Neither `think: false` nor the `/no_think` switch turns its reasoning off. All 10 outputs were reasoning text cut off at 250 tokens, with no summary. This model cannot be used with the current config. A non-thinking instruct build (for example a Qwen3 4B Instruct 2507 tag) has not been tested yet.
- qwen2.5:3b produced 3-5 sentence summaries. Quality problems seen: 5 of 10 Taglish samples were answered in English instead of the source language, and the recipe summary had made-up details (fish sauce, lemongrass, grilling).
- VRAM was not measured, because this machine has no NVIDIA GPU (no nvidia-smi).
- Interim choice (flagged): `llm.model: qwen2.5:3b` in config.yaml. The team should make the final choice on the reference laptop.

## T-04 / T-06 embedding, indexing and search (2026-10-09)

Method: `python scripts/eval_search.py --runs 3`. It builds the fake demo set with `tests/make_demo_data.py` (54 documents plus 5 bad files; temp/hidden/unsupported files are ignored), indexes it into a fresh database 3 times, and runs the 30 fixed queries from `QUERIES` in that file. Offline mode, embeddings on the CPU, default config.

| Hardware | Model | Settings | Method | Run 1-3 | Result |
|---|---|---|---|---|---|
| i3-1215U, CPU | multilingual-e5-small (dim 384) | batch 32, cpu | Load model once | 13.3 s (1 run) | Model load 13.3 s |
| i3-1215U, CPU | multilingual-e5-small | batch 32, cpu | Embed 256 passages of about 1000 chars | 13.4, 12.9, 13.6 passages/s | About 13 passages/s |
| i3-1215U, CPU | multilingual-e5-small | default chunking | Index the 59-file demo set from scratch | 4.9, 4.7, 5.2 s | About 5 s for 59 files (most files are 1 chunk) |
| i3-1215U, CPU | multilingual-e5-small | top_k 50/50, rrf_k 60 | 30 fixed queries, top-3 | 1 run | **28/30 = 93%**. Search latency median 33 ms, max 46 ms |

Misses (unedited): `bakuna ng aso` (expected vet_vaccination_schedule.pdf, whose text is in English), `kailan magpapalit ng langis ang kotse` (expected untitled.txt, whose text says "change oil").

Caveat: the same agent wrote the queries and the demo documents, before any tuning, so the rate is likely optimistic. The team should write an independent query set.

Category assignment at `category.min_score: 0.75` on the demo set gave: Personal 19, Finance 14, Work 10, Other 5, Government and Forms 3, School 3. Many School documents were labeled Personal or Work, so the labels or threshold need tuning in Phase 3.
