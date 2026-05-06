"""EDGAR equity-index P/E aggregation (spec §4.5 fundamentals_carry equity branch).

NOT IMPLEMENTED. This module documents the design for future work. The
current `fundamentals_carry` agent leaves equity-index P/E factors at 0
because of the work required here:

For each equity index in our universe (SPY, QQQ, IWM, EEM):
1. Resolve constituents at each rebalance date (S&P 500, Nasdaq-100,
   Russell 2000, MSCI EM). S&P / Nasdaq are well-documented; Russell 2000
   has 2000 names and rebalances annually; MSCI EM is licensed.
2. For each constituent CIK: fetch the most recent 10-Q / 10-K via EDGAR,
   parse XBRL facts for net income, revenue, FCF, shares outstanding,
   guidance text.
3. Aggregate constituent metrics into index-level: market-cap-weighted P/E,
   FCF yield, revenue growth.
4. Apply spec §7 acceptance-datetime cutoff (filings after 17:30 ET attribute
   to next session's open).

Effort estimate: ~4-8 hours of careful XBRL parsing + constituent-list
maintenance. The XBRL part is the heavy lift — `python-xbrl` and similar
libraries exist but are brittle. A simpler stand-in: scrape iShares
fund-fact-sheet aggregates (P/E, dividend yield, etc.) for SPY/QQQ/IWM/EEM
on a monthly cadence, accept the look-ahead introduced by fund-sponsor
publishing lag (~5 trading days).

Replacement when implemented:

    from data.fetchers.edgar_aggregates import index_pe_yoy
    pe = index_pe_yoy("SPY", as_of)  # → {"agg_pe": 22.4, "fwd_earnings_yield": 0.045, ...}
"""

from __future__ import annotations

from datetime import date


def index_pe_yoy(symbol: str, as_of: date) -> dict[str, float]:
    """Aggregated equity-index fundamentals — NOT IMPLEMENTED.

    Returns zero-values so callers can keep the schema visible. Replace
    this stub with a real EDGAR + XBRL aggregator before the equity-index
    branch of fundamentals_carry produces non-zero output.
    """
    raise NotImplementedError(
        "EDGAR equity-index P/E aggregation is documented in this module "
        "but not implemented. Equity-branch factors in fundamentals_carry "
        "stay at 0.0 until a constituent-level aggregator is wired."
    )
