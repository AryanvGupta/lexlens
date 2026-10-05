import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.config import DATABASE_URL
from app.generation.ask import ask as run_ask
from app.generation.llm import anthropic_call
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


class AskRequest(BaseModel):
    question: str
    k: int = 8


@app.post("/ask")
def ask(req: AskRequest):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(503, "ANTHROPIC_API_KEY is not set")
    return run_ask(PgVectorStore(DATABASE_URL), anthropic_call, req.question, req.k)
