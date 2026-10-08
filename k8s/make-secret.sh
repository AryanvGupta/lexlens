#!/usr/bin/env bash
# Creates/updates the lexlens-secrets Secret from the local .env. Values never touch git or the command line.
set -euo pipefail
cd "$(dirname "$0")/.."
tmp=$(mktemp)
chmod 600 "$tmp"
trap 'rm -f "$tmp"' EXIT
grep -E '^(POSTGRES_PASSWORD|SAMPLE_DB_ADMIN_PASSWORD|SAMPLE_DB_RO_PASSWORD|ANTHROPIC_API_KEY)=' .env > "$tmp" || true
for key in POSTGRES_PASSWORD SAMPLE_DB_ADMIN_PASSWORD SAMPLE_DB_RO_PASSWORD; do
  grep -qE "^$key=.+" "$tmp" || { echo "error: $key is missing or empty in .env (see .env.example)" >&2; exit 1; }
done
grep -qE '^ANTHROPIC_API_KEY=.+' "$tmp" || echo "note: ANTHROPIC_API_KEY is empty; /ask and ask_legal will return an error until it is set" >&2
kubectl --context kind-lexlens -n lexlens create secret generic lexlens-secrets --from-env-file="$tmp" --dry-run=client -o yaml \
  | kubectl --context kind-lexlens -n lexlens apply -f - >/dev/null
echo "secret/lexlens-secrets applied"
