# LexLens

A RAG service over public U.S. Code text that answers with verified citations and refuses when the evidence is thin, exposed to any MCP client (Claude Code, Claude Desktop, VS Code) through a TypeScript MCP server.

Corpus: U.S. Code Titles 11 (Bankruptcy), 17 (Copyrights), 28 (Judiciary), 35 (Patents), 2023 edition, from govinfo.gov (public domain; see [docs/data-sources.md](docs/data-sources.md)). General information from statute text, not legal advice.

**Status: work in progress.** Built so far: ingest, dense/lexical/hybrid retrieval, grounded `/ask`, evals, MCP server with `search_legal` and `ask_legal`. Not built yet: SQL-performance MCP tools, Kubernetes deployment, final write-up. `make up` and `make down` are placeholders. Eval results are in [evals/results/](evals/results/); known failures are logged in [docs/what-broke.md](docs/what-broke.md).

```
MCP client --stdio--> mcp-server (TypeScript) --HTTP--> rag-api (FastAPI) --> Postgres + pgvector
                                                              |
                                                              +--> Anthropic API (answers only)
```

## Run it locally

Prerequisites: [Docker](https://docs.docker.com/get-docker/), [uv](https://docs.astral.sh/uv/), Node.js 22+, `make`. Only `/ask` needs an [Anthropic API key](https://console.anthropic.com); search, ingest and retrieval evals do not.

**1. Configure `.env`**

```bash
cp .env.example .env
```

Edit `.env`: pick a `POSTGRES_PASSWORD`, then set `DATABASE_URL` to match it (same password), and add `ANTHROPIC_API_KEY` if you want `/ask`. `.env` is git-ignored; never commit it.

```
POSTGRES_PASSWORD=choose-something
DATABASE_URL=postgresql://lexlens:choose-something@localhost:5432/lexlens
ANTHROPIC_API_KEY=sk-ant-...
```

**2. Install and ingest the corpus** (starts Postgres in Docker, downloads about 12 MB of statute HTML, downloads the embedding model on first run, takes a few minutes)

```bash
(cd rag-api && uv sync)
make ingest
```

Ingest is a full rebuild and is repeatable: it loads about 2,850 passages.

**3. Start the API** (leave it running; the first request takes about 10 s while the embedding model loads)

```bash
set -a && . ./.env && set +a
cd rag-api && uv run uvicorn app.main:app --port 8000
```

Try it from another terminal:

```bash
curl -s localhost:8000/search -H 'content-type: application/json' \
  -d '{"query": "When is an invention too obvious to be patented?", "k": 3, "mode": "hybrid"}'

curl -s localhost:8000/ask -H 'content-type: application/json' \
  -d '{"question": "How many years does a patent term last from filing?"}'
```

`mode` is `hybrid` (default), `dense` or `lexical`. `/ask` returns `answer`, verified `citations`, `refused` and `reason`. An unanswerable question (try "What is the federal minimum wage?") comes back with `refused: true`.

**4. Use it from an MCP client**

```bash
cd mcp-server && npm install && npm run build
```

Then register it with your client. Config snippets for Claude Code, Claude Desktop and VS Code are in [mcp-server/README.md](mcp-server/README.md). The API from step 3 must be running.

To inspect the tools without an AI client:

```bash
cd mcp-server && npx @modelcontextprotocol/inspector node dist/index.js
```

## Tests and evals

```bash
make lint          # ruff + tsc
make test          # pytest + vitest (no API calls)
make eval          # retrieval eval: recall@k and MRR per mode; free, needs ingested corpus
make eval-answers ARGS=--estimate   # cost estimate, no API calls
make eval-answers  # answer eval: real API calls (about $1 with claude-sonnet-5-5), LLM calls cached on disk
RUN_LIVE_TESTS=1 make test          # also runs the live prompt-injection test (one API call)
```

Results are written to `evals/results/`. Models are configurable with `GEN_MODEL`, `GEN_EFFORT` and `JUDGE_MODEL` (defaults in `rag-api/app/config.py`).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `make ingest` fails to connect | Docker Desktop is not running, or `DATABASE_URL` password differs from `POSTGRES_PASSWORD`. If you changed the password after the first run, `docker compose down -v` resets the database volume. |
| MCP tool says "rag-api is unreachable" | Step 3 is not running, or not on port 8000 (`RAG_API_URL` overrides it). |
| `/ask` returns 503 "ANTHROPIC_API_KEY is not set" | Start the API after `set -a && . ./.env && set +a`. |
| MCP client shows no tools | `mcp-server/dist/` is missing: run `npm run build`. |

## License

MIT. Data sources and terms: [docs/data-sources.md](docs/data-sources.md).
