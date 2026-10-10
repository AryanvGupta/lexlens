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

Rerank rescues q037 (hybrid had it at rank 18), moves q018 and q036 to rank 10, and cannot reach q038 because it only re-orders the hybrid top 30. So rerank alone should remove at most 1 of the 5 remaining over-refusals at k=8; that prediction has not been confirmed with an answer eval. The probe's phrases were chosen by hand for four questions, so it is a diagnosis, not a benchmark. 

**Rerank + larger k, answer eval (M7).** The table above predicted that rerank at k=12 would put q018, q036 and q037 into the top 12 and could not help q038. The answer eval (`ANSWER_MODE=rerank ANSWER_K=12 EVAL_RESULTS=... uv run python ../evals/run_answer_eval.py`; results in `evals/results/experiments/answers/`) confirmed that, with hybrid at k=12 as the control for the k effect:

| config | refusal precision | over-refused | faithfulness | $/100 q | LLM p50 |
|---|---|---|---|---|---|
| hybrid, k=8 (current default) | 0.667 | q018 q033 q036 q037 q038 | 0.974 | $1.36 | 3.4 s |
| hybrid, k=12 | 0.667 | q033 q035 q036 q037 q038 | 0.923 | $1.72 | 3.5 s |
| rerank, k=12 | **0.833** | q033 q038 | 1.000 | $1.76 | 3.7 s |

Rerank at k=12 removed exactly the three questions the probe predicted. q038 (answering chunk outside the top 30) and q033 (vocabulary mismatch, see above) remain. Larger k without rerank did not help: it fixed q018 but newly refused q035. Retrieval latency (`evals/search_latency.py`, warm, M2 laptop, not a CPU-limited pod): dense 30 ms, hybrid 57 ms, rerank 313 ms at p50 (359 ms p95), about 8% on top of the LLM call on the laptop. In the kind cluster (10 requests each, k=12, through the Service) it is far worse: hybrid p50 75 ms, rerank p50 1.8 s (p95 2.3 s), about 49% on top of the 3.7 s LLM p50; Token cost per 100 questions rises about 30% with k=12.

Limits: one run per config at the time (the model is sampled once and then cached; the default config was rerun three times later, see "How much to trust these numbers" below), 44 answerable questions where one question is 2.3 points of precision, and the same questions were used to diagnose and to measure. The prediction was written down before the run, which is the strongest evidence here that the mechanism is real, but this is not a held-out result. Adopted afterwards: `/ask` now defaults to rerank at k=12 (`DEFAULT_K`, `DEFAULT_MODE` in `app/generation/ask.py`), both models are loaded at startup and `/ready` waits for them, and the committed `answers.json` is this configuration. The MCP `ask_legal` tool had been sending `k=8` explicitly (max 10), which would have silently run an unmeasured rerank@8, so its `k` is now optional (max 20) and omitted unless the caller sets it.

**Why rerank is slow in the cluster (diagnosed).** Scoring 30 real chunks (median 389 tokens, max 468) with the cross-encoder takes about 1.6 s inside the pod, matching the 1.8 s p50 measured through the API. A plain `docker run` of the same image is the same speed (0.96 s vs 0.99 s on synthetic text), the cgroup has no CPU limit (`cpu.max` = max), and 1 thread takes 1.35 s against 0.99 s for 8, so it is neither Kubernetes nor thread settings. It is raw compute: the M2 laptop runs this model with Apple's matrix hardware (313 ms), the Linux VM with generic fp32 kernels. Levers that cut the compute: 20 chunks instead of 30 takes 1.1 s; `max_length` 256 takes 0.9 s but cuts each chunk roughly in half, so answering text can fall off the end; int8 quantization was not tested validly (my benchmark's model swap did not take effect, which a score correlation of exactly 1.0 gave away). A smaller pool is not free: `evals/pool_check.py` shows the top-12 set that `/ask` sees changes for 13 of 58 questions at pool 25, 31 at pool 20 and 50 at pool 15, so each is a different configuration that needs its own answer eval (about $1.1 each) before it can replace the measured pool of 30. `RERANK_POOL` is now an environment variable (default 30); the default stays at the measured value.

**How much to trust these numbers (bootstrap and reruns, M7).** With 44 retrieval questions the intervals are wide: recall@5 is 0.920 with a 95% interval of about [0.84, 0.99] for dense, hybrid and rerank alike, and every paired difference among those three (recall@5 and MRR@20) includes zero (`evals/results/experiments/bootstrap/`). The data cannot rank dense, hybrid and rerank on retrieval; only "lexical alone is worse" is supported, and earlier sentences in this log that credit hybrid or rerank with an improvement over dense on a retrieval metric are point-estimate observations, not distinguishable effects. For the answer eval I reran the default config (rerank, k=12) three times with empty caches, so generation and the judge were both resampled (`evals/results/experiments/variance/`). Refusal precision was 0.833 in all four runs including the committed one, and q033 and q038 were over-refused every time, so the headline is typical, not lucky, and those two failures are stable behaviour and not sampling noise. Faithfulness was 1.000 in the committed run and 0.976 (41 of 42) in all three reruns, so about 0.98 is the more representative figure. The comparison that carries the case for rerank at k=12 is the answer-level one: it answers q018, q036 and q037 where hybrid at k=8 refused and refuses nothing hybrid at k=8 answered, but with three differing questions an exact two-sided sign test gives p = 0.25, so it cannot by itself rule out chance; hybrid at k=8 was run once. What supports the mechanism is that the chunk probe predicted exactly those three questions before the run. Three reruns bound the variance only coarsely, and four injection prompts show "never followed in 16 attempts" and no more.

