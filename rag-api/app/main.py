import json
import logging
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import DATABASE_URL
from app.generation.ask import DEFAULT_K
from app.generation.ask import ask as run_ask
from app.generation.llm import anthropic_call
from app.ingest.fetch import sources as corpus_sources
from app.retrieval.search import Mode
from app.retrieval.search import search as run_search
from app.store.pgvector_store import PgVectorStore

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("lexlens")
_warm = threading.Event()  # set once the embedding and rerank models are loaded


def _warm_model() -> None:
    from app.ingest.embed import model
    from app.retrieval.rerank import model as rerank_model

    model()
    rerank_model()  # /ask defaults to rerank; loading it lazily would stall the first request
    _warm.set()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Load in the background so /health answers immediately and /ready flips when done.
    if os.environ.get("WARM_MODEL", "1") == "1":
        threading.Thread(target=_warm_model, daemon=True).start()
    yield


app = FastAPI(title="lexlens rag-api", lifespan=lifespan)


@app.middleware("http")
async def access_log(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["x-request-id"] = rid
    if request.url.path not in (
        "/health",
        "/ready",
    ):  # keep probe noise out of the logs
        log.info(
            json.dumps(
                {
                    "event": "request",
                    "request_id": rid,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "ms": round((time.perf_counter() - start) * 1000, 1),
                }
            )
        )
    return response


class SearchRequest(BaseModel):
    query: str
    k: int = 8
    mode: Mode = "hybrid"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    reasons = []
    if not _warm.is_set():
        reasons.append("models not loaded")
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=2) as c:
            c.execute("SELECT 1")
    except psycopg.Error:
        reasons.append("database unreachable")
    if reasons:
        return JSONResponse(
            {"status": "not ready", "reasons": reasons}, status_code=503
        )
    return {"status": "ready"}


@app.get("/sources")
def sources():
    return {"sources": corpus_sources()}


@app.post("/search")
def search(req: SearchRequest):
    store = PgVectorStore(DATABASE_URL)
    return {"results": run_search(store, req.query, req.k, req.mode)}


class AskRequest(BaseModel):
    question: str
    k: int = DEFAULT_K


@app.post("/ask")
def ask(req: AskRequest):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(503, "ANTHROPIC_API_KEY is not set")
    return run_ask(PgVectorStore(DATABASE_URL), anthropic_call, req.question, req.k)
