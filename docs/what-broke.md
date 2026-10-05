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
