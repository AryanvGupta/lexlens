// Pure functions over EXPLAIN (FORMAT JSON) output. No DB access here.

export interface PlanNode {
  "Node Type": string;
  "Relation Name"?: string;
  Alias?: string;
  "Index Name"?: string;
  Filter?: string;
  "Total Cost": number;
  "Plan Rows": number;
  "Actual Rows"?: number;
  "Actual Loops"?: number;
  "Actual Total Time"?: number;
  "Rows Removed by Filter"?: number;
  "Shared Hit Blocks"?: number;
  "Shared Read Blocks"?: number;
  Plans?: PlanNode[];
  [k: string]: unknown;
}
export interface Explain {
  Plan: PlanNode;
  "Planning Time"?: number;
  "Execution Time"?: number;
}

export const SEQ_SCAN_MIN_ROWS = 1000; // pagila's largest tables have ~50k rows
export const MISMATCH_RATIO = 10;
const TOP_N = 5;
const ratio = (a: number, b: number) => Math.max(a, 1) / Math.max(b, 1);

export function explainFrom(rows: Record<string, unknown>[]): Explain {
  const doc = rows[0]?.["QUERY PLAN"] as Explain[] | undefined;
  if (!doc?.[0]?.Plan) throw new Error("unexpected EXPLAIN output");
  return doc[0];
}

export function nodes(n: PlanNode): PlanNode[] {
  return [n, ...(n.Plans ?? []).flatMap(nodes)];
}

const loops = (n: PlanNode) => n["Actual Loops"] ?? 1;

/** Time spent in the node itself: its total minus its children's totals. */
export function exclusiveMs(n: PlanNode): number {
  const total = (n["Actual Total Time"] ?? 0) * loops(n);
  const kids = (n.Plans ?? []).reduce((s, c) => s + (c["Actual Total Time"] ?? 0) * loops(c), 0);
  return Math.max(0, total - kids);
}

export const describe = (n: PlanNode) =>
  n["Node Type"] + (n["Index Name"] ? ` using ${n["Index Name"]}` : "") + (n["Relation Name"] ? ` on ${n["Relation Name"]}` : "");

/** Rows a seq scan had to read: kept + discarded, over all loops. */
export const scannedRows = (n: PlanNode) => ((n["Actual Rows"] ?? n["Plan Rows"]) + (n["Rows Removed by Filter"] ?? 0)) * loops(n);

export function summarize(e: Explain) {
  const all = nodes(e.Plan);
  return {
    planningMs: e["Planning Time"],
    executionMs: e["Execution Time"],
    totalCost: e.Plan["Total Cost"],
    rootRows: e.Plan["Actual Rows"],
    sharedHit: e.Plan["Shared Hit Blocks"],
    sharedRead: e.Plan["Shared Read Blocks"],
    slowest: all
      .map((n) => ({ node: describe(n), ms: exclusiveMs(n), rows: n["Actual Rows"], loops: loops(n) }))
      .sort((a, b) => b.ms - a.ms)
      .slice(0, TOP_N),
    seqScans: all
      .filter((n) => n["Node Type"] === "Seq Scan" && scannedRows(n) >= SEQ_SCAN_MIN_ROWS)
      .map((n) => ({ table: n["Relation Name"], scanned: scannedRows(n), removed: (n["Rows Removed by Filter"] ?? 0) * loops(n), filter: n.Filter })),
    mismatches: all
      .filter((n) => n["Actual Rows"] !== undefined)
      .map((n) => ({ node: describe(n), est: n["Plan Rows"], act: n["Actual Rows"] as number }))
      .filter((m) => Math.max(m.est, m.act) >= 100 && Math.max(ratio(m.est, m.act), ratio(m.act, m.est)) >= MISMATCH_RATIO)
      .slice(0, TOP_N),
  };
}

export function formatSummary(s: ReturnType<typeof summarize>): string {
  const f = (x?: number) => (x === undefined ? "n/a" : x.toFixed(2));
  const lines = [
    `Execution ${f(s.executionMs)} ms, planning ${f(s.planningMs)} ms, total cost ${f(s.totalCost)}, rows returned ${s.rootRows ?? "n/a"}`,
    `Buffers (root): shared hit ${s.sharedHit ?? "n/a"}, shared read ${s.sharedRead ?? "n/a"}`,
    "",
    "Slowest nodes (exclusive time):",
    ...s.slowest.map((n) => `  ${f(n.ms)} ms  ${n.node}  (rows ${n.rows ?? "n/a"}, loops ${n.loops})`),
    "",
    `Sequential scans reading >= ${SEQ_SCAN_MIN_ROWS} rows:`,
    ...(s.seqScans.length ? s.seqScans.map((n) => `  ${n.table}: ${n.scanned} rows read, ${n.removed} discarded${n.filter ? `, filter ${n.filter}` : ""}`) : ["  none"]),
    "",
    `Row estimate vs actual (off by >= ${MISMATCH_RATIO}x):`,
    ...(s.mismatches.length ? s.mismatches.map((m) => `  ${m.node}: estimated ${m.est}, actual ${m.act}`) : ["  none"]),
  ];
  return lines.join("\n");
}
