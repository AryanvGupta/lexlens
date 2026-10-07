import pg from "pg";
import { afterAll, describe, expect, test } from "vitest";
import { SampleDb, SqlToolError } from "../src/sql/db.js";
import { connect, text } from "./helpers.js";

// Needs the sample-db container (docker compose up -d --wait sample-db) and SAMPLE_DB_URL; skipped otherwise.
const URL_ = process.env.SAMPLE_DB_URL;
async function dbUp() {
  if (!URL_) return false;
  const c = new pg.Client({ connectionString: URL_, connectionTimeoutMillis: 2000 });
  try {
    await c.connect();
    await c.end();
    return true;
  } catch {
    return false;
  }
}
const up = await dbUp();
const rag = { search: async () => [], ask: async () => { throw new Error("unused"); } } as never;
const db = new SampleDb(URL_);
afterAll(() => db.close());
const call = async (name: string, args: Record<string, unknown>) => (await connect(rag, db)).callTool({ name, arguments: args });

describe.skipIf(!up)("database layer enforces read-only even if the guard is bypassed", () => {
  test("raw pg_sleep(10) is killed by the statement timeout", async () => {
    const t = Date.now();
    await expect(db.withReadOnlyTx((tx) => tx.query("SELECT pg_sleep(10)"), 500)).rejects.toThrow(/timeout/);
    expect(Date.now() - t).toBeLessThan(3000);
  });
  test("raw INSERT / DROP are rejected", async () => {
    await expect(db.withReadOnlyTx((tx) => tx.query("INSERT INTO film(title, language_id) VALUES ('x', 1)"))).rejects.toThrow(SqlToolError);
    await expect(db.withReadOnlyTx((tx) => tx.query("DROP TABLE film"))).rejects.toThrow(SqlToolError);
  });
  test("turning read-only off inside the transaction still cannot write (role has SELECT only)", async () => {
    await expect(
      db.withReadOnlyTx(async (tx) => {
        await tx.query("SET transaction_read_only = off").catch(() => {});
        await tx.query("INSERT INTO film(title, language_id) VALUES ('x', 1)");
      }),
    ).rejects.toThrow(SqlToolError);
  });
});

describe.skipIf(!up)("tools against pagila", () => {
  test("explain_query_plan summarizes a real plan", async () => {
    const out = await call("explain_query_plan", { sql: "SELECT * FROM rental WHERE customer_id = 5" });
    expect(out.isError).toBeFalsy();
    expect(text(out)).toMatch(/Execution [\d.]+ ms/);
    expect(text(out)).toContain("Slowest nodes");
  });
  test("DROP TABLE, pg_sleep(60) and multi-statement are rejected immediately by the tools", async () => {
    for (const sql of ["DROP TABLE film", "SELECT pg_sleep(60)", "SELECT 1; DROP TABLE film"]) {
      const t = Date.now();
      const out = await call("explain_query_plan", { sql });
      expect(out.isError, sql).toBe(true);
      expect(Date.now() - t, sql).toBeLessThan(2000);
    }
    expect(text(await call("explain_query_plan", { sql: "SELECT pg_sleep(60)" }))).toContain("not allowed");
  });
  test("a heavy query is cancelled by the timeout instead of hanging", async () => {
    const t = Date.now();
    const out = await call("explain_query_plan", { sql: "SELECT count(*) FROM rental a, rental b, rental c" });
    expect(out.isError).toBe(true);
    expect(text(out)).toContain("timeout");
    expect(Date.now() - t).toBeLessThan(10_000);
  }, 20_000);
  test("compare_plans: sargable rewrite is faster, same rows, plan shape differs", async () => {
    const out = text(
      await call("compare_plans", {
        before_sql: "SELECT * FROM rental WHERE date_trunc('day', rental_date) = '2024-06-15'",
        after_sql: "SELECT * FROM rental WHERE rental_date >= '2024-06-15' AND rental_date < '2024-06-16'",
      }),
    );
    expect(out).toContain("Only in BEFORE plan: Seq Scan on rental");
    // planner may pick an Index Scan or a Bitmap scan depending on statistics; both use the rental_date index
    expect(out).toMatch(/Only in AFTER plan: .*using idx_unq_rental_rental_date_inventory_id_customer_id/);
    expect(out).not.toContain("WARNING");
  });
  test("compare_plans warns when the queries return different rows", async () => {
    const out = text(await call("compare_plans", { before_sql: "SELECT * FROM rental WHERE customer_id = 5", after_sql: "SELECT * FROM rental WHERE customer_id = 6" }));
    expect(out).toContain("WARNING: row counts differ");
  });
  test("suggest_indexes validates with hypopg: useful index vs unusable predicate", async () => {
    const good = text(await call("suggest_indexes", { sql: "SELECT * FROM rental WHERE staff_id = 1 AND return_date IS NULL" }));
    expect(good).toContain('CREATE INDEX ON public."rental" ("staff_id", "return_date")');
    expect(good).toContain("index WOULD be used");
    const bad = text(await call("suggest_indexes", { sql: "SELECT * FROM rental WHERE date_trunc('day', rental_date) = '2024-06-15'" }));
    expect(bad).toContain("would NOT be used");
  });
  test("suggest_indexes: nothing to suggest when no big sequential scan", async () => {
    const out = text(await call("suggest_indexes", { sql: "SELECT * FROM film WHERE film_id = 1" }));
    expect(out).toContain("No index candidates");
  });
});
