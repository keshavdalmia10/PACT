"""Regime-stratified analysis (spec §6.9, §6.10).

NBER recessions and VIX-quartile stratification, à la FINSABER.
"""

from __future__ import annotations

import pandas as pd
import yfinance as yf

from evaluation.metrics import summary

NBER_RECESSIONS = [
    ("2007-12-01", "2009-06-30"),
    ("2020-02-01", "2020-04-30"),
]


def stratify_nber(returns: pd.Series, equity: pd.Series, turnover: pd.Series) -> dict[str, dict]:
    out: dict[str, dict] = {"recession": {}, "expansion": {}}
    in_rec = pd.Series(False, index=returns.index)
    for s, e in NBER_RECESSIONS:
        in_rec.loc[s:e] = True
    out["recession"] = summary(equity[in_rec], returns[in_rec], turnover[in_rec])
    out["expansion"] = summary(equity[~in_rec], returns[~in_rec], turnover[~in_rec])
    return out


def stratify_by_vix(
    returns: pd.Series,
    equity: pd.Series,
    turnover: pd.Series,
) -> dict[str, dict]:
    """Quartile-stratified by ^VIX close on each day."""
    vix = yf.download("^VIX", start=returns.index.min(), end=returns.index.max(), progress=False)
    if isinstance(vix.columns, pd.MultiIndex):
        vix.columns = vix.columns.get_level_values(0)
    vix_close = vix["Adj Close"].reindex(returns.index).ffill()
    qs = pd.qcut(vix_close, 4, labels=["Q1", "Q2", "Q3", "Q4"])
    out: dict[str, dict] = {}
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        mask = qs == q
        out[q] = summary(equity[mask], returns[mask], turnover[mask])
    return out
