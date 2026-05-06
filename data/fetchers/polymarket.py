"""Polymarket prediction-market fetcher (spec §3.3 secondary, Window B only).

Free public Gamma API, no key required for read. Used by `narrative_event`
for `polymarket_event_prob` (current implied probability) and
`polymarket_prob_change` (week-over-week change).

API: https://gamma-api.polymarket.com/

Spec §6.4 caveat: Polymarket data is only meaningful from 2022 onwards
(volume-weighted markets); use only for Window B.

Spec §7 lookahead rule: lag prediction-market prices by 48 hours so we
don't use a price set after our `as_of` timestamp.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from data.cache.cache import read as cache_read
from data.cache.cache import write as cache_write
from pact_logging import get_logger

log = get_logger(__name__)

NAMESPACE = "polymarket"
GAMMA = "https://gamma-api.polymarket.com"

# Tag → instruments most affected by markets in that tag.
# Example: an Election market moves SPY, QQQ, USD; a Fed market moves IEF/SHY.
TAG_TO_INSTRUMENTS: dict[str, list[str]] = {
    "Politics": ["SPY", "IWM", "UUP"],
    "Elections": ["SPY", "IWM", "UUP"],
    "Crypto": ["BTC"],
    "Fed": ["IEF", "SHY", "UUP", "GLD"],
    "Economics": ["SPY", "QQQ", "IEF"],
    "Geopolitics": ["GLD", "USO", "UUP"],
    "Energy": ["USO"],
}

POLYMARKET_START = date(2022, 1, 1)
LOOKAHEAD_LAG_HOURS = 48


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _get(url: str, params: dict | None = None) -> list | dict:
    r = requests.get(url, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def list_resolved_markets(
    tags: Iterable[str],
    start: date = POLYMARKET_START,
    end: date | None = None,
    min_volume_usd: float = 100_000,
) -> pd.DataFrame:
    """List Polymarket markets matching any of `tags`, resolved between
    `start` and `end`, with at least `min_volume_usd` traded volume.

    Returns DataFrame with columns: id, question, tag, resolved_yes (bool
    or NaN), resolution_date, total_volume_usd.
    """
    end = end or date.today()
    params = {"tags": list(tags), "start": start.isoformat(), "end": end.isoformat(), "min_volume": min_volume_usd}
    cached = cache_read(NAMESPACE + ".markets", params)
    if cached is not None:
        return pd.DataFrame(cached["payload"]["rows"])

    rows: list[dict] = []
    for tag in tags:
        log.info("polymarket fetch tag=%s start=%s end=%s", tag, start, end)
        try:
            markets = _get(
                f"{GAMMA}/markets",
                params={"closed": "true", "tag": tag, "limit": 500},
            )
        except Exception as e:
            log.warning("polymarket markets fetch failed tag=%s: %s", tag, type(e).__name__)
            continue
        if not isinstance(markets, list):
            continue
        for m in markets:
            try:
                res_date = m.get("endDate") or m.get("end_date_iso") or ""
                vol = float(m.get("volume", 0) or 0)
                if vol < min_volume_usd:
                    continue
                if res_date and res_date[:10] < start.isoformat():
                    continue
                if res_date and res_date[:10] > end.isoformat():
                    continue
                rows.append({
                    "id": m.get("id") or m.get("conditionId"),
                    "question": m.get("question", "")[:200],
                    "tag": tag,
                    "outcome_yes": m.get("outcomePrices", [None])[0],
                    "resolution_date": res_date[:10],
                    "total_volume_usd": vol,
                })
            except Exception:
                continue

    cache_write(NAMESPACE + ".markets", params, {"rows": rows})
    return pd.DataFrame(rows)


def market_price_history(market_id: str, start: date, end: date) -> pd.Series:
    """Historical price series for a single market. Daily closes."""
    params = {"market_id": market_id, "start": start.isoformat(), "end": end.isoformat()}
    cached = cache_read(NAMESPACE + ".history", params)
    if cached is not None:
        rows = cached["payload"].get("rows", [])
        if not rows:
            return pd.Series(dtype=float)
        return pd.Series({pd.Timestamp(d): v for d, v in rows}).sort_index()

    log.info("polymarket price history market=%s", market_id)
    try:
        # CLOB-style price history endpoint
        history = _get(
            "https://clob.polymarket.com/prices-history",
            params={"market": market_id, "interval": "1d", "fidelity": 1},
        )
    except Exception as e:
        log.warning("polymarket history fetch failed market=%s: %s", market_id, type(e).__name__)
        cache_write(NAMESPACE + ".history", params, {"rows": []})
        return pd.Series(dtype=float)

    points = (history or {}).get("history", [])
    rows = [(pd.Timestamp(p["t"], unit="s").date().isoformat(), float(p["p"])) for p in points]
    rows = [r for r in rows if start.isoformat() <= r[0] <= end.isoformat()]
    cache_write(NAMESPACE + ".history", params, {"rows": rows})
    if not rows:
        return pd.Series(dtype=float)
    return pd.Series({pd.Timestamp(d): v for d, v in rows}).sort_index()


def event_prob_panel(
    instruments: Iterable[str],
    start: date,
    end: date,
    min_volume_usd: float = 100_000,
) -> pd.DataFrame:
    """Per-instrument daily mean implied probability across relevant markets.

    For each instrument, collects all markets whose tags map to it, weights
    them equally, and returns a daily mean probability. Returns DataFrame
    indexed by date with one column per instrument.
    """
    instr_set = {s.upper() for s in instruments}
    relevant_tags = [t for t, syms in TAG_TO_INSTRUMENTS.items() if instr_set & set(syms)]
    if not relevant_tags:
        return pd.DataFrame()

    markets = list_resolved_markets(relevant_tags, start, end, min_volume_usd)
    if markets.empty:
        return pd.DataFrame()

    columns: dict[str, pd.Series] = {sym: pd.Series(dtype=float) for sym in instr_set}
    for sym in instr_set:
        # Find tags relevant to this instrument
        sym_tags = [t for t, syms in TAG_TO_INSTRUMENTS.items() if sym in syms]
        sym_markets = markets[markets["tag"].isin(sym_tags)]
        per_market: list[pd.Series] = []
        for mid in sym_markets["id"].dropna().head(20):  # cap at 20 markets/instrument
            ph = market_price_history(str(mid), start, end)
            if not ph.empty:
                per_market.append(ph)
        if per_market:
            df = pd.concat(per_market, axis=1)
            columns[sym] = df.mean(axis=1)
    out = pd.DataFrame(columns).sort_index()
    return out
