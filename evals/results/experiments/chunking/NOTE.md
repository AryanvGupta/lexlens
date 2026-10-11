These chunking results were produced before hybrid retrieval changed. The `hybrid` rows here are the
earlier equal-weight RRF over dense + Postgres `ts_rank` (the 300/40 row is 0.614 / 0.784 / 0.864 / 0.697),
not the current weighted dense + BM25 hybrid, and there was no `rerank` mode yet. The dense and lexical rows
are unaffected. The conclusion "chunk size in this range is not a lever" was re-checked on the current
stack in `../chunking-current-stack/` and still holds.
