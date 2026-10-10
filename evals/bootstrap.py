"""Bootstrap CIs for the retrieval eval (opt-in; changes nothing at runtime).

cd rag-api && uv run python ../evals/bootstrap.py   # needs DATABASE_URL, same corpus as run_eval.py
Resamples the QUESTIONS (not passages) with replacement; one shared set of resamples is used for every
metric/mode, which is what makes the differences paired.
"""

import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rag-api"))

MODES = ["dense", "lexical", "hybrid", "rerank"]
KS = [1, 5, 10]
DEPTH = 20
B = 10_000


def resamples(n: int, b: int = B, seed: int = 0) -> list[list[int]]:
    rng = random.Random(seed)
    return [[rng.randrange(n) for _ in range(n)] for _ in range(b)]


def boot_ci(vals: list[float], idx: list[list[int]]) -> tuple[float, float]:
    """Percentile 95% CI of the mean of `vals` over the given resamples."""
    means = sorted(sum(vals[i] for i in r) / len(r) for r in idx)
    return means[int(0.025 * len(means))], means[int(0.975 * len(means)) - 1]


def paired_ci(
    a: list[float], b: list[float], idx: list[list[int]]
) -> tuple[float, float]:
    """95% CI of mean(a) - mean(b), resampling questions jointly."""
    return boot_ci([x - y for x, y in zip(a, b, strict=True)], idx)


def main() -> None:
    from app.metrics import recall_at_k, reciprocal_rank
    from app.retrieval.search import search
    from app.store.pgvector_store import PgVectorStore

    store = PgVectorStore(os.environ["DATABASE_URL"])
    qs = [json.loads(line) for line in (ROOT / "evals/dataset/questions.jsonl").open()]
    qs = [q for q in qs if q["answerable"] and not q.get("adversarial")]
    per: dict[str, dict[str, list[float]]] = {}
    for mode in MODES:
        ranked = [
            [h["id"] for h in search(store, q["question"], DEPTH, mode)] for q in qs
        ]
        per[mode] = {
            f"recall@{k}": [
                recall_at_k(r, q["gold_source_ids"], k)
                for q, r in zip(qs, ranked, strict=True)
            ]
            for k in KS
        }
        per[mode]["mrr@20"] = [
            reciprocal_rank(r, q["gold_source_ids"])
            for q, r in zip(qs, ranked, strict=True)
        ]

    base = json.loads((ROOT / "evals/results/retrieval.json").read_text())["metrics"]
    for m in MODES:
        for c, v in per[m].items():
            assert abs(sum(v) / len(v) - base[m][c]) < 1e-3, (
                m,
                c,
                sum(v) / len(v),
                base[m][c],
            )

    idx = resamples(len(qs))
    out: dict = {
        "n": len(qs),
        "resamples": B,
        "seed": 0,
        "modes": {},
        "paired_diffs": {},
    }
    for m in MODES:
        out["modes"][m] = {
            c: {"point": sum(v) / len(v), "ci95": boot_ci(v, idx)}
            for c, v in per[m].items()
        }
    for a, b in [("hybrid", "dense"), ("rerank", "hybrid"), ("rerank", "dense")]:
        for c in ["recall@5", "mrr@20"]:
            pa, pb = per[a][c], per[b][c]
            out["paired_diffs"][f"{a}-{b} {c}"] = {
                "point": sum(pa) / len(pa) - sum(pb) / len(pb),
                "ci95": paired_ci(pa, pb, idx),
            }

    res = Path(
        os.environ.get("EVAL_RESULTS", ROOT / "evals/results/experiments/bootstrap")
    )
    res.mkdir(parents=True, exist_ok=True)
    (res / "bootstrap.json").write_text(json.dumps(out, indent=2) + "\n")
    cols = [f"recall@{k}" for k in KS] + ["mrr@20"]
    L = [
        f"# Bootstrap 95% CIs ({len(qs)} questions, {B} resamples of questions, seed 0, percentile)",
        "",
        "| mode | " + " | ".join(cols) + " |",
        "|---|" + "---|" * len(cols),
    ]
    for m in MODES:
        L.append(
            f"| {m} | "
            + " | ".join(
                "{:.3f} [{:.3f}, {:.3f}]".format(
                    out["modes"][m][c]["point"], *out["modes"][m][c]["ci95"]
                )
                for c in cols
            )
            + " |"
        )
    L += [
        "",
        "Paired differences (same resampled questions):",
        "",
        "| difference | point | 95% CI | excludes 0? |",
        "|---|---|---|---|",
    ]
    for k, d in out["paired_diffs"].items():
        lo, hi = d["ci95"]
        L.append(
            f"| {k} | {d['point']:+.3f} | [{lo:+.3f}, {hi:+.3f}] | {'yes' if lo > 0 or hi < 0 else 'no'} |"
        )
    (res / "summary.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
