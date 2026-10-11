#!/usr/bin/env bash
# In-cluster search latency (hybrid vs rerank, k=12) through the rag-api Service, plus pod memory.
# Needs `make up` and `make ingest`. The mcp-server pod is the client (its image has node, not curl).
# Numbers depend on the machine and on what else is running; run it on an idle machine.
set -euo pipefail
K="kubectl --context kind-lexlens -n lexlens"

$K exec deploy/mcp-server -- node -e '
const qs = ["What does the automatic stay do when a bankruptcy petition is filed?",
  "How long does copyright last for a work created by an individual author?",
  "What factors decide whether a use is a fair use?", "Who owns the copyright in a work made for hire?",
  "When can a federal court hear related state-law claims?",
  "What range of statutory damages can a court award for copyright infringement?",
  "How many years does a patent term last from filing?", "Who is eligible to be a debtor under the bankruptcy code?",
  "When can a trustee avoid a preferential transfer?", "What is the standard of obviousness for a patent?"];
const pct = (a, p) => a.sort((x, y) => x - y)[Math.min(a.length - 1, Math.round(p * (a.length - 1)))];
const post = (q, mode) => fetch("http://rag-api:8000/search", { method: "POST",
  headers: { "content-type": "application/json" }, body: JSON.stringify({ query: q, k: 12, mode }) }).then((r) => r.json());
(async () => {
  console.log("| mode (k=12, 10 questions, warm) | p50 ms | p95 ms |\n|---|---|---|");
  for (const mode of ["hybrid", "rerank"]) {
    for (const q of qs.slice(0, 3)) await post(q, mode); // warm
    const ts = [];
    for (const q of qs) { const t = Date.now(); await post(q, mode); ts.push(Date.now() - t); }
    console.log(`| ${mode} | ${pct(ts, 0.5)} | ${pct(ts, 0.95)} |`);
  }
})()'

echo
echo "rag-api pod memory (limit 2 Gi):"
for p in $($K get pods -l app=rag-api -o name); do
  echo "  $p: $($K exec "$p" -- sh -c 'echo "$(( $(cat /sys/fs/cgroup/memory.current) / 1048576 )) MiB now, $(( $(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo 0) / 1048576 )) MiB peak"')"
done
