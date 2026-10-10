"""Chunk-level probe for the wrong-chunk over-refusals (docs/what-broke.md #2). Free (no API calls).

Section-level gold counts any chunk of the right section as a hit. For the four questions where
the model refused because the answering chunk was missing, this finds the chunk whose text holds
the phrase that answers the question and reports its rank (within the top 8 that /ask sees) per mode.

cd rag-api && set -a && . ../.env && set +a && uv run python ../evals/chunk_probe.py
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rag-api"))

import psycopg  # noqa: E402
from app.retrieval.search import search  # noqa: E402
from app.store.pgvector_store import PgVectorStore  # noqa: E402

# question id -> (question, gold section, phrase found only in the chunk that answers it)
PROBES = {
    "q018": (
        "How many years does a patent term last from filing?",
        "usc-35:154",
        "20 years from the date on which the application",
    ),
    "q036": (
        "What does the automatic stay do when a bankruptcy petition is filed?",
        "usc-11:362",
        "operates as a stay",
    ),
    "q037": (
        "Who is eligible to be a debtor under the bankruptcy code?",
        "usc-11:109",
        "may be a debtor under chapter 7",
    ),
    "q038": (
        "When can a trustee avoid a preferential transfer made before bankruptcy?",
        "usc-11:547",
        "for or on account of an antecedent debt",
    ),
}
MODES = ["dense", "hybrid", "rerank"]
K = 8  # what /ask sees
DEPTH = 30  # ranks reported beyond K show whether a larger k (or the rerank pool of 30) could reach the chunk


def main() -> None:
    dsn = os.environ["DATABASE_URL"]
    store = PgVectorStore(dsn)
    with psycopg.connect(dsn) as c:
        print(f"| question | answering chunk | " + " | ".join(MODES) + " |")
        print("|---|---|" + "---|" * len(MODES))
        for qid, (question, sec, phrase) in PROBES.items():
            ids = [
                r[0]
                for r in c.execute(
                    "SELECT id FROM passages WHERE id LIKE %s AND text ILIKE %s",
                    (sec + ":%", f"%{phrase}%"),
                ).fetchall()
            ]
            if not ids:
                print(
                    f"| {qid} | NOT FOUND (phrase {phrase!r} is in no chunk of {sec}) |"
                    + " |" * len(MODES)
                )
                continue
            cells = []
            for mode in MODES:
                got = [h["id"] for h in search(store, question, DEPTH, mode)]
                ranks = [got.index(i) + 1 for i in ids if i in got]
                cells.append(
                    ("**" if ranks and min(ranks) <= K else "")
                    + (f"rank {min(ranks)}" if ranks else f"> {DEPTH}")
                    + ("**" if ranks and min(ranks) <= K else "")
                )
            print(
                f"| {qid} | {', '.join(i.split(':')[-1] for i in ids)} of {sec} | "
                + " | ".join(cells)
                + " |"
            )


main()
