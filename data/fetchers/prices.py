"""Daily OHLCV prices via yfinance.

BTC splice (spot pre-2024-01-11, IBIT post) is handled here so downstream
code sees a single 'BTC' series.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import yfinance as yf

from data.cache.cache import read as cache_read
from data.cache.cache import write as cache_write
from data.universe import BTC_SPLICE_DATE
from pact_logging import get_logger

log = get_logger(__name__)

NAMESPACE = "prices"


def _cached_yf_download(symbol: str, start: date, end: date) -> pd.DataFrame:
    params = {"symbol": symbol, "start": start.isoformat(), "end": end.isoformat()}
    hit = cache_read(NAMESPACE, params)
    if hit is not None:
        log.debug("prices cache hit symbol=%s start=%s end=%s", symbol, start, end)
        payload = hit["payload"]
        df = pd.DataFrame(payload["data"])
        df.index = pd.to_datetime(payload["index"])
        return df
    log.debug("prices cache miss symbol=%s start=%s end=%s", symbol, start, end)
    df = yf.download(
        symbol,
        start=start.isoformat(),
        end=end.isoformat(),
        progress=False,
        auto_adjust=False,
    )
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    cache_write(
        NAMESPACE,
        params,
        {
            "index": [d.isoformat() for d in df.index],
            "data": {c: [float(v) if pd.notna(v) else None for v in df[c].values] for c in df.columns},
        },
    )
    return df


def fetch_ohlcv(symbol: str, start: date, end: date) -> pd.DataFrame:
    """Single-symbol daily OHLCV. Returns a DataFrame indexed by date."""
    if symbol.upper() == "BTC":
        return _fetch_btc_spliced(start, end)
    df = _cached_yf_download(symbol, start, end)
    if df.empty:
        log.warning("prices empty symbol=%s start=%s end=%s", symbol, start, end)
    return df


def _fetch_btc_spliced(start: date, end: date) -> pd.DataFrame:
    splice = BTC_SPLICE_DATE
    parts: list[pd.DataFrame] = []
    if start < splice:
        parts.append(_cached_yf_download("BTC-USD", start, min(end, splice)))
    if end >= splice:
        parts.append(_cached_yf_download("IBIT", max(start, splice), end))
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts).sort_index()


def fetch_panel(symbols: list[str], start: date, end: date, field: str = "Adj Close") -> pd.DataFrame:
    """Wide panel of one OHLCV field across symbols."""
    log.info("prices panel fetch symbols=%d field=%s start=%s end=%s", len(symbols), field, start, end)
    series = {}
    for s in symbols:
        df = fetch_ohlcv(s, start, end)
        if df.empty or field not in df.columns:
            log.warning("prices skip symbol=%s (empty or missing field=%s)", s, field)
            continue
        series[s.upper()] = df[field]
    panel = pd.DataFrame(series).sort_index()
    log.info("prices panel built rows=%d cols=%d", len(panel), len(panel.columns))
    return panel
