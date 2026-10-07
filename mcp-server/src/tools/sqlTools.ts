import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { candidates, ddl } from "../sql/candidates.js";
import type { Sql, Tx } from "../sql/db.js";
import { runExplain } from "../sql/explain.js";
import { describe, formatSummary, nodes, summarize, type Explain } from "../sql/plan.js";
import { assertSingleSelect } from "../sql/guard.js";
import { guarded } from "./util.js";

const sqlArg = (what: string) => z.string().min(1).max(5000).describe(`${what}: one SELECT statement against the pagila sample database (DVD rental schema)`);
const READ_ONLY = { readOnlyHint: true, openWorldHint: false } as const;
const RUNS = 3;

const median = (xs: Explain[]) => [...xs].sort((a, b) => (a["Execution Time"] ?? 0) - (b["Execution Time"] ?? 0))[Math.floor(xs.length / 2)];

async function columnsByTable(tx: Tx, tables: string[]): Promise<Map<string, string[]>> {
  const rows = await tx.query(
    "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = ANY($1)",
    [tables],
  );
  const m = new Map<string, string[]>();
  for (const r of rows as { table_name: string; column_name: string }[]) m.set(r.table_name, [...(m.get(r.table_name) ?? []), r.column_name]);
  return m;
}

export function registerSqlTools(server: McpServer, sql: Sql) {
  server.registerTool(
    "explain_query_plan",
    {
      title: "Explain a query plan",
      description:
        "Run EXPLAIN (ANALYZE, BUFFERS) on a SELECT against the read-only pagila sample database and summarize it: slowest nodes, large sequential scans, and row-estimate vs actual mismatches. The query is really executed (read-only, 5s timeout). Only a single SELECT is accepted.",
      inputSchema: { sql: sqlArg("Query to explain") },
      annotations: READ_ONLY,
    },
    ({ sql: query }) =>
      guarded(async () => {
        await assertSingleSelect(query); // reject before touching the database
        return sql.withReadOnlyTx(async (tx) => formatSummary(summarize(await runExplain(tx, query, true))));
      }),
  );

  server.registerTool(
    "suggest_indexes",
    {
      title: "Suggest indexes for a query",
      description:
        "Propose candidate indexes for a SELECT on the pagila sample database, based on its large sequential scans (filter and join columns). If the hypopg extension is available each candidate is validated with a hypothetical index (planner cost before/after and whether it would be used); otherwise the result is explicitly an unvalidated suggestion. Nothing is created.",
      inputSchema: { sql: sqlArg("Query to tune") },
      annotations: READ_ONLY,
    },
    ({ sql: query }) =>
      guarded(async () => {
        await assertSingleSelect(query); // reject before touching the database
        return sql.withReadOnlyTx(async (tx) => {
          const analyzed = await runExplain(tx, query, true);
          const baseCost = (await runExplain(tx, query, false)).Plan["Total Cost"];
          const tables = [...new Set(nodes(analyzed.Plan).map((n) => n["Relation Name"]).filter((t): t is string => !!t))];
          const cands = candidates(analyzed.Plan, await columnsByTable(tx, tables));
          if (!cands.length) return "No index candidates: no sequential scan reads 1000+ rows with a usable filter or join column. The plan may already use indexes, or the predicate is not indexable as written (for example a function applied to the column).";
          const hypopg = (await tx.query("SELECT 1 FROM pg_extension WHERE extname = 'hypopg'")).length > 0;
          const lines = [`Baseline planner cost ${baseCost.toFixed(2)}.`, hypopg ? "Validated with hypothetical indexes (hypopg); nothing was created." : "UNVALIDATED suggestions (hypopg is not installed); nothing was created.", ""];
          for (const c of cands) {
            lines.push(`${ddl(c)};`, `  why: ${c.reason}`);
            if (hypopg) {
              await tx.query("SELECT hypopg_create_index($1)", [ddl(c)]);
              const plan = await runExplain(tx, query, false);
              await tx.query("SELECT hypopg_reset()");
              const used = nodes(plan.Plan).some((n) => String(n["Index Name"] ?? "").startsWith("<"));
              lines.push(`  evidence: planner cost ${baseCost.toFixed(2)} -> ${plan.Plan["Total Cost"].toFixed(2)}, index ${used ? "WOULD be used" : "would NOT be used"}`);
            }
          }
          return lines.join("\n");
        });
      }),
  );

  server.registerTool(
    "compare_plans",
    {
      title: "Compare two query plans",
      description:
        `Run EXPLAIN (ANALYZE, BUFFERS) on a before and an after SELECT (each ${RUNS} times, median execution time used because timings are noisy) and report runtime, cost, buffer and plan-shape differences. Does not check that both queries return the same rows beyond comparing the returned row count.`,
      inputSchema: { before_sql: sqlArg("Original query"), after_sql: sqlArg("Rewritten query") },
      annotations: READ_ONLY,
    },
    ({ before_sql, after_sql }) =>
      guarded(async () => {
        await assertSingleSelect(before_sql);
        await assertSingleSelect(after_sql);
        return sql.withReadOnlyTx(async (tx) => {
          const run = async (q: string) => {
            const runs: Explain[] = [];
            for (let i = 0; i < RUNS; i++) runs.push(await runExplain(tx, q, true));
            return median(runs);
          };
          const b = await run(before_sql);
          const a = await run(after_sql);
          const sb = summarize(b);
          const sa = summarize(a);
          const sig = (e: Explain) => new Set(nodes(e.Plan).map(describe));
          const only = (x: Set<string>, y: Set<string>) => [...x].filter((s) => !y.has(s));
          const speed = sb.executionMs && sa.executionMs ? `${(sb.executionMs / sa.executionMs).toFixed(2)}x` : "n/a";
          const rowsNote = sb.rootRows !== sa.rootRows ? `\nWARNING: row counts differ (${sb.rootRows} vs ${sa.rootRows}); the queries are not equivalent.` : "";
          const fmt = (n?: number) => (n === undefined ? "n/a" : n.toFixed(2));
          return [
            `Execution (median of ${RUNS}): ${fmt(sb.executionMs)} ms -> ${fmt(sa.executionMs)} ms (speedup ${speed})`,
            `Planner cost: ${fmt(sb.totalCost)} -> ${fmt(sa.totalCost)}`,
            `Shared buffers hit/read: ${sb.sharedHit}/${sb.sharedRead} -> ${sa.sharedHit}/${sa.sharedRead}`,
            `Rows returned: ${sb.rootRows} -> ${sa.rootRows}${rowsNote}`,
            "",
            `Only in BEFORE plan: ${only(sig(b), sig(a)).join("; ") || "(none)"}`,
            `Only in AFTER plan: ${only(sig(a), sig(b)).join("; ") || "(none)"}`,
          ].join("\n");
        });
      }),
  );
}
