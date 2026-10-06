# lexlens MCP server

TypeScript MCP server (stdio) exposing the rag-api as two tools:

| tool | what it does |
|---|---|
| `search_legal` | ranked passages of U.S. Code Titles 11, 17, 28, 35 (`query`, `k` 1-10, `mode` hybrid/dense/lexical) |
| `ask_legal` | cited answer from retrieved passages, or `REFUSED: <reason>` (`question`, `k`) |

Needs the rag-api running (`make ingest` once, then `uv run uvicorn app.main:app` in `rag-api/`, with `ANTHROPIC_API_KEY` set for `ask_legal`).

```bash
cd mcp-server && npm install && npm run build
```

## Connect a client

Claude Code:

```bash
claude mcp add --scope user lexlens -e RAG_API_URL=http://localhost:8000 -- node /ABSOLUTE/PATH/TO/lexlens/mcp-server/dist/index.js
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "lexlens": {
      "command": "node",
      "args": ["/ABSOLUTE/PATH/TO/lexlens/mcp-server/dist/index.js"],
      "env": { "RAG_API_URL": "http://localhost:8000" }
    }
  }
}
```

Smoke test against the live stack: `node scripts/e2e.mjs` (makes one real `ask_legal` call, about a cent or two).
