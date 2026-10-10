import app.retrieval.rerank as rr


class FakeModel:
    def predict(self, pairs):
        return [float(len(text)) for _, text in pairs]  # longer text scores higher


def hit(i, text):
    return {"id": i, "text": text, "score": 0, "source": {"title": "t"}}


def test_reorders_by_model_score_and_truncates(monkeypatch):
    monkeypatch.setattr(rr, "model", lambda: FakeModel())
    hits = [hit("a", "x"), hit("b", "xxxx"), hit("c", "xx")]
    out = rr.rerank("q", hits, 2)
    assert [h["id"] for h in out] == ["b", "c"]
    assert out[0]["score"] > out[1]["score"] and out[0]["text"] == "xxxx"


def test_empty_candidates_skip_the_model(monkeypatch):
    monkeypatch.setattr(rr, "model", lambda: 1 / 0)  # would raise if called
    assert rr.rerank("q", [], 5) == []
