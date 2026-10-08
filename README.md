# LexLens

A RAG service over public U.S. Code text that answers with verified citations and refuses when the evidence is thin, exposed to any MCP client (Claude Code, Claude Desktop, VS Code) through a TypeScript MCP server.

Corpus: U.S. Code Titles 11 (Bankruptcy), 17 (Copyrights), 28 (Judiciary), 35 (Patents), 2023 edition, from govinfo.gov (public domain; see [docs/data-sources.md](docs/data-sources.md)). General information from statute text, not legal advice.

**Status: work in progress.** Built so far: ingest, dense/lexical/hybrid retrieval, grounded `/ask`, evals, an MCP server (stdio and streamable HTTP) with `search_legal`, `ask_legal` and three read-only SQL-performance tools (`explain_query_plan`, `suggest_indexes`, `compare_plans`, see [docs/sql-worked-example.md](docs/sql-worked-example.md)), and a reproducible local Kubernetes deployment on kind. Not built yet: final write-up. Eval results are in [evals/results/](evals/results/) and summarized [below](#results); known failures are logged in [docs/what-broke.md](docs/what-broke.md).

```
MCP client --stdio or HTTP--> mcp-server (TypeScript) --HTTP--> rag-api (FastAPI) --> Postgres + pgvector
                                     |                                 |
                                     |                                 +--> Anthropic API (answers only)
                                     +--SQL (read-only role)--> sample-db (Postgres + pagila)
```

## Run it on Kubernetes (kind)

This is a reproducible local Kubernetes deployment on [kind](https://kind.sigs.k8s.io/), not a production setup: one node, no ingress, no authentication on the MCP HTTP endpoint (reach it through port-forward only).

Prerequisites: [Docker](https://docs.docker.com/get-docker/), [kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation), [kubectl](https://kubernetes.io/docs/tasks/tools/), `make`. Images include PyTorch, so leave several GB of free disk. Only `/ask` needs an [Anthropic API key](https://console.anthropic.com); everything else here is free.

```bash
cp .env.example .env     # set POSTGRES_PASSWORD, SAMPLE_DB_ADMIN_PASSWORD, SAMPLE_DB_RO_PASSWORD; ANTHROPIC_API_KEY is optional
make up                  # kind cluster, builds 3 images, deploys postgres, sample-db, rag-api (2 replicas), mcp-server
make ingest              # in-cluster Job: loads the corpus (2,852 passages)
make eval                # in-cluster Job: retrieval eval, then checks it reproduces the committed numbers (+/-0.01)
make forward             # rag-api on :8000, MCP on :3000 (Ctrl-C to stop)
```

The secret is built from `.env` at deploy time by `make up` (`k8s/make-secret.sh`) and is never written to git. The `up`, `ingest`, `eval` and `forward` targets use the `kind-lexlens` kube context explicitly, so they never touch your current context. `make down` deletes the cluster.

With `make forward` running, connect an MCP client over HTTP:

```bash
claude mcp add --transport http lexlens http://localhost:3000/mcp
```

The endpoint is stateless streamable HTTP. Other clients: see [mcp-server/README.md](mcp-server/README.md).

## Run it without Kubernetes (docker compose)

The `dev-*` targets run Postgres in Docker Compose and the API and MCP server directly on your machine.

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
make dev-ingest
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
make dev-sample-db
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
make lint          # ruff, tsc, and a render check of the k8s manifests
make test          # pytest + vitest (no API calls; SQL live tests run only if sample-db is up)
make eval          # in-cluster retrieval eval + reproduction check (free; needs make up and make ingest)
make dev-eval      # same retrieval eval against the docker-compose database
make dev-eval-answers ARGS=--estimate   # cost estimate, no API calls
make dev-eval-answers   # answer eval: real API calls (about $1 with claude-sonnet-5-5), LLM calls cached on disk
RUN_LIVE_TESTS=1 make test              # also runs the live prompt-injection test (one API call)
```

Results are written to `evals/results/`. Models are configurable with `GEN_MODEL`, `GEN_EFFORT` and `JUDGE_MODEL` (defaults in `rag-api/app/config.py`). The answer eval is not run by `make eval` and has not been moved into the cluster.

## Results

Dataset: 58 questions in [evals/dataset/questions.jsonl](evals/dataset/questions.jsonl) (44 answerable with section-level gold, 10 unanswerable, 4 adversarial). Retrieval numbers below were reproduced inside the kind cluster with `make eval`: all 12 metrics matched the committed values exactly.

**Retrieval** (44 answerable questions)

| mode | recall@1 | recall@5 | recall@10 | mrr@20 |
|---|---|---|---|---|
| dense | 0.750 | 0.920 | 0.955 | 0.830 |
| lexical | 0.409 | 0.648 | 0.716 | 0.513 |
| hybrid | 0.614 | 0.784 | 0.864 | 0.697 |

Hybrid (RRF over dense + lexical) still scores below dense on this dataset and is not yet tuned; see [what broke #1](docs/what-broke.md). `/ask` defaults to hybrid.

**Answers** (`claude-sonnet-5-5` at low effort, judge `claude-haiku-4-5`; 54 questions + 4 adversarial)

| metric | value |
|---|---|
| citation validity (verbatim-quote check) | 0.994 |
| answers citing a gold section | 0.943 |
| faithfulness (LLM judge) | 0.971 |
| judge vs. human agreement | not yet measured |
| refusal precision / recall | 0.526 / 1.000 |
| injection followed | 0/4 |
| LLM latency p50 / p95 | 3.9 s / 7.0 s |
| cost per 100 questions (token-based) | $1.39 |

Read these with two caveats. Refusal precision is weak: all 10 unanswerable questions are refused, but 9 of the 44 answerable ones are refused too (19 refusals, 10 correct). The diagnosis in [what broke #2](docs/what-broke.md) traces this to retrieval missing or under-retrieving the right passage, not to the refusal rule; no fix yet. And faithfulness comes from an LLM judge that has not been checked against human labels yet, so treat 0.971 as unvalidated until `evals/results/faithfulness_samples.csv` is hand-labelled.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `make up` hangs or the `docker` CLI never returns | Docker Desktop is wedged or the disk is full (the images are large). Free space, fully quit and reopen Docker Desktop, then rerun `make up`; it is safe to repeat. |
| `make up` fails with "POSTGRES_PASSWORD is missing or empty" | `k8s/make-secret.sh` reads `.env`; set `POSTGRES_PASSWORD`, `SAMPLE_DB_ADMIN_PASSWORD` and `SAMPLE_DB_RO_PASSWORD`. |
| `curl localhost:3000/mcp` returns 405 or 400 | It only accepts POST with `accept: application/json, text/event-stream`; a plain GET is rejected by design. |
| `make dev-ingest` fails to connect | Docker Desktop is not running, or `DATABASE_URL` password differs from `POSTGRES_PASSWORD`. If you changed the password after the first run, `docker compose down -v` resets the database volume. |
| MCP tool says "rag-api is unreachable" | Step 3 is not running, or not on port 8000 (`RAG_API_URL` overrides it). |
| `/ask` returns 503 "ANTHROPIC_API_KEY is not set" | Start the API after `set -a && . ./.env && set +a`. |
| SQL tool says "SAMPLE_DB_URL is not set" or "unreachable" | Run `make dev-sample-db` (or `make up` for the cluster), and pass `SAMPLE_DB_URL` in the MCP client config (see mcp-server/README.md). |
| MCP client shows no tools | `mcp-server/dist/` is missing: run `npm run build`. |

## License

MIT. Data sources and terms (U.S. Code via govinfo; Pagila, MIT): [docs/data-sources.md](docs/data-sources.md).
