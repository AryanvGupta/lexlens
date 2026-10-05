def section_key(passage_id: str) -> str:
    """'usc-28:1332:0' -> 'usc-28:1332' (gold ids are section-level)."""
    return passage_id.rsplit(":", 1)[0]


def recall_at_k(ranked_ids: list[str], gold: list[str], k: int) -> float:
    found = {section_key(i) for i in ranked_ids[:k]} & set(gold)
    return len(found) / len(gold)


def reciprocal_rank(ranked_ids: list[str], gold: list[str]) -> float:
    for rank, i in enumerate(ranked_ids, start=1):
        if section_key(i) in gold:
            return 1.0 / rank
    return 0.0
