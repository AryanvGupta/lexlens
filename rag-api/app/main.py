from fastapi import FastAPI
from pydantic import BaseModel

from app.config import DATABASE_URL
from app.retrieval.search import Mode
from app.retrieval.search import search as run_search
from app.store.pgvector_store import PgVectorStore

app = FastAPI(title="lexlens rag-api")


class SearchRequest(BaseModel):
    query: str
    k: int = 8
    mode: Mode = "hybrid"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/search")
def search(req: SearchRequest):
    store = PgVectorStore(DATABASE_URL)
    return {"results": run_search(store, req.query, req.k, req.mode)}
