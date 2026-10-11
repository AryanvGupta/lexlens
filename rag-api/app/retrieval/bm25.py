"""BM25 over the stored tsvector, so stemming and stopwords match the ts_rank ranker.

The index (term frequencies, doc lengths, doc frequencies; ~300k entries for the current corpus)
is held in memory per process and reloaded when the passage count changes. The API builds a
store per request, so the cache is module-level.
"""

import math
from collections import Counter, defaultdict

import psycopg

K1, B = 1.2, 0.75  # standard defaults, not tuned
_cache: dict[tuple[str, str], tuple[int, tuple]] = {}


def load(dsn: str, table: str) -> tuple:
    with psycopg.connect(dsn) as c:
        rows = c.execute(
            f"SELECT id, lexeme, coalesce(array_length(positions, 1), 1) FROM {table}, unnest(tsv)"
        ).fetchall()
    tf, dl, df = defaultdict(dict), Counter(), Counter()
    for pid, lex, n in rows:
        tf[lex][pid] = n
        dl[pid] += n
        df[lex] += 1
    return tf, dl, df


def index(dsn: str, table: str, version: tuple) -> tuple:
    """`version` is any value that changes when the table is rebuilt or changes size (the store passes
    (row count, table oid): ingest drops and recreates the table, which gives it a new oid)."""
    hit = _cache.get((dsn, table))
    if hit is None or hit[0] != version:
        hit = _cache[(dsn, table)] = (version, load(dsn, table))
    return hit[1]


def rank(idx: tuple, terms: list[str], k: int) -> list[tuple[str, float]]:
    tf, dl, df = idx
    if not dl:
        return []
    n, avgdl = len(dl), sum(dl.values()) / len(dl)
    scores: Counter = Counter()
    for t in set(terms):
        if not df[t]:
            continue
        idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
        for pid, f in tf[t].items():
            scores[pid] += idf * f * (K1 + 1) / (f + K1 * (1 - B + B * dl[pid] / avgdl))
    return sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:k]
