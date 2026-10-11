#!/usr/bin/env bash
# Usage: download.sh RAW_DIR N [N...]  -- polite sequential download of U.S. Code Titles from govinfo.gov (public domain).
# Skips files already present; 2 s delay between downloads; prints each size; stops if free disk < 15 GB.
set -euo pipefail
raw=$1; shift
for n in "$@"; do
  f="$raw/usc-$n.htm"
  [ -f "$f" ] && { echo "have usc-$n ($(wc -c <"$f") bytes)"; continue; }
  free=$(df -g "$raw" | awk 'NR==2{print $4}')
  [ "$free" -lt 15 ] && { echo "ABORT: free disk ${free} GB < 15" >&2; exit 1; }
  curl -fsSL --retry 2 --retry-delay 5 --max-time 300 -o "$f.part" \
    "https://www.govinfo.gov/content/pkg/USCODE-2023-title$n/html/USCODE-2023-title$n.htm"
  mv "$f.part" "$f"
  echo "usc-$n: $(wc -c <"$f") bytes"
  sleep 2
done
