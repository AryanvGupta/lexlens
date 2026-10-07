import { fileURLToPath } from "node:url";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { expect, test } from "vitest";
import { text } from "./helpers.js";

// Spawns the built server (npm test builds first) the way Claude Desktop/Code would.
test("real stdio: lists tools, and an unreachable backend gives a clean tool error", async () => {
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [fileURLToPath(new URL("../dist/index.js", import.meta.url))],
    env: { ...process.env, RAG_API_URL: "http://127.0.0.1:1" } as Record<string, string>,
    stderr: "pipe",
  });
  const client = new Client({ name: "stdio-test", version: "0" });
  await client.connect(transport);
  try {
    const { tools } = await client.listTools();
    expect(tools.map((t) => t.name).sort()).toEqual(["ask_legal", "compare_plans", "explain_query_plan", "search_legal", "suggest_indexes"]);
    const out = await client.callTool({ name: "search_legal", arguments: { query: "fair use" } });
    expect(out.isError).toBe(true);
    expect(text(out)).toContain("unreachable");
  } finally {
    await client.close();
  }
}, 30_000);
