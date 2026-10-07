import { RagError } from "../clients/rag.js";
import { SqlToolError } from "../sql/db.js";
import { GuardError } from "../sql/guard.js";

const isSafe = (e: unknown) => e instanceof RagError || e instanceof SqlToolError || e instanceof GuardError;

export const MAX_PASSAGE_CHARS = 800;

export const truncate = (s: string, n = MAX_PASSAGE_CHARS) => (s.length > n ? `${s.slice(0, n)}…` : s);

export const ok = (text: string) => ({ content: [{ type: "text" as const, text }] });

/** Tool-level failure: the model sees a short message and can tell the user. */
export async function guarded(run: () => Promise<string>) {
  try {
    return ok(await run());
  } catch (e) {
    if (!isSafe(e)) console.error(e); // stderr only; stdout is the protocol
    return { isError: true as const, content: [{ type: "text" as const, text: isSafe(e) ? (e as Error).message : "Unexpected error in lexlens MCP server" }] };
  }
}
