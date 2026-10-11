import pytest

import app.retrieval.rerank as rr


class FakeCE:
    """Stands in for CrossEncoder; counts how it was built."""

    built = 0

    def __init__(self, name):
        FakeCE.built += 1


@pytest.fixture(autouse=True)
def fresh_model_cache():
    rr.model.cache_clear()
    yield
    rr.model.cache_clear()


def test_default_does_not_quantize(monkeypatch):
    monkeypatch.setattr(rr, "CrossEncoder", FakeCE)
    monkeypatch.setattr(rr, "RERANK_OPT", "")
    monkeypatch.setattr(rr, "_quantize_int8", lambda m: 1 / 0)  # must not be called
    assert isinstance(rr.model(), FakeCE)


def test_int8_flag_quantizes_the_loaded_model(monkeypatch):
    monkeypatch.setattr(rr, "CrossEncoder", FakeCE)
    monkeypatch.setattr(rr, "RERANK_OPT", "int8")
    monkeypatch.setattr(rr, "_quantize_int8", lambda m: ("quantized", m))
    tag, inner = rr.model()
    assert tag == "quantized" and isinstance(inner, FakeCE)


def test_unknown_option_is_rejected(monkeypatch):
    monkeypatch.setattr(rr, "CrossEncoder", FakeCE)
    monkeypatch.setattr(rr, "RERANK_OPT", "int4")
    with pytest.raises(ValueError, match="int4"):
        rr.model()


def _real_model_or_skip():
    try:
        from sentence_transformers import CrossEncoder

        from app.config import RERANK_MODEL

        return CrossEncoder(RERANK_MODEL)
    except Exception:  # noqa: BLE001 - offline / not downloaded
        pytest.skip("real cross-encoder not available")


def test_real_int8_changes_scores_slightly_and_swaps_modules():
    pairs = [
        (
            "can I copyright a title",
            "17 U.S.C. 102\nCopyright protects original works.",
        ),
        (
            "can I copyright a title",
            "11 U.S.C. 523\nDebts not dischargeable in bankruptcy.",
        ),
    ]
    fp = _real_model_or_skip()
    base = [float(x) for x in fp.predict(pairs)]
    q = rr._quantize_int8(_real_model_or_skip())
    assert any("quantized.dynamic" in type(m).__module__ for m in q.modules())
    got = [float(x) for x in q.predict(pairs)]
    assert got != base  # a swap that did nothing would give identical scores
    assert max(abs(a - b) for a, b in zip(base, got)) < 1.5
    assert (got[0] > got[1]) == (base[0] > base[1])


def test_flag_changes_batch_size_only_when_set(monkeypatch):
    seen = []

    class M:
        def predict(self, pairs, **kw):
            seen.append(kw)
            return [0.0] * len(pairs)

    monkeypatch.setattr(rr, "model", lambda: M())
    h = [{"id": "a", "text": "x", "score": 0, "source": {"title": "t"}}]
    monkeypatch.setattr(rr, "RERANK_OPT", "")
    rr.rerank("q", h, 1)
    monkeypatch.setattr(rr, "RERANK_OPT", "batch8")
    rr.rerank("q", h, 1)
    assert seen == [{}, {"batch_size": 8}]
