"""Wikipedia pageviews fetcher (spec §3.3 secondary; §4.1 narrative_event).

Free public API, no key. Returns daily pageview counts for a given Wikipedia
article. Used by `narrative_event` for `wiki_abnormal_attention` (rolling
z-score) and `wiki_attention_persistence` (autocorrelation).

API: https://wikimedia.org/api/rest_v1/metrics/pageviews/
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from data.cache.cache import read as cache_read
from data.cache.cache import write as cache_write
from pact_logging import get_logger

log = get_logger(__name__)

NAMESPACE = "wikipedia"
BASE = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"

# Wikipedia article slugs per instrument. Mapped where the article is
# directly tradeable-relevant; for indices/ETFs we use the underlying
# concept page.
INSTRUMENT_TO_ARTICLES: dict[str, list[str]] = {
    "SPY": ["S%26P_500"],
    "QQQ": ["Nasdaq-100"],
    "IWM": ["Russell_2000_Index"],
    "IEF": ["United_States_Treasury_security"],
    "SHY": ["United_States_Treasury_security"],
    "GLD": ["Gold_as_an_investment"],
    "USO": ["West_Texas_Intermediate"],
    "UUP": ["U.S._Dollar_Index"],
    "EEM": ["MSCI_Emerging_Markets_Index"],
    "BTC": ["Bitcoin"],
    "VIX": ["VIX"],
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _get(url: str) -> dict:
    r = requests.get(url, headers={"User-Agent": "PACT-research/0.1 (academic)"}, timeout=30)
    r.raise_for_status()
    return r.json()


def pageviews_daily(article: str, start: date, end: date) -> pd.Series:
    """Daily pageviews for a Wikipedia article. Returns Series indexed by date."""
    params = {"article": article, "start": start.isoformat(), "end": end.isoformat()}
    cached = cache_read(NAMESPACE, params)
    if cached is not None:
        return _series_from_payload(cached["payload"])

    log.info("wikipedia fetch article=%s start=%s end=%s", article, start, end)
    url = (
        f"{BASE}/en.wikipedia/all-access/all-agents/{article}"
        f"/daily/{start.strftime('%Y%m%d')}00/{end.strftime('%Y%m%d')}00"
    )
    try:
        payload = _get(url)
    except Exception as e:
        log.warning("wikipedia fetch failed article=%s: %s", article, type(e).__name__)
        cache_write(NAMESPACE, params, {"rows": []})
        return pd.Series(dtype=float)

    rows = [
        (item["timestamp"][:8], int(item["views"]))
        for item in payload.get("items", [])
    ]
    cache_write(NAMESPACE, params, {"rows": rows})
    log.info("wikipedia fetched article=%s rows=%d", article, len(rows))
    return _series_from_payload({"rows": rows})


def pageviews_for_instrument(symbol: str, start: date, end: date) -> pd.Series:
    """Sum pageviews across all Wikipedia articles mapped to an instrument."""
    articles = INSTRUMENT_TO_ARTICLES.get(symbol.upper(), [])
    if not articles:
        return pd.Series(dtype=float)
    series = [pageviews_daily(a, start, end) for a in articles]
    if not series:
        return pd.Series(dtype=float)
    return pd.concat(series, axis=1).sum(axis=1, min_count=1).dropna()


def _series_from_payload(payload: dict) -> pd.Series:
    rows = payload.get("rows", [])
    if not rows:
        return pd.Series(dtype=float)
    idx = [pd.to_datetime(d, format="%Y%m%d") for d, _ in rows]
    vals = [float(v) for _, v in rows]
    return pd.Series(vals, index=idx).sort_index()
