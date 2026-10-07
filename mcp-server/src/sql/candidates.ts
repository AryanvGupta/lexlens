import { nodes, scannedRows, SEQ_SCAN_MIN_ROWS, type PlanNode } from "./plan.js";

export interface Candidate {
  table: string;
  columns: string[];
  reason: string;
}

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const MAX_CANDIDATES = 5;
const MAX_COLUMNS = 3;

/**
 * Heuristic: look at big sequential scans and propose indexes on the columns their
 * filter or join conditions mention (equality columns first).
 * ponytail: regex over plan text, no expression or partial indexes; replace with AST column resolution if suggestions miss.
 */
export function candidates(root: PlanNode, tableColumns: Map<string, string[]>): Candidate[] {
  const all = nodes(root);
  const conds = all.flatMap((n) => ["Hash Cond", "Merge Cond", "Join Filter"].map((k) => n[k]).filter((v): v is string => typeof v === "string"));
  const out: Candidate[] = [];
  for (const n of all) {
    const table = n["Relation Name"];
    if (n["Node Type"] !== "Seq Scan" || !table || scannedRows(n) < SEQ_SCAN_MIN_ROWS) continue;
    const cols = tableColumns.get(table) ?? [];
    if (typeof n.Filter === "string") {
      const filter = n.Filter.replace(/'[^']*'/g, "''").toLowerCase();
      const used = cols.filter((c) => new RegExp(`\\b${escapeRe(c)}\\b`).test(filter));
      const eq = used.filter((c) => new RegExp(`\\(?\\b${escapeRe(c)}\\b\\)?(::[a-z ]+)? = `).test(filter));
      const picked = [...eq, ...used.filter((c) => !eq.includes(c))].slice(0, MAX_COLUMNS);
      if (picked.length) out.push({ table, columns: picked, reason: `sequential scan reads ${scannedRows(n)} rows to apply filter ${n.Filter}` });
    }
    const alias = (n.Alias ?? table).toLowerCase();
    const joinCols = new Set<string>();
    for (const c of conds) for (const m of c.toLowerCase().matchAll(new RegExp(`\\b${escapeRe(alias)}\\.(\\w+)`, "g"))) if (cols.includes(m[1])) joinCols.add(m[1]);
    for (const c of joinCols) out.push({ table, columns: [c], reason: `sequential scan of ${scannedRows(n)} rows on a join column` });
  }
  const seen = new Set<string>();
  return out.filter((c) => !seen.has(ddl(c)) && seen.add(ddl(c))).slice(0, MAX_CANDIDATES);
}

const q = (id: string) => `"${id.replace(/"/g, '""')}"`;
/** Identifiers come from the plan/information_schema, never from user text; quoted anyway. */
export const ddl = (c: Candidate) => `CREATE INDEX ON public.${q(c.table)} (${c.columns.map(q).join(", ")})`;
