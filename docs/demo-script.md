# 2-minute demo script

Recording plan: Claude Code in a terminal, using the stdio MCP server. About 280 spoken words at a normal pace fills two minutes, so trim beat 5 first if you run long.

Numbers in the narration come from the committed README tables and [docs/sql-worked-example.md](sql-worked-example.md). Live output will differ slightly (the model words its answers differently each time, and timings vary), so say "about" and do not read digits off the screen that you have not checked.

## Before you record

1. Start the services (once): `make dev-ingest`, `make dev-sample-db`, then in another terminal
   ```bash
   set -a && . ./.env && set +a
   cd rag-api && uv run uvicorn app.main:app --port 8000
   ```
   Wait until `curl -s localhost:8000/ready` says `ready`. `.env` needs `ANTHROPIC_API_KEY` and the three sample-DB values.
2. Build the MCP server: `cd mcp-server && npm install && npm run build`.
3. Register it **before** recording, using the `claude mcp add` command in [mcp-server/README.md](../mcp-server/README.md). That command contains the read-only database password, so do not run it on camera, and clear the terminal scrollback afterwards.
4. Open Claude Code in an empty directory and confirm the five lexlens tools are listed.
5. Warm up: make one throwaway `search_legal` call (the first search builds the in-memory BM25 index), then clear the screen.
6. Each `ask_legal` call is one real model call (a few cents). Rehearse once or twice, not ten times.
7. Hide anything that shows `.env`, the API key, or the registration command.

## Beats

| time | on screen | say | do |
|---|---|---|---|
| 0:00 to 0:12 | README top: the architecture diagram | "LexLens answers questions about the U.S. Code with verified citations, refuses when the evidence is thin, and exposes all of it to any MCP client. Here it is in Claude Code." | scroll the README to the diagram, then switch to the terminal |
| 0:12 to 0:45 | Claude Code | "I'll ask a real question. It retrieves passages with dense and BM25 search plus a cross-encoder rerank, the model answers, and every quote is checked as an exact substring of the passage it cites. Here is the fair-use answer, citing section 107. A quote that could not be verified would be dropped and flagged." | type: `Using lexlens, what factors decide whether a use of a copyrighted work is a fair use?` Let the `ask_legal` call and the cited answer show. |
| 0:45 to 1:05 | Claude Code | "Now something it should not answer. The federal minimum wage is not in Titles 11, 17, 28 or 35, so it refuses instead of guessing. In my eval it refused all ten unanswerable questions." | type: `Using lexlens, what is the federal minimum wage?` Expect `REFUSED: ...` |
| 1:05 to 1:40 | Claude Code | "The same server has SQL tuning tools against a sample database, read-only by construction. I ask why this query is slow. It reads about fifty-one thousand rows to return twenty. The obvious index looks right, but the tool tests it with a hypothetical index and reports the planner would not use it, because the function on the column hides it. Rewriting it as a range is about three hundred and fifty times faster in my worked example." | type: ``Using lexlens's SQL tools: why is `SELECT * FROM rental WHERE date_trunc('day', rental_date) = '2024-06-15'` slow, and would an index help?`` Then, if it does not offer the rewrite, ask: `Rewrite it as a range on rental_date and compare the plans.` |
| 1:40 to 1:55 | README Results table, then `docs/what-broke.md` entry 2 | "The repo keeps the evals and a log of what broke. Refusal precision went from 0.526 to 0.833 once I traced the over-refusals to retrieval, not the refusal rule. That is measured on the same 44 questions, so it is not a held-out result." | scroll to the answers table, then the what-broke heading |
| 1:55 to 2:00 | README top | "That is LexLens: it runs locally with `make up`, and CI reruns the retrieval eval on every push." | stop |

## What I have and have not checked

- Checked: the five tools, the refusal behaviour (the minimum-wage question is one of the ten unanswerable eval questions and the answer eval refused all ten), the rerank/k=12 default and its eval numbers, the SQL example and its timings (from the committed worked example, run on a laptop).
- Not checked: how Claude Code renders the tool calls on your screen, whether a free-form SQL prompt makes the model call the three tools in the order above (the `tune_query` prompt in the MCP server walks through that workflow if it wanders), and Claude Desktop. Do a dry run.
- The fair-use answer cites live model output. If a run refuses a question the eval says is answerable (2 of the 44 are refused today, q033 and q038), pick another from [evals/dataset/questions.jsonl](../evals/dataset/questions.jsonl).

## If you want the Kubernetes credit

Pre-start the cluster (`make up`, `make ingest`) before recording and cut to a 10-second `kubectl --context kind-lexlens -n lexlens get pods` between beats 4 and 5, with one line: "The same system runs as a reproducible local Kubernetes deployment on kind." The MCP client in this script still talks to the locally run API, not to the cluster, so do not imply otherwise.