**Tried: LLM query rewriting (M7, opt-in `mode=rewrite`, negative result on the dev set).** An opt-in step asks claude-haiku-4-5 to restate the question in statutory vocabulary, retrieves hybrid candidates for both the original and the rewrite, fuses them with RRF, and reranks against the ORIGINAL question. The prompt is generic (no section numbers or dev-question terms; I checked it for the vocabulary of q033). On the 44 dev questions it changed nothing: recall@1/5/10/12 0.716 / 0.920 / 0.966 / 0.977 and MRR 0.822, against the same recall figures and 0.823 for plain rerank, and no question entered or left the top 12 (`evals/rewrite_experiment.py`, `evals/results/experiments/rewrite/`). The model did write "supplemental jurisdiction" for q033 on its own, which pulls 28 USC 1367 into the candidate pool (rank 26 to 30 after reranking, against not in the top 30 before), but the cross-encoder scores candidates against the original question and still keeps it outside the top 12. So the q033 failure is now partly the reranker's, not only candidate recall. Cost: one extra LLM call per request, 1.35 s mean (2.8 s max). Rewrites are nondeterministic (the q033 rank was 30 in one run and 26 in another), it was a single run, and the answer eval was not run because retrieval showed no gain. Not enabled by default; kept as a documented negative result. An obvious variant, reranking against the rewrite or against both, was not tried because choosing it after seeing q033's rank would be tuning on the dev set.

**Not tried yet.** Pulling neighbouring chunks of a hit section and chunk-level gold labels. Score thresholds were not tried: dense scores for unanswerable questions (about 0.69) overlap those for answerable ones. Same 44 questions used to find and to measure the fix, so 0.667 is not a held-out estimate.

**Evidence.** `evals/results/answers.json` (before: 9 over-refusals, precision 0.526; after: 5, 0.667). Not caused by citation checking: `dropped_citations` was 0 for all 9. The hybrid rerun made 97 new LLM calls (cache 95 -> 192; estimate about $0.87), the two k=12 runs 97 and 100 more (192 -> 389; estimate about $1.1 each, token-based about $2.0 together). I did not check the actual bill.

**Injection result.** 0/4 adversarial questions followed the injected instruction (canary absent from the answer). One of the four (q058) was refused rather than answered; the live test `tests/test_injection_live.py` also passes.

## 3. SQL guard ran after the database connection was opened (M5)

**Symptom.** A vitest case written to prove "a rejected `DROP TABLE` never touches the database" failed: with no database configured, `explain_query_plan` answered "SAMPLE_DB_URL is not set" instead of "Only SELECT statements are allowed".

**Diagnosis.** The failing assertion pointed straight at the call order: `explain_query_plan` and `suggest_indexes` called the guard inside `withReadOnlyTx`, after the connection and `BEGIN READ ONLY` had already happened. `compare_plans` already validated first.

**Root cause.** Validation lived only in the shared `runExplain` helper, which is only reached once a transaction is open.

**Fix.** Both tools now call `assertSingleSelect` before `withReadOnlyTx` (the helper still re-validates as defence in depth).

**Evidence.** `mcp-server/test/sqlUnit.test.ts` "guard runs before the database is touched" failed before the change and passes after. Not exploitable as written (the transaction was read-only), but a rejected statement should never cost a connection.

Also found while testing against a freshly rebuilt database: the planner picked a Bitmap scan where the earlier database had an Index Scan, which broke an over-specific plan-shape assertion. The test now asserts what matters (the `rental_date` index is used) rather than the scan node type.

## 4. Reranker could not load in the cluster, and `make up` kept the old image (M7)

**Symptom.** After making rerank the `/ask` default and loading the reranker at startup, `make up` failed: both `rag-api` pods stayed 0/1, failed the startup probe with 503 and were restarted (3, then 5 restarts). Local tests and evals all passed.

**Diagnosis.** `/ready` returned `{"reasons":["models not loaded"]}`; the container log ended in `OSError: We couldn't connect to 'https://huggingface.co' ... couldn't find them in the cached files`, raised from `rerank_model()` in the warm-up thread. The pod could reach huggingface.co (HTTP 200), so it was not a network problem. `rag-api/Dockerfile` bakes only the embedding model and sets `HF_HUB_OFFLINE=1` on purpose, so the reranker could never be fetched.

**Root cause.** I added a second model without adding it to the image bake step. Nothing outside the cluster exercises the offline, baked-image path.

**Fix.** Bake both models in the Dockerfile. That was not enough on its own: the rebuilt image was loaded into the kind node, but the running pods kept the old one, because the tag is a fixed `:local` and `kubectl apply` sees no spec change (restarting a container inside the same pod did not re-resolve the image either). `make up` now runs `rollout restart` for the two deployments when they already exist. Verified by `make up` exiting 0 with both `rag-api` pods 1/1 and 0 restarts. (I first compared the pod's `imageID` with Docker's image ID to show they differed; those are different kinds of identifier and prove nothing. The container log was the real evidence.)

**Evidence.** After the fix: in-cluster `make eval` reproduced all 16 retrieval metrics exactly (dense, lexical, hybrid, rerank); `k8s/verify-probes.sh` passed (34 requests, none non-200, replacement Ready in 11 s); rag-api pods used about 700 to 800 MiB peak against the 2 GiB limit. A live `/ask` was not run in the cluster (it would cost API money); the `/ask` path was exercised by the answer eval locally.
