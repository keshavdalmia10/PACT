"""SEC EDGAR — keyed off acceptance datetime UTC (spec §3.2, §7).

Hard rule: filings accepted after 17:30 ET attribute to next business
day's open. We expose `effective_session_date` to enforce this everywhere.
"""

from __future__ import annotations

import os
import time
from datetime import date, datetime, time as dtime
from typing import Any

import pandas as pd
import requests
from pytz import timezone as pytz_timezone
from tenacity import retry, stop_after_attempt, wait_exponential

from data.cache.cache import read as cache_read
from data.cache.cache import write as cache_write

NAMESPACE = "edgar"
BASE = "https://data.sec.gov"
ET = pytz_timezone("America/New_York")
CUTOFF = dtime(17, 30)  # 17:30 ET


def _user_agent() -> str:
    ua = os.environ.get("SEC_USER_AGENT")
    if not ua:
        raise RuntimeError(
            "SEC_USER_AGENT must be set, e.g. 'Your Name your@email'. "
            "SEC requires a real contact in User-Agent."
        )
    return ua


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=1, max=10))
def _get(url: str) -> dict[str, Any]:
    resp = requests.get(url, headers={"User-Agent": _user_agent()}, timeout=30)
    resp.raise_for_status()
    time.sleep(0.11)  # SEC rate limit ~10 req/sec
    return resp.json()


def submissions(cik: int) -> dict[str, Any]:
    """Submissions index for a given CIK (zero-padded 10 digits)."""
    cik_str = str(cik).zfill(10)
    params = {"cik": cik_str}
    cached = cache_read(NAMESPACE + ".submissions", params)
    if cached is not None:
        return cached["payload"]
    url = f"{BASE}/submissions/CIK{cik_str}.json"
    payload = _get(url)
    cache_write(NAMESPACE + ".submissions", params, payload)
    return payload


def recent_filings(cik: int, forms: tuple[str, ...] = ("8-K",)) -> pd.DataFrame:
    """Recent filings table; one row per filing.

    Includes accepted (acceptance datetime UTC) and effective_session_date,
    which applies the 17:30-ET-cutoff rule.
    """
    sub = submissions(cik)
    rec = sub.get("filings", {}).get("recent", {})
    df = pd.DataFrame(rec)
    if df.empty:
        return df
    df = df[df["form"].isin(forms)].copy()
    df["accepted_utc"] = pd.to_datetime(df["acceptanceDateTime"], utc=True)
    df["effective_session_date"] = df["accepted_utc"].apply(_effective_session_date)
    df["filingDate"] = pd.to_datetime(df["filingDate"]).dt.date
    return df.reset_index(drop=True)


def _effective_session_date(accepted_utc: pd.Timestamp) -> date:
    """17:30 ET cutoff rule (spec §7 step 3)."""
    et = accepted_utc.tz_convert(ET)
    if et.time() >= CUTOFF:
        next_day = et + pd.Timedelta(days=1)
        # Skip weekends; a real impl should skip exchange holidays too.
        while next_day.weekday() >= 5:
            next_day += pd.Timedelta(days=1)
        return next_day.date()
    return et.date()


def is_after_cutoff_et(when_utc: datetime) -> bool:
    et = when_utc.astimezone(ET) if when_utc.tzinfo else ET.localize(when_utc)
    return et.time() >= CUTOFF
