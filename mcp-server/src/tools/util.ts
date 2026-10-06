import { RagError } from "../clients/rag.js";

export const MAX_PASSAGE_CHARS = 800;

export const truncate = (s: string, n = MAX_PASSAGE_CHARS) => (s.length > n ? `${s.slice(0, n)}…` : s);

export const ok = (text: string) => ({ content: [{ type: "text" as const, text }] });

/** Tool-level failure: the model sees a short message and can tell the user. */
export async function guarded(run: () => Promise<string>) {
  try {
    return ok(await run());
  } catch (e) {
    if (!(e instanceof RagError)) console.error(e); // stderr only; stdout is the protocol
    return { isError: true as const, content: [{ type: "text" as const, text: e instanceof RagError ? e.message : "Unexpected error in lexlens MCP server" }] };
  }
}
