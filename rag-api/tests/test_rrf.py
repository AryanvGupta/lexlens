from app.retrieval.search import rrf


def h(i):
    return {"id": i, "text": i, "score": 0}


def test_agreement_beats_single_ranker():
    fused = rrf([[h("a"), h("b"), h("c")], [h("b"), h("d")]])
    assert fused[0]["id"] == "b"  # ranked 2nd and 1st beats 1st and absent
    assert {x["id"] for x in fused} == {"a", "b", "c", "d"}


def test_score_formula():
    fused = rrf([[h("a")], [h("a")]], k=60)
    assert fused[0]["score"] == 2 / 61
