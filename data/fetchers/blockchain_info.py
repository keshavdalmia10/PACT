"""BTC on-chain via blockchain.info charts API (spec §3.3 secondary; §4.5 BTC).

Free public API, no key. Used by `fundamentals_carry` agent for the BTC
branch. Each chart endpoint returns daily-frequency time series.

Coverage: blockchain.info has BTC mainnet data back to 2009. We fetch only
what the spec wires for: active addresses, hash rate, transaction volume.
MVRV needs realized-cap (UTXO cost-basis) data which blockchain.info does
not expose; we use a price-vs-200d-moving-average proxy as a stand-in and
document the substitution.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from data.cache.cache import read as cache_read
from data.cache.cache import write as cache_write
from pact_logging import get_logger

log = get_logger(__name__)

NAMESPACE = "blockchain_info"
BASE = "https://api.blockchain.info/charts"

# Charts we query. Names follow blockchain.info's URL slugs.
CHARTS = {
    "active_addresses": "n-unique-addresses",
    "hash_rate":        "hash-rate",
    "transactions":     "n-transactions",
    "market_price_usd": "market-price",
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _get(chart_slug: str, timespan: str = "all") -> dict:
    """Fetch a single chart. blockchain.info's `timespan` is anchored on
    today (e.g. "365days" = last 365 days), so we always pull "all" and
    slice locally. Each chart is daily and small (~1MB JSON for 5000+
    days), cached once per slug."""
    r = requests.get(
        f"{BASE}/{chart_slug}",
        params={"timespan": timespan, "format": "json", "sampled": "false"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def fetch_chart(chart: str, start: date, end: date) -> pd.Series:
    """Daily values for a single chart sliced to [start, end].

    Cache key is by chart only — we always fetch the full history once
    and slice locally on each call.
    """
    if chart not in CHARTS:
        raise KeyError(f"unknown chart: {chart}; valid: {list(CHARTS)}")
    slug = CHARTS[chart]
    cache_params = {"chart": chart, "timespan": "all"}
    cached = cache_read(NAMESPACE, cache_params)
    if cached is not None:
        rows = cached["payload"].get("rows", [])
        s = _series_from_rows(rows)
        return s.loc[pd.Timestamp(start) : pd.Timestamp(end)]

    log.info("blockchain_info fetch chart=%s timespan=all", chart)
    try:
        payload = _get(slug, timespan="all")
    except Exception as e:
        log.warning("blockchain_info fetch failed chart=%s: %s", chart, type(e).__name__)
        cache_write(NAMESPACE, cache_params, {"rows": []})
        return pd.Series(dtype=float)

    rows = [(p["x"], float(p["y"])) for p in payload.get("values", [])]
    cache_write(NAMESPACE, cache_params, {"rows": rows})
    log.info("blockchain_info fetched chart=%s rows=%d", chart, len(rows))
    s = _series_from_rows(rows)
    return s.loc[pd.Timestamp(start) : pd.Timestamp(end)]


def fetch_panel(start: date, end: date) -> pd.DataFrame:
    """Wide panel of all CHARTS over [start, end]."""
    out = {}
    for chart in CHARTS:
        s = fetch_chart(chart, start, end)
        if not s.empty:
            out[chart] = s
    if not out:
        return pd.DataFrame()
    df = pd.DataFrame(out).sort_index()
    return df


def mvrv_proxy(prices: pd.Series, window: int = 200) -> pd.Series:
    """Stand-in for MVRV using price vs trailing N-day mean.

    True MVRV = market value / realized value, where realized value depends
    on per-UTXO cost basis. blockchain.info does not expose the realized-cap
    series, so we approximate with the ratio of current price to the
    trailing-`window`-day mean — captures over/undervaluation regimes
    similarly though not identical in scale.
    """
    if prices.empty:
        return pd.Series(dtype=float)
    rolling = prices.rolling(window, min_periods=window // 2).mean()
    return (prices / rolling).rename("mvrv_proxy")


def _series_from_rows(rows: list[tuple[int, float]]) -> pd.Series:
    if not rows:
        return pd.Series(dtype=float)
    idx = [pd.Timestamp(t, unit="s").normalize() for t, _ in rows]
    vals = [v for _, v in rows]
    return pd.Series(vals, index=idx).sort_index()
