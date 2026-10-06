import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import type { Rag } from "../clients/rag.js";
import { guarded } from "./util.js";

export function registerAskLegal(server: McpServer, rag: Rag) {
  server.registerTool(
    "ask_legal",
    {
      title: "Ask a question about the U.S. Code",
      description:
        "Answer a question using only retrieved passages of U.S. Code Titles 11, 17, 28 and 35. Every citation quote is verified against the passage text. If the passages do not support an answer the result starts with REFUSED and a reason; that is a normal outcome, not an error. General information, not legal advice. Calls an LLM, so it is slower and costs more than search_legal.",
      inputSchema: {
        question: z.string().min(1).max(500).describe("The legal question"),
        k: z.number().int().min(1).max(10).default(8).describe("Passages to retrieve as evidence"),
      },
      annotations: { readOnlyHint: true, openWorldHint: false },
    },
    ({ question, k }) =>
      guarded(async () => {
        const r = await rag.ask(question, k);
        if (r.refused) return `REFUSED: ${r.reason}`;
        const title = new Map(r.retrieved.map((p) => [p.id, p.source.title]));
        const cites = r.citations
          .map((c) => `- [${c.passage_id}] (${title.get(c.passage_id) ?? "unknown source"}) "${c.quote}"`)
          .join("\n");
        const dropped = r.dropped_citations ? `\n(${r.dropped_citations} unverifiable citation(s) were dropped)` : "";
        return `ANSWER: ${r.answer}\n\nCITATIONS:\n${cites}${dropped}`;
      }),
  );
}
