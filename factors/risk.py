"""Volatility, VaR, and correlation factors (spec §4.1 Technical & Risk agents)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm


def ewma_volatility(returns: pd.Series, lam: float = 0.94) -> pd.Series:
    """RiskMetrics-style EWMA variance, returned as annualized vol."""
    var = np.zeros(len(returns))
    var[0] = returns.iloc[0] ** 2 if len(returns) else 0.0
    for t in range(1, len(returns)):
        var[t] = lam * var[t - 1] + (1 - lam) * returns.iloc[t] ** 2
    return pd.Series(np.sqrt(var) * np.sqrt(252), index=returns.index, name="ewma_vol_ann")


def garch_forecast(returns: pd.Series, horizon: int = 1) -> float:
    """One-step-ahead GARCH(1,1) volatility forecast (annualized).

    Returns NaN-safe: empty / too-short series → np.nan.
    """
    r = returns.dropna()
    if len(r) < 100:
        return float("nan")
    from arch import arch_model

    am = arch_model(r * 100, vol="GARCH", p=1, q=1, mean="Zero", dist="normal")
    res = am.fit(disp="off", show_warning=False)
    f = res.forecast(horizon=horizon, reindex=False)
    sigma = np.sqrt(f.variance.values[-1, -1]) / 100
    return float(sigma * np.sqrt(252))


def cornish_fisher_var(returns: pd.Series, alpha: float = 0.05) -> float:
    """Cornish-Fisher VaR with skew/kurt adjustment.

    Sign convention: positive number = expected loss at the alpha tail.
    """
    r = returns.dropna()
    if len(r) < 30:
        return float("nan")
    z = norm.ppf(alpha)
    s = float(r.skew())
    k = float(r.kurt())
    z_cf = z + (z**2 - 1) * s / 6 + (z**3 - 3 * z) * k / 24 - (2 * z**3 - 5 * z) * s**2 / 36
    return float(-(r.mean() + z_cf * r.std()))


def rolling_correlation(returns: pd.DataFrame, window: int = 60) -> pd.DataFrame:
    """Pairwise rolling correlation, returned in long form (date, i, j, rho)."""
    rolled = returns.rolling(window).corr()
    long = rolled.stack().rename("rho").reset_index()
    long.columns = ["date", "i", "j", "rho"]
    return long[long["i"] < long["j"]].reset_index(drop=True)
