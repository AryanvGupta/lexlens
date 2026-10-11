import json

from app.ingest import fetch


def test_defaults(monkeypatch):
    monkeypatch.delenv("LEXLENS_SOURCES", raising=False)
    monkeypatch.delenv("LEXLENS_RAW", raising=False)
    assert fetch.sources_path() == fetch.ROOT / "data" / "sources.json"
    assert fetch.raw_dir() == fetch.ROOT / "data" / "raw"


def test_env_overrides_no_network(monkeypatch, tmp_path):
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps([{"id": "usc-1", "title": "T1", "url": "http://x"}]))
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "usc-1.htm").write_text("<html/>")  # already downloaded: no HTTP call
    monkeypatch.setenv("LEXLENS_SOURCES", str(manifest))
    monkeypatch.setenv("LEXLENS_RAW", str(raw))
    monkeypatch.setattr(
        fetch.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError)
    )
    out = fetch.fetch_all()
    assert [(s["id"], p) for s, p in out] == [("usc-1", raw / "usc-1.htm")]
