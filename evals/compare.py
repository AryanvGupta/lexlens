"""Compare retrieval-eval numbers printed by the in-cluster eval Job with the committed results.

Usage: python3 evals/compare.py <job-log-file>   (exit 1 if any metric differs by more than TOL)
"""

import json
import sys
from pathlib import Path

TOL = 0.01  # embeddings/torch can differ slightly across machines; anything bigger is a real change

log = Path(sys.argv[1]).read_text()
cluster = json.loads(log.split("--- JSON ---", 1)[1])
committed = json.loads((Path(__file__).parent / "results/retrieval.json").read_text())

bad = 0
print(f"\n{'metric':<22}{'committed':>10}{'cluster':>10}{'diff':>8}")
for mode, metrics in committed["metrics"].items():
    for name, want in metrics.items():
        got = cluster["metrics"][mode][name]
        flag = "" if abs(got - want) <= TOL else "  <-- exceeds tolerance"
        bad += bool(flag)
        print(f"{mode + ' ' + name:<22}{want:>10.3f}{got:>10.3f}{got - want:>+8.3f}{flag}")
if cluster["n"] != committed["n"]:
    bad += 1
    print(f"question count differs: {cluster['n']} vs {committed['n']}")
print(f"\n{'OK: reproduced within +/-' + str(TOL) if not bad else 'MISMATCH: ' + str(bad) + ' metric(s) off'}")
sys.exit(1 if bad else 0)
