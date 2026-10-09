"""T-00 model test: time local Ollama models on 10 Taglish samples.

Usage: python scripts/bench_llm.py qwen3:4b qwen2.5:3b [--runs 1] [--out data/bench_llm.json]

Only calls the local Ollama server on 127.0.0.1. Prints per-sample timings
and the generated summaries so the team can judge quality by hand.
Assumption (flagged): this script lives in scripts/, which is not in PRD 8.7;
it is a dev tool, not part of the app.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

import httpx

OLLAMA = "http://127.0.0.1:11434"
SYSTEM = (
    "You summarize documents for a file search tool. Write 3 to 5 sentences in the same "
    "language as the document (English, Filipino, or Taglish). Use only the text provided. "
    "Do not add advice or opinions."
)

SAMPLES = [
    ("Group project notes", "Meeting namin kahapon para sa research paper sa Biology. Napagkasunduan na si Ana ang gagawa ng introduction at si Ben naman ang sa methodology. Deadline ng first draft ay sa Biyernes. Kailangan pa namin ng tatlong sources tungkol sa mangrove ecosystems sa Bataan. Mag-meet ulit kami sa library sa Lunes ng 3pm."),
    ("Electric bill March", "Meralco billing statement para sa buwan ng Marso. Total amount due: PHP 3,482.50. Due date ay April 15. Mas mataas ito ng 18% kumpara sa nakaraang buwan dahil sa paggamit ng aircon. Pwedeng magbayad sa GCash, Bayad Center, o sa mismong Meralco office."),
    ("Barangay clearance requirements", "Para makakuha ng barangay clearance, magdala ng valid ID at proof of residency like a utility bill. Ang processing fee ay PHP 100. Bukas ang barangay hall mula 8am hanggang 5pm, Monday to Friday. Ang clearance ay valid for six months at kailangan ito sa job application."),
    ("Thesis defense reminders", "Reminder sa lahat ng graduating students: ang thesis defense schedule ay naka-post na sa bulletin board. Each group has 20 minutes for the presentation at 10 minutes for Q&A. Magdala ng tatlong printed copies ng manuscript para sa panel. Bawal ang late, dapat nandoon kayo 30 minutes before your slot."),
    ("Budget plan para sa Disyembre", "Ang monthly budget ko for December: rent PHP 8,000, food PHP 6,000, transportation PHP 2,000, at load PHP 500. Naglaan din ako ng PHP 3,000 para sa Noche Buena at mga regalo. Target kong mag-ipon ng at least PHP 2,500 ngayong buwan kahit maraming gastos sa Pasko."),
    ("Letter to Lola", "Mahal kong Lola, kumusta na po kayo diyan sa probinsya? Okay naman po kami dito sa Manila, busy lang sa school at work. Uuwi po kami sa Holy Week para bisitahin kayo. Si Mama po ay nagpapadala ng mga gamot ninyo next week. Ingat po kayo palagi at huwag kalimutang uminom ng tubig."),
    ("Company memo work from home", "To all employees: simula next month, ang work from home policy ay magiging hybrid na. Kailangan pumasok sa office every Tuesday and Thursday. Ang ibang araw ay pwedeng remote basta naka-online sa Teams from 9am to 6pm. Please coordinate with your team lead para sa schedule ng desk reservations."),
    ("Resume ni Juan", "Juan Dela Cruz, fresh graduate ng BS Information Technology. May internship experience sa isang software company kung saan gumawa ako ng inventory system gamit ang Python at MySQL. Marunong din ako sa HTML, CSS, at JavaScript. Naghahanap ako ng entry-level na trabaho bilang web developer sa Metro Manila."),
    ("Recipe adobong manok", "Para sa adobong manok, kailangan mo ng isang kilong manok, kalahating tasa ng toyo, isang third cup ng suka, bawang, paminta, at dahon ng laurel. I-marinate ang manok ng 30 minutes. Pakuluan sa mahinang apoy hanggang lumambot, mga 40 minutes. Huwag haluin agad pagkalagay ng suka para hindi maging maasim."),
    ("Travel itinerary Baguio", "Day 1: alis ng Manila 5am, dating sa Baguio mga 11am, check-in sa hotel malapit sa Session Road. Day 2: punta sa Burnham Park, Mines View, at Good Shepherd para sa ube jam pasalubong. Day 3: strawberry farm sa La Trinidad bago umuwi. Estimated budget per person ay PHP 7,000 kasama na ang bus fare."),
]


def ollama_ps() -> str:
    try:
        return subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception as exc:  # noqa: BLE001
        return f"ollama ps failed: {exc}"


def run_one(client: httpx.Client, model: str, name: str, text: str) -> dict:
    body = {
        "model": model,
        "stream": False,
        "think": False,
        "keep_alive": "5m",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Document name: {name}\n\n{text}"},
        ],
        "options": {"temperature": 0.2, "num_ctx": 4096, "num_predict": 250},
    }
    t0 = time.perf_counter()
    r = client.post(f"{OLLAMA}/api/chat", json=body)
    wall = time.perf_counter() - t0
    r.raise_for_status()
    d = r.json()
    eval_s = d.get("eval_duration", 0) / 1e9
    return {
        "sample": name,
        "wall_s": round(wall, 2),
        "load_s": round(d.get("load_duration", 0) / 1e9, 2),
        "prompt_tokens": d.get("prompt_eval_count"),
        "output_tokens": d.get("eval_count"),
        "tokens_per_s": round(d.get("eval_count", 0) / eval_s, 2) if eval_s else None,
        "summary": d["message"]["content"].strip(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="+")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--out", default="data/bench_llm.json")
    args = ap.parse_args()
    results: dict[str, dict] = {}
    with httpx.Client(timeout=600) as client:
        for model in args.models:
            rows = []
            for run in range(args.runs):
                for name, text in SAMPLES:
                    row = run_one(client, model, name, text)
                    row["run"] = run + 1
                    rows.append(row)
                    print(f"[{model}] run {run + 1} {name}: {row['wall_s']}s, {row['tokens_per_s']} tok/s", flush=True)
            ps = ollama_ps()
            warm = [r["wall_s"] for r in rows if not (r["run"] == 1 and r["sample"] == SAMPLES[0][0])]
            results[model] = {
                "rows": rows,
                "ollama_ps": ps,
                "median_wall_s_warm": round(statistics.median(warm), 2) if warm else None,
                "median_tokens_per_s": round(statistics.median(r["tokens_per_s"] for r in rows if r["tokens_per_s"]), 2),
                "first_call_wall_s": rows[0]["wall_s"],
            }
            print(ps)
            subprocess.run(["ollama", "stop", model], capture_output=True)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    for model, res in results.items():
        print(f"{model}: first call {res['first_call_wall_s']}s, warm median {res['median_wall_s_warm']}s, median {res['median_tokens_per_s']} tok/s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
