import type { AddressInfo } from "node:net";
import http from "node:http";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { afterAll, beforeAll, expect, test } from "vitest";
import { RagClient } from "../src/clients/rag.js";
import { createHttpApp } from "../src/http.js";
import { buildServer } from "../src/index.js";

const seen: (string | null)[] = [];
let failRag = false;
const fakeFetch = (async (_url: string, init: RequestInit) => {
  seen.push(new Headers(init.headers).get("x-request-id"));
  if (failRag) return new Response("{}", { status: 500 });
  return new Response(JSON.stringify({ results: [{ id: "usc-17:107:0", text: "fair use", score: 1, source: { title: "17 U.S.C. 107", url: "u" } }] }));
}) as unknown as typeof fetch;

let server: http.Server;
let port: number;
beforeAll(async () => {
  const rag = new RagClient("http://rag.invalid", fakeFetch);
  const app = createHttpApp(() => buildServer(rag), ["127.0.0.1"]);
  server = await new Promise<http.Server>((r) => { const s = app.listen(0, "127.0.0.1", () => r(s)); });
  port = (server.address() as AddressInfo).port;
});
afterAll(() => new Promise((r) => server.close(r)));

const scrape = () =>
  new Promise<string>((resolve, reject) => {
    http.get({ host: "127.0.0.1", port, path: "/metrics" }, (res) => {
      let b = "";
      res.on("data", (c) => (b += c));
      res.on("end", () => resolve(b));
    }).on("error", reject);
  });
const value = (text: string, series: string) => Number(new RegExp(`^${series.replace(/[{}"]/g, "\\$&")} (\\S+)$`, "m").exec(text)?.[1] ?? 0);

async function callSearch(headers?: Record<string, string>) {
  const client = new Client({ name: "obs-test", version: "0" });
  await client.connect(new StreamableHTTPClientTransport(new URL(`http://127.0.0.1:${port}/mcp`), { requestInit: { headers } }));
  const out = await client.callTool({ name: "search_legal", arguments: { query: "fair use" } });
  await client.close();
  return out;
}

test("tool calls are counted and timed, and /metrics serves the exposition format", async () => {
  const ok = 'lexlens_mcp_tool_calls_total{tool="search_legal",outcome="ok"}';
  const before = value(await scrape(), ok);
  await callSearch();
  const text = await scrape();
  expect(value(text, ok)).toBe(before + 1);
  expect(text).toContain('lexlens_mcp_tool_seconds_count{tool="search_legal"}');
  expect(text).toContain("process_cpu_user_seconds_total");
});

test("the caller's x-request-id is forwarded to rag-api on every call it triggers", async () => {
  seen.length = 0;
  await callSearch({ "x-request-id": "trace-abc.1" });
  expect(seen).toContain("trace-abc.1");
});

test("an unsafe x-request-id is replaced instead of forwarded", async () => {
  seen.length = 0;
  await callSearch({ "x-request-id": "bad id\twith spaces" });
  expect(seen.length).toBeGreaterThan(0);
  expect(seen.every((id) => id !== null && /^[\w.-]{1,64}$/.test(id))).toBe(true);
});

test("a failing rag-api shows up as tool outcome=error and rag outcome=error", async () => {
  const toolErr = 'lexlens_mcp_tool_calls_total{tool="search_legal",outcome="error"}';
  const ragErr = 'lexlens_rag_client_seconds_count{path="/search",outcome="error"}';
  const before = await scrape();
  failRag = true;
  try {
    const out = await callSearch();
    expect(out.isError).toBe(true);
  } finally {
    failRag = false;
  }
  const after = await scrape();
  expect(value(after, toolErr)).toBe(value(before, toolErr) + 1);
  expect(value(after, ragErr)).toBe(value(before, ragErr) + 1);
});
