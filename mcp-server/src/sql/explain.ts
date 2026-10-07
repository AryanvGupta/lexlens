import { assertExplainWrapper, assertSingleSelect } from "./guard.js";
import type { Tx } from "./db.js";
import { explainFrom, type Explain } from "./plan.js";

/** Validate, wrap in EXPLAIN, re-validate the composed text, run. The only place user SQL reaches the DB. */
export async function runExplain(tx: Tx, sql: string, analyze: boolean): Promise<Explain> {
  await assertSingleSelect(sql);
  const composed = `EXPLAIN (${analyze ? "ANALYZE, BUFFERS, " : ""}FORMAT JSON) ${sql.trim().replace(/;+\s*$/, "")}`;
  await assertExplainWrapper(composed);
  return explainFrom(await tx.query(composed));
}
