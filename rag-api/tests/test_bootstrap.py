import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evals"))
from bootstrap import boot_ci, paired_ci, resamples


def test_constant_values_give_degenerate_ci():
    idx = resamples(5, b=200, seed=0)
    assert boot_ci([1.0] * 5, idx) == (1.0, 1.0)
    assert paired_ci([1.0] * 5, [0.0] * 5, idx) == (1.0, 1.0)


def test_deterministic_and_brackets_mean():
    vals = [0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 0.0]
    assert resamples(8, 100, 0) == resamples(8, 100, 0)
    lo, hi = boot_ci(vals, resamples(8, 1000, 0))
    assert lo <= sum(vals) / 8 <= hi
