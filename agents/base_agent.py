"""Base agent abstraction per spec §4.

Every agent extracts structured factors first, logs them, then asks an LLM
to combine factors into per-instrument views. Raw text never goes straight
into the LLM. The unified output schema is `InstrumentView`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from pact_logging import get_logger

log = get_logger(__name__)

Direction = Literal[-1, 0, 1]
Horizon = Literal["1w", "1m", "1q"]


class InstrumentView(BaseModel):
    """Per-instrument view emitted by every agent (spec §4.2)."""

    instrument: str
    direction: Direction
    conviction: float = Field(ge=0.0, le=1.0)
    horizon: Horizon
    factors: dict[str, float] = Field(default_factory=dict)
    rationale: str = ""

    @field_validator("instrument")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class AgentDecision(BaseModel):
    """Wrapper for one agent's full per-rebalance output."""

    agent_name: str
    as_of: date
    views: list[InstrumentView]
    metadata: dict[str, str | float | int] = Field(default_factory=dict)

    def view_for(self, symbol: str) -> InstrumentView | None:
        symbol = symbol.upper()
        for v in self.views:
            if v.instrument == symbol:
                return v
        return None


class BaseAgent(ABC):
    """All trading agents inherit from this.

    Subclasses implement `extract_factors` and `decide`. The harness calls
    `run`, which threads factors through the LLM and validates output.
    """

    name: str = "base"

    def __init__(self, llm_client, universe: tuple[str, ...]) -> None:
        self.llm = llm_client
        self.universe = tuple(s.upper() for s in universe)

    @abstractmethod
    def extract_factors(self, as_of: date) -> dict[str, dict[str, float]]:
        """Return {instrument: {factor_name: value}}.

        Pure data step — no LLM calls. Must be deterministic given inputs.
        """

    @abstractmethod
    def decide(
        self,
        as_of: date,
        factors_by_instrument: dict[str, dict[str, float]],
    ) -> list[InstrumentView]:
        """Combine factors into views. May call self.llm."""

    def run(self, as_of: date) -> AgentDecision:
        log.debug("agent run name=%s as_of=%s", self.name, as_of)
        factors = self.extract_factors(as_of)
        views = self.decide(as_of, factors)
        nz = sum(1 for v in views if v.direction != 0)
        log.info(
            "agent done name=%s as_of=%s factors=%d views=%d nonzero=%d",
            self.name, as_of, len(factors), len(views), nz,
        )
        return AgentDecision(agent_name=self.name, as_of=as_of, views=views)
