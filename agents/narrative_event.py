"""Narrative/Event Agent (spec §4.1).

Primary inputs: GDELT GKG, EDGAR 8-Ks. Secondary: Wikipedia, Google Trends,
Polymarket. 16 factors per spec; secondary factors are optional (controlled
by alt-data ablation switches).

Factor extraction is currently zero-stubbed for primary factors (GDELT
BigQuery requires credentials; EDGAR aggregation across index members is
non-trivial). The LLM-driven decide() path is wired so that as soon as real
factors land, the agent emits real views without further refactoring.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable

from agents._llm_helpers import views_from_llm_or_anchor
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

SYSTEM_PROMPT = (
    "You are the Narrative/Event Agent. Inputs are per-instrument factor "
    "blobs from GDELT, EDGAR, and (optionally) alt-data sources. Map them "
    "into per-instrument views over a 1-week horizon. If all factors for an "
    "instrument are zero or missing, emit direction=0, conviction=0. Never "
    "invent factors. Output strict JSON: a list of "
    '{"instrument": SYMBOL, "direction": -1|0|1, "conviction": 0..1, '
    '"horizon": "1w", "rationale": "<=240 chars cite the strongest factor"}.'
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
        anchor = [
            InstrumentView(
                instrument=sym,
                direction=0,
                conviction=0.0,
                horizon="1w",
                factors=f,
                rationale="narrative anchor: GDELT/EDGAR aggregation pending",
            )
            for sym, f in factors_by_instrument.items()
        ]

        if all(all(v == 0.0 for v in f.values()) for f in factors_by_instrument.values()):
            return anchor

        return views_from_llm_or_anchor(
            self.llm,
            system_prompt=SYSTEM_PROMPT,
            user_payload={
                "as_of": as_of.isoformat(),
                "factors": factors_by_instrument,
                "enabled_secondary": sorted(self.enabled_secondary),
            },
            universe=self.universe,
            default_horizon="1w",
            anchor_views=anchor,
            agent_name=self.name,
        )
