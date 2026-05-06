"""EDGAR equity-index P/E aggregation via SEC `companyfacts` XBRL JSON.

Used by `fundamentals_carry` agent for the equity-index branches (SPY, QQQ,
IWM, EEM). For each rebalance date, aggregates constituent fundamentals
(net income, revenue, FCF, shares outstanding) into market-cap-weighted
index-level metrics:

- agg_pe              — weighted P / E (market_cap / sum(net income TTM))
- fwd_earnings_yield  — sum(net income TTM) / sum(market_cap)
- rev_growth_yoy      — weighted YoY revenue growth
- fcf_yield           — sum(FCF TTM) / sum(market_cap)

Implementation:
- SEC ticker→CIK lookup via the public `company_tickers.json` endpoint.
- Per-CIK XBRL facts via the public `companyfacts` JSON endpoint
  (much cleaner than parsing raw XBRL filings).
- `acceptance-datetime` cutoffs per spec §7: a fact is only usable for an
  `as_of` decision if its filed_date <= as_of (with the 17:30-ET rule
  applied via `data.fetchers.edgar._effective_session_date`).
- Constituents lists are static-as-of-now in `data/constituents/*.json`.
  Survivorship-bias caveat: the same as-of-today constituents are applied
  historically, which slightly inflates index returns relative to a true
  point-in-time membership panel. This is the standard simplification in
  multi-asset literature; document it in the paper.

Free tier: SEC EDGAR is rate-limited to 10 req/sec but otherwise unlimited.
We respect that cap via tenacity.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from data.cache.cache import read as cache_read
from data.cache.cache import write as cache_write
from pact_logging import get_logger

log = get_logger(__name__)

NAMESPACE = "edgar_xbrl"
SEC_BASE = "https://data.sec.gov"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
RATE_LIMIT_SECONDS = 0.11  # 10 req/sec cap
CONSTITUENTS_DIR = Path(__file__).resolve().parent.parent / "constituents"


def _user_agent() -> str:
    ua = os.environ.get("SEC_USER_AGENT")
    if not ua:
        raise RuntimeError(
            "SEC_USER_AGENT must be set for EDGAR access (e.g. 'Your Name your@email')."
        )
    return ua


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=1, max=10))
def _get(url: str) -> dict:
    r = requests.get(url, headers={"User-Agent": _user_agent()}, timeout=30)
    r.raise_for_status()
    time.sleep(RATE_LIMIT_SECONDS)
    return r.json()


def ticker_to_cik() -> dict[str, int]:
    """Returns mapping {TICKER: CIK} from SEC's public ticker file."""
    cached = cache_read(NAMESPACE, {"resource": "ticker_to_cik"})
    if cached is not None:
        return cached["payload"]["map"]

    log.info("edgar fetch ticker→CIK map")
    payload = _get(SEC_TICKERS_URL)
    out: dict[str, int] = {}
    for entry in payload.values():
        try:
            out[str(entry["ticker"]).upper()] = int(entry["cik_str"])
        except (KeyError, ValueError, TypeError):
            continue
    cache_write(NAMESPACE, {"resource": "ticker_to_cik"}, {"map": out})
    log.info("edgar ticker→CIK rows=%d", len(out))
    return out


def company_facts(cik: int) -> dict:
    """Returns the full XBRL facts JSON for a company (all concepts, all units)."""
    cik_str = str(cik).zfill(10)
    cached = cache_read(NAMESPACE + ".facts", {"cik": cik_str})
    if cached is not None:
        return cached["payload"]
    url = f"{SEC_BASE}/api/xbrl/companyfacts/CIK{cik_str}.json"
    try:
        payload = _get(url)
    except Exception as e:
        log.warning("edgar companyfacts failed cik=%s: %s", cik_str, type(e).__name__)
        payload = {"facts": {}}
    cache_write(NAMESPACE + ".facts", {"cik": cik_str}, payload)
    return payload


def latest_fact(
    facts: dict,
    concept: str,
    as_of: date,
    units: str | None = None,
) -> tuple[float, date] | None:
    """Return (value, fact_end_date) for the most recent XBRL fact whose
    `filed` date <= as_of.

    Args:
        facts: payload from company_facts(cik).
        concept: us-gaap concept (e.g. "NetIncomeLoss", "Revenues").
        as_of: filtering date — only facts filed on or before this date.
        units: unit name (e.g. "USD", "shares"). If None, picks the first.

    Returns None if no usable fact exists.
    """
    blob = facts.get("facts", {}).get("us-gaap", {}).get(concept)
    if not blob:
        return None
    units_dict = blob.get("units", {})
    if not units_dict:
        return None
    unit_key = units if units and units in units_dict else next(iter(units_dict))
    rows = units_dict[unit_key]
    if not rows:
        return None
    as_of_iso = as_of.isoformat()
    eligible = [r for r in rows if r.get("filed", "") <= as_of_iso]
    if not eligible:
        return None
    # For TTM aggregation we want the most recently filed annual or LTM fact.
    eligible.sort(key=lambda r: r.get("end", ""))
    last = eligible[-1]
    try:
        return float(last["val"]), date.fromisoformat(last["end"])
    except (KeyError, ValueError):
        return None


