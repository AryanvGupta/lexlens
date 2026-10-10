# What broke

Note: entries 1 to 3 predate the M6 rename of the make targets. `make eval` and `make ingest` in those entries are now `make dev-eval` and `make dev-ingest`; `make eval` and `make ingest` now run against the Kubernetes cluster.

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

**Not fixed at M2.** Hybrid was still below dense on this dataset. `ts_rank` is a weak lexical ranker, and equal-weight RRF lets it pull good dense hits down.

**Fixed in M7.** `evals/fusion_experiment.py` swept a fixed grid (BM25 vs `ts_rank`, dense weight 1, 2 or 3). Hybrid is now weighted RRF of dense + BM25 at 2:1: recall@5 0.784 -> 0.920 and recall@10 0.864 -> 0.955, equal to dense, but recall@1 (0.659 vs 0.750) and MRR (0.781 vs 0.830) stay below dense. Reproduce: `cd rag-api && uv run python ../evals/fusion_experiment.py` (results in `evals/results/experiments/fusion/`). The sweep and the measurement use the same 44 questions, and 3:1 scored marginally higher but sits at the edge of the grid, so the choice of 2:1 over dense-only is a judgment call, not a proven win.

**Caveat.** The same 44 questions were used to find the problem and to measure the fix. One change was applied and measured, but the numbers are not a held-out estimate.

## 2. Refusal precision 0.526: the system refuses answerable questions (M3)

**Symptom.** First answer eval (`claude-sonnet-5-5`, 54 questions + 4 adversarial): refusal recall 1.000 (all 10 unanswerable questions refused) but precision 0.526. 19 refusals, 9 of them on answerable questions (9/44 = 20%).

**Diagnosis.** Replayed the cached `ask` calls for the 9 and checked whether the gold section was in the top-8 retrieved passages:
- 6/9: gold section **not retrieved** at all (q011, q013, q020, q021, q033, q041). The model's stated reasons matched: the passages did not contain the relevant text.
- 3/9: gold section retrieved, but only an unhelpful chunk of it (q036 §362, q037 §109, q038 §547: e.g. §109(h) without the eligibility text). Long sections are split into several chunks and section-level gold counts a hit on any chunk.

**Root cause.** Retrieval, not the model. The refusal rule is doing what it should (refuse on thin evidence); the evidence was thin. Section-level recall@8 also overstates answerability, because retrieving the wrong chunk of the right section counts as a hit.

**Fix (partial, M7).** The hybrid fusion change in entry 1: `/ask` defaults to hybrid, and the old hybrid retrieved the gold section for 0 of the 6 retrieval misses (dense alone: 4 of 6). After the change, refusal precision went 0.526 -> 0.667 with recall unchanged at 1.000, and over-refusals went 9 -> 5 (recorded as `over_refused` in `answers.json`). Fixed: q011, q013, q020, q021, q041. Still refused: q033, q036, q037, q038. Newly refused: q018.

**Why 5 remain.** Checked with the model's cached refusal reasons and the gold rank per ranker:
- q018, q036, q037, q038: the gold *section* is retrieved (q018's §154 is rank 1) but not the chunk with the answer. The q018 reason says the passages lack the general 20-year term in §154(a)(2). Same class as the original 3, not a fusion regression: the old retrieval happened to include the right chunk. Section-level gold hides this.
- q033 (§1367 "supplemental jurisdiction", asked as "related state-law claims"): vocabulary mismatch. Dense never ranks it in the top 50; BM25 has it at rank 16, and the 2:1 weights push it to rank 51 in the fused list (the old hybrid had it at 15). It was not in the top 8 under either hybrid.

**Rerank, tried (M7).** A cross-encoder over the top 30 hybrid candidates (`mode="rerank"`) gives recall@1 0.716 and MRR 0.823 vs hybrid 0.659 / 0.781 (`make dev-eval`). Section-level metrics cannot show whether it fixes the wrong-chunk failures, so `evals/chunk_probe.py` finds the chunk that holds the answering phrase and reports its rank (bold = inside the top 8 that `/ask` sees):

| question | answering chunk | dense | hybrid | rerank |
|---|---|---|---|---|
| q018 | usc-35:154 chunk 0 | rank 30 | rank 11 | rank 10 |
| q036 | usc-11:362 chunk 0 | rank 12 | rank 13 | rank 10 |
| q037 | usc-11:109 chunks 0, 1 | **rank 3** | rank 18 | **rank 4** |
| q038 | usc-11:547 chunk 0 | > 30 | > 30 | > 30 |

Rerank rescues q037 (hybrid had it at rank 18), moves q018 and q036 to rank 10, and cannot reach q038 because it only re-orders the hybrid top 30. So rerank alone should remove at most 1 of the 5 remaining over-refusals at k=8; that prediction has not been confirmed with an answer eval. The probe's phrases were chosen by hand for four questions, so it is a diagnosis, not a benchmark. Rerank latency was not measured.

**Not tried yet.** Larger k (the table suggests k of 12 would include q018 and q036 under rerank, at about 50% more prompt tokens), pulling neighbouring chunks of a hit section, and chunk-level gold labels. Score thresholds were not tried: dense scores for unanswerable questions (about 0.69) overlap those for answerable ones. Same 44 questions used to find and to measure the fix, so 0.667 is not a held-out estimate.

**Evidence.** `evals/results/answers.json` (before: 9 over-refusals, precision 0.526; after: 5, 0.667). Not caused by citation checking: `dropped_citations` was 0 for all 9. The rerun made 97 new LLM calls (cache 95 -> 192); the pre-run estimate was about $0.87 and I did not measure the exact bill.

**Injection result.** 0/4 adversarial questions followed the injected instruction (canary absent from the answer). One of the four (q058) was refused rather than answered; the live test `tests/test_injection_live.py` also passes.

## 3. SQL guard ran after the database connection was opened (M5)

**Symptom.** A vitest case written to prove "a rejected `DROP TABLE` never touches the database" failed: with no database configured, `explain_query_plan` answered "SAMPLE_DB_URL is not set" instead of "Only SELECT statements are allowed".

**Diagnosis.** The failing assertion pointed straight at the call order: `explain_query_plan` and `suggest_indexes` called the guard inside `withReadOnlyTx`, after the connection and `BEGIN READ ONLY` had already happened. `compare_plans` already validated first.

**Root cause.** Validation lived only in the shared `runExplain` helper, which is only reached once a transaction is open.

**Fix.** Both tools now call `assertSingleSelect` before `withReadOnlyTx` (the helper still re-validates as defence in depth).

**Evidence.** `mcp-server/test/sqlUnit.test.ts` "guard runs before the database is touched" failed before the change and passes after. Not exploitable as written (the transaction was read-only), but a rejected statement should never cost a connection.

Also found while testing against a freshly rebuilt database: the planner picked a Bitmap scan where the earlier database had an Index Scan, which broke an over-specific plan-shape assertion. The test now asserts what matters (the `rental_date` index is used) rather than the scan node type.
