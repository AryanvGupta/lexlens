Rerun of the chunking experiment on the current stack (weighted dense + BM25 hybrid at 2:1, and the
cross-encoder `rerank` mode), 44 answerable dev questions, section-level gold, database `lexlens_scale`.
Reproduce: `DATABASE_URL=.../lexlens_scale EXPECT_DB=lexlens_scale CHUNK_OUT=evals/results/experiments/chunking-current-stack
LEXLENS_RAW=<dir with the 4 baseline .htm> evals/chunking_experiment.sh`. The 300/40 row reproduces the committed baseline.

Reading it (one question = 0.023; recall@10 below is counted per question from `not_fully_found_in_top10`):
- Questions that differ in recall@10 between 300/40 and each other config are 0 to 4 per mode. The most lopsided
  case is hybrid at 75/10, 1 question better and 3 worse (exact sign test p = 0.62). No difference reaches p < 0.5.
  Every recall@5 / recall@10 / MRR difference is within one to four questions, i.e. within noise.
- Rerank is flat across all four sizes (recall@10 0.943 to 0.966, MRR 0.811 to 0.837).
- Hybrid is the most chunk-size-sensitive mode in point estimates: 300/0 is nominally the best (recall@5 0.943,
  recall@10 0.977) and 150/20 the worst (recall@5 0.852, MRR 0.731), but 0.943 vs 0.920 is one question and
  0.852 vs 0.920 is three; neither is distinguishable from noise at n = 44.
- So the earlier conclusion holds on the current stack: chunk size in this range is not a demonstrated lever, and
  300/40 stays (the default). Smaller chunks (150/20, 75/10) never beat it on dense, hybrid or rerank recall@10 (lexical 75/10 is 1 question better) and
  cost 1.8x / 3.6x the rows; 300/0 is nominally equal or marginally better (1 to 2 questions, not distinguishable), so there is no evidence
  for changing the default; overlap's value for phrases split at chunk boundaries is not tested by section-level gold.
- Section-level gold cannot show whether a smaller chunk contains the answering text more often; the
  answer-level effect of chunking was not measured.
