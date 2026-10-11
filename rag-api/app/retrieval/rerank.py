import os
from functools import lru_cache

from sentence_transformers import CrossEncoder

from app.config import RERANK_MODEL

# Opt-in speed option, unset by default (then nothing below changes the default path):
#   RERANK_OPT=batch8  same fp32 weights, scored in batches of 8 (less padding).
#   RERANK_OPT=int8    dynamic int8 quantization of the Linear layers (oneDNN engine), batches of 8.
# Both are different configurations (scores shift slightly), see evals/rerank_fidelity.py.
RERANK_OPT = os.environ.get("RERANK_OPT", "")
_OPTIONS = ("", "batch8", "int8")


def _quantize_int8(m: CrossEncoder) -> CrossEncoder:
    import torch

    # onednn was the fastest engine measured on the linux/arm64 target; macOS only has qnnpack
    for engine in ("onednn", "x86", "qnnpack"):
        if engine in torch.backends.quantized.supported_engines:
            torch.backends.quantized.engine = engine
            break
    m.to("cpu")  # dynamic int8 kernels are CPU-only (macOS would otherwise pick MPS)
    # CrossEncoder is an nn.Module whose HF model sits inside its first module
    torch.ao.quantization.quantize_dynamic(
        m, {torch.nn.Linear}, dtype=torch.qint8, inplace=True
    )
    if not any("quantized.dynamic" in type(x).__module__ for x in m.modules()):
        raise RuntimeError("RERANK_OPT=int8 did not quantize any layer")
    return m


@lru_cache
def model() -> CrossEncoder:
    if RERANK_OPT not in _OPTIONS:
        raise ValueError(f"RERANK_OPT={RERANK_OPT!r}; supported: {_OPTIONS[1:]}")
    m = CrossEncoder(RERANK_MODEL)
    return _quantize_int8(m) if RERANK_OPT == "int8" else m


def rerank(query: str, hits: list[dict], k: int) -> list[dict]:
    """Re-order candidates by cross-encoder relevance to the query; score becomes the model logit."""
    if not hits:
        return []
    scores = model().predict(
        [(query, f"{h['source']['title']}\n{h['text']}") for h in hits],
        **({"batch_size": 8} if RERANK_OPT else {}),
    )
    ranked = sorted(zip(hits, scores), key=lambda x: (-float(x[1]), x[0]["id"]))
    return [{**h, "score": float(s)} for h, s in ranked[:k]]
