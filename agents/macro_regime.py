"""Macro Regime Agent (spec §4.1).

Inputs: ALFRED first-release macro series + FOMC text.
Output: regime quadrant (growth × inflation) + per-instrument view.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import numpy as np
import pandas as pd

from agents.base_agent import BaseAgent, InstrumentView
from data.fetchers.alfred import HEADLINE_SERIES, first_release


class MacroRegimeAgent(BaseAgent):
    name = "macro_regime"

    def extract_factors(self, as_of: date) -> dict[str, dict[str, float]]:
        start = as_of - timedelta(days=400)
        macro = {}
        for label, sid in HEADLINE_SERIES.items():
            try:
                s = first_release(sid, start, as_of)
                macro[label] = float(s.iloc[-1]) if len(s) else float("nan")
                macro[f"{label}_chg_3m"] = (
                    float(s.iloc[-1] - s.iloc[-90]) if len(s) > 90 else float("nan")
                )
            except Exception:
                macro[label] = float("nan")

        # Same regime view applies to every instrument (the LLM differentiates).
        return {sym: dict(macro) for sym in self.universe}

    def decide(
        self,
        as_of: date,
        factors_by_instrument: dict[str, dict[str, float]],
    ) -> list[InstrumentView]:
        macro = next(iter(factors_by_instrument.values()), {})
        regime = self._classify_regime(macro)
        prior = _macro_priors(regime)
        views: list[InstrumentView] = []
        for sym, f in factors_by_instrument.items():
            d = prior.get(sym, 0)
            views.append(
                InstrumentView(
                    instrument=sym,
                    direction=d,
                    conviction=0.4 if d != 0 else 0.0,
                    horizon="1q",
                    factors={**f, "regime": _regime_to_int(regime)},
                    rationale=f"Macro regime: {regime}",
                )
            )
        return views

    @staticmethod
    def _classify_regime(m: dict[str, float]) -> str:
        gdp_chg = m.get("gdp_chg_3m", 0.0) or 0.0
        cpi_chg = m.get("cpi_yoy_chg_3m", 0.0) or 0.0
        growth_up = gdp_chg > 0
        infl_up = cpi_chg > 0
        return f"{'growth_up' if growth_up else 'growth_down'}_x_{'infl_up' if infl_up else 'infl_down'}"


def _macro_priors(regime: str) -> dict[str, int]:
    # Coarse prior — refined by the LLM in production. Kept conservative.
    table = {
        "growth_up_x_infl_up": {"SPY": 1, "QQQ": 1, "IWM": 1, "GLD": 1, "USO": 1, "IEF": -1, "SHY": -1, "UUP": 0, "EEM": 1, "BTC": 1},
        "growth_up_x_infl_down": {"SPY": 1, "QQQ": 1, "IEF": 1, "GLD": 0, "USO": 0, "UUP": 0, "EEM": 1, "BTC": 1, "SHY": 1, "IWM": 1},
        "growth_down_x_infl_up": {"SPY": -1, "QQQ": -1, "GLD": 1, "USO": 0, "IEF": -1, "UUP": 1, "EEM": -1, "BTC": -1, "SHY": 0, "IWM": -1},
        "growth_down_x_infl_down": {"SPY": -1, "QQQ": -1, "GLD": 0, "USO": -1, "IEF": 1, "UUP": 1, "EEM": -1, "BTC": -1, "SHY": 1, "IWM": -1},
    }
    return table.get(regime, {})


def _regime_to_int(r: str) -> float:
    return {
        "growth_up_x_infl_up": 0.0,
        "growth_up_x_infl_down": 1.0,
        "growth_down_x_infl_up": 2.0,
        "growth_down_x_infl_down": 3.0,
    }.get(r, -1.0)
