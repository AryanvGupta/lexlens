import json
import os
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]


def sources_path() -> Path:
    """Manifest; LEXLENS_SOURCES overrides the default data/sources.json."""
    return Path(os.environ.get("LEXLENS_SOURCES") or ROOT / "data" / "sources.json")


def raw_dir() -> Path:
    """Download dir; LEXLENS_RAW overrides the default data/raw."""
    return Path(os.environ.get("LEXLENS_RAW") or ROOT / "data" / "raw")


def sources() -> list[dict]:
    return json.loads(sources_path().read_text())


def fetch_all() -> list[tuple[dict, Path]]:
    raw = raw_dir()
    raw.mkdir(parents=True, exist_ok=True)
    out = []
    for s in sources():
        path = raw / f"{s['id']}.htm"
        if not path.exists():
            r = httpx.get(s["url"], timeout=120, follow_redirects=True)
            r.raise_for_status()
            path.write_bytes(r.content)
            print(f"downloaded {s['id']}: {len(r.content) / 1e6:.1f} MB", flush=True)
            time.sleep(2)  # polite rate limit
        out.append((s, path))
    return out
