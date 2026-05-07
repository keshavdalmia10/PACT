"""Pre-warm the constituent-price cache for EDGAR XBRL aggregation.

The matrix sweep's `fundamentals_carry` agent calls into
`edgar_aggregates.market_cap()` for ~110 constituents (SPY 50 + QQQ 30 +
EEM 30) on every rebalance, which triggers a yfinance call per constituent
the first time. Yahoo Finance rate-limits aggressive bursts and leaks
connections, hanging the process.

This script does the same fetches up front, sequentially, with a
`sleep(0.5)` between each — friendly enough that Yahoo doesn't rate-limit.
After it runs, the matrix sweep hits the local prices cache for every
constituent and never touches yfinance during the live run.

Usage:
    python scripts/prefetch_constituents.py --window b
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from data.fetchers.prices import fetch_ohlcv
from pact_logging import get_logger
from scripts._common import load_config

log = get_logger(__name__)

CONSTITUENTS_DIR = Path(__file__).resolve().parent.parent / "data" / "constituents"


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _load_all_constituents() -> set[str]:
    seen: set[str] = set()
    for fp in CONSTITUENTS_DIR.glob("*.json"):
        try:
            data = json.loads(fp.read_text())
        except Exception:
            continue
        for tkr in data.get("constituents", []):
            seen.add(str(tkr).upper())
    return seen


def main() -> None:
    p = argparse.ArgumentParser(description="Pre-fetch constituent prices into the local cache.")
    p.add_argument("--window", choices=["a", "b"], default="b")
    p.add_argument("--sleep-seconds", type=float, default=0.5,
                   help="seconds between yfinance calls (default 0.5)")
    p.add_argument("--padding-days", type=int, default=15,
                   help="days of lookback before window start (must match market_cap's offset)")
    args = p.parse_args()

    cfg = load_config("ablation_matrix.yaml")
    block = cfg[f"window_{args.window}"]
    start = _parse_date(block["start"]) - timedelta(days=args.padding_days)
    end = _parse_date(block["end"])

    tickers = sorted(_load_all_constituents())
    log.info("prefetch_constituents start=%s end=%s n_tickers=%d", start, end, len(tickers))

    failed: list[str] = []
    for i, sym in enumerate(tickers, 1):
        try:
            df = fetch_ohlcv(sym, start, end)
            log.info("[%3d/%d] %-6s rows=%d", i, len(tickers), sym, len(df))
        except Exception as e:
            log.warning("[%3d/%d] %-6s FAILED %s: %s", i, len(tickers), sym, type(e).__name__, e)
            failed.append(sym)
        time.sleep(args.sleep_seconds)

    log.info("prefetch done. fetched=%d, failed=%d", len(tickers) - len(failed), len(failed))
    if failed:
        log.warning("failed tickers (will fall back during sweep): %s", failed)
    print(f"prefetch complete: {len(tickers) - len(failed)}/{len(tickers)} tickers cached.")
    if failed:
        print(f"failed: {failed}")


if __name__ == "__main__":
    main()
