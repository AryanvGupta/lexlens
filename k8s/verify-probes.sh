#!/usr/bin/env bash
# Deletes one rag-api pod while polling the rag-api Service from inside the cluster.
# Passes if every request returned 200: the surviving replica kept serving and the
# replacement received no traffic until its startup/readiness probe passed.
# Needs `make up`. Takes about a minute.
set -euo pipefail
K="kubectl --context kind-lexlens -n lexlens"
log=$(mktemp)
trap 'kill "${poller:-0}" 2>/dev/null || true; rm -f "$log"' EXIT

# the mcp-server pod is the in-cluster client (its image has node, not curl)
$K exec deploy/mcp-server -- node -e '
const end = Date.now() + 120000;
(async () => { while (Date.now() < end) {
  try { const r = await fetch("http://rag-api:8000/ready", { signal: AbortSignal.timeout(2000) }); console.log(r.status); }
  catch (e) { console.log("ERR"); }
  await new Promise((r) => setTimeout(r, 500));
} })()' > "$log" 2>&1 &
poller=$!
sleep 5

victim=$($K get pods -l app=rag-api -o name | head -1)
echo "deleting $victim ($($K get pods -l app=rag-api --no-headers | wc -l | tr -d ' ') replicas)"
start=$(date +%s)
$K delete "$victim" >/dev/null
$K wait --for=condition=Ready pod -l app=rag-api --timeout=180s >/dev/null  # the replacement exists once the delete returns
echo "replacement Ready $(( $(date +%s) - start ))s after the delete"
sleep 2
kill "$poller"; wait "$poller" 2>/dev/null || true

total=$(wc -l < "$log" | tr -d ' ')
bad=$(grep -vc '^200$' "$log" || true)
echo "requests during the test: $total, non-200: $bad"
[ "$total" -gt 20 ] && [ "$bad" -eq 0 ] && echo "OK" || { echo "FAIL"; exit 1; }
