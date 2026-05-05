"""Driver: robustness checks on saved ablation cells (spec §6.8, §6.9, §6.10).

For each saved cell in `results/raw/`, no re-run required:
- **Transaction-cost sensitivity**: net-of-cost Sharpe at TC ∈ {5, 10, 30, 50, 100, 200} bps,
  using saved gross-of-cost daily returns + turnover series. Reveals how much
  of a protocol's reported Sharpe survives realistic costs.
- **NBER stratification**: recession vs expansion sub-period summary stats.
- **VIX-quartile stratification**: only computed when there's overlap with
  yfinance VIX history; one row per quartile.

Outputs:
  results/tables/robustness_tc.csv
  results/tables/regime_nber.csv
  results/tables/regime_vix.csv

Usage:
  python scripts/run_robustness.py                       # all cells in results/raw/
  python scripts/run_robustness.py --cell <cell_id>      # single cell
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from evaluation.metrics import sharpe, sortino, max_drawdown, turnover_metric
from evaluation.regime_stratification import stratify_nber, stratify_by_vix
from pact_logging import get_logger
from scripts._common import RAW_DIR, TABLES_DIR, load_backtest_result

log = get_logger(__name__)

TC_GRID_BPS = [5, 10, 30, 50, 100, 200]


def _iter_cells(filter_id: str | None):
    for sub in sorted(RAW_DIR.iterdir()):
        if not (sub.is_dir() and (sub / "metadata.json").exists()):
            continue
        if filter_id and sub.name != filter_id:
            continue
        yield sub


def tc_sensitivity_row(cell_dir: Path) -> list[dict]:
    """Sharpe / ann_return / MDD at each TC bps in TC_GRID_BPS."""
    meta = json.loads((cell_dir / "metadata.json").read_text())
    loaded = load_backtest_result(cell_dir)
    ret_net_at_30 = loaded["returns"]
    turnover = loaded["turnover"]
    base_tc = float(meta.get("transaction_cost_bps_roundtrip", 30.0))

    # Reverse out the original cost to recover gross returns:
    # net = gross - turnover * (base_tc / 1e4)  ->  gross = net + turnover * (base_tc / 1e4)
    cost_at_base = turnover.reindex(ret_net_at_30.index).fillna(0.0) * (base_tc / 10_000)
    gross = ret_net_at_30 + cost_at_base

    rows = []
    for tc in TC_GRID_BPS:
        cost = turnover.reindex(gross.index).fillna(0.0) * (tc / 10_000)
        net = gross - cost
        eq = (1 + net).cumprod()
        rows.append({
            "cell_id": meta["cell_id"],
            "window": meta.get("window"),
            "regime": meta.get("regime"),
            "protocol": meta.get("protocol"),
            "tc_bps": tc,
            "sharpe": sharpe(net),
            "sortino": sortino(net),
            "max_drawdown": max_drawdown(eq),
            "ann_return": float((1 + net.mean()) ** 252 - 1) if len(net) else float("nan"),
            "ann_vol": float(net.std() * (252 ** 0.5)) if len(net) else float("nan"),
        })
    return rows


def nber_row(cell_dir: Path) -> list[dict]:
    meta = json.loads((cell_dir / "metadata.json").read_text())
    loaded = load_backtest_result(cell_dir)
    s = stratify_nber(loaded["returns"], loaded["equity"], loaded["turnover"])
    rows = []
    for regime_label, stats in s.items():
        rows.append({
            "cell_id": meta["cell_id"],
            "window": meta.get("window"),
            "regime": meta.get("regime"),
            "protocol": meta.get("protocol"),
            "stratum": regime_label,
            **{k: _safe_float(v) for k, v in stats.items()},
        })
    return rows


def vix_rows(cell_dir: Path) -> list[dict]:
    meta = json.loads((cell_dir / "metadata.json").read_text())
    loaded = load_backtest_result(cell_dir)
    try:
        s = stratify_by_vix(loaded["returns"], loaded["equity"], loaded["turnover"])
    except Exception as e:
        log.warning("vix stratification failed for %s: %s", meta["cell_id"], e)
        return []
    rows = []
    for q, stats in s.items():
        rows.append({
            "cell_id": meta["cell_id"],
            "window": meta.get("window"),
            "regime": meta.get("regime"),
            "protocol": meta.get("protocol"),
            "stratum": q,
            **{k: _safe_float(v) for k, v in stats.items()},
        })
    return rows


def _safe_float(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def main() -> None:
    p = argparse.ArgumentParser(description="Run robustness checks across saved ablation cells.")
    p.add_argument("--cell", default=None, help="single cell id (defaults to all)")
    p.add_argument("--skip-vix", action="store_true", help="skip VIX-quartile stratification (avoids yfinance hit)")
    args = p.parse_args()

    tc_rows: list[dict] = []
    nber_rows_all: list[dict] = []
    vix_rows_all: list[dict] = []

    cells = list(_iter_cells(args.cell))
    if not cells:
        print("no matching cells in results/raw/. did you run scripts/run_ablation_matrix.py?")
        return

    for cell in cells:
        log.info("robustness cell=%s", cell.name)
        try:
            tc_rows.extend(tc_sensitivity_row(cell))
            nber_rows_all.extend(nber_row(cell))
            if not args.skip_vix:
                vix_rows_all.extend(vix_rows(cell))
        except Exception as e:
            log.exception("cell %s failed: %s", cell.name, e)

    tc_df = pd.DataFrame(tc_rows)
    nber_df = pd.DataFrame(nber_rows_all)
    vix_df = pd.DataFrame(vix_rows_all)

    tc_path = TABLES_DIR / "robustness_tc.csv"
    nber_path = TABLES_DIR / "regime_nber.csv"
    vix_path = TABLES_DIR / "regime_vix.csv"

    tc_df.to_csv(tc_path, index=False)
    nber_df.to_csv(nber_path, index=False)
    if not vix_df.empty:
        vix_df.to_csv(vix_path, index=False)

    log.info("wrote %s rows=%d", tc_path, len(tc_df))
    log.info("wrote %s rows=%d", nber_path, len(nber_df))
    if not vix_df.empty:
        log.info("wrote %s rows=%d", vix_path, len(vix_df))

    print("=== TC sensitivity ===")
    if not tc_df.empty:
        print(tc_df.pivot_table(index=["cell_id"], columns="tc_bps", values="sharpe").round(4).to_string())
    print()
    print("=== NBER stratification ===")
    if not nber_df.empty:
        print(nber_df[["cell_id", "stratum", "sharpe", "max_drawdown", "annualized_return"]].to_string(index=False))
    if not vix_df.empty:
        print()
        print("=== VIX quartile stratification ===")
        print(vix_df[["cell_id", "stratum", "sharpe", "annualized_return"]].to_string(index=False))


if __name__ == "__main__":
    main()
