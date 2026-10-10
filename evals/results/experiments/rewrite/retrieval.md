# Query-rewrite experiment (44 answerable dev questions, rewrite model `claude-haiku-4-5`)

| mode | recall@1 | recall@5 | recall@10 | recall@12 | mrr@30 |
|---|---|---|---|---|---|
| hybrid | 0.659 | 0.920 | 0.955 | 0.955 | 0.781 |
| rerank | 0.716 | 0.920 | 0.966 | 0.977 | 0.823 |
| rewrite | 0.716 | 0.920 | 0.966 | 0.977 | 0.822 |

q033 gold ['usc-28:1367']: rank hybrid=None, rerank=None, rewrite=30 (None = outside top 30).
q033 rewrite text: `supplemental jurisdiction federal court state law claims pendant claim ancillary jurisdiction`

Gold fully in top-12 under rerank but NOT rewrite: none
Gold fully in top-12 under rewrite but NOT rerank: none
Rewrite calls that fell back to the original question: none
Rewrite LLM step wall clock per question: mean 1.35s, max 2.77s.

Per-question rank of first gold section (hybrid / rerank / rewrite):

- q001: 1 / 1 / 1
- q002: 1 / 1 / 1
- q003: 1 / 1 / 1
- q004: 2 / 2 / 2
- q005: 1 / 3 / 3
- q006: 1 / 1 / 1
- q007: 1 / 1 / 1
- q008: 1 / 1 / 1
- q009: 1 / 1 / 1
- q010: 2 / 1 / 1
- q011: 2 / 1 / 1
- q012: 1 / 1 / 1
- q013: 4 / 7 / 7
- q014: 2 / 1 / 1
- q015: 1 / 2 / 2
- q016: 1 / 1 / 1
- q017: 1 / 1 / 1
- q018: 1 / 2 / 2
- q019: 1 / 1 / 1
- q020: 3 / 1 / 1
- q021: 4 / 3 / 3
- q022: 1 / 1 / 1
- q023: 2 / 1 / 1
- q024: 2 / 1 / 1
- q025: 1 / 1 / 1
- q026: 1 / 1 / 1
- q027: 1 / 1 / 1
- q028: 1 / 2 / 2
- q029: 1 / 1 / 1
- q030: 1 / 1 / 1
- q031: 1 / 1 / 1
- q032: 2 / 2 / 2
- q033: None / None / 30
- q034: 1 / 1 / 1
- q035: 1 / 4 / 5
- q036: 1 / 1 / 1
- q037: 15 / 1 / 1
- q038: 1 / 1 / 1
- q039: 2 / 1 / 1
- q040: 1 / 1 / 1
- q041: 9 / 6 / 8
- q042: 1 / 1 / 1
- q043: 1 / 1 / 1
- q044: 3 / 2 / 2
