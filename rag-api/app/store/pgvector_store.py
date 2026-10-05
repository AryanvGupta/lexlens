import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from app.config import EMBED_DIM

from .base import VectorStore

SCHEMA = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS passages (
  id text PRIMARY KEY,
  source_id text NOT NULL,
  title text NOT NULL,
  section text NOT NULL,
  url text NOT NULL,
  text text NOT NULL,
  char_start int NOT NULL,
  char_end int NOT NULL,
  embedding vector({EMBED_DIM}) NOT NULL,
  tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', title || ' ' || text)) STORED
);
CREATE INDEX IF NOT EXISTS passages_emb_idx ON passages USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS passages_tsv_idx ON passages USING gin (tsv);
"""

COLS = ("id", "source_id", "title", "section", "url", "text", "char_start", "char_end")


def _hit(r):
    return {
        "id": r[0],
        "text": r[1],
        "score": float(r[6]),
        "source": {"title": f"{r[5]} {r[2]}", "section": r[3], "url": r[4]},
    }


class PgVectorStore(VectorStore):
    def __init__(self, dsn: str, table: str = "passages"):
        self.dsn = dsn
        self.table = table

    def _conn(self):
        conn = psycopg.connect(self.dsn, autocommit=True)
        register_vector(conn)
        return conn

    def init(self, reset: bool = False) -> None:
        with psycopg.connect(self.dsn, autocommit=True) as c:
            c.execute("CREATE EXTENSION IF NOT EXISTS vector")  # before register_vector
            if reset:
                c.execute(f"DROP TABLE IF EXISTS {self.table}")
            c.execute(SCHEMA.replace("passages", self.table))

    def upsert(self, rows, embeddings) -> None:
        sql = (
            f"INSERT INTO {self.table} ({','.join(COLS)}, embedding) "
            f"VALUES ({','.join(['%s'] * (len(COLS) + 1))}) "
            "ON CONFLICT (id) DO UPDATE SET "
            + ",".join(f"{c}=EXCLUDED.{c}" for c in (*COLS[1:], "embedding"))
        )
        with self._conn() as c, c.cursor() as cur:
            cur.executemany(
                sql,
                [
                    (*[r[k] for k in COLS], np.array(e, dtype=np.float32))
                    for r, e in zip(rows, embeddings)
                ],
            )

    def search_dense(self, embedding, k):
        with self._conn() as c:
            cur = c.execute(
                f"SELECT id, text, title, section, url, source_id, "
                f"1 - (embedding <=> %s) AS score FROM {self.table} "
                "ORDER BY embedding <=> %s LIMIT %s",
                (np.array(embedding, dtype=np.float32),) * 2 + (k,),
            )
            return [_hit(r) for r in cur.fetchall()]

    def search_lexical(self, query, k):
        # OR the terms: a natural-language question ANDed together matches nothing.
        # ponytail: ts_rank, not true BM25 (no IDF/length normalisation across corpus)
        with self._conn() as c:
            cur = c.execute(
                f"WITH q AS (SELECT replace(plainto_tsquery('english', %s)::text, '&', '|')::tsquery AS q) "
                f"SELECT id, text, title, section, url, source_id, ts_rank(tsv, q.q) AS score "
                f"FROM {self.table}, q WHERE tsv @@ q.q ORDER BY score DESC, id LIMIT %s",
                (query, k),
            )
            return [_hit(r) for r in cur.fetchall()]

    def count(self) -> int:
        with self._conn() as c:
            return c.execute(f"SELECT count(*) FROM {self.table}").fetchone()[0]
