"""Compare a retrieval-eval run with the committed results (evals/results/retrieval.json).

Usage: python3 evals/compare.py <file> [--tol X] [--drops-only]
  <file>        the in-cluster eval Job log (JSON follows a "--- JSON ---" line) or a plain retrieval.json
  --tol X       allowed difference, default 0.01 (embeddings/torch differ slightly across machines)
  --drops-only  only fail when a metric is BELOW the committed value by more than tol (CI regression gate)
Exit 1 on any failure.
"""

import json
import sys
from pathlib import Path

args = sys.argv[1:]
tol = float(args[args.index("--tol") + 1]) if "--tol" in args else 0.01
drops_only = "--drops-only" in args

text = Path(args[0]).read_text()
measured = json.loads(
    text.split("--- JSON ---", 1)[1] if "--- JSON ---" in text else text
)
committed = json.loads((Path(__file__).parent / "results/retrieval.json").read_text())

bad = 0
print(f"\n{'metric':<22}{'committed':>10}{'measured':>10}{'diff':>8}")
for mode, metrics in committed["metrics"].items():
    for name, want in metrics.items():
        got = measured["metrics"][mode][name]
        off = (want - got > tol) if drops_only else (abs(got - want) > tol)
        bad += off
        print(
            f"{mode + ' ' + name:<22}{want:>10.3f}{got:>10.3f}{got - want:>+8.3f}{'  <-- exceeds tolerance' if off else ''}"
        )
if measured["n"] != committed["n"]:
    bad += 1
    print(f"question count differs: {measured['n']} vs {committed['n']}")
kind = "no drop beyond" if drops_only else "reproduced within +/-"
print(
    f"\n{'OK: ' + kind + ' ' + str(tol) if not bad else 'MISMATCH: ' + str(bad) + ' metric(s) off'}"
)
sys.exit(1 if bad else 0)
