# lexlens MCP server

TypeScript MCP server (stdio) exposing the rag-api as two tools:

| tool | what it does |
|---|---|
| `search_legal` | ranked passages of U.S. Code Titles 11, 17, 28, 35 (`query`, `k` 1-10, `mode` hybrid/dense/lexical) |
| `ask_legal` | cited answer from retrieved passages, or `REFUSED: <reason>` (`question`, `k`) |
| `explain_query_plan` | `EXPLAIN (ANALYZE, BUFFERS)` on a SELECT against the pagila sample DB, summarized: slowest nodes, big seq scans, estimate mismatches |
| `suggest_indexes` | candidate indexes for a SELECT, validated with hypothetical indexes (hypopg) when available |
| `compare_plans` | before/after SELECT: median runtime, cost, buffers and plan-shape differences |

Also exposes one resource (`lexlens://corpus/sources`, the pinned corpus list) and one prompt (`tune_query`).

The SQL tools are read-only by construction (parser guard, read-only transaction, SELECT-only role). See [docs/sql-worked-example.md](../docs/sql-worked-example.md) for a real before/after run.

The SQL tools need the sample database (`make dev-sample-db`, or `make up` for the cluster; then `SAMPLE_DB_URL` from `.env`). The legal tools need the rag-api running (`make dev-ingest` once, then `uv run uvicorn app.main:app` in `rag-api/`, with `ANTHROPIC_API_KEY` set for `ask_legal`).

```bash
cd mcp-server && npm install && npm run build
```

## Connect a client

Claude Code:

```bash
claude mcp add --scope user lexlens -e RAG_API_URL=http://localhost:8000 -e SAMPLE_DB_URL=postgresql://lexlens_ro:<SAMPLE_DB_RO_PASSWORD>@localhost:5433/pagila -- node /ABSOLUTE/PATH/TO/lexlens/mcp-server/dist/index.js
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "lexlens": {
      "command": "node",
      "args": ["/ABSOLUTE/PATH/TO/lexlens/mcp-server/dist/index.js"],
      "env": {
        "RAG_API_URL": "http://localhost:8000",
        "SAMPLE_DB_URL": "postgresql://lexlens_ro:<SAMPLE_DB_RO_PASSWORD>@localhost:5433/pagila"
      }
    }
  }
}
```

Smoke test against the live stack: `node scripts/e2e.mjs` (makes one real `ask_legal` call, about a cent or two).
