"""Multi-horizon momentum and trend persistence (spec §4.1 Technical agent)."""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_HORIZONS = {"1m": 21, "3m": 63, "6m": 126, "12m": 252}


def multi_horizon_momentum(
    prices: pd.DataFrame,
    horizons: dict[str, int] | None = None,
) -> pd.DataFrame:
    """Per-symbol total return over each horizon, indexed by date."""
    horizons = horizons or DEFAULT_HORIZONS
    out = {}
    for label, n in horizons.items():
        out[label] = prices.pct_change(n)
    res = pd.concat(out, axis=1)
    res.columns = res.columns.set_names(["horizon", "symbol"])
    return res


def trend_persistence(prices: pd.DataFrame, window: int = 63) -> pd.DataFrame:
    """Fraction of up-days within `window` minus 0.5 — sign of recent trend."""
    rets = prices.pct_change()
    return (rets > 0).rolling(window).mean() - 0.5


def cross_sectional_rank(scores: pd.DataFrame) -> pd.DataFrame:
    """Rank within each row, scaled to [-1, +1]."""
    ranks = scores.rank(axis=1, pct=True)
    return 2 * ranks - 1
