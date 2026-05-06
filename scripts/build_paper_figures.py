"""Driver: turn raw cells into paper-ready figures (spec §11 results section).

Reads `results/raw/<cell_id>/` artifacts and writes PNGs to
`results/figures/`. Figures produced:

- `headline_sharpe_grid.png` — protocol × regime Sharpe heatmap
- `equity_curves__<protocol>.png` — per-protocol equity curves across regimes
- `tc_sensitivity.png` — Sharpe vs transaction-cost from robustness_tc.csv
- `attribution_bars__<cell>.png` — per-agent LOO Sharpe deltas (when LOO data exists)

Usage:
  python scripts/build_paper_figures.py
  python scripts/build_paper_figures.py --window b
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pact_logging import get_logger
from scripts._common import FIGURES_DIR, RAW_DIR, TABLES_DIR, load_backtest_result

log = get_logger(__name__)

plt.rcParams.update({
    "figure.dpi": 110,
    "savefig.dpi": 200,
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def _iter_cells(window_filter: str | None):
    for sub in sorted(RAW_DIR.iterdir()):
        if not (sub.is_dir() and (sub / "metadata.json").exists()):
            continue
        meta = json.loads((sub / "metadata.json").read_text())
        if window_filter and meta.get("window") != window_filter:
            continue
        yield sub, meta


def figure_sharpe_grid(window: str | None) -> Path | None:
    rows: list[dict] = []
    for sub, meta in _iter_cells(window):
        loaded = load_backtest_result(sub)
        rets = loaded["returns"]
        sr = float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() else float("nan")
        rows.append({
            "protocol": meta.get("protocol"),
            "regime": meta.get("regime"),
            "sharpe": sr,
        })
    if not rows:
        return None
    df = pd.DataFrame(rows)
    if df.empty:
        return None
    pivot = df.pivot_table(index="protocol", columns="regime", values="sharpe", aggfunc="first")

    fig, ax = plt.subplots(figsize=(7, 4.5))
    im = ax.imshow(pivot.values, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.values[i, j]
            ax.text(j, i, f"{v:.2f}" if pd.notna(v) else "—",
                    ha="center", va="center",
                    color="white" if pd.notna(v) and abs(v) > 0.4 else "black",
                    fontsize=9)
    ax.set_title(f"Sharpe by protocol × regime (window={window or 'all'})")
    fig.colorbar(im, ax=ax, label="Sharpe")
    out = FIGURES_DIR / "headline_sharpe_grid.png"
    fig.tight_layout(); fig.savefig(out); plt.close(fig)
    log.info("figure: %s", out)
    return out


def figure_equity_curves(window: str | None) -> list[Path]:
    by_protocol: dict[str, list[tuple[str, pd.Series]]] = {}
    for sub, meta in _iter_cells(window):
        proto = meta.get("protocol")
        regime = meta.get("regime")
        loaded = load_backtest_result(sub)
        if proto and regime and len(loaded["equity"]):
            by_protocol.setdefault(proto, []).append((regime, loaded["equity"]))

    out_paths: list[Path] = []
    for proto, regimes in by_protocol.items():
        fig, ax = plt.subplots(figsize=(8, 4))
        for regime, eq in regimes:
            ax.plot(eq.index, eq.values / float(eq.iloc[0]), label=regime, linewidth=1.5)
        ax.axhline(1.0, color="gray", linewidth=0.5, alpha=0.5)
        ax.set_title(f"{proto} — equity curve (window={window or 'all'})")
        ax.set_ylabel("equity (normalized)")
        ax.legend()
        out = FIGURES_DIR / f"equity_curves__{proto}.png"
        fig.tight_layout(); fig.savefig(out); plt.close(fig)
        out_paths.append(out)
        log.info("figure: %s", out)
    return out_paths


def figure_tc_sensitivity(window: str | None) -> Path | None:
    src = TABLES_DIR / "robustness_tc.csv"
    if not src.exists():
        return None
    df = pd.read_csv(src)
    if window:
        df = df[df["window"] == window]
    if df.empty:
        return None
    df["label"] = df["regime"].astype(str) + " / " + df["protocol"].astype(str)
    fig, ax = plt.subplots(figsize=(8, 5.5))
    for label, sub in df.groupby("label"):
        sub = sub.sort_values("tc_bps")
        ax.plot(sub["tc_bps"], sub["sharpe"], marker="o", linewidth=1.2, markersize=4, label=label, alpha=0.85)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_xlabel("Transaction cost (bps round-trip)")
    ax.set_ylabel("Sharpe")
    ax.set_title(f"Cost sensitivity (window={window or 'all'})")
    ax.legend(fontsize=7, ncol=2, loc="upper right")
    out = FIGURES_DIR / "tc_sensitivity.png"
    fig.tight_layout(); fig.savefig(out); plt.close(fig)
    log.info("figure: %s", out)
    return out


def figure_attribution_bars() -> Path | None:
    src = TABLES_DIR / "attribution_loo.csv"
    if not src.exists():
        return None
    df = pd.read_csv(src)
    if df.empty:
        return None
    fig, ax = plt.subplots(figsize=(9, max(3, len(df.cell_id.unique()) * 1.5)))
    cells = df["cell_id"].unique()
    width = 0.8 / max(len(cells), 1)
    agents = df["dropped_agent"].unique()
    x = np.arange(len(agents))
    for i, cell in enumerate(cells):
        sub = df[df["cell_id"] == cell].set_index("dropped_agent").reindex(agents)
        ax.bar(x + i * width, sub["sharpe_delta"], width, label=cell.split("__")[-1])
    ax.set_xticks(x + width * (len(cells) - 1) / 2)
    ax.set_xticklabels(agents, rotation=30, ha="right")
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_ylabel("Sharpe(full) − Sharpe(without agent)")
    ax.set_title("Per-agent leave-one-out attribution")
    ax.legend(fontsize=8)
    out = FIGURES_DIR / "attribution_bars.png"
    fig.tight_layout(); fig.savefig(out); plt.close(fig)
    log.info("figure: %s", out)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Generate paper figures from saved cells.")
    p.add_argument("--window", default=None, help="filter to one window key (a, b, quick)")
    args = p.parse_args()

    written = []
    out = figure_sharpe_grid(args.window)
    if out: written.append(out)
    written.extend(figure_equity_curves(args.window))
    out = figure_tc_sensitivity(args.window)
    if out: written.append(out)
    out = figure_attribution_bars()
    if out: written.append(out)

    print("Wrote figures:")
    for p in written:
        print(f"  {p}")
    if not written:
        print("(no figures — did you run scripts/run_ablation_matrix.py and run_robustness.py?)")


if __name__ == "__main__":
    main()
