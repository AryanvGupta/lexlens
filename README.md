# LexLens

A RAG service over public U.S. Code text that answers with verified citations and refuses when the evidence is thin, exposed to any MCP client (Claude Code, Claude Desktop, VS Code) through a TypeScript MCP server.

Corpus: U.S. Code Titles 11 (Bankruptcy), 17 (Copyrights), 28 (Judiciary), 35 (Patents), 2023 edition, from govinfo.gov (public domain; see [docs/data-sources.md](docs/data-sources.md)). General information from statute text, not legal advice.

**Status: work in progress.** Built so far: ingest, dense/lexical/hybrid retrieval, grounded `/ask`, evals, and an MCP server with `search_legal`, `ask_legal` and three read-only SQL-performance tools (`explain_query_plan`, `suggest_indexes`, `compare_plans`, see [docs/sql-worked-example.md](docs/sql-worked-example.md)). Not built yet: Kubernetes deployment, final write-up. `make up` and `make down` are placeholders. Eval results are in [evals/results/](evals/results/); known failures are logged in [docs/what-broke.md](docs/what-broke.md).

```
MCP client --stdio--> mcp-server (TypeScript) --HTTP--> rag-api (FastAPI) --> Postgres + pgvector
                              |                                  |
                              |                                  +--> Anthropic API (answers only)
                              +--SQL (read-only role)--> sample-db (Postgres + pagila)
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

**4. (Optional) Start the sample database for the SQL tools** (builds a Postgres 18 image with hypopg and loads [pagila](docs/data-sources.md); about 13 MB download, a minute or two)

```bash
make sample-db
```

Needs `SAMPLE_DB_ADMIN_PASSWORD`, `SAMPLE_DB_RO_PASSWORD` and `SAMPLE_DB_URL` in `.env` (see `.env.example`; the URL uses the read-only password and port 5433).

**5. Use it from an MCP client**

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
make test          # pytest + vitest (no API calls; SQL live tests run only if sample-db is up)
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
| SQL tool says "SAMPLE_DB_URL is not set" or "unreachable" | Run `make sample-db`, and pass `SAMPLE_DB_URL` in the MCP client config (see mcp-server/README.md). |
| MCP client shows no tools | `mcp-server/dist/` is missing: run `npm run build`. |

## License

MIT. Data sources and terms (U.S. Code via govinfo; Pagila, MIT): [docs/data-sources.md](docs/data-sources.md).
