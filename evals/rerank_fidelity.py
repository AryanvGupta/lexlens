"""Does an optimized rerank path (RERANK_OPT) rank like the default fp32 path? Free (no API calls).

Step 1 (host, needs DATABASE_URL): dump the hybrid candidates of every dev question
  cd rag-api && uv run python ../evals/rerank_fidelity.py dump cands.json
Step 2 (anywhere with the model, e.g. the lexlens/rag-api:local image): compare
  python ../evals/rerank_fidelity.py compare cands.json int8 [out.json]
Reports per question the top-K id set and top-1 under fp32 vs the option, plus Spearman and
Pearson correlation of the 30 scores.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rag-api"))

K = 12  # app.generation.ask.DEFAULT_K


def dump(out: str) -> None:
    from app.retrieval.search import RERANK_POOL, search
    from app.store.pgvector_store import PgVectorStore

    store = PgVectorStore(os.environ["DATABASE_URL"])
    rows = []
    for line in (ROOT / "evals/dataset/questions.jsonl").open():
        q = json.loads(line)
        hits = search(store, q["question"], max(K, RERANK_POOL), "hybrid")
        rows.append(
            {
                "id": q["id"],
                "question": q["question"],
                "hits": [
                    {"id": h["id"], "text": h["text"], "source": {"title": h["source"]["title"]}}
                    for h in hits
                ],
            }
        )
    json.dump(rows, open(out, "w"))
    print(f"wrote {len(rows)} questions to {out}")


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: -xs[i])
    r = [0.0] * len(xs)
    for pos, i in enumerate(order):
        r[i] = float(pos)
    return r


def pearson(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = sum((x - ma) ** 2 for x in a) ** 0.5
    vb = sum((y - mb) ** 2 for y in b) ** 0.5
    return cov / (va * vb) if va and vb else 1.0


def compare(path: str, opt: str, out: str | None) -> None:
    import app.retrieval.rerank as rr

    data = json.load(open(path))
    sc = {}
    for label, o in (("fp32", ""), (opt, opt)):
        rr.RERANK_OPT = o
        rr.model.cache_clear()
        m = rr.model()
        if o == "int8":
            n = sum("quantized.dynamic" in type(x).__module__ for x in m.modules())
            assert n > 0, f"{o}: no dynamic-quantized modules, the option did not take effect"
            print(f"{o}: {n} dynamic-quantized Linear modules")
        sc[label] = [
            [
                float(x)
                for x in m.predict(
                    [(d["question"], f"{h['source']['title']}\n{h['text']}") for h in d["hits"]],
                    **({"batch_size": 8} if o else {}),  # same call as rerank()
                )
            ]
            for d in data
        ]
    rows, set_diff, top1_diff = [], [], []
    for d, a, b in zip(data, sc["fp32"], sc[opt]):
        ids = [h["id"] for h in d["hits"]]

        def top(s):
            return [ids[i] for i in sorted(range(len(ids)), key=lambda i: (-s[i], ids[i]))[:K]]

        ta, tb = top(a), top(b)
        if set(ta) != set(tb):
            set_diff.append(d["id"])
        if ta[0] != tb[0]:
            top1_diff.append(d["id"])
        rows.append(
            {
                "id": d["id"],
                "spearman": pearson(ranks(a), ranks(b)),
                "pearson": pearson(a, b),
                "max_abs_diff": max(abs(x - y) for x, y in zip(a, b)),
                "set_same": set(ta) == set(tb),
                "top1_same": ta[0] == tb[0],
                "top12_fp32": ta,
                f"top12_{opt}": tb,
            }
        )
    n = len(rows)
    ov = [len(set(r["top12_fp32"]) & set(r[f"top12_{opt}"])) for r in rows]
    print(f"mean top-{K} overlap {sum(ov) / n:.2f}/{K}  min {min(ov)}")
    print(f"questions: {n}")
    print(f"top-{K} id set differs: {len(set_diff)} {' '.join(set_diff)}")
    print(f"top-1 differs: {len(top1_diff)} {' '.join(top1_diff)}")
    print(f"mean Spearman {sum(r['spearman'] for r in rows) / n:.4f}  min {min(r['spearman'] for r in rows):.4f}")
    print(f"mean Pearson  {sum(r['pearson'] for r in rows) / n:.4f}  min {min(r['pearson'] for r in rows):.4f}")
    print(f"max |score diff| overall {max(r['max_abs_diff'] for r in rows):.3f}")
    if out:
        json.dump(rows, open(out, "w"), indent=1)


if __name__ == "__main__":
    if sys.argv[1] == "dump":
        dump(sys.argv[2])
    else:
        compare(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
