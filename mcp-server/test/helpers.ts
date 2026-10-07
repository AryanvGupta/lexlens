import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import type { AskResult, Passage, Rag } from "../src/clients/rag.js";
import { buildServer } from "../src/index.js";
import type { Sql } from "../src/sql/db.js";

export const passage = (over: Partial<Passage> = {}): Passage => ({
  id: "usc-17:107:0",
  text: "the fair use of a copyrighted work is not an infringement",
  score: 0.87,
  source: { title: "usc-17 §107. Fair use", section: "107", url: "u" },
  ...over,
});

export const askResult = (over: Partial<AskResult> = {}): AskResult => ({
  answer: "Fair use is not infringement.",
  citations: [{ passage_id: "usc-17:107:0", quote: "fair use of a copyrighted work" }],
  refused: false,
  reason: "",
  dropped_citations: 0,
  retrieved: [passage()],
  ...over,
});

export async function connect(rag: Rag, sql?: Sql) {
  const [a, b] = InMemoryTransport.createLinkedPair();
  await buildServer(rag, sql).connect(a);
  const client = new Client({ name: "test", version: "0" });
  await client.connect(b);
  return client;
}

/** Validation failures surface as a thrown protocol error or an isError result; accept either. */
export async function rejected(p: Promise<unknown>): Promise<boolean> {
  try {
    const r = (await p) as { isError?: boolean };
    return r.isError === true;
  } catch {
    return true;
  }
}

export const text = (r: unknown) => (r as { content: { text: string }[] }).content[0].text;
