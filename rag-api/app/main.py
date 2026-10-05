from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app.config import DATABASE_URL
from app.ingest.embed import embed_query
from app.store.pgvector_store import PgVectorStore

app = FastAPI(title="lexlens rag-api")


class SearchRequest(BaseModel):
    query: str
    k: int = 8
    mode: Literal["dense"] = "dense"  # lexical, hybrid arrive in M2


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/search")
def search(req: SearchRequest):
    return {
        "results": PgVectorStore(DATABASE_URL).search_dense(
            embed_query(req.query), req.k
        )
    }
