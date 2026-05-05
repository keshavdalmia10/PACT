"""Open-source path — ChronoGPT pinned by HF commit hash (spec §6.1, §8).

The ChronoGPT family is published as **yearly dated checkpoints**:
`manelalab/chrono-gpt-instruct-v1-YYYY1231`, each trained only on data
through `<YYYY>-12-31`. For a backtest decision at date D, the
contamination-clean choice is the checkpoint with cutoff = year(D) - 1.

Two construction paths:

1. Pinned single checkpoint (legacy / debug):
       ChronoGPTClient(cutoff_year=2023)
   loads `chrono-gpt-instruct-v1-20231231` at the pinned commit sha from
   `chronogpt_revisions.INSTRUCT_REVISIONS`.

2. As-of-aware (default for backtests):
       client = ChronoGPTClient.for_decision_year(2024)
   resolves the right checkpoint automatically.

Pinned shas live in `chronogpt_revisions.py`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from llm.base import (
    LLMClient,
    LLMResponse,
    canonicalize_prompt,
    prompt_hash,
    read_cache,
    write_cache,
)
from llm.chronogpt_revisions import (
    INSTRUCT_FAMILY,
    INSTRUCT_REVISIONS,
    LATEST_CUTOFF_YEAR,
    cutoff_year_for,
    repo_id,
    revision,
)
from pact_logging import get_logger

log = get_logger(__name__)


class ChronoGPTClient(LLMClient):
    def __init__(
        self,
        cutoff_year: int = LATEST_CUTOFF_YEAR,
        family: str = INSTRUCT_FAMILY,
        device: str = "auto",
        offline: bool = False,
    ) -> None:
        if cutoff_year not in INSTRUCT_REVISIONS:
            raise ValueError(
                f"no pinned revision for cutoff_year={cutoff_year}; "
                f"available: {sorted(INSTRUCT_REVISIONS)}"
            )
        self._cutoff_year = cutoff_year
        self._family = family
        self._hf_model = repo_id(cutoff_year, family)
        self._revision = revision(cutoff_year)
        # `model` is the cache-key identity; include the sha so different
        # pins produce different cache entries.
        self.model = f"{self._hf_model}@{self._revision}"
        self._device = device
        self.offline = offline
        self._pipe = None

    @classmethod
    def for_decision_year(
        cls,
        decision_year: int,
        family: str = INSTRUCT_FAMILY,
        device: str = "auto",
        offline: bool = False,
    ) -> "ChronoGPTClient":
        """Pick the contamination-clean checkpoint for a given backtest year."""
        return cls(
            cutoff_year=cutoff_year_for(decision_year),
            family=family,
            device=device,
            offline=offline,
        )

    @classmethod
    def for_as_of(cls, as_of: date, **kwargs) -> "ChronoGPTClient":
        return cls.for_decision_year(as_of.year, **kwargs)

    def _ensure_pipe(self):
        if self._pipe is None:
            if self.offline:
                raise RuntimeError("ChronoGPT in offline mode; cache misses will fail.")
            log.info(
                "chronogpt loading model=%s revision=%s device=%s",
                self._hf_model, self._revision[:12], self._device,
            )
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
            log.info("chronogpt loaded model=%s", self._hf_model)
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
            log.error("chronogpt offline cache miss model=%s hash=%s", self.model, h[:12])
            raise KeyError(f"Cache miss in offline mode for prompt hash {h}.")

        log.info("chronogpt generate model=%s hash=%s temp=%s", self.model, h[:12], temperature)
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

        payload = {"text": text, "model": self.model, "cutoff_year": self._cutoff_year}
        write_cache(self.model, h, canonical, payload)
        return LLMResponse(text=text, model=self.model, prompt_hash=h, raw=payload, cached=False)
