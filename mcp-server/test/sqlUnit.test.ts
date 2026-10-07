import { describe, expect, test } from "vitest";
import { candidates, ddl } from "../src/sql/candidates.js";
import { SampleDb } from "../src/sql/db.js";
import { explainFrom, formatSummary, summarize, type Explain } from "../src/sql/plan.js";
import { connect, text } from "./helpers.js";

// Hand-built plan shaped like EXPLAIN (ANALYZE, FORMAT JSON): hash join of a big filtered seq scan and a small table.
const plan: Explain = {
  "Planning Time": 0.5,
  "Execution Time": 20,
  Plan: {
    "Node Type": "Hash Join", "Total Cost": 900, "Plan Rows": 100, "Actual Rows": 5000, "Actual Loops": 1, "Actual Total Time": 20,
    "Hash Cond": "(r.inventory_id = i.inventory_id)", "Shared Hit Blocks": 10, "Shared Read Blocks": 2,
    Plans: [
      { "Node Type": "Seq Scan", "Relation Name": "rental", Alias: "r", Filter: "((staff_id = 1) AND (return_date IS NULL))", "Rows Removed by Filter": 40000, "Total Cost": 800, "Plan Rows": 100, "Actual Rows": 5000, "Actual Loops": 1, "Actual Total Time": 15 },
      { "Node Type": "Seq Scan", "Relation Name": "tiny", Alias: "i", "Total Cost": 5, "Plan Rows": 10, "Actual Rows": 10, "Actual Loops": 1, "Actual Total Time": 1 },
    ],
  },
};
const cols = new Map([["rental", ["rental_id", "staff_id", "return_date", "inventory_id"]], ["tiny", ["inventory_id"]]]);

describe("plan summary", () => {
  test("exclusive time, big seq scans only, and estimate mismatches", () => {
    const s = summarize(plan);
    expect(s.slowest[0].node).toBe("Seq Scan on rental");
    expect(s.slowest[0].ms).toBe(15);
    expect(s.slowest.find((n) => n.node === "Hash Join")?.ms).toBe(4); // 20 - 15 - 1
    expect(s.seqScans.map((x) => x.table)).toEqual(["rental"]); // tiny is below the threshold
    expect(s.mismatches.map((m) => m.node)).toContain("Hash Join"); // est 100 vs actual 5000
    expect(formatSummary(s)).toContain("rental: 45000 rows read, 40000 discarded");
  });
  test("explainFrom rejects non-plan output", () => {
    expect(() => explainFrom([{ nope: 1 }])).toThrow();
  });
});

describe("index candidates", () => {
  test("equality filter columns first; join column on the big scan; small tables skipped", () => {
    const c = candidates(plan.Plan, cols);
    expect(c.map(ddl)).toEqual([
      'CREATE INDEX ON public."rental" ("staff_id")'.replace('("staff_id")', '("staff_id", "return_date")'),
      'CREATE INDEX ON public."rental" ("inventory_id")',
    ]);
  });
  test("identifiers are quoted", () => {
    expect(ddl({ table: 'we"ird', columns: ["a b"], reason: "" })).toBe('CREATE INDEX ON public."we""ird" ("a b")');
  });
});

describe("tools without a usable database", () => {
  const rag = { search: async () => [], ask: async () => { throw new Error("unused"); } };
  test("SAMPLE_DB_URL unset", async () => {
    const out = await (await connect(rag as never)).callTool({ name: "explain_query_plan", arguments: { sql: "SELECT 1" } });
    expect(out.isError).toBe(true);
    expect(text(out)).toContain("SAMPLE_DB_URL is not set");
  });
  test("unreachable database", async () => {
    const out = await (await connect(rag as never, new SampleDb("postgresql://u:p@127.0.0.1:1/x"))).callTool({ name: "explain_query_plan", arguments: { sql: "SELECT 1" } });
    expect(out.isError).toBe(true);
    expect(text(out)).toContain("unreachable");
  });
  test("guard runs before the database is touched", async () => {
    const out = await (await connect(rag as never)).callTool({ name: "explain_query_plan", arguments: { sql: "DROP TABLE film" } });
    expect(out.isError).toBe(true);
    expect(text(out)).toContain("Only SELECT");
  });
});
