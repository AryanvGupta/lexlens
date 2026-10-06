export interface Passage {
  id: string;
  text: string;
  score: number;
  source: { title: string; section?: string; url: string };
}
export interface AskResult {
  answer: string;
  citations: { passage_id: string; quote: string }[];
  refused: boolean;
  reason: string;
  dropped_citations: number;
  retrieved: Passage[];
}
export type Mode = "dense" | "lexical" | "hybrid";

export interface Rag {
  search(query: string, k: number, mode: Mode): Promise<Passage[]>;
  ask(question: string, k: number): Promise<AskResult>;
}

/** Message is safe to show to an MCP client: short, no stack, no internals. */
export class RagError extends Error {}

// First request loads the embedding model (~10s); ask also waits on the LLM.
const SEARCH_TIMEOUT_MS = 30_000;
const ASK_TIMEOUT_MS = 60_000;

export class RagClient implements Rag {
  constructor(
    private baseUrl: string,
    private fetchFn: typeof fetch = fetch,
  ) {}

  private async post<T>(path: string, body: unknown, timeoutMs: number): Promise<T> {
    let res: Response;
    try {
      res = await this.fetchFn(`${this.baseUrl}${path}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(timeoutMs),
      });
    } catch {
      throw new RagError("rag-api is unreachable or timed out. Is it running (RAG_API_URL)?");
    }
    if (!res.ok) {
      const detail = await res.json().then((j) => j?.detail, () => undefined);
      throw new RagError(
        res.status === 503 && typeof detail === "string"
          ? `rag-api is not ready: ${detail}`
          : `rag-api returned HTTP ${res.status}`,
      );
    }
    try {
      return (await res.json()) as T;
    } catch {
      throw new RagError("rag-api returned an unreadable response");
    }
  }

  async search(query: string, k: number, mode: Mode): Promise<Passage[]> {
    const r = await this.post<{ results?: Passage[] }>("/search", { query, k, mode }, SEARCH_TIMEOUT_MS);
    if (!Array.isArray(r.results)) throw new RagError("rag-api returned an unexpected response");
    return r.results;
  }

  async ask(question: string, k: number): Promise<AskResult> {
    const r = await this.post<AskResult>("/ask", { question, k }, ASK_TIMEOUT_MS);
    if (typeof r.refused !== "boolean" || !Array.isArray(r.citations)) {
      throw new RagError("rag-api returned an unexpected response");
    }
    return r;
  }
}
