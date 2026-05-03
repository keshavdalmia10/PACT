"""Open-source path — ChronoGPT pinned by HF commit hash (spec §6.1).

Contamination-clean: the model's training cutoff is matched to the test-period
start. ChronoBERT can be added as a sibling for sentiment/classification.
"""

from __future__ import annotations

from typing import Any

from llm.base import (
    LLMClient,
    LLMResponse,
    canonicalize_prompt,
    prompt_hash,
    read_cache,
    write_cache,
)

DEFAULT_MODEL = "manelalab/chrono-gpt-v1-realtime"


class ChronoGPTClient(LLMClient):
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        revision: str | None = None,
        device: str = "auto",
        offline: bool = False,
    ) -> None:
        # `revision` is the HF commit hash — pin it for reproducibility.
        self.model = model if revision is None else f"{model}@{revision}"
        self._hf_model = model
        self._revision = revision
        self._device = device
        self.offline = offline
        self._pipe = None

    def _ensure_pipe(self):
        if self._pipe is None:
            if self.offline:
                raise RuntimeError("ChronoGPT in offline mode; cache misses will fail.")
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

            tok = AutoTokenizer.from_pretrained(self._hf_model, revision=self._revision)
            mdl = AutoModelForCausalLM.from_pretrained(
                self._hf_model, revision=self._revision
            )
            self._pipe = pipeline(
                "text-generation",
                model=mdl,
                tokenizer=tok,
                device_map=self._device if self._device != "auto" else None,
            )
        return self._pipe

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
                text=resp["text"], model=self.model, prompt_hash=h, raw=resp, cached=True
            )

        if self.offline:
            raise KeyError(f"Cache miss in offline mode for prompt hash {h}.")

        pipe = self._ensure_pipe()
        prompt = f"<|system|>\n{system}\n<|user|>\n{user}\n<|assistant|>\n"
        gen_kwargs: dict[str, Any] = {
            "max_new_tokens": max_tokens,
            "do_sample": temperature > 0,
            "temperature": max(temperature, 1e-5),
            "return_full_text": False,
        }
        if seed is not None:
            import torch

            torch.manual_seed(seed)
        out = pipe(prompt, **gen_kwargs)
        text = out[0]["generated_text"] if out else ""

        payload = {"text": text, "model": self.model}
        write_cache(self.model, h, canonical, payload)
        return LLMResponse(text=text, model=self.model, prompt_hash=h, raw=payload, cached=False)
