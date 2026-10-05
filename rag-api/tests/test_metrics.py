from app.metrics import recall_at_k, reciprocal_rank

IDS = ["s:1:0", "s:2:0", "s:2:1", "s:3:0"]


def test_recall_counts_sections_not_chunks():
    assert recall_at_k(IDS, ["s:2"], 3) == 1.0
    assert recall_at_k(IDS, ["s:2", "s:3"], 3) == 0.5
    assert recall_at_k(IDS, ["s:3"], 2) == 0.0


def test_reciprocal_rank():
    assert reciprocal_rank(IDS, ["s:2"]) == 0.5
    assert reciprocal_rank(IDS, ["s:9"]) == 0.0
