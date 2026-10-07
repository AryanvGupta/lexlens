import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import type { Rag } from "./clients/rag.js";
import { RagError } from "./clients/rag.js";

/** The two non-tool MCP primitives: a resource (corpus source list) and a prompt template (query tuning workflow). */
export function registerPrimitives(server: McpServer, rag: Rag) {
  server.registerResource(
    "corpus_sources",
    "lexlens://corpus/sources",
    {
      title: "Corpus sources",
      description: "The pinned U.S. Code titles that search_legal and ask_legal draw from (id, title, source URL).",
      mimeType: "application/json",
    },
    async (uri) => {
      try {
        return { contents: [{ uri: uri.href, mimeType: "application/json", text: JSON.stringify(await rag.sources(), null, 2) }] };
      } catch (e) {
        throw new Error(e instanceof RagError ? e.message : "Could not read corpus sources");
      }
    },
  );

  server.registerPrompt(
    "tune_query",
    {
      title: "Tune a slow query",
      description: "Walk through explain_query_plan, suggest_indexes and compare_plans for a query on the pagila sample database.",
      argsSchema: { sql: z.string().min(1).max(5000).describe("The SELECT query to tune") },
    },
    ({ sql }) => ({
      messages: [
        {
          role: "user" as const,
          content: {
            type: "text" as const,
            text: [
              "Tune this query on the pagila sample database (read-only; SELECT statements only).",
              "1. Call explain_query_plan and say where the time goes.",
              "2. Call suggest_indexes. Report whether each suggestion was validated with a hypothetical index, and whether the planner would use it.",
              "3. If a query rewrite could help (for example avoiding a function on an indexed column), call compare_plans with the original and the rewrite.",
              "Do not claim an improvement unless compare_plans or the hypothetical-index evidence shows it, and say if the rewrite returns different rows.",
              "",
              "Query:",
              sql,
            ].join("\n"),
          },
        },
      ],
    }),
  );
}
