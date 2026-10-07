import pg from "pg";

/** Message is safe to show to an MCP client. */
export class SqlToolError extends Error {}

export interface Tx {
  query(sql: string, params?: unknown[]): Promise<Record<string, unknown>[]>;
}
export interface Sql {
  withReadOnlyTx<T>(fn: (tx: Tx) => Promise<T>, timeoutMs?: number): Promise<T>;
}

export const DEFAULT_TIMEOUT_MS = 5000;

/**
 * Every call runs in BEGIN READ ONLY with a statement timeout and is rolled back.
 * Connect with a SELECT-only role (sample-db/init-roles.sh); this is the guarantee,
 * the parser guard in sql/guard.ts is the first line of defence.
 */
export class SampleDb implements Sql {
  private pool?: pg.Pool;
  constructor(private url: string | undefined) {}

  async withReadOnlyTx<T>(fn: (tx: Tx) => Promise<T>, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
    if (!this.url) throw new SqlToolError("SAMPLE_DB_URL is not set; the SQL tools need the sample database.");
    this.pool ??= new pg.Pool({ connectionString: this.url, max: 4, connectionTimeoutMillis: 5000 });
    let client: pg.PoolClient;
    try {
      client = await this.pool.connect();
    } catch {
      throw new SqlToolError("Sample database is unreachable or rejected the credentials (SAMPLE_DB_URL).");
    }
    try {
      await client.query("BEGIN READ ONLY");
      await client.query(`SET LOCAL statement_timeout = ${Math.trunc(timeoutMs)}`);
      return await fn({ query: async (sql, params) => (await client.query(sql, params as unknown[])).rows });
    } catch (e) {
      const err = e as { code?: string; message?: string };
      if (err.code === "57014") throw new SqlToolError(`Query exceeded the ${timeoutMs / 1000}s timeout and was cancelled.`);
      if (typeof err.code === "string" && err.code.length === 5) throw new SqlToolError(`Query failed: ${String(err.message).slice(0, 300)}`);
      throw e;
    } finally {
      await client.query("ROLLBACK").catch(() => {});
      client.release();
    }
  }

  async close() {
    await this.pool?.end();
  }
}
