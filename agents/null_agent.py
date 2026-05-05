"""Placeholder agent used by attribution drivers (spec §6.7).

For leave-one-out / Shapley attribution we need to "drop" an agent from a
protocol without changing the protocol's wiring (sequential_pipeline,
hierarchical, etc. hardcode agent names). NullAgent answers like every other
agent but returns zero-direction, zero-conviction views with no factors —
contributing nothing.
"""

from __future__ import annotations

from datetime import date

from agents.base_agent import BaseAgent, InstrumentView


class NullAgent(BaseAgent):
    """Drop-in replacement that emits empty views."""

    def __init__(self, replaces_name: str, universe: tuple[str, ...]):
        super().__init__(llm_client=None, universe=universe)
        self.name = replaces_name  # so any name-based bookkeeping still works

    def extract_factors(self, as_of: date) -> dict[str, dict[str, float]]:
        return {sym: {} for sym in self.universe}

    def decide(
        self,
        as_of: date,
        factors_by_instrument: dict[str, dict[str, float]],
    ) -> list[InstrumentView]:
        return [
            InstrumentView(instrument=sym, direction=0, conviction=0.0, horizon="1m")
            for sym in self.universe
        ]
