import os

import psycopg
import pytest

from app.config import EMBED_DIM
from app.store.pgvector_store import PgVectorStore

DSN = os.environ.get("DATABASE_URL", "")


def _db_up():
    try:
        psycopg.connect(DSN, connect_timeout=3).close()
        return True
    except psycopg.Error:
        return False


pytestmark = pytest.mark.skipif(
    not _db_up(), reason="Postgres not reachable (set DATABASE_URL)"
)


def vec(i):
    v = [0.0] * EMBED_DIM
    v[i] = 1.0
    return v


def row(id, text):
    return {
        "id": id,
        "source_id": "s",
        "title": "t",
        "section": "1",
        "url": "u",
        "text": text,
        "char_start": 0,
        "char_end": 1,
    }


def test_roundtrip_and_upsert_idempotent():
    s = PgVectorStore(DSN, table="passages_test")
    s.init(reset=True)
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("TRUNCATE passages_test")
    rows = [row("a", "apple"), row("b", "banana")]
    s.upsert(rows, [vec(0), vec(1)])
    s.upsert(rows, [vec(0), vec(1)])  # second load must not duplicate
    assert s.count() == 2
    hits = s.search_dense(vec(1), k=2)
    assert hits[0]["id"] == "b" and hits[0]["score"] == pytest.approx(1.0)
    assert hits[0]["source"]["url"] == "u"


def test_lexical_ors_terms_and_ranks():
    s = PgVectorStore(DSN, table="passages_test")
    s.init(reset=True)
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute("TRUNCATE passages_test")
    s.upsert(
        [row("a", "apple pie recipe"), row("b", "banana bread"), row("c", "unrelated")],
        [vec(0), vec(1), vec(2)],
    )
    hits = s.search_lexical("what is the apple banana situation", k=5)
    assert {h["id"] for h in hits} == {"a", "b"}  # OR semantics; 'c' has no match


def test_bm25_ranks_by_term_and_loads_text():
    s = PgVectorStore(DSN, table="passages_test")
    s.init(reset=True)
    s.upsert(
        [row("a", "apple pie recipe"), row("b", "banana bread"), row("c", "unrelated")],
        [vec(0), vec(1), vec(2)],
    )
    hits = s.search_bm25("what is the apple situation", k=5)
    assert [h["id"] for h in hits] == ["a"]  # 'c' and 'b' have no matching term
    assert hits[0]["text"] == "apple pie recipe" and hits[0]["score"] > 0


def test_bm25_index_follows_a_same_size_rebuild():
    s = PgVectorStore(DSN, table="passages_test")
    s.init(reset=True)
    s.upsert([row("a", "apple pie"), row("b", "banana bread")], [vec(0), vec(1)])
    assert [h["id"] for h in s.search_bm25("apple", k=5)] == ["a"]
    s.init(
        reset=True
    )  # drop and recreate, as ingest does; same number of rows, different text
    s.upsert([row("a", "cherry tart"), row("b", "date cake")], [vec(0), vec(1)])
    assert s.search_bm25("apple", k=5) == []
    assert [h["id"] for h in s.search_bm25("cherry", k=5)] == ["a"]
