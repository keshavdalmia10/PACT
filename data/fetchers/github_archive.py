"""GitHub Archive (BigQuery) fetcher — engineering-velocity factor for QQQ.

Free-tier-safe: queries `githubarchive.day.YYYYMMDD` partitioned tables
filtered by repo (S&P 500 IT-sector member orgs / NASDAQ-100 components).
Each daily query scans ~5-50 GB; aggregating monthly across the cell window
typically lands well under 1 TB.

Used by `fundamentals_carry` for the QQQ branch's
`github_eng_velocity_log_abnormal` factor — a proxy for tech-sector
production momentum (commit volume on key public-company orgs).

Coverage: GitHub Archive starts 2011-02-12. Pre-2011 returns empty.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Iterable

import pandas as pd

from data.cache.cache import read as cache_read
from data.cache.cache import write as cache_write
from pact_logging import get_logger

log = get_logger(__name__)

NAMESPACE = "github_archive"
DEFAULT_MAX_BYTES = 200 * 10**9  # 200 GB cap per query (free-tier safe)
GHARCHIVE_START = date(2011, 2, 12)

# QQQ proxy: open-source orgs of NASDAQ-100 mega-cap tech companies whose
# repos generate meaningful public commit/PR/issue volume.
QQQ_TECH_ORGS = (
    "google", "microsoft", "facebook", "apple", "amzn",
    "tensorflow", "pytorch", "openai", "nvidia", "intel",
)


def _client():
    project = os.environ.get("GCP_PROJECT_ID")
    if not project:
        raise RuntimeError(
            "GCP_PROJECT_ID not set; GitHub Archive fetcher requires a GCP project."
        )
    from google.cloud import bigquery

    return bigquery.Client(project=project)


def daily_org_event_count(
    orgs: Iterable[str],
    start: date,
    end: date,
    max_bytes: int = DEFAULT_MAX_BYTES,
    dry_run_first: bool = True,
) -> pd.DataFrame:
    """Daily event count per org over [start, end], wide-format.

    Returns DataFrame indexed by date with one column per org plus a `total`.
    """
    if start < GHARCHIVE_START:
        start = GHARCHIVE_START
    orgs_tuple = tuple(sorted({o.lower() for o in orgs}))
    if not orgs_tuple:
        raise ValueError("orgs must be non-empty")

    params = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "orgs": list(orgs_tuple),
    }
    cached = cache_read(NAMESPACE, params)
    if cached is not None:
        rows = cached["payload"]["rows"]
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["day"] = pd.to_datetime(df["day"])
        return df.set_index("day").sort_index()

    log.info("github_archive fetch start=%s end=%s orgs=%d", start, end, len(orgs_tuple))
    client = _client()
    org_clauses = ",\n  ".join(
        [f"COUNTIF(LOWER(actor.login) LIKE '{o}%' OR LOWER(repo.name) LIKE '{o}/%') AS n_{o.replace('-', '_')}"
         for o in orgs_tuple]
    )
    sql = f"""
SELECT
  DATE(created_at) AS day,
  {org_clauses},
  COUNT(*) AS total
FROM `githubarchive.day.*`
WHERE _TABLE_SUFFIX BETWEEN '{start.strftime("%Y%m%d")}' AND '{end.strftime("%Y%m%d")}'
GROUP BY day
ORDER BY day
"""
    from google.cloud import bigquery

    if dry_run_first:
        dry = client.query(
            sql,
            job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False),
        )
        log.info("github_archive dry-run estimate: %.2f GB", dry.total_bytes_processed / 1e9)
        if dry.total_bytes_processed > max_bytes:
            raise RuntimeError(
                f"github_archive query estimated {dry.total_bytes_processed/1e9:.1f} GB "
                f"> max_bytes ({max_bytes/1e9:.1f} GB). Reduce window."
            )

    job = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(maximum_bytes_billed=max_bytes),
    )
    df = job.to_dataframe()
    log.info("github_archive fetched rows=%d bytes_billed=%.2f GB", len(df), job.total_bytes_billed / 1e9)

    cache_write(NAMESPACE, params, {"rows": df.assign(day=df["day"].astype(str)).to_dict(orient="records")})
    df["day"] = pd.to_datetime(df["day"])
    return df.set_index("day").sort_index()


def qqq_engineering_velocity(start: date, end: date) -> pd.Series:
    """Daily total event count across QQQ_TECH_ORGS, used as engineering
    velocity proxy for QQQ. Returns Series with `total` column.
    """
    df = daily_org_event_count(QQQ_TECH_ORGS, start, end)
    if df.empty or "total" not in df.columns:
        return pd.Series(dtype=float)
    return df["total"].astype(float)
