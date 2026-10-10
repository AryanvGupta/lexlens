from functools import lru_cache

from sentence_transformers import CrossEncoder

from app.config import RERANK_MODEL


@lru_cache
def model() -> CrossEncoder:
    return CrossEncoder(RERANK_MODEL)


def rerank(query: str, hits: list[dict], k: int) -> list[dict]:
    """Re-order candidates by cross-encoder relevance to the query; score becomes the model logit."""
    if not hits:
        return []
    scores = model().predict(
        [(query, f"{h['source']['title']}\n{h['text']}") for h in hits]
    )
    ranked = sorted(zip(hits, scores), key=lambda x: (-float(x[1]), x[0]["id"]))
    return [{**h, "score": float(s)} for h, s in ranked[:k]]
