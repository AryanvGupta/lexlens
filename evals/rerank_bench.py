"""Time the cross-encoder over real candidate pools for several variants. Free (no API calls).

Candidates come from a JSON dump (list of {id, question, hits:[{id,text,source:{title}}]}).
Run inside the target image, e.g.:
  docker run --rm -i --entrypoint python -v $PWD:/work -w /work/rag-api -e PYTHONPATH=/work/rag-api \
    -e HF_HUB_OFFLINE=1 lexlens/rag-api:local ../evals/rerank_bench.py cands.json fp32 int8 ...
"""

import json
import statistics
import sys
import time
import warnings

import torch
from sentence_transformers import CrossEncoder

from app.config import RERANK_MODEL

warnings.filterwarnings("ignore")


def build(variant: str):
    """Returns (model, predict_kwargs, context_manager_factory)."""
    m = CrossEncoder(RERANK_MODEL)
    kw: dict = {}
    for part in variant.split("+"):
        if part == "fp32":
            pass
        elif part in ("qnnpack", "onednn", "x86", "fbgemm"):
            torch.backends.quantized.engine = part
        elif part == "int8":
            torch.ao.quantization.quantize_dynamic(
                m, {torch.nn.Linear}, dtype=torch.qint8, inplace=True
            )
            n = sum("quantized.dynamic" in type(x).__module__ for x in m.modules())
            assert n > 0, "int8 did not take effect"
            print(f"  int8: {n} dynamic-quantized Linear modules")
        elif part == "bf16":
            m.to(torch.bfloat16)
        elif part.startswith("t"):  # t4 = 4 intra-op threads
            torch.set_num_threads(int(part[1:]))
        elif part.startswith("bs"):
            kw["batch_size"] = int(part[2:])
        elif part == "sdpa":
            pass
        else:
            raise SystemExit(f"unknown variant part {part}")
    return m, kw


def main(path: str, variants: list[str], n: int = 100) -> None:
    """Round-robin timing: for each question every variant is timed back to back, so machine
    drift hits all variants equally (sequential per-variant runs drifted by +/-40%)."""
    data = json.load(open(path))[:n]
    pairs = [
        [(d["question"], f"{h['source']['title']}\n{h['text']}") for h in d["hits"]]
        for d in data
    ]
    built = {v: build(v) for v in variants}
    ts = {v: [] for v in variants}
    scores = {v: [] for v in variants}
    with torch.inference_mode():
        for v, (m, kw) in built.items():  # warm
            m.predict(pairs[0], **kw)
            m.predict(pairs[1], **kw)
        for i, p in enumerate(pairs):
            for v in variants[i % len(variants) :] + variants[: i % len(variants)]:
                m, kw = built[v]
                t = time.perf_counter()
                s = m.predict(p, **kw)
                ts[v].append(time.perf_counter() - t)
                scores[v].append([float(x) for x in s])
    for v in variants:
        t = sorted(ts[v])
        p95 = t[min(len(t) - 1, int(round(0.95 * len(t))) - 1)]
        print(
            f"{v:22s} n={len(t)} median={statistics.median(t):.3f}s p95={p95:.3f}s "
            f"mean={statistics.mean(t):.3f}s",
            flush=True,
        )


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
