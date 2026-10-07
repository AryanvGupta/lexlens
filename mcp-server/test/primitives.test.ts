import { describe, expect, test, vi } from "vitest";
import { RagError, type Rag } from "../src/clients/rag.js";
import { connect } from "./helpers.js";

const rag = (over: Partial<Rag> = {}): Rag => ({
  search: vi.fn(async () => []),
  ask: vi.fn(async () => { throw new Error("unused"); }),
  sources: vi.fn(async () => [{ id: "usc-17", title: "Title 17 - Copyrights", url: "http://x" }]),
  ...over,
});

describe("resource", () => {
  test("is listed and returns the source list as JSON", async () => {
    const c = await connect(rag());
    const { resources } = await c.listResources();
    expect(resources.map((r) => r.uri)).toEqual(["lexlens://corpus/sources"]);
    const read = await c.readResource({ uri: "lexlens://corpus/sources" });
    expect(read.contents[0].mimeType).toBe("application/json");
    expect(JSON.parse((read.contents[0] as { text: string }).text)).toEqual([{ id: "usc-17", title: "Title 17 - Copyrights", url: "http://x" }]);
  });
  test("backend failure surfaces a short error", async () => {
    const c = await connect(rag({ sources: async () => { throw new RagError("rag-api is unreachable or timed out."); } }));
    await expect(c.readResource({ uri: "lexlens://corpus/sources" })).rejects.toThrow(/unreachable/);
  });
});

describe("prompt", () => {
  test("tune_query embeds the query and names the three tools", async () => {
    const c = await connect(rag());
    expect((await c.listPrompts()).prompts.map((p) => p.name)).toEqual(["tune_query"]);
    const r = await c.getPrompt({ name: "tune_query", arguments: { sql: "SELECT * FROM rental" } });
    const t = (r.messages[0].content as { text: string }).text;
    for (const s of ["SELECT * FROM rental", "explain_query_plan", "suggest_indexes", "compare_plans"]) expect(t).toContain(s);
  });
  test("rejects a missing sql argument", async () => {
    await expect((await connect(rag())).getPrompt({ name: "tune_query", arguments: {} })).rejects.toThrow();
  });
});
