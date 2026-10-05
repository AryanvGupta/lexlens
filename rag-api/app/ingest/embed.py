from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import EMBED_MODEL

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@lru_cache
def model() -> SentenceTransformer:
    return SentenceTransformer(EMBED_MODEL)


def embed_passages(texts: list[str]) -> list[list[float]]:
    return model().encode(texts, normalize_embeddings=True, batch_size=32).tolist()


def embed_query(q: str) -> list[float]:
    return model().encode(QUERY_PREFIX + q, normalize_embeddings=True).tolist()