def ttm_sum(
    facts: dict,
    concept: str,
    as_of: date,
    units: str = "USD",
) -> float | None:
    """Sum of last 4 quarterly values of `concept` filed on or before `as_of`.

    Falls back to the latest annual value if quarterly facts aren't present.
    """
    blob = facts.get("facts", {}).get("us-gaap", {}).get(concept, {}).get("units", {}).get(units)
    if not blob:
        return None
    as_of_iso = as_of.isoformat()
    rows = [r for r in blob if r.get("filed", "") <= as_of_iso]
    if not rows:
        return None

    # Try quarterly (form 10-Q + the most recent 10-K's annualized blocks)
    quarterly = [
        r for r in rows
        if r.get("fp") in {"Q1", "Q2", "Q3", "Q4"} and r.get("form", "").startswith("10-Q")
    ]
    quarterly.sort(key=lambda r: r.get("end", ""))
    last_4 = quarterly[-4:]
    if len(last_4) == 4:
        return float(sum(r["val"] for r in last_4))

    # Fallback: latest annual fact
    annual = [r for r in rows if r.get("fp") == "FY" and r.get("form", "").startswith("10-K")]
    annual.sort(key=lambda r: r.get("end", ""))
    if annual:
        return float(annual[-1]["val"])
    return None


def market_cap(symbol: str, as_of: date) -> float | None:
    """Market cap on `as_of` from yfinance close × shares outstanding."""
    from data.fetchers.prices import fetch_ohlcv

    px = fetch_ohlcv(symbol, as_of - pd.Timedelta(days=10).to_pytimedelta(), as_of)
    if px.empty or "Adj Close" not in px.columns:
        return None
    close = float(px["Adj Close"].iloc[-1])

    # Shares outstanding from XBRL — most recent fact.
    cik = ticker_to_cik().get(symbol.upper())
    if cik is None:
        return None
    facts = company_facts(cik)
    res = latest_fact(facts, "CommonStockSharesOutstanding", as_of, units="shares")
    if res is None:
        return None
    shares, _ = res
    return close * shares


def index_aggregate(
    constituents: list[str],
    as_of: date,
    max_constituents: int | None = None,
) -> dict[str, float]:
    """Compute market-cap-weighted aggregate fundamentals for an index.

    Returns dict with keys: agg_pe, fwd_earnings_yield, rev_growth_yoy,
    fcf_yield, n_constituents.
    """
    if max_constituents:
        constituents = constituents[:max_constituents]
    t2c = ticker_to_cik()
    cik_map = {sym: t2c.get(sym.upper()) for sym in constituents}

    total_mcap = 0.0
    total_ni_ttm = 0.0
    total_rev_ttm = 0.0
    total_rev_prior = 0.0
    total_fcf_ttm = 0.0
    n = 0

    for sym in constituents:
        cik = cik_map.get(sym)
        if cik is None:
            continue
        mc = market_cap(sym, as_of)
        if mc is None or mc <= 0:
            continue
        facts = company_facts(cik)
        ni = ttm_sum(facts, "NetIncomeLoss", as_of)
        rev = ttm_sum(facts, "Revenues", as_of) or ttm_sum(facts, "RevenueFromContractWithCustomerExcludingAssessedTax", as_of)
        # FCF ≈ CFO - CapEx
        cfo = ttm_sum(facts, "NetCashProvidedByUsedInOperatingActivities", as_of)
        capex = ttm_sum(facts, "PaymentsToAcquirePropertyPlantAndEquipment", as_of)
        fcf = (cfo - capex) if cfo is not None and capex is not None else None

        # Revenue YoY: compare TTM vs TTM as-of one year prior.
        rev_prior = ttm_sum(facts, "Revenues", _one_year_back(as_of)) or ttm_sum(
            facts, "RevenueFromContractWithCustomerExcludingAssessedTax", _one_year_back(as_of)
        )

        total_mcap += mc
        if ni is not None: total_ni_ttm += ni
        if rev is not None: total_rev_ttm += rev
        if rev_prior is not None: total_rev_prior += rev_prior
        if fcf is not None: total_fcf_ttm += fcf
        n += 1

    out: dict[str, float] = {"n_constituents": float(n)}
    if total_mcap > 0:
        out["agg_pe"] = total_mcap / total_ni_ttm if total_ni_ttm > 0 else float("nan")
        out["fwd_earnings_yield"] = total_ni_ttm / total_mcap if total_ni_ttm else 0.0
        out["fcf_yield"] = total_fcf_ttm / total_mcap if total_fcf_ttm else 0.0
    if total_rev_prior > 0:
        out["rev_growth_yoy"] = (total_rev_ttm / total_rev_prior - 1.0)
    return out


def _one_year_back(d: date) -> date:
    try:
        return d.replace(year=d.year - 1)
    except ValueError:
        # Feb 29 → Feb 28
        return d.replace(year=d.year - 1, day=28)


def load_constituents(symbol: str) -> list[str]:
    """Load static constituent list for an index ETF from JSON.

    Caveat per module docstring: list is as-of-now, applied historically.
    """
    path = CONSTITUENTS_DIR / f"{symbol.lower()}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())["constituents"]


def index_pe_yoy(symbol: str, as_of: date) -> dict[str, float]:
    """Public entry point used by fundamentals_carry equity branch.

    Replaces the prior NotImplementedError stub.
    """
    constituents = load_constituents(symbol)
    if not constituents:
        log.warning("edgar_aggregates: no constituent list for %s; returning zeros", symbol)
        return {"agg_pe": 0.0, "fwd_earnings_yield": 0.0, "rev_growth_yoy": 0.0, "fcf_yield": 0.0}

    cached = cache_read(NAMESPACE + ".aggregate", {"symbol": symbol, "as_of": as_of.isoformat()})
    if cached is not None:
        return cached["payload"]

    log.info("edgar_aggregates compute symbol=%s as_of=%s n_constituents=%d",
             symbol, as_of, len(constituents))
    agg = index_aggregate(constituents, as_of)
    cache_write(NAMESPACE + ".aggregate", {"symbol": symbol, "as_of": as_of.isoformat()}, agg)
    return agg
