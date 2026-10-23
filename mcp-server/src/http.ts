import { createHash, randomUUID, timingSafeEqual } from "node:crypto";
import express from "express";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { hostHeaderValidation } from "@modelcontextprotocol/sdk/server/middleware/hostHeaderValidation.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { registry } from "./metrics.js";
import { withRequestId } from "./requestContext.js";

const jsonRpcError = (code: number, message: string) => ({ jsonrpc: "2.0", error: { code, message }, id: null });

/**
 * Stateless streamable-HTTP MCP endpoint (a fresh server and transport per request).
 * Optional bearer auth: pass authToken (index.ts passes MCP_AUTH_TOKEN). Empty = no auth, so
 * expose it only inside the cluster / via port-forward. The environment is deliberately not read here, so a
 * token in a developer's shell can never change what the tests see. /healthz is never authenticated.
 * Host-header validation is the DNS-rebinding guard from the SDK.
 */
export function createHttpApp(makeServer: () => McpServer, allowedHosts: string[], authToken = "") {
  const app = express();
  // Before host validation on purpose: kubelet probes send the pod IP as Host.
  app.get("/healthz", (_req, res) => void res.json({ status: "ok" }));
  // Same exposure as /healthz: unauthenticated, so reach it from inside the cluster only.
  app.get("/metrics", async (_req, res) => void res.type(registry.contentType).send(await registry.metrics()));
  app.use(hostHeaderValidation(allowedHosts));
  if (authToken) {
    // Hash both sides so timingSafeEqual gets equal-length buffers whatever the client sends.
    const digest = (v: string) => createHash("sha256").update(v).digest();
    const want = digest(authToken);
    app.use("/mcp", (req, res, next) => {
      const m = /^Bearer (.+)$/.exec(req.headers.authorization ?? "");
      if (m && timingSafeEqual(digest(m[1]), want)) return next();
      res.status(401).set("WWW-Authenticate", "Bearer").json(jsonRpcError(-32001, "Unauthorized"));
    });
  }
  app.use(express.json({ limit: "1mb" }));
  // Reuse the caller's x-request-id (or mint one) and forward it to rag-api, so one id follows a tool call end to end.
  app.use("/mcp", (req, res, next) => {
    const given = req.headers["x-request-id"];
    const id = typeof given === "string" && /^[\w.-]{1,64}$/.test(given) ? given : randomUUID().slice(0, 12);
    res.setHeader("x-request-id", id);
    withRequestId(id, next);
  });

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
