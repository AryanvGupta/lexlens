import json
import logging

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


class _Conn:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, q):
        return None


@pytest.fixture
def warm():
    main._warm.set()
    yield
    main._warm.clear()


def test_ready_503_until_model_is_loaded(monkeypatch):
    monkeypatch.setattr(main.psycopg, "connect", lambda *a, **k: _Conn())
    r = client.get("/ready")
    assert r.status_code == 503 and "models not loaded" in r.json()["reasons"]


def test_ready_503_when_database_down(monkeypatch, warm):
    def boom(*a, **k):
        raise psycopg.OperationalError("down")

    monkeypatch.setattr(main.psycopg, "connect", boom)
    r = client.get("/ready")
    assert r.status_code == 503 and r.json()["reasons"] == ["database unreachable"]


def test_ready_200_when_model_and_database_ok(monkeypatch, warm):
    monkeypatch.setattr(main.psycopg, "connect", lambda *a, **k: _Conn())
    assert client.get("/ready").json() == {"status": "ready"}


def test_health_is_independent_of_dependencies():
    assert client.get("/health").status_code == 200


def test_request_id_generated_echoed_and_logged(caplog):
    caplog.set_level(logging.INFO, logger="lexlens")
    r = client.get("/sources", headers={"x-request-id": "abc123"})
    assert r.headers["x-request-id"] == "abc123"
    assert client.get("/sources").headers["x-request-id"] != "abc123"
    line = json.loads(caplog.records[0].message)
    assert (
        line["request_id"] == "abc123"
        and line["path"] == "/sources"
        and line["status"] == 200
    )


def test_probe_paths_are_not_logged(caplog):
    caplog.set_level(logging.INFO, logger="lexlens")
    client.get("/health")
    assert caplog.records == []
