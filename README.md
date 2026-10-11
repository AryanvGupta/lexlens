# LexLens

A RAG service over public U.S. Code text that answers with verified citations and refuses when the evidence is thin, exposed to any MCP client (Claude Code, Claude Desktop, VS Code) through a TypeScript MCP server.

Corpus: U.S. Code Titles 11 (Bankruptcy), 17 (Copyrights), 28 (Judiciary), 35 (Patents), 2023 edition, from govinfo.gov (public domain; see [docs/data-sources.md](docs/data-sources.md)). General information from statute text, not legal advice.

**Status: complete for its planned scope** (ingest, dense / BM25-hybrid / reranked retrieval, grounded `/ask` with verified citations and refusal, an MCP server over stdio and streamable HTTP with `search_legal`, `ask_legal` and three read-only SQL-performance tools, a reproducible local Kubernetes deployment on kind, and CI with a retrieval regression gate). Read [Limitations](#limitations) for what has not been verified. Eval results are in [evals/results/](evals/results/) and summarized [below](#results); every failure and fix is logged in [docs/what-broke.md](docs/what-broke.md). The SQL tools have a real before/after run in [docs/sql-worked-example.md](docs/sql-worked-example.md).

```
MCP client --stdio or HTTP--> mcp-server (TypeScript) --HTTP--> rag-api (FastAPI) --> Postgres + pgvector
                                     |                                 |
                                     |                                 +--> Anthropic API (answers only)
                                     +--SQL (read-only role)--> sample-db (Postgres + pagila)
```

## Run it on Kubernetes (kind)

This is a reproducible local Kubernetes deployment on [kind](https://kind.sigs.k8s.io/), not a production setup: one node, no ingress, and no authentication on the MCP HTTP endpoint unless you set `MCP_AUTH_TOKEN` (see below). Reach it through port-forward only.

Prerequisites: [Docker](https://docs.docker.com/get-docker/), [kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation), [kubectl](https://kubernetes.io/docs/tasks/tools/), `make`. Images include PyTorch, so leave several GB of free disk. You also need `python3` on the host (`make eval` runs `evals/compare.py`) and network access (ingest downloads about 12 MB of statute HTML from govinfo.gov inside the cluster); `uv` installs Python 3.12 for `rag-api` by itself. Timings measured from a fresh clone on an M-series Mac with a warm Docker cache and an 8-CPU Docker VM, while other jobs were running: `make up` 15 min (most of it `kind load docker-image`, which prints one line per image and then looks frozen), `make ingest` 7.5 min, `make eval` 3.5 min, `k8s/verify-probes.sh` 28 s. A machine without cached Docker images will take longer. Only `/ask` needs an [Anthropic API key](https://console.anthropic.com); everything else here is free.

```bash
cp .env.example .env     # set POSTGRES_PASSWORD, SAMPLE_DB_ADMIN_PASSWORD, SAMPLE_DB_RO_PASSWORD (any non-empty values, e.g. `openssl rand -hex 12`); ANTHROPIC_API_KEY is optional; DATABASE_URL and SAMPLE_DB_URL are only for the compose path
make up                  # kind cluster, builds 3 images, deploys postgres, sample-db, rag-api (2 replicas), mcp-server
make ingest              # in-cluster Job: loads the corpus (2,852 passages)
make eval                # in-cluster Job: retrieval eval; ends with a 16-row comparison table and `OK: reproduced within +/- 0.01`
make forward             # rag-api on :8000, MCP on :3000 (Ctrl-C to stop)
k8s/verify-probes.sh     # about 30 s: delete a rag-api pod while polling the Service; prints OK
make down                # delete the cluster
```

With `make forward` running, `curl localhost:8000/health` returns `{"status":"ok"}` and `/search` works without an API key; `/ask` returns 503 `ANTHROPIC_API_KEY is not set` until a key is in the cluster Secret.

The secret is built from `.env` at deploy time by `make up` (`k8s/make-secret.sh`) and is never written to git. The `up`, `ingest`, `eval` and `forward` targets use the `kind-lexlens` kube context explicitly, so they never touch your current context. `make down` deletes the cluster. `k8s/verify-probes.sh` deletes a `rag-api` pod while polling the Service from inside the cluster, and passes only if every request returned 200 (the other replica kept serving, and the replacement got no traffic until it was Ready). It covers the startup and readiness probes, not the liveness probe or the single-replica `mcp-server`.

With `make forward` running, connect an MCP client over HTTP:

```bash
claude mcp add --transport http lexlens http://localhost:3000/mcp
```

The endpoint is stateless streamable HTTP. Other clients: see [mcp-server/README.md](mcp-server/README.md).

**Optional bearer-token auth (off by default).** Put a long random value in `.env` (`MCP_AUTH_TOKEN=$(openssl rand -hex 32)`) and run `make up` again (it re-applies the Secret and restarts the deployments). With a token set, every `/mcp` request needs `Authorization: Bearer <token>` or gets HTTP 401; `/healthz` stays open for the kubelet probes. The token travels in plain HTTP, so keep using port-forward. The server side is covered by tests (`mcp-server/test/httpAuth.test.ts`); registering a client with the header, for example `claude mcp add --transport http lexlens http://localhost:3000/mcp --header "Authorization: Bearer $MCP_AUTH_TOKEN"`, is untested with a real client (check the flag with `claude mcp add --help`).

## Run it without Kubernetes (docker compose)

The `dev-*` targets run Postgres in Docker Compose and the API and MCP server directly on your machine.

Prerequisites: [Docker](https://docs.docker.com/get-docker/), [uv](https://docs.astral.sh/uv/), Node.js 22+ (tested with 26), `make`. Only `/ask` needs an [Anthropic API key](https://console.anthropic.com); search, ingest and retrieval evals do not.

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

`/search` takes `mode`: `hybrid` (default), `dense`, `lexical`, `rerank` (hybrid candidates re-ordered by a local cross-encoder) or `rewrite` (experimental, see Limitations); the MCP `search_legal` tool exposes neither of the last two. `/ask` uses `rerank` with `k` = 12 unless you pass `k`; both models load at startup and `/ready` waits for them (in the cluster images both are baked in; locally the reranker, about 90 MB, downloads on first start). `/ask` returns `answer`, verified `citations`, `refused` and `reason`. An unanswerable question (try "What is the federal minimum wage?") comes back with `refused: true`.

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

Results are written to `evals/results/`. Models are configurable with `GEN_MODEL`, `GEN_EFFORT` and `JUDGE_MODEL` (defaults in `rag-api/app/config.py`). The answer eval is not run by `make eval` and has not been moved into the cluster. CI (`.github/workflows/ci.yml`) runs lint, unit tests, gitleaks, and a retrieval regression gate: it ingests the corpus into a pgvector service, runs the retrieval eval, and fails if any metric drops more than 0.05 (about two questions) below the committed `evals/results/retrieval.json`. It needs no API key; the answer eval is not run in CI because it costs money.

## Results

Dataset: 58 questions in [evals/dataset/questions.jsonl](evals/dataset/questions.jsonl) (44 answerable with section-level gold, 10 unanswerable, 4 adversarial). Retrieval numbers below come from `make dev-eval`. All four rows (16 metrics) were reproduced inside the kind cluster with `make eval`, identical to the committed values, and the CI runner reproduces them too.

**Retrieval** (44 answerable questions)

| mode | recall@1 | recall@5 | recall@10 | mrr@20 |
|---|---|---|---|---|
| dense | 0.750 | 0.920 | 0.955 | 0.830 |
| lexical | 0.409 | 0.648 | 0.716 | 0.513 |
| hybrid | 0.659 | 0.920 | 0.955 | 0.781 |
| rerank | 0.716 | 0.920 | 0.966 | 0.823 |

`rerank` re-orders the top 30 hybrid candidates with `cross-encoder/ms-marco-MiniLM-L-6-v2`. Its recall@1 and MRR point estimates are higher than hybrid's and slightly below dense's, but those differences are not distinguishable with 44 questions (intervals below), and it adds latency: 313 ms vs 57 ms for hybrid at p50 on a warm M2 laptop (`evals/search_latency.py`), but about 1.8 s vs 75 ms in the kind cluster (10 requests each through the Service, k=12; the Docker VM has 8 CPUs and the pod requests 250m). The gap is compute, not configuration (same speed in a plain `docker run`, no CPU limit, weak thread scaling): the laptop has Apple matrix hardware and the Linux VM runs plain fp32 kernels. Shrinking `RERANK_POOL` is not free; see [what broke #2](docs/what-broke.md). Section-level metrics hide its main benefit, which shows at chunk level and in the answer eval below (`evals/chunk_probe.py`, [what broke #2](docs/what-broke.md)).

Hybrid is weighted reciprocal rank fusion of dense and BM25 at 2:1 (`lexical` mode is still Postgres `ts_rank`). An earlier equal-weight RRF over dense + `ts_rank` scored 0.614 / 0.784 / 0.864 / 0.697, below dense; the weights and BM25 were chosen from the sweep in [evals/results/experiments/fusion/summary.md](evals/results/experiments/fusion/summary.md), on the same 44 questions, so treat the gain as unconfirmed on unseen questions. Hybrid now matches dense at recall@5 and @10; its recall@1 and MRR point estimates are lower than dense's, though not distinguishably so (intervals below). `/search` defaults to hybrid; `/ask` defaults to rerank at k=12.

**Answers** (the `/ask` default: rerank, k=12; `claude-sonnet-5-5` at low effort, judge `claude-haiku-4-5`; 54 questions + 4 adversarial)

| metric | value |
|---|---|
| citation validity (verbatim-quote check) | 1.000 (0.995 to 1.000 over 4 runs) |
| answers citing a gold section | 1.000 |
| faithfulness (LLM judge) | 1.000 (0.976 to 1.000 over 4 runs) |
| judge vs. human agreement | not yet measured |
| refusal precision / recall | 0.833 / 1.000 (identical in all 4 runs) |
| injection followed | 0/4 |
| LLM latency p50 / p95 | 3.7 s / 6.1 s |
| cost per 100 questions (token-based) | $1.76 |

History of refusal precision: 0.526 with the first equal-weight hybrid (9 over-refusals), 0.667 after weighted BM25 hybrid at k=8 (5), 0.833 with rerank at k=12 (2). Read the table with three caveats. Refusal precision is better but not solved: all 10 unanswerable questions are refused, but 2 of the 44 answerable ones are too (12 refusals, 10 correct): `q038` (the answering chunk is outside the 30 candidates rerank sees) and `q033` (the question's wording does not match the statute's; see [what broke #2](docs/what-broke.md)). The configuration was chosen and measured on the same questions, with one run each, so one question is 2.3 points of precision and these gains are not a held-out estimate. And faithfulness comes from an LLM judge that has not been checked against human labels yet, so treat the faithfulness number as unvalidated until `evals/results/faithfulness_samples.csv` is hand-labelled.

**How the default was chosen** (`ANSWER_MODE` / `ANSWER_K` env vars select a config, `EVAL_RESULTS` an output directory; details and limits in [what broke #2](docs/what-broke.md))

| config | refusal precision | over-refused (of 44) | faithfulness | $/100 q | retrieval p50 |
|---|---|---|---|---|---|
| hybrid, k=8 (previous default) | 0.667 | 5 | 0.974 | $1.36 | 57 ms |
| hybrid, k=12 | 0.667 | 5 | 0.923 | $1.72 | 57 ms |
| **rerank, k=12 (current default)** | 0.833 | 2 | 1.000 | $1.76 | 313 ms |

One run per config on the same 44 questions, so differences of one question are noise; the latency column is warm on an M2 laptop; in the kind cluster rerank is about 1.8 s at p50 and hybrid 75 ms, which makes rerank about half (49%) of the 3.7 s LLM call there.

**How much to trust these numbers** (95% bootstrap intervals over the 44 questions, 10,000 resamples, seed 0: `evals/bootstrap.py`, `evals/results/experiments/bootstrap/`)

| mode | recall@5 | MRR@20 |
|---|---|---|
| dense | 0.920 [0.841, 0.989] | 0.830 [0.733, 0.914] |
| lexical | 0.648 [0.511, 0.784] | 0.513 [0.387, 0.635] |
| hybrid | 0.920 [0.841, 0.989] | 0.781 [0.682, 0.870] |
| rerank | 0.920 [0.841, 0.989] | 0.823 [0.732, 0.907] |

Every paired difference among dense, hybrid and rerank (recall@5 and MRR@20) has an interval that includes zero, for example rerank minus hybrid MRR@20 is +0.043 [-0.051, +0.137]. With 44 questions the retrieval data cannot rank those three; only "lexical alone is worse" is supported. The case for rerank rests on the answer-level result, not on these retrieval metrics.

The default answer-eval configuration (rerank, k=12) was rerun three more times with empty caches, so generation and the judge were both sampled again (`evals/variance_report.py`, `evals/results/experiments/variance/`). Refusal precision was 0.833 in all four runs, and `q033` and `q038` were over-refused in all four. Faithfulness was 1.000 in the committed run and 0.976 in all three reruns, and citation validity was 0.995 to 1.000, so about 0.98 is the more representative faithfulness figure. Comparing the two answer configurations directly, rerank at k=12 answers `q018`, `q036` and `q037` where hybrid at k=8 refused, and refuses none that hybrid at k=8 answered; with only three differing questions an exact sign test gives p = 0.25, so this result alone cannot rule out chance. Hybrid at k=8 was run once.

## What broke (highlights)

The full log, with symptoms, diagnosis, root cause, fix and evidence, is [docs/what-broke.md](docs/what-broke.md). Four entries:

- **Hybrid retrieval scored below dense (M2).** The section heading was neither embedded nor in the full-text index. Embedding `title + text` lifted hybrid recall@5 from 0.659 to 0.784; replacing equal-weight RRF over `ts_rank` with weighted fusion of dense and BM25 later brought it to 0.920, equal to dense.
- **The system refused answerable questions (M3).** Refusal precision was 0.526. Reading the model's own refusal reasons showed the answering passage was not being retrieved, so the refusal rule was fine and retrieval was the problem. A chunk-level probe predicted which questions a cross-encoder rerank at k=12 would fix, and the answer eval then confirmed it: precision 0.833.
- **The SQL safety guard ran after the database connection opened (M5).** A test written to prove a rejected `DROP TABLE` never touches the database failed. The guard now runs first.
- **The reranker could not load in the cluster, and `make up` kept the old image (M7).** The image baked in only one model and forbids downloads at startup, so the pods crash-looped on the startup probe while local tests passed. Both causes were fixed and the cluster checks re-run.

## Limitations

- **Scope.** Statute text from four Titles of the 2023 U.S. Code only: no case law, no regulations, no updates. General information, not legal advice.
- **Evaluation.** 58 questions (44 answerable, 10 unanswerable, 4 adversarial) written by the author. The same questions were used to diagnose problems and to measure fixes, so the gains here are not held-out results, and the default configuration was rerun three more times (refusal precision identical, faithfulness 0.976 to 1.000) while the other configurations were run once. One answerable question is about 2.3 points of refusal precision.
- **Faithfulness is unvalidated.** It comes from an LLM judge that has not been compared with human labels; `evals/results/faithfulness_samples.csv` is waiting to be hand-labelled.
- **Query rewriting did not help.** An opt-in LLM rewrite step (`mode=rewrite`, claude-haiku-4-5, about 1.4 s extra per request) pulls the `q033` gold section into the candidate pool but does not change top-12 recall on the dev set (0.977 with and without it), because the reranker still ranks it outside the top 12. It is off by default and kept as a documented negative result: `evals/results/experiments/rewrite/retrieval.md`.
- **Over-refusal remains.** Two of the 44 answerable questions are still refused: one because the question's wording does not match the statute's ("related state-law claims" vs "supplemental jurisdiction"), one because the answering chunk is outside the 30 candidates rerank sees.
- **Retrieval trade-offs.** Hybrid's recall@1 and MRR point estimates trail dense's, though not distinguishably with 44 questions. Rerank improves answers but costs about 1.8 s per search in the cluster (compute-bound on this hardware) against 75 ms for hybrid. Two opt-in speed options exist, both off by default and not the measured configuration: `RERANK_OPT=batch8` (same model scored in batches of 8, about 15 to 19% faster, identical rankings on all 58 dev questions) and `RERANK_OPT=int8` (dynamic int8 quantization, about 43% faster in the container, 0.85 s vs 1.5 s for the rerank step; the top-12 set changes for 40 of 58 questions, and in one answer-eval run refusal behaviour was identical but faithfulness was 0.929 against 0.976 to 1.000 for the default, which one run cannot explain). Details: [what broke #2](docs/what-broke.md).
- **Deployment.** One-node local kind cluster, no authentication on the MCP HTTP endpoint, not production. Startup and readiness probes were verified by deleting a `rag-api` pod; the liveness probe and the single-replica `mcp-server` were not. A live `/ask` was not run inside the cluster (the answer eval runs locally), and `make up` was not tried on a machine without cached Docker images.
- **Clients.** The HTTP MCP endpoint was tested with raw protocol calls and the SDK client in the test suite, and the stdio server with the SDK client. It has not been tried with Claude Code or Claude Desktop in this repo's tests.
- **Corpus size.** 2,852 passages. A bigger corpus was tested for retrieval only (`evals/scale_experiment.py`, results in `evals/results/experiments/scale/`): adding unrelated Titles to reach about 3x and 10x the passages left recall@10 unchanged at 3x and 0 to 2 questions lower at 10x (dense 0.955 to 0.909, hybrid 0.955 to 0.932, rerank 0.966 to 0.943), none distinguishable from noise with 44 questions, and the remaining failures did not change. The costs that are clear are the in-process BM25 index (heap 16 MB at 1x to 164 MB at 10x, build 0.2 s to 2.1 s) and hybrid latency (p50 59 ms to 77 ms); dense search stayed flat at about 33 ms. Answer-level metrics were not measured at scale (the extra Titles make some of the dev set's unanswerable questions answerable), and unrelated Titles are a weaker test than realistic growth.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `make up` looks frozen for 10+ minutes at `kind load docker-image` | Normal on a first run: it loads three images (about 2.7 GB for `rag-api`) and prints one line per image. |
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
