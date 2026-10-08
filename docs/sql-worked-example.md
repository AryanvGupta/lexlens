# Worked example: tuning a query with the SQL tools

Everything below is real output from the three MCP SQL tools (`explain_query_plan`, `suggest_indexes`, `compare_plans`) against the pagila sample database on one laptop (Postgres 18, pagila freshly loaded). Timings are machine-specific and the planner's choice of scan type can vary with table statistics, so rerun it yourself rather than expecting identical numbers. A single `explain_query_plan` run is noisy (the first call below took about twice as long as the psql run of the same query); `compare_plans` uses the median of three for that reason.

Reproduce: `make dev-sample-db`, `cd mcp-server && npm install && npm run build`, set `SAMPLE_DB_URL` (see `.env.example`), then call the tools from any MCP client (the `tune_query` prompt walks through this workflow), or run the live tests: `make test`.

## The query

Find the rentals on one day (`rental` has 51,805 rows):

```sql
SELECT * FROM rental WHERE date_trunc('day', rental_date) = '2024-06-15'
```

### 1. Where does the time go? (`explain_query_plan`)

```
Execution 11.18 ms, planning 0.58 ms, total cost 1531.92, rows returned 20
Buffers (root): shared hit 624, shared read 0

Slowest nodes (exclusive time):
  11.14 ms  Seq Scan on rental  (rows 20, loops 1)

Sequential scans reading >= 1000 rows:
  rental: 51805 rows read, 51785 discarded, filter (date_trunc('day'::text, rental_date) = '2024-06-15 00:00:00+00'::timestamp with time zone)

Row estimate vs actual (off by >= 10x):
  Seq Scan on rental: estimated 303, actual 20
```

The raw plan for the same query (`EXPLAIN (ANALYZE, BUFFERS)` in psql):

```
Seq Scan on rental  (cost=0.00..1531.92 rows=303 width=56) (actual time=3.570..5.667 rows=20.00 loops=1)
  Filter: (date_trunc('day'::text, rental_date) = '2024-06-15 00:00:00+00'::timestamp with time zone)
  Rows Removed by Filter: 51785
  Buffers: shared hit=624
Planning:
  Buffers: shared hit=130
Planning Time: 0.161 ms
Execution Time: 5.703 ms
```

It reads every row (51,785 discarded) to keep 20, because the filter applies a function to the column.

### 2. Would an index help? (`suggest_indexes`)

```
Baseline planner cost 1531.92.
Validated with hypothetical indexes (hypopg); nothing was created.

CREATE INDEX ON public."rental" ("rental_date");
  why: sequential scan reads 51805 rows to apply filter (date_trunc('day'::text, rental_date) = '2024-06-15 00:00:00+00'::timestamp with time zone)
  evidence: planner cost 1531.92 -> 1531.92, index would NOT be used
```

No. The tool proposes an index on `rental_date`, then checks it with a hypothetical index (hypopg) and reports that the planner would **not** use it: `date_trunc('day', rental_date) = ...` hides the column from the index. The problem is the predicate, not a missing index. (A limit of the heuristic: it does not look at existing indexes. `rental` already has `idx_unq_rental_rental_date_inventory_id_customer_id`, whose first column is `rental_date`.)

### 3. Rewrite and compare (`compare_plans`)

Same question as a range predicate:

```sql
SELECT * FROM rental WHERE rental_date >= '2024-06-15' AND rental_date < '2024-06-16'
```

Raw plan of the rewrite:

```
Bitmap Heap Scan on rental  (cost=11.40..534.21 rows=303 width=56) (actual time=0.014..0.016 rows=20.00 loops=1)
  Recheck Cond: ((rental_date >= '2024-06-15 00:00:00+00'::timestamp with time zone) AND (rental_date < '2024-06-16 00:00:00+00'::timestamp with time zone))
  Heap Blocks: exact=1
  Buffers: shared hit=3
  ->  Bitmap Index Scan on idx_unq_rental_rental_date_inventory_id_customer_id  (cost=0.00..11.32 rows=303 width=0) (actual time=0.005..0.005 rows=20.00 loops=1)
        Index Cond: ((rental_date >= '2024-06-15 00:00:00+00'::timestamp with time zone) AND (rental_date < '2024-06-16 00:00:00+00'::timestamp with time zone))
        Index Searches: 1
        Buffers: shared hit=2
Planning:
  Buffers: shared hit=130
Planning Time: 0.287 ms
Execution Time: 0.041 ms
```

```
Execution (median of 3): 4.56 ms -> 0.01 ms (speedup 350.77x)
Planner cost: 1531.92 -> 534.21
Shared buffers hit/read: 624/0 -> 3/0
Rows returned: 20 -> 20

Only in BEFORE plan: Seq Scan on rental
Only in AFTER plan: Bitmap Heap Scan on rental; Bitmap Index Scan using idx_unq_rental_rental_date_inventory_id_customer_id
```

Median of three runs, same 20 rows returned, a sequential scan replaced by an index-backed scan. `compare_plans` only compares the returned row counts; it does not prove the two queries are equivalent in general.

## A case where an index does help

```sql
SELECT * FROM rental WHERE staff_id = 1 AND return_date IS NULL
```

```
Baseline planner cost 1380.60.
Validated with hypothetical indexes (hypopg); nothing was created.

CREATE INDEX ON public."rental" ("staff_id", "return_date");
  why: sequential scan reads 51805 rows to apply filter ((return_date IS NULL) AND (staff_id = 1))
  evidence: planner cost 1380.60 -> 11.75, index WOULD be used
```

Here the hypothetical index lowers the planner's cost estimate and would be used. This is planner cost evidence, not a measured speedup: no index was created (the role is read-only), so confirm on a copy of the database before adding it anywhere real.

## How the tools stay safe

Layers, outermost first:

1. **Parser guard** (`mcp-server/src/sql/guard.ts`): the real Postgres parser (libpg-query) accepts exactly one `SELECT`. It rejects any other statement type, multi-statement input, data-modifying CTEs, `SELECT INTO`, locking clauses and a denylist of dangerous functions (`pg_sleep`, `nextval`, `set_config`, `lo_*`, ...). The denylist is defence in depth and is not exhaustive.
2. **Read-only transaction**: every call runs in `BEGIN READ ONLY`, with a statement timeout, and is rolled back.
3. **Database role**: the tools connect as `lexlens_ro`, which has `SELECT` only, `default_transaction_read_only=on` and a 5 s `statement_timeout`.

`mcp-server/test/guard.test.ts` and `test/sqlLive.test.ts` cover `DROP TABLE`, `SELECT pg_sleep(60)` and multi-statement input at the guard, and show that layers 2 and 3 hold even if the guard is bypassed (a raw `pg_sleep(10)` is cancelled by the timeout; raw `INSERT`/`DROP` and even `SET transaction_read_only = off` followed by an `INSERT` fail).
