"""Run-to-run variance table for the answer eval (opt-in).

python evals/variance_report.py evals/results/experiments/variance
Reads <dir>/rep*/answers.json plus the committed evals/results/answers.json ("run 0").
"""

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS = [
    "refusal_precision",
    "refusal_recall",
    "answers_citing_gold_section",
    "faithfulness",
    "citation_validity",
    "injection_followed",
]


def val(r: dict, m: str) -> float:
    v = r[m]
    if isinstance(v, str):  # "0/4"
        a, b = v.split("/")
        return int(a) / int(b)
    return float(v)


def main() -> None:
    d = Path(sys.argv[1])
    files = [ROOT / "evals/results/answers.json", *sorted(d.glob("rep*/answers.json"))]
    runs = [json.loads(f.read_text()) for f in files]
    names = ["run 0 (committed)"] + [f.parent.name for f in files[1:]]
    L = [
        f"# Answer-eval run-to-run variance ({len(runs)} runs, default config rerank k=12)",
        "",
        "Each replicate used an empty cache, so generation and the judge model were both re-sampled.",
        "",
        "| metric | " + " | ".join(names) + " | mean | min | max |",
        "|---|" + "---|" * (len(runs) + 3),
    ]
    for m in METRICS:
        v = [val(r, m) for r in runs]
        L.append(
            f"| {m} | "
            + " | ".join(f"{x:.3f}" for x in v)
            + f" | {sum(v) / len(v):.3f} | {min(v):.3f} | {max(v):.3f} |"
        )
    c = Counter(q for r in runs for q in r["over_refused"])
    L += ["", "Questions over-refused (appearances across runs):", ""]
    L += [f"- {q}: {n}/{len(runs)}" for q, n in sorted(c.items())] or ["- none"]
    (d / "summary.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


main()
