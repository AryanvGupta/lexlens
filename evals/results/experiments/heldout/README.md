# Held-out results

Run once each, per `evals/dataset/HELDOUT-PROTOCOL.md` (frozen in commit 9adba0c before any run; `heldout.sha256` checks the file).

- `retrieval/` : `EVAL_DATASET=evals/dataset/heldout.jsonl make dev-eval`-style run of `evals/run_eval.py` (dense, lexical, hybrid, rerank on the 40 answerable questions).
- `answers-A-hybrid-k8/` : `ANSWER_MODE=hybrid ANSWER_K=8` answer eval (previous default).
- `answers-B-rerank-k12/` : `ANSWER_MODE=rerank ANSWER_K=12` answer eval (current default).
- `bootstrap/` : 95% bootstrap intervals over the 40 answerable questions (`evals/bootstrap.py` with `EVAL_DATASET`, `EVAL_BASELINE`, `EVAL_RESULTS`).

Commands (from `rag-api/`, with `.env` loaded): `EVAL_DATASET=../evals/dataset/heldout.jsonl EVAL_RESULTS=... uv run python ../evals/run_eval.py`, and the same variables plus `ANSWER_MODE`, `ANSWER_K`, `EVAL_CACHE` for `../evals/run_answer_eval.py`. `rows.json` holds each question's answer, citations and retrieved ids. The adversarial answers were not saved at run time; they were read afterwards by replaying the cached calls, which reproduced `answers.json` exactly.

Known measurement issue: the injection metric overcounts when the model quotes the canary while ignoring the instruction (`h042` under A). See `docs/what-broke.md` entry 5.
