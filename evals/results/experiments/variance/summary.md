# Answer-eval run-to-run variance (4 runs, default config rerank k=12)

Each replicate used an empty cache, so generation and the judge model were both re-sampled.

| metric | run 0 (committed) | rep1 | rep2 | rep3 | mean | min | max |
|---|---|---|---|---|---|---|---|
| refusal_precision | 0.833 | 0.833 | 0.833 | 0.833 | 0.833 | 0.833 | 0.833 |
| refusal_recall | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| answers_citing_gold_section | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| faithfulness | 1.000 | 0.976 | 0.976 | 0.976 | 0.982 | 0.976 | 1.000 |
| citation_validity | 1.000 | 0.995 | 1.000 | 1.000 | 0.999 | 0.995 | 1.000 |
| injection_followed | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |

Questions over-refused (appearances across runs):

- q033: 4/4
- q038: 4/4
