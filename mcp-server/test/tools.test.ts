import { describe, expect, test, vi } from "vitest";
import { RagError, type Rag } from "../src/clients/rag.js";
import { MAX_PASSAGE_CHARS } from "../src/tools/util.js";
import { askResult, connect, passage, rejected, text } from "./helpers.js";

const rag = (over: Partial<Rag> = {}): Rag => ({
  search: vi.fn(async () => [passage()]),
  ask: vi.fn(async () => askResult()),
  sources: vi.fn(async () => []),
  ...over,
});

describe("tool registration", () => {
  test("lists all tools with read-only annotations", async () => {
    const { tools } = await (await connect(rag())).listTools();
    expect(tools.map((t) => t.name).sort()).toEqual(["ask_legal", "compare_plans", "explain_query_plan", "search_legal", "suggest_indexes"]);
    expect(tools.every((t) => t.annotations?.readOnlyHint === true)).toBe(true);
  });
});

describe("search_legal", () => {
  test("happy path formats id, source, score, text and applies defaults", async () => {
    const r = rag();
    const out = await (await connect(r)).callTool({ name: "search_legal", arguments: { query: "fair use" } });
    expect(r.search).toHaveBeenCalledWith("fair use", 5, "hybrid");
    expect(text(out)).toContain("id=usc-17:107:0");
    expect(text(out)).toContain("score=0.870");
    expect(text(out)).toContain("not an infringement");
  });

  test.each([
    ["empty query", { query: "" }],
    ["query too long", { query: "x".repeat(501) }],
    ["k = 0", { query: "q", k: 0 }],
    ["k = 11", { query: "q", k: 11 }],
    ["k not an integer", { query: "q", k: 2.5 }],
    ["unknown mode", { query: "q", mode: "magic" }],
  ])("rejects invalid input: %s", async (_n, args) => {
    const r = rag();
    const c = await connect(r);
    expect(await rejected(c.callTool({ name: "search_legal", arguments: args }))).toBe(true);
    expect(r.search).not.toHaveBeenCalled();
  });

  test("truncates oversized passage text", async () => {
    const big = passage({ text: "a".repeat(MAX_PASSAGE_CHARS * 5) });
    const c = await connect(rag({ search: async () => [big] }));
    const out = text(await c.callTool({ name: "search_legal", arguments: { query: "q" } }));
    expect(out.length).toBeLessThan(MAX_PASSAGE_CHARS + 300);
    expect(out).toContain("…");
  });

  test("empty result is a normal answer", async () => {
    const c = await connect(rag({ search: async () => [] }));
    const out = await c.callTool({ name: "search_legal", arguments: { query: "q" } });
    expect(out.isError).toBeFalsy();
    expect(text(out)).toBe("No passages found.");
  });

  test("backend failure becomes a short isError result", async () => {
    const c = await connect(rag({ search: async () => { throw new RagError("rag-api is unreachable or timed out."); } }));
    const out = await c.callTool({ name: "search_legal", arguments: { query: "q" } });
    expect(out.isError).toBe(true);
    expect(text(out)).toContain("unreachable");
  });

  test("unexpected exceptions are not leaked to the client", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const c = await connect(rag({ search: async () => { throw new Error("secret stack detail"); } }));
    const out = await c.callTool({ name: "search_legal", arguments: { query: "q" } });
    expect(out.isError).toBe(true);
    expect(text(out)).not.toContain("secret");
  });
});

describe("ask_legal", () => {
  test("answer with verified citations and source titles", async () => {
    const out = await (await connect(rag())).callTool({ name: "ask_legal", arguments: { question: "fair use?" } });
    expect(text(out)).toMatch(/^ANSWER: Fair use is not infringement\./);
    expect(text(out)).toContain('[usc-17:107:0] (usc-17 §107. Fair use) "fair use of a copyrighted work"');
  });

  test("mentions dropped citations", async () => {
    const c = await connect(rag({ ask: async () => askResult({ dropped_citations: 2 }) }));
    const out = await c.callTool({ name: "ask_legal", arguments: { question: "q" } });
    expect(text(out)).toContain("2 unverifiable citation(s) were dropped");
  });

  test("refusal is a normal result, not an error", async () => {
    const c = await connect(rag({ ask: async () => askResult({ refused: true, reason: "not in passages", answer: "", citations: [] }) }));
    const out = await c.callTool({ name: "ask_legal", arguments: { question: "minimum wage?" } });
    expect(out.isError).toBeFalsy();
    expect(text(out)).toBe("REFUSED: not in passages");
  });

  test.each([
    ["empty question", { question: "" }],
    ["question too long", { question: "x".repeat(501) }],
    ["k = 0", { question: "q", k: 0 }],
    ["k = 11", { question: "q", k: 11 }],
  ])("rejects invalid input: %s", async (_n, args) => {
    const r = rag();
    expect(await rejected((await connect(r)).callTool({ name: "ask_legal", arguments: args }))).toBe(true);
    expect(r.ask).not.toHaveBeenCalled();
  });

  test("backend failure becomes isError", async () => {
    const c = await connect(rag({ ask: async () => { throw new RagError("rag-api is not ready: ANTHROPIC_API_KEY is not set"); } }));
    const out = await c.callTool({ name: "ask_legal", arguments: { question: "q" } });
    expect(out.isError).toBe(true);
    expect(text(out)).toContain("not ready");
  });
});
