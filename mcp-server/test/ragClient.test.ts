import { describe, expect, test } from "vitest";
import { RagClient, RagError } from "../src/clients/rag.js";

const json = (body: unknown, status = 200) =>
  (async () => new Response(JSON.stringify(body), { status })) as unknown as typeof fetch;

const client = (f: typeof fetch) => new RagClient("http://rag", f);

describe("RagClient error mapping", () => {
  test("connection failure", async () => {
    const f = (async () => { throw new TypeError("fetch failed"); }) as unknown as typeof fetch;
    await expect(client(f).search("q", 5, "hybrid")).rejects.toThrow(/unreachable or timed out/);
  });

  test("timeout (AbortSignal) is reported the same way", async () => {
    const f = (async () => { throw new DOMException("timed out", "TimeoutError"); }) as unknown as typeof fetch;
    await expect(client(f).ask("q", 8)).rejects.toBeInstanceOf(RagError);
  });

  test("503 surfaces the backend's reason", async () => {
    await expect(client(json({ detail: "ANTHROPIC_API_KEY is not set" }, 503)).ask("q", 8)).rejects.toThrow(
      /not ready: ANTHROPIC_API_KEY is not set/,
    );
  });

  test("5xx without detail", async () => {
    await expect(client(json({}, 500)).search("q", 5, "dense")).rejects.toThrow("rag-api returned HTTP 500");
  });

  test("malformed bodies are rejected", async () => {
    await expect(client(json({ nope: 1 })).search("q", 5, "dense")).rejects.toThrow(/unexpected response/);
    await expect(client(json({ answer: "x" })).ask("q", 8)).rejects.toThrow(/unexpected response/);
    const notJson = (async () => new Response("<html>", { status: 200 })) as unknown as typeof fetch;
    await expect(client(notJson).search("q", 5, "dense")).rejects.toThrow(/unreadable/);
  });

  test("sends the documented request body", async () => {
    let seen: { url?: string; body?: unknown } = {};
    const f = (async (url: string, init: RequestInit) => {
      seen = { url, body: JSON.parse(init.body as string) };
      return new Response(JSON.stringify({ results: [] }));
    }) as unknown as typeof fetch;
    await client(f).search("fair use", 3, "lexical");
    expect(seen).toEqual({ url: "http://rag/search", body: { query: "fair use", k: 3, mode: "lexical" } });
  });
});

test("sources: GET /sources and shape check", async () => {
  let method = "";
  const f = (async (_u: string, init: RequestInit) => {
    method = init.method as string;
    return new Response(JSON.stringify({ sources: [{ id: "a", title: "A", url: "u" }] }));
  }) as unknown as typeof fetch;
  expect(await client(f).sources()).toEqual([{ id: "a", title: "A", url: "u" }]);
  expect(method).toBe("GET");
  await expect(client(json({})).sources()).rejects.toThrow(/unexpected response/);
});
