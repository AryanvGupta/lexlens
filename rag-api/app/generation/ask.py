import json
import re

from app.config import GEN_EFFORT, GEN_MODEL
from app.retrieval.search import search

from .prompt import SCHEMA, SYSTEM, build_user

MIN_QUOTE_CHARS = 15  # a one-word "quote" proves nothing


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def verify_citations(
    citations: list[dict], passages: list[dict]
) -> tuple[list[dict], int]:
    """Keep citations whose id was retrieved and whose quote is a verbatim substring."""
    by_id = {p["id"]: _norm(p["text"]) for p in passages}
    kept = [
        c
        for c in citations
        if c.get("passage_id") in by_id
        and len(_norm(c.get("quote", ""))) >= MIN_QUOTE_CHARS
        and _norm(c["quote"]) in by_id[c["passage_id"]]
    ]
    return kept, len(citations) - len(kept)


def _refusal(reason: str, passages: list[dict], dropped: int = 0) -> dict:
    return {
        "answer": "",
        "citations": [],
        "refused": True,
        "reason": reason,
        "dropped_citations": dropped,
        "retrieved": passages,
    }


def ask(store, call, question: str, k: int = 8, mode: str = "hybrid") -> dict:
    passages = search(store, question, k, mode)
    r = call(
        model=GEN_MODEL,
        system=SYSTEM,
        user=build_user(question, passages),
        schema=SCHEMA,
        effort=GEN_EFFORT,
    )
    if r["stop_reason"] != "end_turn":
        return _refusal(f"model stopped with {r['stop_reason']}", passages)
    try:
        out = json.loads(r["text"])
        refused, reason, answer = out["refused"], out["reason"], out["answer"]
        cites = out["citations"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return _refusal("malformed model output", passages)
    if refused:
        return _refusal(reason or "insufficient evidence", passages)
    kept, dropped = verify_citations(cites, passages)
    if not kept:
        return _refusal("no verifiable citations for the answer", passages, dropped)
    return {
        "answer": answer,
        "citations": kept,
        "refused": False,
        "reason": "",
        "dropped_citations": dropped,
        "retrieved": passages,
    }
