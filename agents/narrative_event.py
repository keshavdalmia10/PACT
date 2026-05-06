"""Narrative/Event Agent (spec §4.1).

Primary inputs: GDELT GKG (real, via BigQuery), EDGAR 8-Ks (stubbed).
Secondary inputs: Wikipedia, Google Trends, Polymarket — gated by
`enable_secondary` flag, stubbed at zero until per-source fetchers exist.

Architecture: when constructed with `cell_window=(start, end)`, the agent
pre-fetches the GDELT daily panel for the whole window in a single batched
BigQuery call (cached locally). Subsequent `extract_factors(as_of)` calls
slice the panel up to `as_of` — point-in-time clean, zero per-rebalance
network cost.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

import numpy as np
import pandas as pd

from agents._llm_helpers import views_from_llm_or_anchor
from agents.base_agent import BaseAgent, InstrumentView
from data.fetchers.gdelt import GDELT_V2_START, fetch_panel as gdelt_panel
from pact_logging import get_logger

log = get_logger(__name__)

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
        cell_window: tuple[date, date] | None = None,
        gdelt_lookback_days: int = 60,
    ):
        super().__init__(llm_client, universe)
        self.enabled_secondary = set(enable_secondary)
        self.cell_window = cell_window
        self.gdelt_lookback_days = gdelt_lookback_days
        self._gdelt_panel: pd.DataFrame | None = None

    def _ensure_gdelt_panel(self, as_of: date) -> pd.DataFrame | None:
        """Fetch GDELT daily panel covering the cell window (or `as_of`-only fallback).

        Returns None when the requested window is fully before GDELT V2 starts
        (pre-2015-02-18) — the agent then falls back to zero anchors.
        """
        if self._gdelt_panel is not None:
            return self._gdelt_panel

        if self.cell_window:
            start, end = self.cell_window
            # Need a lookback before the cell start for surprise/WoW.
            start = start - timedelta(days=self.gdelt_lookback_days)
        else:
            end = as_of
            start = as_of - timedelta(days=self.gdelt_lookback_days * 4)

        if end < GDELT_V2_START:
            log.warning("narrative: cell window ends before GDELT v2 start; skipping fetch")
            self._gdelt_panel = pd.DataFrame()
            return None
        if start < GDELT_V2_START:
            start = GDELT_V2_START

        try:
            panel = gdelt_panel(
                start=start,
                end=end,
                instruments=[s for s in self.universe if s != "SHY"],  # SHY: thin filter, skip
            )
            panel["day"] = pd.to_datetime(panel["day"])
            panel = panel.set_index("day").sort_index()
            self._gdelt_panel = panel
            log.info(
                "narrative gdelt panel ready rows=%d range=%s..%s",
                len(panel), panel.index.min().date() if len(panel) else None,
                panel.index.max().date() if len(panel) else None,
            )
            return panel
        except Exception as e:
            log.warning("narrative gdelt fetch failed (%s); falling back to zero factors", type(e).__name__)
            self._gdelt_panel = pd.DataFrame()
            return None

    def extract_factors(self, as_of: date) -> dict[str, dict[str, float]]:
        panel = self._ensure_gdelt_panel(as_of)
        as_of_ts = pd.Timestamp(as_of)

        out: dict[str, dict[str, float]] = {}
        for sym in self.universe:
            f = {k: 0.0 for k in PRIMARY_FACTORS}
            for k in SECONDARY_FACTORS:
                if k in self.enabled_secondary:
                    f[k] = 0.0

            if panel is not None and not panel.empty:
                n_col = f"n_{sym}"
                tone_col = f"tone_{sym}"
                if n_col in panel.columns:
                    # Point-in-time slice: only rows up to as_of.
                    pit = panel.loc[panel.index <= as_of_ts]
                    if len(pit) >= 7:
                        recent_7d = pit.tail(7)
                        n_recent = float(recent_7d[n_col].sum())
                        tone_recent = float(recent_7d[tone_col].mean()) if tone_col in pit.columns else 0.0
                        f["gdelt_event_volume_log"] = float(np.log1p(n_recent))
                        f["gdelt_tone"] = tone_recent if pd.notna(tone_recent) else 0.0
                        # Week-over-week surprise: tone_recent vs prior 4-week mean.
                        if len(pit) >= 35:
                            prior = pit.iloc[-35:-7]
                            prior_tone = float(prior[tone_col].mean()) if tone_col in prior.columns else 0.0
                            prior_std = float(prior[tone_col].std()) if tone_col in prior.columns else 0.0
                            if prior_std > 0:
                                f["gdelt_tone_surprise_wow"] = (tone_recent - prior_tone) / prior_std
                            else:
                                f["gdelt_tone_surprise_wow"] = 0.0
                        f["gdelt_theme_intensity"] = float(np.log1p(n_recent))
            out[sym] = f
        return out

    def decide(
        self,
        as_of: date,
        factors_by_instrument: dict[str, dict[str, float]],
    ) -> list[InstrumentView]:
        anchor = [
            self._anchor_view(sym, f) for sym, f in factors_by_instrument.items()
        ]

        if all(_all_zero(f) for f in factors_by_instrument.values()):
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

    @staticmethod
    def _anchor_view(sym: str, f: dict[str, float]) -> InstrumentView:
        """Anchor view from GDELT factors when no LLM is available.

        Tone surprise crossing thresholds → directional view.
        """
        surprise = f.get("gdelt_tone_surprise_wow", 0.0)
        tone = f.get("gdelt_tone", 0.0)
        # Strong negative tone surprise → bearish; strong positive → bullish.
        if surprise > 0.5 and tone > 0:
            direction, conviction = 1, min(0.3 + abs(surprise) * 0.1, 0.6)
            why = f"GDELT tone surprise +{surprise:.2f} σ; tone={tone:.2f}"
        elif surprise < -0.5 and tone < 0:
            direction, conviction = -1, min(0.3 + abs(surprise) * 0.1, 0.6)
            why = f"GDELT tone surprise {surprise:.2f} σ; tone={tone:.2f}"
        else:
            direction, conviction = 0, 0.0
            why = f"GDELT tone={tone:.2f} surprise={surprise:.2f} (below threshold)"
        return InstrumentView(
            instrument=sym, direction=direction, conviction=conviction, horizon="1w",
            factors=f, rationale=why,
        )


def _all_zero(f: dict[str, float]) -> bool:
    return all(v == 0.0 for v in f.values())
