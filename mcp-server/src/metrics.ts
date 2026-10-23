import { Counter, Histogram, Registry, collectDefaultMetrics } from "prom-client";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";

/** One registry per process, served at GET /metrics on the HTTP transport. */
export const registry = new Registry();
collectDefaultMetrics({ register: registry });

const buckets = [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60];

// `tool` is one of the registered tool names and `outcome` is ok|error, so labels stay bounded.
export const toolCalls = new Counter({
  name: "lexlens_mcp_tool_calls_total",
  help: "MCP tool calls by tool and outcome",
  labelNames: ["tool", "outcome"],
  registers: [registry],
});
export const toolSeconds = new Histogram({
  name: "lexlens_mcp_tool_seconds",
  help: "MCP tool latency in seconds",
  labelNames: ["tool"],
  buckets,
  registers: [registry],
});
// `path` is the rag-api endpoint (/search, /ask, /sources); `outcome` is ok|error.
export const ragSeconds = new Histogram({
  name: "lexlens_rag_client_seconds",
  help: "Latency of calls from the MCP server to rag-api, in seconds",
  labelNames: ["path", "outcome"],
  buckets,
  registers: [registry],
});

/**
 * Wrap server.registerTool so every tool is counted and timed without touching each tool file.
 * A tool that returns isError or throws counts as outcome=error.
 */
export function instrumentTools(server: McpServer): McpServer {
  const register = server.registerTool.bind(server) as (name: string, config: unknown, cb: (...a: unknown[]) => unknown) => unknown;
  (server as unknown as { registerTool: typeof register }).registerTool = (name, config, cb) =>
    register(name, config, async (...args: unknown[]) => {
      const end = toolSeconds.startTimer({ tool: name });
      let outcome = "ok";
      try {
        const result = (await cb(...args)) as { isError?: boolean } | undefined;
        if (result?.isError) outcome = "error";
        return result;
      } catch (e) {
        outcome = "error";
        throw e;
      } finally {
        end();
        toolCalls.inc({ tool: name, outcome });
      }
    });
  return server;
}
