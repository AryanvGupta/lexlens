from typing import Literal

from app.ingest.embed import embed_query
from app.store.base import VectorStore

Mode = Literal["dense", "lexical", "hybrid"]
RRF_K = 60  # standard constant from the original RRF paper
POOL = 50  # candidates taken from each ranker before fusion


def rrf(rankings: list[list[dict]], k: int = RRF_K) -> list[dict]:
    """Reciprocal rank fusion: score(d) = sum over rankers of 1/(k + rank)."""
    scores: dict[str, float] = {}
    by_id: dict[str, dict] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, start=1):
            scores[hit["id"]] = scores.get(hit["id"], 0.0) + 1.0 / (k + rank)
            by_id.setdefault(hit["id"], hit)
    return [
        {**by_id[i], "score": s}
        for i, s in sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    ]


def search(
    store: VectorStore, query: str, k: int = 8, mode: Mode = "hybrid"
) -> list[dict]:
    if mode == "dense":
        return store.search_dense(embed_query(query), k)
    if mode == "lexical":
        return store.search_lexical(query, k)
    fused = rrf(
        [
            store.search_dense(embed_query(query), POOL),
            store.search_lexical(query, POOL),
        ]
    )
    return fused[:k]
