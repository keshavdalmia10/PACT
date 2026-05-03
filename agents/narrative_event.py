"""Narrative/Event Agent (spec §4.1).

Primary inputs: GDELT GKG, EDGAR 8-Ks. Secondary: Wikipedia, Google Trends,
Polymarket. 16 factors per spec; secondary factors are optional (controlled
by alt-data ablation switches).
"""

from __future__ import annotations

from datetime import date
from typing import Iterable

from agents.base_agent import BaseAgent, InstrumentView

PRIMARY_FACTORS: tuple[str, ...] = (
    "gdelt_event_volume_log",
    "gdelt_tone",
    "gdelt_tone_surprise_wow",
    "gdelt_theme_intensity",
    "gdelt_geo_concentration",
    "gdelt_event_novelty",
    "edgar_8k_volume",
    "edgar_8k_item_dist_entropy",
    "earnings_surprise_sentiment",
    "guidance_change",
)

SECONDARY_FACTORS: tuple[str, ...] = (
    "wiki_abnormal_attention",
    "wiki_attention_persistence",
    "gtrends_abnormal_level",
    "gtrends_momentum",
    "polymarket_event_prob",
    "polymarket_prob_change",
)


class NarrativeEventAgent(BaseAgent):
    name = "narrative_event"

    def __init__(
        self,
        llm_client,
        universe: tuple[str, ...],
        enable_secondary: Iterable[str] = (),
    ):
        super().__init__(llm_client, universe)
        self.enabled_secondary = set(enable_secondary)

    def extract_factors(self, as_of: date) -> dict[str, dict[str, float]]:
        # Real implementation calls GDELT BigQuery + EDGAR + the enabled
        # secondary fetchers. Here we publish the factor schema as zeros so
        # the harness wires up cleanly and contracts are visible.
        out = {}
        for sym in self.universe:
            f = {k: 0.0 for k in PRIMARY_FACTORS}
            for k in SECONDARY_FACTORS:
                if k in self.enabled_secondary:
                    f[k] = 0.0
            out[sym] = f
        return out

    def decide(
        self,
        as_of: date,
        factors_by_instrument: dict[str, dict[str, float]],
    ) -> list[InstrumentView]:
        return [
            InstrumentView(
                instrument=sym,
                direction=0,
                conviction=0.0,
                horizon="1w",
                factors=f,
                rationale="narrative agent: stub view (factor extraction pending)",
            )
            for sym, f in factors_by_instrument.items()
        ]
