#!/usr/bin/env bash
# Usage: k8s/run-job.sh <name> [timeout_seconds]   (runs k8s/jobs/<name>.yaml, prints its logs, exit 1 if it failed)
set -euo pipefail
cd "$(dirname "$0")/.."
K="kubectl --context kind-lexlens -n lexlens"
name=$1
timeout=${2:-900}
$K rollout status statefulset/postgres --timeout=120s
$K delete job "$name" --ignore-not-found --wait=true >/dev/null
$K apply -f "k8s/jobs/$name.yaml" >/dev/null
end=$((SECONDS + timeout))
while ((SECONDS < end)); do
  ok=$($K get job "$name" -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}')
  bad=$($K get job "$name" -o jsonpath='{.status.conditions[?(@.type=="Failed")].status}')
  if [[ "$ok" == "True" || "$bad" == "True" ]]; then
    logs=$($K logs "job/$name" 2>&1 || true)
    echo "$logs"
    [[ -n "${LOG_FILE:-}" ]] && echo "$logs" > "$LOG_FILE"
    [[ "$ok" == "True" ]] && exit 0
    echo "job/$name failed" >&2
    exit 1
  fi
  sleep 5
done
echo "job/$name did not finish within ${timeout}s" >&2
$K logs "job/$name" 2>&1 | tail -20 >&2 || true
exit 1
