"""ALFRED (vintage FRED) — point-in-time macro series (spec §3.2, §7).

Hard rule per spec: return first-release values only — never revised.

Two-tier strategy:
- Daily non-revised series (interest rates, FX): values aren't revised, so
  latest == first-release. Use plain `fred.get_series(observation_start,
  observation_end)`.
- Monthly/quarterly revised series (CPI, GDP, UNRATE, INDPRO): use the
  ALFRED REST API directly with `output_type=4` (first-release only). This
  bypasses fredapi's `get_series_first_release()` which fails on series with
  >2000 vintages. Falls back to fredapi's `get_series` (latest revision)
  with a warning if the REST call fails.

Performance / caching:
- The first_release(start, end, ...) call is range-keyed for backwards
  compat. It scans the local cache for a wider already-cached range that
  contains [start, end] and serves the slice — eliminating per-rebalance
  cache misses on rolling windows. Set `prefetch=True` once at the start of
  a backtest cell to prime a wide cache for every HEADLINE_SERIES key.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Iterable

import pandas as pd
import requests
from fredapi import Fred
from tenacity import retry, stop_after_attempt, wait_exponential

from data.cache.cache import read as cache_read
from data.cache.cache import write as cache_write
from data.cache.cache import cache_path as _cache_path_for
from pact_logging import get_logger

log = get_logger(__name__)

NAMESPACE = "alfred"
ALFRED_REST = "https://api.stlouisfed.org/fred/series/observations"

# Series that are revised after first publication. For these, first-release
# vs latest-revised matters — point-in-time research must use first-release.
REVISED_SERIES: frozenset[str] = frozenset(
    {"CPIAUCSL", "GDP", "UNRATE", "INDPRO"}
)


def _client(api_key: str | None = None) -> Fred:
    key = api_key or os.environ.get("FRED_API_KEY")
    if not key:
        raise RuntimeError("FRED_API_KEY not set; ALFRED requires a free API key.")
    return Fred(api_key=key)


def _api_key() -> str:
    key = os.environ.get("FRED_API_KEY")
    if not key:
        raise RuntimeError("FRED_API_KEY not set; ALFRED requires a free API key.")
    return key


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=1, max=10))
def _rest_first_release(series_id: str, start: date, end: date) -> pd.Series:
    """Fetch first-release observations via the ALFRED REST API directly.

    `output_type=4` returns the first vintage value for each observation —
    contamination-clean and works for revised series of any vintage count.
    """
    params = {
        "api_key": _api_key(),
        "series_id": series_id,
        "observation_start": start.isoformat(),
        "observation_end": end.isoformat(),
        "output_type": 4,  # vintage data: first release only
        "file_type": "json",
    }
    r = requests.get(ALFRED_REST, params=params, timeout=30)
    r.raise_for_status()
    payload = r.json()
    obs = payload.get("observations", [])
    rows = []
    for o in obs:
        # Sometimes the API returns the value in a column keyed by the realtime date.
        # Standard schema has `date` and `value`. With output_type=4 the value is
        # in the same `value` field but represents the first release.
        v = o.get("value", ".")
        if v in (".", "", None):
            continue
        try:
            rows.append((pd.Timestamp(o["date"]), float(v)))
        except (ValueError, KeyError):
            continue
    if not rows:
        return pd.Series(dtype=float, name=series_id)
    s = pd.Series({d: v for d, v in rows}, name=series_id).sort_index()
    return s


def first_release(
    series_id: str,
    start: date,
    end: date,
    api_key: str | None = None,
) -> pd.Series:
    """Return point-in-time observations of a FRED series.

    For non-revised daily series, this is exactly first-release.
    For revised series, attempts ALFRED REST `output_type=4`; falls back to
    fredapi's `get_series` (latest revision) on failure with a warning.

    Cache strategy: looks for an exact-key cache hit first; if absent, scans
    the namespace for a wider already-cached range covering [start, end] and
    serves the slice. This makes rolling-window callers (every rebalance has
    a different start) hit cache after the first call.
    """
    # Exact hit
    params = {"series_id": series_id, "start": start, "end": end, "kind": "first_release"}
    cached = cache_read(NAMESPACE, params)
    if cached is not None:
        log.debug("alfred cache hit series=%s start=%s end=%s", series_id, start, end)
        return _payload_to_series(cached["payload"], series_id)

    # Wider-window cache scan (eliminates rolling-window cache misses)
    wider = _find_wider_cache(series_id, start, end)
    if wider is not None:
        log.debug("alfred wider-window cache hit series=%s start=%s end=%s", series_id, start, end)
        return _slice_by_date(wider, start, end)

    log.info("alfred fetch series=%s start=%s end=%s", series_id, start, end)
    s = _fetch_uncached(series_id, start, end, api_key=api_key)

    cache_write(
        NAMESPACE,
        params,
        {"index": [pd.Timestamp(d).isoformat() for d in s.index], "values": [float(v) for v in s.values]},
    )
    log.info("alfred fetched series=%s rows=%d", series_id, len(s))
    return s


def _fetch_uncached(
    series_id: str,
    start: date,
    end: date,
    api_key: str | None,
) -> pd.Series:
    fred = _client(api_key)
    if series_id in REVISED_SERIES:
        # Use REST output_type=4 for true first-release; fall back to fredapi
        # (latest revision) on failure.
        try:
            s = _rest_first_release(series_id, start, end)
            if not s.empty:
                return s
            log.warning("alfred REST first-release returned empty for %s; falling back", series_id)
        except Exception as e:
            log.warning(
                "alfred REST first-release failed for %s (%s); falling back to latest revision",
                series_id, type(e).__name__,
            )
        s = fred.get_series(
            series_id,
            observation_start=start.isoformat(),
            observation_end=end.isoformat(),
        )
    else:
        # Non-revised daily series — latest == first-release.
        s = fred.get_series(
            series_id,
            observation_start=start.isoformat(),
            observation_end=end.isoformat(),
        )

    s = s.dropna()
    s.name = series_id
    return s


def prefetch_window(series_ids: Iterable[str], start: date, end: date, api_key: str | None = None) -> None:
    """Pre-warm the cache with a wide window so all subsequent rolling
    queries inside [start, end] hit the wider-window cache lookup.

    Call this once at the top of a backtest cell with the cell's full
    date range — every rebalance's smaller `first_release(...)` call will
    then return instantly via slice instead of hitting the network.
    """
    for sid in series_ids:
        first_release(sid, start, end, api_key=api_key)


def _find_wider_cache(series_id: str, start: date, end: date) -> pd.Series | None:
    """Scan namespace cache directory for any cached range covering [start, end]."""
    # The cache file path encodes a SHA hash of params, so we can't decode
    # ranges from filenames. Instead, walk the directory and read each entry's
    # `params` block (cheap — file headers are small).
    base = _cache_path_for(NAMESPACE, {"series_id": series_id, "start": start, "end": end, "kind": "first_release"}).parent
    if not base.exists():
        return None
    candidates: list[tuple[pd.Timestamp, pd.Timestamp, dict]] = []
    target_start = pd.Timestamp(start)
    target_end = pd.Timestamp(end)
    for fp in base.glob("*.json"):
        try:
            import json as _json
            with fp.open() as f:
                rec = _json.load(f)
        except Exception:
            continue
        params = rec.get("params", {})
        if params.get("series_id") != series_id or params.get("kind") != "first_release":
            continue
        try:
            cs = pd.Timestamp(params["start"])
            ce = pd.Timestamp(params["end"])
        except Exception:
            continue
        if cs <= target_start and ce >= target_end:
            candidates.append((cs, ce, rec.get("payload", {})))
    if not candidates:
        return None
    # Pick the *narrowest* covering range to minimize work.
    candidates.sort(key=lambda c: (c[1] - c[0]))
    payload = candidates[0][2]
    return _payload_to_series(payload, series_id)


def _payload_to_series(payload: dict, series_id: str) -> pd.Series:
    return pd.Series(
        data=payload["values"],
        index=pd.to_datetime(payload["index"]),
        name=series_id,
    )


def _slice_by_date(s: pd.Series, start: date, end: date) -> pd.Series:
    """Slice a date-indexed Series by [start, end] without string ambiguity."""
    s = s.copy()
    s.index = pd.to_datetime(s.index)
    return s.loc[pd.Timestamp(start) : pd.Timestamp(end)]


HEADLINE_SERIES = {
    "fed_funds": "DFEDTARU",
    "ten_year": "DGS10",
    "two_year": "DGS2",
    "cpi_yoy": "CPIAUCSL",
    "unemployment": "UNRATE",
    "gdp": "GDP",
    "industrial_production": "INDPRO",
}
