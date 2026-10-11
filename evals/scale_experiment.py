"""Corpus-scaling experiment: ingest N Titles into a scratch DB, then measure retrieval, size and latency.

  cd rag-api && DATABASE_URL=.../lexlens_scale uv run python ../evals/scale_experiment.py 1x:../data/sources.json 3x:../evals/scale/sources-3x.json 10x:../evals/scale/sources-extra.json

Env: SCALE_RAW (raw HTML dir, default ../scale-raw next to the repo), SCALE_OUT (results dir),
BENCH_LOCK (dir taken with mkdir only around the latency window; skipped if unset).
SAFETY: ingest drops and rebuilds the table, so this refuses to run unless the database is `lexlens_scale`.
Retrieval metrics only: extra Titles make some 'unanswerable' dev questions answerable, so no answer/refusal eval.
"""

import json
import os
import resource
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rag-api"))
DSN = os.environ["DATABASE_URL"]
if DSN.rsplit("/", 1)[-1] != "lexlens_scale":
    sys.exit(
        f"ABORT: database is {DSN.rsplit('/', 1)[-1]!r}, only 'lexlens_scale' allowed"
    )
OUT = Path(os.environ.get("SCALE_OUT", ROOT / "evals/results/experiments/scale"))
RAW = os.environ.get("SCALE_RAW", str(ROOT.parent / "scale-raw"))
LOCK = os.environ.get("BENCH_LOCK")
K = 12


def dev_questions() -> list[str]:
    qs = [json.loads(line) for line in (ROOT / "evals/dataset/questions.jsonl").open()]
    return [q["question"] for q in qs if q["answerable"] and not q.get("adversarial")]


def rss_mb() -> float:
    return (
        int(subprocess.check_output(["ps", "-o", "rss=", "-p", str(os.getpid())]))
        / 1024
    )


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[round(p * (len(xs) - 1))]


def ingest(manifest: str) -> float:
    env = {
        **os.environ,
        "LEXLENS_SOURCES": str(Path(manifest).resolve()),
        "LEXLENS_RAW": RAW,
    }
    print(f"ingest into {DSN.rsplit('/', 1)[-1]} from {manifest}", flush=True)
    t = time.perf_counter()
    subprocess.run(
        [sys.executable, "-m", "app.ingest"], env=env, check=True, cwd=ROOT / "rag-api"
    )
    return time.perf_counter() - t


def sizes() -> dict:
    import psycopg

    with psycopg.connect(DSN) as c:
        q = lambda s: c.execute(s).fetchone()[0]
        return {
            "total_mb": q("SELECT pg_total_relation_size('passages')") / 2**20,
            "table_mb": q("SELECT pg_relation_size('passages')") / 2**20,
            "hnsw_mb": q("SELECT pg_relation_size('passages_emb_idx')") / 2**20,
            "gin_mb": q("SELECT pg_relation_size('passages_tsv_idx')") / 2**20,
        }


