import { loadModule, parse } from "libpg-query";

/** Message is safe to show to an MCP client. */
export class GuardError extends Error {}

export const MAX_SQL_CHARS = 5000;

// Defence in depth only: the real guarantees are the read-only transaction,
// the statement timeout and the SELECT-only role (see sql/db.ts).
// ponytail: denylist is not exhaustive; extend when a new risky function shows up.
const DENIED_FUNCS = /^(pg_sleep.*|nextval|setval|set_config|lo_.*|pg_read_.*|pg_ls_.*|pg_stat_file|dblink.*|pg_terminate_backend|pg_cancel_backend|pg_reload_conf|pg_rotate_logfile|pg_advisory_.*|pg_notify|pg_create_.*|pg_drop_.*|hypopg_.*)$/;

type Node = Record<string, unknown>;

function walk(node: unknown, visit: (key: string, value: unknown) => void): void {
  if (Array.isArray(node)) return node.forEach((n) => walk(n, visit));
  if (node && typeof node === "object") {
    for (const [k, v] of Object.entries(node as Node)) {
      visit(k, v);
      walk(v, visit);
    }
  }
}

/** Throws GuardError unless `sql` is exactly one plain SELECT. Parses with the real Postgres parser. */
export async function assertSingleSelect(sql: string): Promise<void> {
  if (!sql.trim()) throw new GuardError("Query is empty.");
  if (sql.length > MAX_SQL_CHARS) throw new GuardError(`Query is longer than ${MAX_SQL_CHARS} characters.`);
  await loadModule();
  let stmts: { stmt: Node }[];
  try {
    stmts = ((await parse(sql)).stmts ?? []) as unknown as { stmt: Node }[];
  } catch (e) {
    throw new GuardError(`SQL syntax error: ${String((e as Error).message).slice(0, 200)}`);
  }
  if (stmts.length !== 1) throw new GuardError("Exactly one statement is allowed (no multi-statement queries).");
  const root = stmts[0].stmt;
  if (!("SelectStmt" in root)) throw new GuardError("Only SELECT statements are allowed.");
  walk(root, (key, value) => {
    if (/Stmt$/.test(key) && key !== "SelectStmt") throw new GuardError("Only SELECT statements are allowed (data-modifying statements are rejected, including inside CTEs).");
    if (key === "intoClause" && value) throw new GuardError("SELECT INTO is not allowed.");
    if (key === "lockingClause" && value) throw new GuardError("Locking clauses (FOR UPDATE/SHARE) are not allowed.");
    if (key === "FuncCall") {
      const names = ((value as Node).funcname as { String?: { sval?: string } }[]) ?? [];
      const fn = names.at(-1)?.String?.sval?.toLowerCase() ?? "";
      if (DENIED_FUNCS.test(fn)) throw new GuardError(`Function ${fn}() is not allowed.`);
    }
  });
}

/** After wrapping in EXPLAIN, re-check the composed text is still one EXPLAIN of that SELECT. */
export async function assertExplainWrapper(composed: string): Promise<void> {
  await loadModule();
  const stmts = ((await parse(composed)).stmts ?? []) as unknown as { stmt: Node }[];
  if (stmts.length !== 1 || !("ExplainStmt" in stmts[0].stmt)) throw new GuardError("Internal guard: unexpected statement shape.");
}
