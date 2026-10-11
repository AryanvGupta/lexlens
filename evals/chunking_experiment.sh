#!/usr/bin/env bash
# Chunking experiment: re-ingest with each (words, overlap) and run the retrieval eval.
# Results go to evals/results/experiments/chunking/; the baseline (300/40) runs last
# so the database is left in its normal state. Uses the compose DB; takes several minutes.
# Env: DATABASE_URL (a preset value wins over .env; ingest DROPS AND REBUILDS its table, so also set
# EXPECT_DB=<name> to abort unless the database name matches), CHUNK_OUT (output dir), LEXLENS_RAW (raw HTML dir).
set -euo pipefail
cd "$(dirname "$0")/.."
preset="${DATABASE_URL-}"
set -a; [ -f ./.env ] && . ./.env; set +a
[ -n "$preset" ] && export DATABASE_URL="$preset"   # a preset value wins over .env
[ -z "$preset" ] && docker compose up -d --wait postgres
dbname="${DATABASE_URL##*/}"
echo "database: $dbname"
if [ -n "${EXPECT_DB-}" ] && [ "$dbname" != "$EXPECT_DB" ]; then echo "ABORT: database is '$dbname', expected '$EXPECT_DB'" >&2; exit 1; fi
out="${CHUNK_OUT:-evals/results/experiments/chunking}"
mkdir -p "$out"

for cfg in "300 0" "150 20" "75 10" "300 40"; do
  set -- $cfg
  d="$out/w$1-o$2"
  echo "== chunk words=$1 overlap=$2 db=$dbname"
  (cd rag-api && CHUNK_WORDS=$1 CHUNK_OVERLAP=$2 uv run python -m app.ingest) | tail -1 | tee "$d.rows" >/dev/null
  (cd rag-api && EVAL_RESULTS="../$d" uv run python ../evals/run_eval.py) >/dev/null
done

python3 - "$out" <<'EOF' | tee "$out/summary.md"
import json, sys
from pathlib import Path
out = Path(sys.argv[1])
cols = ["recall@1", "recall@5", "recall@10", "mrr@20"]
print("| words/overlap | chunks | mode | " + " | ".join(cols) + " |")
print("|---|---|---|" + "---|" * len(cols))
for d in sorted(out.glob("w*-o*/"), key=lambda p: -int(p.name.split("-")[0][1:])):
    w, o = d.name[1:].split("-o")
    rows = (out / f"{d.name}.rows").read_text().split(":")[1].strip()
    m = json.loads((d / "retrieval.json").read_text())["metrics"]
    for mode in m:
        print(f"| {w}/{o} | {rows} | {mode} | " + " | ".join(f"{m[mode][c]:.3f}" for c in cols) + " |")
EOF
