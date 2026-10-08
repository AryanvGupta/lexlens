"""Fusion experiment: weighted RRF and BM25 vs the current ts_rank hybrid. Free (no API calls).

cd rag-api && set -a && . ../.env && set +a && uv run python ../evals/fusion_experiment.py

Candidates are fetched once per question (dense, ts_rank, BM25), then fused offline. The grid is
fixed up front (standard BM25 k1/b, RRF k=60, weights 1:1, 2:1, 3:1) because 44 questions cannot
support tuning. BM25 statistics come from the stored tsvector, so stemming and stopwords match
the ts_rank ranker exactly.
"""

import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rag-api"))

import psycopg  # noqa: E402
from app.ingest.embed import embed_query  # noqa: E402
from app.metrics import recall_at_k, reciprocal_rank  # noqa: E402
from app.retrieval.search import POOL, RRF_K  # noqa: E402
from app.store.pgvector_store import PgVectorStore  # noqa: E402

K1, B = 1.2, 0.75
KS = [1, 5, 10]
DEPTH = 20


def load_bm25(dsn: str):
    with psycopg.connect(dsn) as c:
        rows = c.execute(
            "SELECT id, lexeme, coalesce(array_length(positions, 1), 1) "
            "FROM passages, unnest(tsv)"
        ).fetchall()
    tf, dl, df = defaultdict(dict), Counter(), Counter()
    for pid, lex, n in rows:
        tf[lex][pid] = n
        dl[pid] += n
        df[lex] += 1
    return tf, dl, df


def bm25_rank(dsn, bm25, question: str, k: int) -> list[dict]:
    tf, dl, df = bm25
    with psycopg.connect(dsn) as c:
        terms = c.execute(
            "SELECT unnest(tsvector_to_array(to_tsvector('english', %s)))", (question,)
        ).fetchall()
    n, avgdl = len(dl), sum(dl.values()) / len(dl)
    scores: Counter = Counter()
    for (t,) in terms:
        idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) if df[t] else 0.0
        for pid, f in tf.get(t, {}).items():
            scores[pid] += idf * f * (K1 + 1) / (f + K1 * (1 - B + B * dl[pid] / avgdl))
    top = sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:k]
    return [{"id": pid, "score": s} for pid, s in top]


def wrrf(rankings: list[list[dict]], weights: list[float]) -> list[dict]:
    s: dict[str, float] = {}
    for ranking, w in zip(rankings, weights):
        for rank, h in enumerate(ranking, start=1):
            s[h["id"]] = s.get(h["id"], 0.0) + w / (RRF_K + rank)
    return [{"id": i, "score": v} for i, v in sorted(s.items(), key=lambda x: (-x[1], x[0]))]


def main() -> None:
    dsn = os.environ["DATABASE_URL"]
    store, bm25 = PgVectorStore(dsn), load_bm25(dsn)
    qs = [json.loads(line) for line in (ROOT / "evals/dataset/questions.jsonl").open()]
    qs = [q for q in qs if q["answerable"] and not q.get("adversarial")]

    cand = []
    for q in qs:
        cand.append(
            {
                "dense": store.search_dense(embed_query(q["question"]), POOL),
                "tsrank": store.search_lexical(q["question"], POOL),
                "bm25": bm25_rank(dsn, bm25, q["question"], POOL),
            }
        )

    systems = {"dense": lambda c: c["dense"], "ts_rank (lexical)": lambda c: c["tsrank"], "bm25 (lexical)": lambda c: c["bm25"]}
    for lex, name in (("tsrank", "ts_rank"), ("bm25", "bm25")):
        for wd in (1, 2, 3):
            systems[f"hybrid {name} dense:lex={wd}:1"] = lambda c, lex=lex, wd=wd: wrrf([c["dense"], c[lex]], [wd, 1])

    def score(fn):
        ids = [[h["id"] for h in fn(c)[:DEPTH]] for c in cand]
        per = [{f"recall@{k}": recall_at_k(i, q["gold_source_ids"], k) for k in KS} | {"mrr@20": reciprocal_rank(i, q["gold_source_ids"])} for q, i in zip(qs, ids)]
        return per

    results = {n: score(fn) for n, fn in systems.items()}
    base = results["hybrid ts_rank dense:lex=1:1"]
    committed = json.loads((ROOT / "evals/results/retrieval.json").read_text())["metrics"]["hybrid"]
    for m, v in committed.items():  # sanity: the 1:1 ts_rank row must be the product's hybrid
        got = sum(r[m] for r in base) / len(base)
        assert abs(got - v) < 1e-3, f"baseline mismatch on {m}: {got:.3f} vs committed {v:.3f}"

    cols = [f"recall@{k}" for k in KS] + ["mrr@20"]
    lines = [
        f"# Fusion experiment ({len(qs)} answerable questions, section-level gold, RRF k={RRF_K}, BM25 k1={K1} b={B})",
        "",
        "`vs base` = questions whose recall@5 went up / down relative to `hybrid ts_rank 1:1` (the current hybrid).",
        "",
        "| system | " + " | ".join(cols) + " | vs base (r@5 up/down) |",
        "|---|" + "---|" * (len(cols) + 1),
    ]
    for n, per in results.items():
        up = sum(a["recall@5"] > b["recall@5"] for a, b in zip(per, base))
        dn = sum(a["recall@5"] < b["recall@5"] for a, b in zip(per, base))
        lines.append(f"| {n} | " + " | ".join(f"{sum(r[c] for r in per) / len(per):.3f}" for c in cols) + f" | +{up} / -{dn} |")
    # the 6 over-refused questions whose gold section was not in the top 8 (docs/what-broke.md #2); /ask uses k=8
    missed = {"q011", "q013", "q020", "q021", "q033", "q041"}
    idx = [i for i, q in enumerate(qs) if q["id"] in missed]
    assert len(idx) == len(missed)
    lines += ["", f"Over-refusal check (what-broke #2): of the {len(idx)} questions whose gold section was missing from the top 8, how many a system retrieves in its top 8:", "", "| system | found in top 8 |", "|---|---|"]
    for n, fn in systems.items():
        hit = sum(recall_at_k([h["id"] for h in fn(cand[i])], qs[i]["gold_source_ids"], 8) == 1.0 for i in idx)
        lines.append(f"| {n} | {hit} / {len(idx)} |")
    out = ROOT / "evals/results/experiments/fusion"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


main()
