# Build from the repo root: docker build -f rag-api/Dockerfile .
# torch is pinned to the CPU-only index for Linux in pyproject.toml (the default wheel pulls several GB of CUDA libraries).
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH HF_HOME=/opt/hf PYTHONUNBUFFERED=1
WORKDIR /app/rag-api
COPY rag-api/pyproject.toml rag-api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
# Bake both models into the image (HF_HUB_OFFLINE=1 below forbids downloads at startup).
# Keep these names in sync with EMBED_MODEL and RERANK_MODEL in rag-api/app/config.py.
RUN python -c "from sentence_transformers import CrossEncoder, SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5'); CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"
COPY rag-api/app app
COPY data/sources.json /app/data/sources.json
COPY evals/run_eval.py /app/evals/run_eval.py
COPY evals/dataset /app/evals/dataset
RUN useradd --uid 10001 --create-home lexlens \
    && mkdir -p /app/data/raw /app/evals/results \
    && chown -R lexlens /app/data /app/evals
USER 10001
ENV HF_HUB_OFFLINE=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
