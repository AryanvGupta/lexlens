import type { AddressInfo } from "node:net";
import http from "node:http";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { afterAll, beforeAll, expect, test, vi } from "vitest";
import { buildServer } from "../src/index.js";
import { createHttpApp } from "../src/http.js";
import { passage } from "./helpers.js";

const TOKEN = "s3cret-test-token-xyz";
const rag = { search: async () => [passage()], ask: async () => { throw new Error("unused"); }, sources: async () => [] };
let server: http.Server;
let port: number;
const logged: string[] = [];
beforeAll(async () => {
  for (const m of ["log", "info", "warn", "error"] as const) vi.spyOn(console, m).mockImplementation((...a) => void logged.push(a.map(String).join(" ")));
  const app = createHttpApp(() => buildServer(rag as never), ["127.0.0.1"], TOKEN);
  server = await new Promise<http.Server>((r) => { const s = app.listen(0, "127.0.0.1", () => r(s)); });
  port = (server.address() as AddressInfo).port;
});
afterAll(() => new Promise((r) => server.close(r)));

const request = (method: string, path: string, auth?: string) =>
  new Promise<{ status: number; body: string; www?: string }>((resolve, reject) => {
    const headers: Record<string, string> = { "content-type": "application/json", accept: "application/json, text/event-stream" };
    if (auth !== undefined) headers.authorization = auth;
    const req = http.request({ host: "127.0.0.1", port, method, path, headers }, (res) => {
      let b = "";
      res.on("data", (c) => (b += c));
      res.on("end", () => resolve({ status: res.statusCode ?? 0, body: b, www: res.headers["www-authenticate"] as string | undefined }));
    });
    req.on("error", reject);
    req.end(method === "POST" ? JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/list" }) : undefined);
  });

test("missing and wrong tokens are 401 with WWW-Authenticate and a JSON-RPC error", async () => {
  for (const auth of [undefined, "Bearer nope", `Bearer ${TOKEN}x`, "Bearer ", TOKEN, `Basic ${TOKEN}`]) {
    const r = await request("POST", "/mcp", auth);
    expect(r.status).toBe(401);
    expect(r.www).toBe("Bearer");
    expect(JSON.parse(r.body).error.message).toBe("Unauthorized");
    expect(r.body).not.toContain(TOKEN);
  }
  expect((await request("GET", "/mcp")).status).toBe(401);
  expect((await request("DELETE", "/mcp")).status).toBe(401);
  expect((await request("GET", "/mcp", `Bearer ${TOKEN}`)).status).toBe(405);
});

test("right token: real client lists tools", async () => {
  const client = new Client({ name: "auth-test", version: "0" });
  await client.connect(new StreamableHTTPClientTransport(new URL(`http://127.0.0.1:${port}/mcp`), { requestInit: { headers: { Authorization: `Bearer ${TOKEN}` } } }));
  expect((await client.listTools()).tools.map((t) => t.name)).toContain("search_legal");
  await client.close();
});

test("/healthz stays open without credentials", async () => {
  expect((await request("GET", "/healthz")).status).toBe(200);
});

test("token never reaches console output", () => {
  expect(logged.join("\n")).not.toContain(TOKEN);
});
