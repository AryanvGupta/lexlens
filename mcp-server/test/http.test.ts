import type { AddressInfo } from "node:net";
import http from "node:http";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { afterAll, beforeAll, expect, test } from "vitest";
import { buildServer } from "../src/index.js";
import { createHttpApp } from "../src/http.js";
import { passage, text } from "./helpers.js";

const rag = { search: async () => [passage()], ask: async () => { throw new Error("unused"); }, sources: async () => [] };
let server: http.Server;
let port: number;
beforeAll(async () => {
  const app = createHttpApp(() => buildServer(rag as never), ["127.0.0.1", "mcp-server"]);
  server = await new Promise<http.Server>((r) => { const s = app.listen(0, "127.0.0.1", () => r(s)); });
  port = (server.address() as AddressInfo).port;
});
afterAll(() => new Promise((r) => server.close(r)));

const request = (method: string, path: string, host: string, body?: string) =>
  new Promise<{ status: number; body: string }>((resolve, reject) => {
    const req = http.request({ host: "127.0.0.1", port, method, path, headers: { host, "content-type": "application/json", accept: "application/json, text/event-stream" } }, (res) => {
      let b = "";
      res.on("data", (c) => (b += c));
      res.on("end", () => resolve({ status: res.statusCode ?? 0, body: b }));
    });
    req.on("error", reject);
    req.end(body);
  });

test("real streamable-HTTP client lists tools and calls one", async () => {
  const client = new Client({ name: "http-test", version: "0" });
  await client.connect(new StreamableHTTPClientTransport(new URL(`http://127.0.0.1:${port}/mcp`)));
  expect((await client.listTools()).tools.map((t) => t.name)).toContain("search_legal");
  const out = await client.callTool({ name: "search_legal", arguments: { query: "fair use" } });
  expect(text(out)).toContain("usc-17:107:0");
  await client.close();
});

test("/healthz answers for any Host header (kubelet probes use the pod IP)", async () => {
  const r = await request("GET", "/healthz", "10.244.0.7:3000");
  expect(r.status).toBe(200);
  expect(JSON.parse(r.body)).toEqual({ status: "ok" });
});

test("/mcp rejects an unknown Host header (DNS-rebinding guard)", async () => {
  const init = JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/list" });
  expect((await request("POST", "/mcp", "evil.example", init)).status).toBe(403);
});

test("GET and DELETE on /mcp are 405 (stateless server has no sessions)", async () => {
  expect((await request("GET", "/mcp", "mcp-server")).status).toBe(405);
  expect((await request("DELETE", "/mcp", "mcp-server")).status).toBe(405);
});
