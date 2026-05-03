"""GDELT 2.0 GKG (spec §3.2, §7).

Hard rules:
- Use the GKG file timestamp, not the event date.
- Lag intraday signals by 30 minutes.
- Daily aggregates use prior-day close-to-close.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

import pandas as pd
import requests

from data.cache.cache import read as cache_read
from data.cache.cache import write as cache_write

NAMESPACE = "gdelt"
GKG_BASE = "http://data.gdeltproject.org/gdeltv2"
INTRADAY_LAG = timedelta(minutes=30)


def gkg_file_url(file_ts_utc: datetime) -> str:
    """File names are at 15-minute boundaries: yyyymmddhhmmss.gkg.csv.zip."""
    minute = (file_ts_utc.minute // 15) * 15
    rounded = file_ts_utc.replace(minute=minute, second=0, microsecond=0)
    stamp = rounded.strftime("%Y%m%d%H%M%S")
    return f"{GKG_BASE}/{stamp}.gkg.csv.zip"


def fetch_gkg_window(
    start_utc: datetime,
    end_utc: datetime,
    apply_lag: bool = True,
) -> pd.DataFrame:
    """Fetch GKG file metadata for a window. (Stub: returns file URLs only.)

    Full GKG parsing belongs in a dedicated worker; the BigQuery path is
    typically the right call for backfills. This stub records the URLs to
    fetch so the contract and lag rule are visible at the call site.
    """
    if apply_lag:
        end_utc = end_utc - INTRADAY_LAG
    if end_utc <= start_utc:
        return pd.DataFrame(columns=["file_ts_utc", "url"])
    rows = []
    cur = start_utc.replace(minute=(start_utc.minute // 15) * 15, second=0, microsecond=0)
    while cur <= end_utc:
        rows.append({"file_ts_utc": cur, "url": gkg_file_url(cur)})
        cur += timedelta(minutes=15)
    return pd.DataFrame(rows)


def daily_theme_intensity(
    files_df: pd.DataFrame,
    themes: Iterable[str],
) -> pd.DataFrame:
    """Aggregate matched themes into daily intensity (placeholder).

    Real implementation downloads each .gkg.csv.zip, splits column 8
    (V2THEMES), counts mentions per theme, and aggregates by file_ts date.
    """
    raise NotImplementedError(
        "Wire to GDELT BigQuery (`gdelt-bq.gdeltv2.gkg`) for backfills; "
        "use the file-download path only for incremental updates."
    )
