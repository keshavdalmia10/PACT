"""ALFRED (vintage FRED) — first-release ONLY (spec §3.2, §7).

Hard rule: never return revised series. Every value carries the realtime
date it was first released, so downstream point-in-time logic can filter.
"""

from __future__ import annotations

import os
from datetime import date

import pandas as pd
from fredapi import Fred

from data.cache.cache import read as cache_read
from data.cache.cache import write as cache_write

NAMESPACE = "alfred"


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
    """Return the first-release vintage of a FRED series.

    Each observation is the value as first published — never revised.
    Index is the observation date; values are first-print numbers.
    """
    params = {"series_id": series_id, "start": start, "end": end, "kind": "first_release"}
    cached = cache_read(NAMESPACE, params)
    if cached is not None:
        payload = cached["payload"]
        return pd.Series(
            data=payload["values"],
            index=pd.to_datetime(payload["index"]),
            name=series_id,
        )

    fred = _client(api_key)
    s = fred.get_series_first_release(series_id)
    s = s.loc[start.isoformat() : end.isoformat()]
    s.name = series_id

    cache_write(
        NAMESPACE,
        params,
        {"index": [d.isoformat() for d in s.index], "values": [float(v) for v in s.values]},
    )
    return s


HEADLINE_SERIES = {
    "fed_funds": "DFEDTARU",
    "ten_year": "DGS10",
    "two_year": "DGS2",
    "cpi_yoy": "CPIAUCSL",
    "unemployment": "UNRATE",
    "gdp": "GDP",
    "industrial_production": "INDPRO",
}
