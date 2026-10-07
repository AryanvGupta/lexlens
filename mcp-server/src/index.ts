import { pathToFileURL } from "node:url";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { RagClient, type Rag } from "./clients/rag.js";
import { registerAskLegal } from "./tools/askLegal.js";
import { registerPrimitives } from "./primitives.js";
import { registerSqlTools } from "./tools/sqlTools.js";
import { SampleDb, type Sql } from "./sql/db.js";
import { registerSearchLegal } from "./tools/searchLegal.js";

export function buildServer(rag: Rag, sql: Sql = new SampleDb(undefined)): McpServer {
  const server = new McpServer({ name: "lexlens", version: "0.1.0" });
  registerSearchLegal(server, rag);
  registerAskLegal(server, rag);
  registerSqlTools(server, sql);
  registerPrimitives(server, rag);
  return server;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const rag = new RagClient(process.env.RAG_API_URL ?? "http://localhost:8000");
  await buildServer(rag, new SampleDb(process.env.SAMPLE_DB_URL)).connect(new StdioServerTransport());
  console.error("lexlens MCP server running on stdio");
}
