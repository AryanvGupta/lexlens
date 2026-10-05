from dataclasses import asdict

from app.config import DATABASE_URL
from app.store.pgvector_store import PgVectorStore

from .chunk import chunk_source
from .embed import embed_passages
from .fetch import fetch_all


def main() -> None:
    store = PgVectorStore(DATABASE_URL)
    store.init(reset=True)  # derived data: every ingest is a full rebuild
    for source, path in fetch_all():
        chunks = chunk_source(source, path.read_text(encoding="utf-8"))
        store.upsert(
            [asdict(c) for c in chunks], embed_passages([f"{c.title}\n{c.text}" for c in chunks])
        )
        print(f"{source['id']}: {len(chunks)} chunks")
    print(f"total rows: {store.count()}")


main()
