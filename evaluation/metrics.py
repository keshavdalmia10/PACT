"""Performance metrics (spec §6.10).

Sharpe, Sortino, MDD, turnover, Coordination Breakeven Spread (CBS).
CBS is the cost level at which a coordinated protocol's net Sharpe equals
the no-communication ensemble's — a primary attribution number per
Nguyen & Pham.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

ANNUALIZATION_DAILY = 252


def sharpe(returns: pd.Series, rf_daily: float = 0.0) -> float:
    r = returns.dropna() - rf_daily
    if len(r) < 2 or r.std() == 0:
        return float("nan")
    return float(r.mean() / r.std() * np.sqrt(ANNUALIZATION_DAILY))


def sortino(returns: pd.Series, rf_daily: float = 0.0) -> float:
    r = returns.dropna() - rf_daily
    downside = r[r < 0]
    if len(downside) < 2 or downside.std() == 0:
        return float("nan")
    return float(r.mean() / downside.std() * np.sqrt(ANNUALIZATION_DAILY))


def max_drawdown(equity: pd.Series) -> float:
    e = equity.dropna()
    if e.empty:
        return float("nan")
    return float((e / e.cummax() - 1).min())


def turnover_metric(turnover_per_period: pd.Series) -> float:
    """Average gross traded per rebalance period."""
    s = turnover_per_period.dropna()
    s = s[s > 0]
    return float(s.mean()) if len(s) else 0.0


def summary(equity: pd.Series, returns: pd.Series, turnover: pd.Series) -> dict[str, float]:
    return {
        "sharpe": sharpe(returns),
        "sortino": sortino(returns),
        "max_drawdown": max_drawdown(equity),
        "annualized_return": float((1 + returns.mean()) ** ANNUALIZATION_DAILY - 1),
        "annualized_vol": float(returns.std() * np.sqrt(ANNUALIZATION_DAILY)),
        "avg_turnover_per_rebal": turnover_metric(turnover),
    }


def coordination_breakeven_spread(
    returns_coord: pd.Series,
    returns_ensemble: pd.Series,
    turnover_coord: pd.Series,
    turnover_ensemble: pd.Series,
    cost_grid_bps: np.ndarray | None = None,
) -> float:
    """Cost level (bps) at which net Sharpe of coordinated == ensemble.

    Returns NaN if no crossing in grid.
    """
    grid = cost_grid_bps if cost_grid_bps is not None else np.linspace(0, 200, 401)
    best, best_gap = float("nan"), float("inf")
    for c in grid:
        cost = c / 10_000
        net_c = returns_coord - turnover_coord * cost
        net_e = returns_ensemble - turnover_ensemble * cost
        gap = sharpe(net_c) - sharpe(net_e)
        if not np.isnan(gap) and abs(gap) < best_gap:
            best_gap = abs(gap)
            best = float(c)
        if gap < 0 and not np.isnan(gap):
            return float(c)
    return best
