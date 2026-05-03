"""Daily OHLCV prices via yfinance.

BTC splice (spot pre-2024-01-11, IBIT post) is handled here so downstream
code sees a single 'BTC' series.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import yfinance as yf

from data.universe import BTC_SPLICE_DATE


def fetch_ohlcv(symbol: str, start: date, end: date) -> pd.DataFrame:
    """Single-symbol daily OHLCV. Returns a DataFrame indexed by date."""
    if symbol.upper() == "BTC":
        return _fetch_btc_spliced(start, end)
    df = yf.download(
        symbol,
        start=start.isoformat(),
        end=end.isoformat(),
        progress=False,
        auto_adjust=False,
    )
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def _fetch_btc_spliced(start: date, end: date) -> pd.DataFrame:
    splice = BTC_SPLICE_DATE
    parts: list[pd.DataFrame] = []
    if start < splice:
        spot = yf.download(
            "BTC-USD",
            start=start.isoformat(),
            end=min(end, splice).isoformat(),
            progress=False,
            auto_adjust=False,
        )
        if isinstance(spot.columns, pd.MultiIndex):
            spot.columns = spot.columns.get_level_values(0)
        parts.append(spot)
    if end >= splice:
        ibit = yf.download(
            "IBIT",
            start=max(start, splice).isoformat(),
            end=end.isoformat(),
            progress=False,
            auto_adjust=False,
        )
        if isinstance(ibit.columns, pd.MultiIndex):
            ibit.columns = ibit.columns.get_level_values(0)
        parts.append(ibit)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts).sort_index()


def fetch_panel(symbols: list[str], start: date, end: date, field: str = "Adj Close") -> pd.DataFrame:
    """Wide panel of one OHLCV field across symbols."""
    series = {}
    for s in symbols:
        df = fetch_ohlcv(s, start, end)
        if df.empty or field not in df.columns:
            continue
        series[s.upper()] = df[field]
    return pd.DataFrame(series).sort_index()