def latency(questions: list[str]) -> dict:
    import numpy as np

    from app.ingest.embed import embed_query
    from app.retrieval import bm25
    from app.retrieval.search import search
    from app.store.pgvector_store import PgVectorStore

    store = PgVectorStore(DSN)
    n = store.count()
    bm25._cache.clear()
    r0, t = rss_mb(), time.perf_counter()
    bm25.index(DSN, "passages", n)
    bm = {
        "build_s": time.perf_counter() - t,
        "rss_before_mb": r0,
        "rss_after_mb": rss_mb(),
    }
    bm["rss_delta_mb"] = bm["rss_after_mb"] - r0
    tf = bm25.index(DSN, "passages", n)[0]
    bm["terms"], bm["postings"] = len(tf), sum(len(v) for v in tf.values())
    # ps RSS on macOS is noisy (page compression), so also count the Python heap the index holds
    bm25._cache.clear()
    tracemalloc.start()
    bm25.index(DSN, "passages", n)
    bm["heap_mb"] = tracemalloc.get_traced_memory()[0] / 2**20
    bm["heap_peak_mb"] = tracemalloc.get_traced_memory()[1] / 2**20
    tracemalloc.stop()
    out = {"bm25": bm}
    vecs = [embed_query(q) for q in questions]  # also loads the embedding model
    for q in questions[:3]:  # warm the cross-encoder
        search(store, q, K, "rerank")
    ts = []
    for v in vecs:
        t = time.perf_counter()
        store.search_dense(v, K)
        ts.append((time.perf_counter() - t) * 1000)
    out["dense_sql_hnsw_ms"] = {"p50": pct(ts, 0.5), "p95": pct(ts, 0.95)}
    with store._conn() as c:  # is the HNSW index actually used?
        plan = c.execute(
            "EXPLAIN SELECT id FROM passages ORDER BY embedding <=> %s LIMIT 12",
            (np.array(vecs[0], dtype=np.float32),),
        ).fetchall()
    out["dense_plan_uses_hnsw"] = any("passages_emb_idx" in r[0] for r in plan)
    for mode in ("dense", "hybrid", "rerank"):
        ts = []
        for q in questions:
            t = time.perf_counter()
            search(store, q, K, mode)
            ts.append((time.perf_counter() - t) * 1000)
        out[mode] = {"p50": pct(ts, 0.5), "p95": pct(ts, 0.95)}
    out["rss_final_mb"] = rss_mb()
    out["maxrss_mb"] = (
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20
    )  # bytes on macOS
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    questions = dev_questions()
    for spec in sys.argv[1:]:
        label, manifest = spec.split(":", 1)
        res: dict = {
            "label": label,
            "manifest": manifest,
            "n_questions": len(questions),
        }
        res["ingest_wall_s"] = ingest(manifest)
        from app.store.pgvector_store import PgVectorStore

        res["passages"] = PgVectorStore(DSN).count()
        res["pg"] = sizes()
        d = OUT / label
        subprocess.run(
            [sys.executable, str(ROOT / "evals/run_eval.py")],
            env={**os.environ, "EVAL_RESULTS": str(d)},
            check=True,
            cwd=ROOT / "rag-api",
            stdout=subprocess.DEVNULL,
        )
        res["retrieval"] = json.loads((d / "retrieval.json").read_text())
        # latency runs in a fresh process so the BM25 RSS delta is not polluted by the eval's cache
        if LOCK:
            while subprocess.run(
                ["mkdir", LOCK], capture_output=True, check=False
            ).returncode:
                print("bench lock busy, waiting", flush=True)
                time.sleep(30)
        try:
            p = subprocess.run(
                [sys.executable, __file__, "_latency"],
                check=True,
                capture_output=True,
                text=True,
                cwd=ROOT / "rag-api",
            )
            res["latency"] = json.loads(p.stdout.strip().splitlines()[-1])
        finally:
            if LOCK:
                os.rmdir(LOCK)
        (OUT / f"{label}.json").write_text(json.dumps(res, indent=2) + "\n")
        print(
            f"{label}: {res['passages']} passages, ingest {res['ingest_wall_s']:.0f}s",
            flush=True,
        )
    summarize()


def summarize() -> None:
    rs = [
        json.loads(p.read_text())
        for p in sorted(OUT.glob("*x.json"), key=lambda p: int(p.stem[:-1]))
    ]
    L = [
        "| scale | passages | ingest s | table+idx MB (heap/HNSW/GIN) | BM25 build s | BM25 RSS +MB (heap MB) | process RSS MB |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rs:
        p, b = r["pg"], r["latency"]["bm25"]
        L.append(
            f"| {r['label']} | {r['passages']} | {r['ingest_wall_s']:.0f} | {p['total_mb']:.0f} ({p['table_mb']:.0f}/{p['hnsw_mb']:.0f}/{p['gin_mb']:.0f}) | {b['build_s']:.1f} | {b['rss_delta_mb']:.0f} ({b['heap_mb']:.0f}) | {r['latency']['rss_final_mb']:.0f} |"
        )
    L += ["", "| scale | mode | p50 ms | p95 ms |", "|---|---|---|---|"]
    for r in rs:
        for m in ("dense", "hybrid", "rerank"):
            L.append(
                f"| {r['label']} | {m} | {r['latency'][m]['p50']:.0f} | {r['latency'][m]['p95']:.0f} |"
            )
        h = r["latency"]["dense_sql_hnsw_ms"]
        L.append(
            f"| {r['label']} | dense SQL only (HNSW used: {r['latency']['dense_plan_uses_hnsw']}) | {h['p50']:.1f} | {h['p95']:.1f} |"
        )
    cols = ["recall@1", "recall@5", "recall@10", "mrr@20"]
    L += [
        "",
        "| scale | mode | " + " | ".join(cols) + " |",
        "|---|---|" + "---|" * len(cols),
    ]
    for r in rs:
        for m, v in r["retrieval"]["metrics"].items():
            L.append(
                f"| {r['label']} | {m} | "
                + " | ".join(f"{v[c]:.3f}" for c in cols)
                + " |"
            )
    (OUT / "summary.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    if sys.argv[1:] == ["_latency"]:
        print(json.dumps(latency(dev_questions())))
    else:
        main()
