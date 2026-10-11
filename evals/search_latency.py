"""Retrieval latency per mode (embedding + DB + rerank), warm, no API calls.

cd rag-api && set -a && . ../.env && set +a && uv run python ../evals/search_latency.py
"""

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rag-api"))

from app.retrieval.search import search
from app.store.pgvector_store import PgVectorStore

K = 12
qs = [
    json.loads(line)["question"]
    for line in (ROOT / "evals/dataset/questions.jsonl").open()
]
store = PgVectorStore(os.environ["DATABASE_URL"])
print(f"| mode (k={K}) | p50 ms | p95 ms |\n|---|---|---|")
for mode in ("dense", "hybrid", "rerank"):
    for q in qs[:3]:  # warm models and the BM25 index
        search(store, q, K, mode)
    ts = []
    for q in qs:
        t = time.perf_counter()
        search(store, q, K, mode)
        ts.append((time.perf_counter() - t) * 1000)
    ts.sort()
    print(
        f"| {mode} | {ts[len(ts) // 2]:.0f} | {ts[round(0.95 * (len(ts) - 1))]:.0f} |"
    )
