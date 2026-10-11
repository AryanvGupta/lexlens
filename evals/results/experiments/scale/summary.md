| scale | passages | ingest s | table+idx MB (heap/HNSW/GIN) | BM25 build s | BM25 RSS +MB (heap MB) | process RSS MB |
|---|---|---|---|---|---|---|
| 1x | 2852 | 45 | 19 (4/6/3) | 0.2 | 36 (16) | 290 |
| 3x | 8855 | 133 | 58 (12/17/6) | 0.6 | 153 (51) | 399 |
| 10x | 27565 | 435 | 175 (36/54/11) | 2.1 | 468 (164) | 661 |

| scale | mode | p50 ms | p95 ms |
|---|---|---|---|
| 1x | dense | 31 | 35 |
| 1x | hybrid | 59 | 65 |
| 1x | rerank | 311 | 359 |
| 1x | dense SQL only (HNSW used: True) | 14.8 | 17.9 |
| 3x | dense | 33 | 36 |
| 3x | hybrid | 63 | 71 |
| 3x | rerank | 313 | 352 |
| 3x | dense SQL only (HNSW used: True) | 18.2 | 23.1 |
| 10x | dense | 33 | 35 |
| 10x | hybrid | 77 | 98 |
| 10x | rerank | 354 | 401 |
| 10x | dense SQL only (HNSW used: True) | 17.1 | 24.8 |

| scale | mode | recall@1 | recall@5 | recall@10 | mrr@20 |
|---|---|---|---|---|---|
| 1x | dense | 0.750 | 0.920 | 0.955 | 0.830 |
| 1x | lexical | 0.409 | 0.648 | 0.716 | 0.513 |
| 1x | hybrid | 0.659 | 0.920 | 0.955 | 0.781 |
| 1x | rerank | 0.716 | 0.920 | 0.966 | 0.823 |
| 3x | dense | 0.750 | 0.920 | 0.955 | 0.830 |
| 3x | lexical | 0.409 | 0.602 | 0.716 | 0.508 |
| 3x | hybrid | 0.636 | 0.898 | 0.955 | 0.761 |
| 3x | rerank | 0.716 | 0.943 | 0.966 | 0.830 |
| 10x | dense | 0.705 | 0.898 | 0.909 | 0.792 |
| 10x | lexical | 0.409 | 0.602 | 0.670 | 0.502 |
| 10x | hybrid | 0.636 | 0.852 | 0.932 | 0.753 |
| 10x | rerank | 0.693 | 0.920 | 0.943 | 0.803 |
