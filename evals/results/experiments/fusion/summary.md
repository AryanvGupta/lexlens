# Fusion experiment (44 answerable questions, section-level gold, RRF k=60, BM25 k1=1.2 b=0.75)

`vs base` = questions whose recall@5 went up / down relative to `hybrid ts_rank 1:1` (the current hybrid).

| system | recall@1 | recall@5 | recall@10 | mrr@20 | vs base (r@5 up/down) |
|---|---|---|---|---|---|
| dense | 0.750 | 0.920 | 0.955 | 0.830 | +7 / -1 |
| ts_rank (lexical) | 0.409 | 0.648 | 0.716 | 0.513 | +0 / -6 |
| bm25 (lexical) | 0.352 | 0.716 | 0.773 | 0.536 | +0 / -3 |
| hybrid ts_rank dense:lex=1:1 | 0.614 | 0.784 | 0.864 | 0.697 | +0 / -0 |
| hybrid ts_rank dense:lex=2:1 | 0.659 | 0.830 | 0.909 | 0.741 | +2 / -0 |
| hybrid ts_rank dense:lex=3:1 | 0.636 | 0.875 | 0.932 | 0.735 | +4 / -0 |
| hybrid bm25 dense:lex=1:1 | 0.648 | 0.898 | 0.955 | 0.754 | +6 / -1 |
| hybrid bm25 dense:lex=2:1 | 0.659 | 0.920 | 0.955 | 0.781 | +7 / -1 |
| hybrid bm25 dense:lex=3:1 | 0.659 | 0.943 | 0.977 | 0.777 | +8 / -1 |

Over-refusal check (what-broke #2): of the 6 questions whose gold section was missing from the top 8, how many a system retrieves in its top 8:

| system | found in top 8 |
|---|---|
| dense | 4 / 6 |
| ts_rank (lexical) | 1 / 6 |
| bm25 (lexical) | 0 / 6 |
| hybrid ts_rank dense:lex=1:1 | 0 / 6 |
| hybrid ts_rank dense:lex=2:1 | 3 / 6 |
| hybrid ts_rank dense:lex=3:1 | 3 / 6 |
| hybrid bm25 dense:lex=1:1 | 4 / 6 |
| hybrid bm25 dense:lex=2:1 | 4 / 6 |
| hybrid bm25 dense:lex=3:1 | 5 / 6 |
