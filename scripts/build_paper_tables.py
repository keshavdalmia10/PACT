"""Driver: turn raw ablation cells into paper-ready tables (spec §6.10).

Reads `results/raw/<cell_id>/` directories produced by `run_ablation_matrix.py`
and emits:

- `results/tables/headline_metrics.csv` — Sharpe / Sortino / MDD / vol / turnover
  per (window, regime, protocol)
- `results/tables/headline_metrics.md` — same in markdown for the paper
- `results/tables/cbs_vs_ensemble.csv` — Coordination Breakeven Spread of every
  coordinated cell vs the matching `independent_ensemble` baseline (per regime
  / window). NaN if no ensemble baseline exists for that regime+window.

Usage:
    python scripts/build_paper_tables.py
    python scripts/build_paper_tables.py --window a --regime open_source
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from evaluation.metrics import (
    coordination_breakeven_spread,
    max_drawdown,
    sharpe,
    sortino,
    turnover_metric,
)
from pact_logging import get_logger
from scripts._common import RAW_DIR, TABLES_DIR, load_backtest_result

log = get_logger(__name__)


def _iter_cells(raw_dir: Path):
    for sub in sorted(raw_dir.iterdir()):
        if sub.is_dir() and (sub / "metadata.json").exists():
            yield sub


def collect_cells(window_filter: str | None, regime_filter: str | None) -> pd.DataFrame:
    """Return a long-form metrics frame across all matching raw cells."""
    rows = []
    for cell in _iter_cells(RAW_DIR):
        meta = json.loads((cell / "metadata.json").read_text())
        if window_filter and meta.get("window") != window_filter:
            continue
        if regime_filter and meta.get("regime") != regime_filter:
            continue
        loaded = load_backtest_result(cell)
        eq, ret, to = loaded["equity"], loaded["returns"], loaded["turnover"]
        rows.append(
            {
                "cell_id": meta["cell_id"],
                "window": meta.get("window"),
                "regime": meta.get("regime"),
                "protocol": meta.get("protocol"),
                "start": meta.get("start"),
                "end": meta.get("end"),
                "n_obs": int(len(ret.dropna())),
                "rebalances": meta.get("rebalances"),
                "sharpe": sharpe(ret),
                "sortino": sortino(ret),
                "max_drawdown": max_drawdown(eq),
                "ann_return": float((1 + ret.mean()) ** 252 - 1) if len(ret) else float("nan"),
                "ann_vol": float(ret.std() * (252 ** 0.5)) if len(ret) else float("nan"),
                "avg_turnover_per_rebal": turnover_metric(to),
                "final_equity": float(eq.iloc[-1]) if len(eq) else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def compute_cbs_table(metrics: pd.DataFrame) -> pd.DataFrame:
    """For each coordinated cell, compute its CBS vs the matching ensemble baseline."""
    out = []
    keyed = {(r.window, r.regime, r.protocol): r for r in metrics.itertuples(index=False)}
    for (window, regime, protocol), row in keyed.items():
        if protocol == "independent_ensemble":
            continue
        baseline_key = (window, regime, "independent_ensemble")
        if baseline_key not in keyed:
            out.append(
                {
                    "window": window, "regime": regime, "protocol": protocol,
                    "cbs_bps": float("nan"),
                    "note": "no ensemble baseline in this (window, regime)",
                }
            )
            continue
        c_cell = load_backtest_result(RAW_DIR / row.cell_id)
        e_cell = load_backtest_result(RAW_DIR / keyed[baseline_key].cell_id)
        cbs = coordination_breakeven_spread(
            returns_coord=c_cell["returns"],
            returns_ensemble=e_cell["returns"],
            turnover_coord=c_cell["turnover"],
            turnover_ensemble=e_cell["turnover"],
        )
        out.append({"window": window, "regime": regime, "protocol": protocol, "cbs_bps": cbs, "note": ""})
    return pd.DataFrame(out)


def write_markdown(metrics: pd.DataFrame, path: Path) -> None:
    if metrics.empty:
        path.write_text("_no cells found_\n")
        return
    pivot_cols = ["sharpe", "sortino", "max_drawdown", "ann_return", "ann_vol", "avg_turnover_per_rebal"]
    fmt = metrics[["window", "regime", "protocol", *pivot_cols, "rebalances", "n_obs"]].copy()
    for c in pivot_cols:
        fmt[c] = fmt[c].map(lambda x: f"{x:.4f}" if pd.notna(x) else "—")
    path.write_text("# Headline metrics (auto-generated)\n\n" + fmt.to_markdown(index=False) + "\n")


def main() -> None:
    p = argparse.ArgumentParser(description="Build paper-ready summary tables from raw cells.")
    p.add_argument("--window", default=None, help="filter to one window key (a, b, quick)")
    p.add_argument("--regime", default=None, help="filter to one regime")
    args = p.parse_args()

    metrics = collect_cells(args.window, args.regime)
    if metrics.empty:
        log.warning("no cells matched filter; nothing to write")
        print("no cells matched. did you run scripts/run_ablation_matrix.py?")
        return

    metrics_path = TABLES_DIR / "headline_metrics.csv"
    metrics.to_csv(metrics_path, index=False)
    log.info("wrote %s rows=%d", metrics_path, len(metrics))

    md_path = TABLES_DIR / "headline_metrics.md"
    write_markdown(metrics, md_path)
    log.info("wrote %s", md_path)

    cbs = compute_cbs_table(metrics)
    cbs_path = TABLES_DIR / "cbs_vs_ensemble.csv"
    cbs.to_csv(cbs_path, index=False)
    log.info("wrote %s rows=%d", cbs_path, len(cbs))

    print(metrics.to_string(index=False))
    print()
    print("CBS vs ensemble:")
    print(cbs.to_string(index=False))


if __name__ == "__main__":
    main()
