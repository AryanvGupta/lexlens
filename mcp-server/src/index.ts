import { pathToFileURL } from "node:url";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { RagClient, type Rag } from "./clients/rag.js";
import { createHttpApp } from "./http.js";
import { registerAskLegal } from "./tools/askLegal.js";
import { registerPrimitives } from "./primitives.js";
import { registerSqlTools } from "./tools/sqlTools.js";
import { SampleDb, type Sql } from "./sql/db.js";
import { registerSearchLegal } from "./tools/searchLegal.js";
import { instrumentTools } from "./metrics.js";

export function buildServer(rag: Rag, sql: Sql = new SampleDb(undefined)): McpServer {
  const server = instrumentTools(new McpServer({ name: "lexlens", version: "0.1.0" }));
  registerSearchLegal(server, rag);
  registerAskLegal(server, rag);
  registerSqlTools(server, sql);
  registerPrimitives(server, rag);
  return server;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const rag = new RagClient(process.env.RAG_API_URL ?? "http://localhost:8000");
  const sql = new SampleDb(process.env.SAMPLE_DB_URL);
  if (process.env.MCP_TRANSPORT === "http") {
    const port = Number(process.env.PORT ?? 3000);
    const hosts = (process.env.MCP_ALLOWED_HOSTS ?? "localhost,127.0.0.1").split(",").map((h) => h.trim());
    createHttpApp(() => buildServer(rag, sql), hosts, process.env.MCP_AUTH_TOKEN ?? "").listen(port, "0.0.0.0", () =>
      console.error(`lexlens MCP server listening on http://0.0.0.0:${port}/mcp`),
    );
  } else {
    await buildServer(rag, sql).connect(new StdioServerTransport());
    console.error("lexlens MCP server running on stdio");
  }
}
