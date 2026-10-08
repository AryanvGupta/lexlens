from collections import Counter

from app.retrieval.bm25 import rank


def index(docs: dict[str, list[str]]):
    tf: dict[str, dict[str, int]] = {}
    dl, df = Counter(), Counter()
    for pid, words in docs.items():
        for w, n in Counter(words).items():
            tf.setdefault(w, {})[pid] = n
            df[w] += 1
        dl[pid] = len(words)
    return tf, dl, df


def test_rare_term_outweighs_common_term():
    docs = {f"c{i}": ["patent", "filler"] for i in range(8)}
    docs["r"] = ["patent", "obviousness"]
    top = rank(index(docs), ["patent", "obviousness"], 3)
    assert top[0][0] == "r"  # 'patent' is everywhere (low idf); 'obviousness' is rare


def test_shorter_doc_wins_on_equal_term_frequency():
    docs = {"short": ["apple", "x"], "long": ["apple"] + ["y"] * 30, "other": ["z"]}
    assert [p for p, _ in rank(index(docs), ["apple"], 2)] == ["short", "long"]


def test_unknown_terms_and_empty_index():
    assert rank(index({"a": ["apple"]}), ["pear"], 5) == []
    assert rank(index({}), ["apple"], 5) == []
