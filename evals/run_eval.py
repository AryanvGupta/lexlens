"""Retrieval eval. Run via `make dev-eval` (local compose DB) or `make eval` (in-cluster Job); needs an ingested corpus."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rag-api"))

from app.metrics import recall_at_k, reciprocal_rank
from app.retrieval.search import search
from app.store.pgvector_store import PgVectorStore

MODES = ["dense", "lexical", "hybrid", "rerank"]
KS = [1, 5, 10]
DEPTH = 20


def main() -> None:
    store = PgVectorStore(os.environ["DATABASE_URL"])
    qs = [
        json.loads(line)
        for line in Path(
            os.environ.get("EVAL_DATASET", ROOT / "evals/dataset/questions.jsonl")
        )
        .read_text()
        .splitlines()
    ]
    qs = [
        q for q in qs if q["answerable"] and not q.get("adversarial")
    ]  # refusal and adversarial: M3
    out, misses = {}, {}
    for mode in MODES:
        rows = []
        for q in qs:
            ids = [h["id"] for h in search(store, q["question"], DEPTH, mode)]
            rows.append((q, ids))
        out[mode] = {
            f"recall@{k}": sum(recall_at_k(i, q["gold_source_ids"], k) for q, i in rows)
            / len(rows)
            for k in KS
        }
        out[mode]["mrr@20"] = sum(
            reciprocal_rank(i, q["gold_source_ids"]) for q, i in rows
        ) / len(rows)
        misses[mode] = [
            q["id"] for q, i in rows if recall_at_k(i, q["gold_source_ids"], 10) < 1.0
        ]
    res = Path(os.environ.get("EVAL_RESULTS", ROOT / "evals/results"))
    res.mkdir(parents=True, exist_ok=True)
    (res / "retrieval.json").write_text(
        json.dumps(
            {"n": len(qs), "metrics": out, "not_fully_found_in_top10": misses}, indent=2
        )
        + "\n"
    )
    cols = [f"recall@{k}" for k in KS] + ["mrr@20"]
    lines = [
        f"# Retrieval eval ({len(qs)} answerable questions, section-level gold)",
        "",
        "| mode | " + " | ".join(cols) + " |",
        "|---|" + "---|" * len(cols),
    ]
    lines += [
        f"| {m} | " + " | ".join(f"{out[m][c]:.3f}" for c in cols) + " |" for m in MODES
    ]
    (res / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


main()
