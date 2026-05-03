"""Signal → position mapping (spec §5).

Vol-targeted sizing per instrument, gross-leverage cap, per-name cap, then
an ex-ante portfolio-vol overlay (target 12% annualized).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from agents.base_agent import InstrumentView


@dataclass
class PortfolioConfig:
    instrument_vol_target: float = 0.10        # 10% annualized per name
    portfolio_vol_target: float = 0.12         # 12% annualized
    max_gross_leverage: float = 2.00           # sum |w| ≤ 200%
    per_name_gross_cap: float = 0.25           # 25% gross per instrument
    cross_asset_risk_scaler: float = 1.0
    min_realized_vol: float = 0.02             # floor to avoid /0


def views_to_target_weights(
    views: list[InstrumentView],
    realized_vol_by_symbol: dict[str, float],
    cov_matrix: pd.DataFrame | None = None,
    cfg: PortfolioConfig | None = None,
) -> dict[str, float]:
    cfg = cfg or PortfolioConfig()

    # Step 1: per-instrument raw signal × vol-target sizing
    raw: dict[str, float] = {}
    for v in views:
        rv = max(realized_vol_by_symbol.get(v.instrument, cfg.min_realized_vol), cfg.min_realized_vol)
        signed = v.direction * v.conviction
        raw[v.instrument] = signed * (cfg.instrument_vol_target / rv) * cfg.cross_asset_risk_scaler

    # Step 2: per-name cap
    for k in raw:
        raw[k] = float(np.clip(raw[k], -cfg.per_name_gross_cap, cfg.per_name_gross_cap))

    # Step 3: gross-leverage cap (scale down if exceeded)
    gross = sum(abs(v) for v in raw.values())
    if gross > cfg.max_gross_leverage:
        scale = cfg.max_gross_leverage / gross
        raw = {k: v * scale for k, v in raw.items()}

    # Step 4: portfolio-vol overlay (only if covariance provided)
    if cov_matrix is not None and not cov_matrix.empty:
        symbols = [s for s in raw if s in cov_matrix.index and s in cov_matrix.columns]
        if symbols:
            w = np.array([raw[s] for s in symbols])
            sub = cov_matrix.loc[symbols, symbols].values
            port_var = float(w @ sub @ w)
            port_vol = np.sqrt(max(port_var, 0.0)) * np.sqrt(252)
            if port_vol > 0:
                k = cfg.portfolio_vol_target / port_vol
                k = min(k, 1.0)  # only scale DOWN — don't lever up via vol overlay
                raw = {s: (raw[s] * k if s in symbols else raw[s]) for s in raw}

    return raw
