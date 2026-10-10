"""Opt-in query-rewrite experiment on the 44 answerable dev questions: hybrid vs rerank vs rewrite.
Makes ~44 small LLM calls (REWRITE_MODEL). Run from rag-api/: uv run python ../evals/rewrite_experiment.py"""

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rag-api"))

from app.metrics import recall_at_k, reciprocal_rank, section_key  # noqa: E402
from app.retrieval.rewrite import REWRITE_MODEL, rewrite_query  # noqa: E402
from app.retrieval.search import search  # noqa: E402
from app.store.pgvector_store import PgVectorStore  # noqa: E402

MODES = ["hybrid", "rerank", "rewrite"]
DEPTH = 30
OUT = ROOT / "evals/results/experiments/rewrite"


def gold_rank(ids, gold):
    ranks = [i for i, x in enumerate(ids, 1) if section_key(x) in gold]
    return ranks[0] if ranks else None


def main() -> None:
    store = PgVectorStore(os.environ["DATABASE_URL"])
    qs = [json.loads(line) for line in (ROOT / "evals/dataset/questions.jsonl").open()]
    qs = [q for q in qs if q["answerable"] and not q.get("adversarial")]
    rewrites, secs = {}, []
    for q in qs:
        t = time.perf_counter()
        rewrites[q["id"]] = rewrite_query(q["question"])
        secs.append(time.perf_counter() - t)
    ids = {m: {} for m in MODES}
    for m in MODES:
        for q in qs:
            ids[m][q["id"]] = [h["id"] for h in search(store, q["question"], DEPTH, m)]
    failed = [i for i, q in zip(rewrites, qs) if rewrites[i] == q["question"]]

    def agg(m, f):
        return sum(f(ids[m][q["id"]], q["gold_source_ids"]) for q in qs) / len(qs)

    lines = [
        f"# Query-rewrite experiment ({len(qs)} answerable dev questions, rewrite model `{REWRITE_MODEL}`)",
        "",
        "| mode | recall@1 | recall@5 | recall@10 | recall@12 | mrr@30 |",
        "|---|---|---|---|---|---|",
    ]
    for m in MODES:
        r = [agg(m, lambda i, g, k=k: recall_at_k(i, g, k)) for k in (1, 5, 10, 12)]
        lines.append(
            f"| {m} | "
            + " | ".join(f"{x:.3f}" for x in r)
            + f" | {agg(m, reciprocal_rank):.3f} |"
        )
    q33 = next(q for q in qs if q["id"] == "q033")
    lines += [
        "",
        f"q033 gold {q33['gold_source_ids']}: rank hybrid={gold_rank(ids['hybrid']['q033'], q33['gold_source_ids'])}, "
        f"rerank={gold_rank(ids['rerank']['q033'], q33['gold_source_ids'])}, "
        f"rewrite={gold_rank(ids['rewrite']['q033'], q33['gold_source_ids'])} (None = outside top {DEPTH}).",
        f"q033 rewrite text: `{rewrites['q033']}`",
        "",
    ]

    def in12(m, q):
        return recall_at_k(ids[m][q["id"]], q["gold_source_ids"], 12) == 1.0

    lost = [q["id"] for q in qs if in12("rerank", q) and not in12("rewrite", q)]
    gained = [q["id"] for q in qs if in12("rewrite", q) and not in12("rerank", q)]
    lines += [
        f"Gold fully in top-12 under rerank but NOT rewrite: {lost or 'none'}",
        f"Gold fully in top-12 under rewrite but NOT rerank: {gained or 'none'}",
        f"Rewrite calls that fell back to the original question: {failed or 'none'}",
        f"Rewrite LLM step wall clock per question: mean {sum(secs) / len(secs):.2f}s, max {max(secs):.2f}s.",
        "",
        "Per-question rank of first gold section (hybrid / rerank / rewrite):",
        "",
    ]
    for q in qs:
        r = [gold_rank(ids[m][q["id"]], q["gold_source_ids"]) for m in MODES]
        lines.append(f"- {q['id']}: {r[0]} / {r[1]} / {r[2]}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "retrieval.md").write_text("\n".join(lines) + "\n")
    (OUT / "rewrites.json").write_text(json.dumps(rewrites, indent=1) + "\n")
    print("\n".join(lines))


main()
