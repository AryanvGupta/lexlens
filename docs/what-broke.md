# What broke

## 1. Hybrid retrieval scored worse than dense (M2)

**Symptom.** First `make eval` (44 answerable questions): hybrid (RRF over dense + lexical) was *below* dense, the opposite of what hybrid is supposed to do.

| mode | recall@5 | mrr@20 |
|---|---|---|
| dense | 0.898 | 0.678 |
| lexical | 0.545 | 0.417 |
| hybrid | 0.659 | 0.566 |

**Diagnosis.** Looked at lexical top-5 for failing questions (`search_lexical` on q011, q013, q017). Not a query bug: the OR-ed tsquery was correct. Two causes visible in the output:
1. The section heading (e.g. "§106. Exclusive rights in copyrighted works", "§101. Inventions patentable") lived in the `title` column but was neither embedded nor in the `tsvector`, so the most informative words for a question were unsearchable.
2. `ts_rank` has no IDF: "patent" in Title 35 or "copyright" in Title 17 appear everywhere and do not discriminate.

**Fix.** Embed `"{title}\n{text}"` and build the `tsvector` from `title || ' ' || text`. The stored `text` column stays raw so M3 quote verification still works. `make ingest` now drops and rebuilds the table (derived data).

**Evidence.** `make eval` before/after:

| mode | recall@5 before | after | mrr@20 before | after |
|---|---|---|---|---|
| dense | 0.898 | 0.920 | 0.678 | 0.830 |
| lexical | 0.545 | 0.648 | 0.417 | 0.513 |
| hybrid | 0.659 | 0.784 | 0.566 | 0.697 |

**Not fixed.** Hybrid is still below dense on this dataset. `ts_rank` is a weak lexical ranker, and equal-weight RRF lets it pull good dense hits down. Not tuned further here; to be examined in the M7 experiments (weighted fusion, a real BM25 implementation).

**Caveat.** The same 44 questions were used to find the problem and to measure the fix. One change was applied and measured, but the numbers are not a held-out estimate.

## 2. Refusal precision 0.526: the system refuses answerable questions (M3)

**Symptom.** First answer eval (`claude-sonnet-5-5`, 54 questions + 4 adversarial): refusal recall 1.000 (all 10 unanswerable questions refused) but precision 0.526. 19 refusals, 9 of them on answerable questions (9/44 = 20%).

**Diagnosis.** Replayed the cached `ask` calls for the 9 and checked whether the gold section was in the top-8 retrieved passages:
- 6/9: gold section **not retrieved** at all (q011, q013, q020, q021, q033, q041). The model's stated reasons matched: the passages did not contain the relevant text.
- 3/9: gold section retrieved, but only an unhelpful chunk of it (q036 §362, q037 §109, q038 §547: e.g. §109(h) without the eligibility text). Long sections are split into several chunks and section-level gold counts a hit on any chunk.

**Root cause.** Retrieval, not the model. The refusal rule is doing what it should (refuse on thin evidence); the evidence was thin. Section-level recall@8 also overstates answerability, because retrieving the wrong chunk of the right section counts as a hit.

**Fix.** None yet. Candidates for M7, to be measured: larger k, retrieving neighbouring chunks of a hit section, the optional rerank step, and chunk-level gold labels. Retrieval score thresholds were not tried: dense scores for unanswerable questions (about 0.69) overlap those for answerable ones.

**Evidence.** `evals/results/answers.json`. Not caused by citation checking: `dropped_citations` was 0 for all 9.

**Injection result.** 0/4 adversarial questions followed the injected instruction (canary absent from the answer). One of the four (q058) was refused rather than answered; the live test `tests/test_injection_live.py` also passes.

## 3. SQL guard ran after the database connection was opened (M5)

**Symptom.** A vitest case written to prove "a rejected `DROP TABLE` never touches the database" failed: with no database configured, `explain_query_plan` answered "SAMPLE_DB_URL is not set" instead of "Only SELECT statements are allowed".

**Diagnosis.** The failing assertion pointed straight at the call order: `explain_query_plan` and `suggest_indexes` called the guard inside `withReadOnlyTx`, after the connection and `BEGIN READ ONLY` had already happened. `compare_plans` already validated first.

**Root cause.** Validation lived only in the shared `runExplain` helper, which is only reached once a transaction is open.

**Fix.** Both tools now call `assertSingleSelect` before `withReadOnlyTx` (the helper still re-validates as defence in depth).

**Evidence.** `mcp-server/test/sqlUnit.test.ts` "guard runs before the database is touched" failed before the change and passes after. Not exploitable as written (the transaction was read-only), but a rejected statement should never cost a connection.

Also found while testing against a freshly rebuilt database: the planner picked a Bitmap scan where the earlier database had an Index Scan, which broke an over-specific plan-shape assertion. The test now asserts what matters (the `rental_date` index is used) rather than the scan node type.
