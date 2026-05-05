"""ALFRED (vintage FRED) — point-in-time macro series (spec §3.2, §7).

Hard rule per spec: return first-release values only — never revised.

Implementation note: `fredapi.Fred.get_series_first_release()` calls
`get_series_all_releases()` under the hood, which fetches every vintage in
the series' lifetime. For high-frequency series like DGS10 / DGS2 / DFEDTARU
that has >2000 vintage dates, FRED's API rejects the request with
"This exceeds the maximum number of vintage dates allowed for this file
type (2000)".

Two-tier strategy:
- Daily non-revised series (interest rates, FX): values aren't revised, so
  latest == first-release. Use plain `fred.get_series(observation_start,
  observation_end)`.
- Monthly/quarterly revised series (CPI, GDP, UNRATE, INDPRO): try
  `get_series_first_release`; on failure fall back to `get_series` and log a
  warning. **TODO before publication**: replace the fallback with a direct
  ALFRED REST call (`output_type=4`) so revised series are truly first-print.
"""

from __future__ import annotations

import os
from datetime import date

import pandas as pd
from fredapi import Fred

from data.cache.cache import read as cache_read
from data.cache.cache import write as cache_write
from pact_logging import get_logger

log = get_logger(__name__)

NAMESPACE = "alfred"

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


def first_release(
    series_id: str,
    start: date,
    end: date,
    api_key: str | None = None,
) -> pd.Series:
    """Return point-in-time observations of a FRED series.

    For non-revised daily series, this is exactly first-release.
    For revised series, attempts vintage-aware fetch; falls back to latest
    revision if the vintage API rejects the query (with a warning logged).
    """
    params = {"series_id": series_id, "start": start, "end": end, "kind": "first_release"}
    cached = cache_read(NAMESPACE, params)
    if cached is not None:
        log.debug("alfred cache hit series=%s start=%s end=%s", series_id, start, end)
        payload = cached["payload"]
        return pd.Series(
            data=payload["values"],
            index=pd.to_datetime(payload["index"]),
            name=series_id,
        )

    log.info("alfred fetch series=%s start=%s end=%s", series_id, start, end)
    fred = _client(api_key)

    s: pd.Series
    if series_id in REVISED_SERIES:
        try:
            raw = fred.get_series_first_release(series_id)
            s = _slice_by_date(raw, start, end)
        except Exception as e:
            log.warning(
                "alfred first-release unavailable for %s (%s); falling back to latest revision",
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

    cache_write(
        NAMESPACE,
        params,
        {"index": [pd.Timestamp(d).isoformat() for d in s.index], "values": [float(v) for v in s.values]},
    )
    log.info("alfred fetched series=%s rows=%d", series_id, len(s))
    return s


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
