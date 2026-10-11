# Held-out test set: protocol (written and committed BEFORE any system was run on it)

`evals/dataset/heldout.jsonl` has 60 questions (40 answerable, 12 unanswerable, 8 adversarial with an injected passage). Its SHA-256 is in `heldout.sha256`; the commit that adds both is dated before any held-out result exists.

## Provenance
- Drafted by an AI agent from the corpus text alone, with a rule that it must never run the system on the questions. Each answerable gold section carries a verbatim supporting quote; unanswerable rows were checked with keyword searches over all 2,852 passages.
- The 48 gold sections share no id with the 45 gold ids of the dev set (`evals/dataset/questions.jsonl`); an independent check of full ids confirmed it, after an earlier version of the draft failed that check and three rows were replaced.
- Reviewed by the orchestrating assistant (Claude), not by a human: kept as drafted except `h054`, replaced because its original wording ("What can a debt collector not do when contacting me about an old debt?") could be answered defensibly from the bankruptcy stay in 11 U.S.C. 362(a)(6), which would score a reasonable answer as a failed refusal. The replacement ("How many hours can a commercial truck driver legally drive in one day?") has zero hits for the hours-of-service terms in the corpus.
- No question was run through any retrieval or answer code before the freeze commit. The author of the repo did not write the questions.

## What will be run, once each
Answer eval (`evals/run_answer_eval.py` with `EVAL_DATASET=evals/dataset/heldout.jsonl`), generation `claude-sonnet-5-5` at low effort, judge `claude-haiku-4-5`:
- **A: the previous default**, `ANSWER_MODE=hybrid ANSWER_K=8`.
- **B: the current default**, `ANSWER_MODE=rerank ANSWER_K=12`.
Retrieval eval (`evals/run_eval.py`, same dataset): dense, lexical, hybrid, rerank on the 40 answerable questions.

## Primary question
Does B over-refuse fewer answerable questions than A on questions it was not tuned on? Measured as the count of the 40 answerable (non-adversarial) questions that are refused, with an exact two-sided sign test on the questions where A and B differ.

## Also reported, whatever the outcome
Refusal precision and recall; recall@1/5/10 and MRR@20 per retrieval mode with bootstrap 95% intervals (40 questions); citation validity; answers citing a gold section; faithfulness (LLM judge, still unvalidated by humans); injection followed out of the 8 adversarial rows; cost and latency.

## Rules
1. Each configuration is run once. A run that crashes may be rerun unchanged; a run whose result is merely disappointing may not.
2. The dataset, prompts, models, k, modes and this protocol are not changed after the first result is seen. Problems found in the questions afterwards (a bad gold label, an ambiguous question) are reported next to the result and not fixed in the headline numbers.
3. Every result is published in the README and `docs/what-broke.md`, including negative ones.
4. Budget: about $2.5 in total (two answer evals of 60 questions). Costs are logged.

## Known limits
Sixty questions, with 12 unanswerable and 8 adversarial rows, so counts matter more than percentages. One run per configuration, so no variance estimate on this set. The questions were written by a model and reviewed by a model; a human has not read them. The same assistant that chose the configurations also runs the evaluation.
