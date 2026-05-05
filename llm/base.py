"""Common LLM client interface.

All clients (frontier API, ChronoGPT) implement the same `complete` method
and the same JSON cache contract (§6.1, §8 reproducibility).
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pact_logging import get_logger

log = get_logger(__name__)

LLM_CACHE_ROOT = Path(__file__).resolve().parent.parent / "data" / "cache" / "llm"
LLM_CACHE_ROOT.mkdir(parents=True, exist_ok=True)


@dataclass
class LLMResponse:
    text: str
    model: str
    prompt_hash: str
    raw: dict[str, Any] = field(default_factory=dict)
    cached: bool = False


def canonicalize_prompt(
    *,
    system: str,
    user: str,
    model: str,
    temperature: float,
    seed: int | None,
) -> str:
    """Canonical string used as the cache key input.

    Order matters: changing it invalidates every cached response, so think
    twice before touching it.
    """
    payload = {
        "system": system,
        "user": user,
        "model": model,
        "temperature": temperature,
        "seed": seed,
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def prompt_hash(canonical: str) -> str:
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def cache_path(model: str, h: str) -> Path:
    safe_model = model.replace("/", "_")
    d = LLM_CACHE_ROOT / safe_model
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{h}.json"


def read_cache(model: str, h: str) -> dict[str, Any] | None:
    p = cache_path(model, h)
    if not p.exists():
        log.debug("llm cache miss model=%s hash=%s", model, h[:12])
        return None
    log.debug("llm cache hit model=%s hash=%s", model, h[:12])
    with p.open() as f:
        return json.load(f)


def write_cache(model: str, h: str, canonical: str, response: dict[str, Any]) -> None:
    p = cache_path(model, h)
    record = {
        "model": model,
        "prompt_hash": h,
        "canonical_prompt": canonical,
        "response": response,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    with p.open("w") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    log.debug("llm cache write model=%s hash=%s bytes=%d", model, h[:12], p.stat().st_size)


class LLMClient(ABC):
    model: str

    @abstractmethod
    def complete(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.0,
        seed: int | None = 42,
        max_tokens: int = 2048,
    ) -> LLMResponse: ...
