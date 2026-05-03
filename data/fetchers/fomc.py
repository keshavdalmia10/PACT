"""FOMC corpus — statements, minutes, speeches (spec §3.2).

Hard rule on timestamps:
- Statement: meeting end (per Fed published schedule)
- Minutes: 14:00 ET, exactly 3 weeks after the meeting (ALFRED Release 101)
- Speech: time delivered
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import requests
from pytz import timezone as pytz_timezone

from data.cache.cache import read as cache_read
from data.cache.cache import write as cache_write

ET = pytz_timezone("America/New_York")
NAMESPACE = "fomc"


@dataclass
class FOMCDocument:
    kind: str              # "statement" | "minutes" | "speech"
    meeting_date: datetime | None
    release_dt_et: datetime
    url: str
    text: str | None = None


def minutes_release_dt(meeting_date: datetime) -> datetime:
    """Minutes drop 2pm ET, 3 weeks after meeting."""
    base = meeting_date.astimezone(ET) if meeting_date.tzinfo else ET.localize(meeting_date)
    return (base + timedelta(weeks=3)).replace(hour=14, minute=0, second=0, microsecond=0)


def fetch_statement(meeting_date_str: str, ending_time_et: tuple[int, int] = (14, 0)) -> FOMCDocument:
    """Fetch a statement page from federalreserve.gov.

    URL convention: /newsevents/pressreleases/monetary{YYYYMMDD}a.htm.
    """
    url = f"https://www.federalreserve.gov/newsevents/pressreleases/monetary{meeting_date_str}a.htm"
    params = {"url": url}
    cached = cache_read(NAMESPACE + ".statement", params)
    if cached is not None:
        text = cached["payload"]["text"]
    else:
        resp = requests.get(url, timeout=30, headers={"User-Agent": "research-bot"})
        resp.raise_for_status()
        text = resp.text
        cache_write(NAMESPACE + ".statement", params, {"text": text})

    md = ET.localize(datetime.strptime(meeting_date_str, "%Y%m%d").replace(
        hour=ending_time_et[0], minute=ending_time_et[1]
    ))
    return FOMCDocument(kind="statement", meeting_date=md, release_dt_et=md, url=url, text=text)
