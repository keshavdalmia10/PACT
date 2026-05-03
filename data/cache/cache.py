"""On-disk cache for raw data-fetcher responses (spec §8 reproducibility).

Every fetcher writes its raw payload here keyed by a deterministic hash of
the request parameters. The pipeline must be deterministic on second run.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CACHE_ROOT = Path(__file__).parent / "store"
CACHE_ROOT.mkdir(parents=True, exist_ok=True)


def _hash_key(namespace: str, params: dict[str, Any]) -> str:
    canon = json.dumps(params, sort_keys=True, default=str)
    h = hashlib.sha256(f"{namespace}|{canon}".encode()).hexdigest()
    return h[:16]


def cache_path(namespace: str, params: dict[str, Any]) -> Path:
    ns_dir = CACHE_ROOT / namespace
    ns_dir.mkdir(parents=True, exist_ok=True)
    return ns_dir / f"{_hash_key(namespace, params)}.json"


def read(namespace: str, params: dict[str, Any]) -> dict[str, Any] | None:
    p = cache_path(namespace, params)
    if not p.exists():
        return None
    with p.open() as f:
        return json.load(f)


def write(namespace: str, params: dict[str, Any], payload: Any) -> Path:
    p = cache_path(namespace, params)
    record = {
        "namespace": namespace,
        "params": params,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    with p.open("w") as f:
        json.dump(record, f, default=str, indent=2)
    return p
