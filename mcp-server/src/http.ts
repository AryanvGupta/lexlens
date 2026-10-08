import express from "express";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { hostHeaderValidation } from "@modelcontextprotocol/sdk/server/middleware/hostHeaderValidation.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";

const jsonRpcError = (code: number, message: string) => ({ jsonrpc: "2.0", error: { code, message }, id: null });

/**
 * Stateless streamable-HTTP MCP endpoint (a fresh server and transport per request).
 * No authentication: expose it only inside the cluster / via port-forward.
 * Host-header validation is the DNS-rebinding guard from the SDK.
 */
export function createHttpApp(makeServer: () => McpServer, allowedHosts: string[]) {
  const app = express();
  // Before host validation on purpose: kubelet probes send the pod IP as Host.
  app.get("/healthz", (_req, res) => void res.json({ status: "ok" }));
  app.use(hostHeaderValidation(allowedHosts));
  app.use(express.json({ limit: "1mb" }));

  app.post("/mcp", async (req, res) => {
    const server = makeServer();
    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
    res.on("close", () => {
      void transport.close();
      void server.close();
    });
    try {
      await server.connect(transport);
      await transport.handleRequest(req, res, req.body);
    } catch (e) {
      console.error("MCP request failed:", e); // stderr/logs only; the client gets a generic error
      if (!res.headersSent) res.status(500).json(jsonRpcError(-32603, "Internal server error"));
    }
  });
  const notAllowed: express.RequestHandler = (_req, res) => void res.status(405).json(jsonRpcError(-32000, "Method not allowed."));
  app.get("/mcp", notAllowed);
  app.delete("/mcp", notAllowed);
  return app;
}
