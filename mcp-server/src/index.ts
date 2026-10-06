import { pathToFileURL } from "node:url";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { RagClient, type Rag } from "./clients/rag.js";
import { registerAskLegal } from "./tools/askLegal.js";
import { registerSearchLegal } from "./tools/searchLegal.js";

export function buildServer(rag: Rag): McpServer {
  const server = new McpServer({ name: "lexlens", version: "0.1.0" });
  registerSearchLegal(server, rag);
  registerAskLegal(server, rag);
  return server;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const rag = new RagClient(process.env.RAG_API_URL ?? "http://localhost:8000");
  await buildServer(rag).connect(new StdioServerTransport());
  console.error("lexlens MCP server running on stdio");
}
