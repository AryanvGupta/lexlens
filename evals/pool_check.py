"""Does a smaller rerank pool change what /ask would see? Free (no API calls).

For every eval question, compares the top-K ids from rerank at the default pool against smaller
pools. If a question's top-K set is identical, its cached answer-eval result still applies.

cd rag-api && set -a && . ../.env && set +a && uv run python ../evals/pool_check.py
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rag-api"))

import app.retrieval.search as S  # noqa: E402
from app.generation.ask import DEFAULT_K  # noqa: E402
from app.store.pgvector_store import PgVectorStore  # noqa: E402

store = PgVectorStore(os.environ["DATABASE_URL"])
qs = [json.loads(line) for line in (ROOT / "evals/dataset/questions.jsonl").open()]


def top(q, pool):
    S.RERANK_POOL = pool
    return [h["id"] for h in S.search(store, q["question"], DEFAULT_K, "rerank")]


ref = {q["id"]: top(q, 30) for q in qs}
print(
    f"| pool | questions with a different top-{DEFAULT_K} set (of {len(qs)}) | which |\n|---|---|---|"
)
for pool in (25, 20, 15):
    diff = [q["id"] for q in qs if set(top(q, pool)) != set(ref[q["id"]])]
    print(f"| {pool} | {len(diff)} | {' '.join(diff) or '-'} |")
