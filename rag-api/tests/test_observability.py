from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


def _sample(text: str, name: str, **labels) -> float:
    """Value of one exposition line, e.g. lexlens_searches_total{mode="hybrid"}."""
    want = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    for line in text.splitlines():
        if line.startswith(name + "{") and want in line:
            return float(line.rsplit(" ", 1)[1])
    return 0.0


def _metrics() -> str:
    r = client.get("/metrics")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    return r.text


def test_request_counter_and_latency_use_the_route_template():
    before = _sample(
        _metrics(), "lexlens_http_requests_total", route="/sources", status="200"
    )
    client.get("/sources")
    text = _metrics()
    assert (
        _sample(text, "lexlens_http_requests_total", route="/sources", status="200")
        == before + 1
    )
    assert 'lexlens_http_request_seconds_count{method="GET",route="/sources"}' in text


def test_unknown_paths_share_one_label_so_scanners_cannot_add_series():
    client.get("/wp-admin/a")
    client.get("/wp-admin/b")
    text = _metrics()
    assert "wp-admin" not in text
    assert (
        _sample(text, "lexlens_http_requests_total", route="unmatched", status="404")
        >= 2
    )


def test_search_counts_by_mode(monkeypatch):
    monkeypatch.setattr(main, "run_search", lambda *a, **k: [])
    monkeypatch.setattr(main, "PgVectorStore", lambda *a, **k: object())
    before = _sample(_metrics(), "lexlens_searches_total", mode="lexical")
    assert (
        client.post("/search", json={"query": "x", "mode": "lexical"}).status_code
        == 200
    )
    assert _sample(_metrics(), "lexlens_searches_total", mode="lexical") == before + 1


def test_ask_outcome_counts_answered_and_refused(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(main, "PgVectorStore", lambda *a, **k: object())
    results = iter([{"refused": False}, {"refused": True}, {"refused": True}])
    monkeypatch.setattr(main, "run_ask", lambda *a, **k: next(results))
    base = _metrics()
    for _ in range(3):
        client.post("/ask", json={"question": "q"})
    text = _metrics()
    assert (
        _sample(text, "lexlens_asks_total", outcome="answered")
        == _sample(base, "lexlens_asks_total", outcome="answered") + 1
    )
    assert (
        _sample(text, "lexlens_asks_total", outcome="refused")
        == _sample(base, "lexlens_asks_total", outcome="refused") + 2
    )


def test_metrics_scrapes_are_not_logged(caplog):
    import logging

    caplog.set_level(logging.INFO, logger="lexlens")
    client.get("/metrics")
    assert caplog.records == []
