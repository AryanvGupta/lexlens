# Corpus-scaling experiment (distractor load)

Tables: `summary.md`; raw: `1x.json 3x.json 10x.json`. Reproduce: see the header of `evals/scale_experiment.py`
(database `lexlens_scale` only). 1x = the 4 baseline Titles (2,852 passages); 3x = + Titles 8, 18, 29 (8,855, 3.1x);
10x = + Titles 15, 20, 21, 31, 38, 47 (27,565, 9.7x). Chunking 300/40, all four retrieval modes on the 44 answerable
dev questions (the 4 baseline Titles stay in every corpus, so gold sections exist; extra Titles are distractors).
Machine: M2 laptop, Postgres in Docker, warm, k=12, bench lock held only for the timing window. Single run per scale
(1x was measured twice, see below).

Not run, on purpose: any answer eval or refusal analysis. With more Titles in the corpus, some dev questions labelled
unanswerable become answerable (their answer may now exist in an added Title), so refusal precision/recall at scale would
be meaningless.

## What moved beyond noise
One question is 0.023. Rerank recall@5 on the identical 1x corpus came out 0.943 in one run and 0.920 in another, so a
one-question move can occur with no change in the data (cross-encoder scores are not bit-stable across runs).
- Retrieval quality, 1x -> 3x: nothing outside noise. Recall@10 is identical for dense (0.955), hybrid (0.955), rerank (0.966).
- Retrieval quality, 1x -> 10x: point estimates fall for every mode: dense recall@10 0.955 -> 0.909 (2 questions: q013, q034),
  hybrid 0.955 -> 0.932 (net 1: q014, q034 lost, q037 gained), rerank 0.966 -> 0.943 (1: q034), lexical 0.716 -> 0.670 (2).
  Exact sign tests on the discordant questions give p = 0.50 (dense, lexical) and 1.0 (hybrid, rerank): none is distinguishable
  from noise at n = 44. The direction is consistent across all four modes and q034 is lost by three of them, which is
  suggestive of a real, small distractor effect (a few percentage points at 10x), not demonstrated. Dense MRR@20 fell
  0.830 -> 0.792 and recall@1 0.750 -> 0.705 (2 questions).
- Rerank is the most stable (recall@10 -1 question, MRR 0.824 -> 0.803).
- q033 (vocabulary gap) stays missed in every mode at every scale; more data did not fix it, as the README claims.
  Failures that existed at 1x are not rescued by 3x or 10x.

## What degraded, in order of confidence
1. Memory (clear, linear): the in-process BM25 index holds 184k / 622k / 2.0M postings (1x/3x/10x); the Python heap it
   occupies is 16 / 51 / 164 MB (tracemalloc), and process RSS grows by 36 / 153 / 468 MB while building it (the RSS figure
   includes the transient list of all (id, lexeme, count) rows fetched from Postgres, and CPython rarely returns that to the
   OS; macOS `ps` RSS is also noisy because of memory compression, so the heap number is the better steady-state figure).
   Build time at startup/first hybrid query: 0.2 / 0.6 / 2.1 s. It is rebuilt whenever the passage count changes, and the API
   process holds it per worker, so memory scales with workers x corpus. Still small at 10x on a laptop; the pod memory limit was not tested.
2. Hybrid latency (modest): p50 59 / 63 / 77 ms, p95 65 / 71 / 98 ms (1x/3x/10x). BM25 scoring walks every posting of each
   query term in Python, which grows with corpus size; at 10x that is +18 ms p50 and +33 ms p95.
3. Rerank p50 311 / 313 / 354 ms: the cross-encoder cost is fixed (30 candidates); the 10x bump is larger than the extra hybrid
   cost alone and I did not isolate it (other agents' jobs may have been running on the laptop; load average ~2), so treat it
   as within noise of timing.
4. Dense is flat: p50 31 / 33 / 33 ms; the SQL-only HNSW query (embedding precomputed, EXPLAIN confirms `passages_emb_idx` is
   used) is 14.8 / 18.2 / 17.1 ms p50, so HNSW search time does not grow with 10x passages here.
5. Ingest time and size are linear: wall clock 45 / 133 / 435 s (about 16 ms per passage, dominated by embedding on CPU, and
   includes model load); table + indexes 19 / 58 / 175 MB (HNSW 5.6 / 17.3 / 53.8 MB, GIN 3.0 / 5.7 / 10.7 MB, heap 3.6 /
   11.6 / 36.2 MB). The first 1x run showed GIN 5.0 MB (total 21 MB) for the same data, so GIN size varies by a couple of MB
   with build state.

## Implication for the README claim
"A larger corpus would add distractors rather than fix the remaining failures" is consistent with this data: the remaining
misses (q033, q038 chunk-level, q023, q025) did not improve at 3x or 10x and the point estimates for every mode move
slightly down at 10x. The magnitude is small (0 to 2 questions at 10x) and not statistically distinguishable, so the supported
statement is "no evidence a bigger corpus helps; weak, not significant evidence that 10x distractors cost a few points of
recall; clear evidence it costs BM25 memory and some hybrid latency".

## Limits
- The extra Titles are unrelated to the dev questions (Crimes, Labor, Education, Commerce, ...), so this measures random
  distractor load, not realistic growth (a realistic larger legal corpus has near-duplicate and topically adjacent text,
  which is a harder test; why q034 is lost was not investigated).
- 44 questions, section-level gold, one run per scale; no per-question bootstrap was computed for the scale comparison
  (only sign tests on recall@10 misses; the committed per-question outputs were not kept).
- Latency is a warm laptop with Apple matrix hardware for the cross-encoder; the kind cluster is far slower for rerank.
- Chunk-level correctness and the answer-level effect (refusals, faithfulness) were not measured at scale.
- Download sizes (MB): see COORD patch scale-data-sources.md; the raw HTML lives outside the repo.
