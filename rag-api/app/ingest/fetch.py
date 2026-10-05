import json
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"


def sources() -> list[dict]:
    return json.loads((ROOT / "data" / "sources.json").read_text())


def fetch_all() -> list[tuple[dict, Path]]:
    RAW.mkdir(parents=True, exist_ok=True)
    out = []
    for s in sources():
        path = RAW / f"{s['id']}.htm"
        if not path.exists():
            r = httpx.get(s["url"], timeout=120, follow_redirects=True)
            r.raise_for_status()
            path.write_bytes(r.content)
            time.sleep(2)  # polite rate limit
        out.append((s, path))
    return out
