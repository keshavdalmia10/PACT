"""Frontier path — pinned dated model ID, fully cached (spec §6.1, §8).

Strict rules:
- Model ID is pinned (e.g. `gpt-4o-2024-11-20`); document in paper.
- Every response cached by SHA-256 of canonical prompt; replay-only on hit.
- temperature=0 and a fixed seed for max determinism.
- Log `system_fingerprint` from API for reproducibility.
- Frontier path runs ONLY on post-cutoff window (verify cutoff at submission).
"""

from __future__ import annotations

import os
from typing import Any

from llm.base import (
    LLMClient,
    LLMResponse,
    canonicalize_prompt,
    prompt_hash,
    read_cache,
    write_cache,
)

DEFAULT_MODEL = "gpt-4o-2024-11-20"


class GPT4oClient(LLMClient):
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        offline: bool = False,
    ) -> None:
        self.model = model
        self.offline = offline
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._client = None  # lazy import to keep cold-start cheap

    def _ensure_client(self):
        if self._client is None:
            if self.offline:
                raise RuntimeError(
                    "GPT4oClient is in offline mode; no API client available. "
                    "All prompts must be cache hits."
                )
            if not self._api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY not set. Either provide api_key or run offline=True."
                )
            from openai import OpenAI

            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def complete(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.0,
        seed: int | None = 42,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        canonical = canonicalize_prompt(
            system=system,
            user=user,
            model=self.model,
            temperature=temperature,
            seed=seed,
        )
        h = prompt_hash(canonical)

        hit = read_cache(self.model, h)
        if hit is not None:
            resp = hit["response"]
            return LLMResponse(
                text=resp["text"],
                model=self.model,
                prompt_hash=h,
                raw=resp,
                cached=True,
            )

        if self.offline:
            raise KeyError(
                f"Cache miss in offline mode for prompt hash {h}. "
                "Run online once to populate cache."
            )

        client = self._ensure_client()
        api_resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            seed=seed,
            max_tokens=max_tokens,
        )
        text = api_resp.choices[0].message.content or ""
        payload: dict[str, Any] = {
            "text": text,
            "system_fingerprint": getattr(api_resp, "system_fingerprint", None),
            "usage": api_resp.usage.model_dump() if api_resp.usage else None,
            "finish_reason": api_resp.choices[0].finish_reason,
        }
        write_cache(self.model, h, canonical, payload)
        return LLMResponse(text=text, model=self.model, prompt_hash=h, raw=payload, cached=False)
