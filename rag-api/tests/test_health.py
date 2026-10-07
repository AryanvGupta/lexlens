from fastapi.testclient import TestClient

from app.main import app


def test_health():
    r = TestClient(app).get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_sources_lists_pinned_corpus():
    r = TestClient(app).get("/sources")
    ids = [s["id"] for s in r.json()["sources"]]
    assert (
        r.status_code == 200
        and "usc-17" in ids
        and all(i.startswith("usc-") for i in ids)
    )
