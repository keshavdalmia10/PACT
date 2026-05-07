"""Statistical tests and additional robustness checks for the paper.

Produces:
- results/tables/sharpe_ttests.csv — Ledoit-Wolf robust Sharpe-ratio tests
  on key pairwise comparisons, with Benjamini-Hochberg-corrected
  q-values at FDR = 5%.
- results/tables/sharpe_bootstrap_ci.csv — block-bootstrap 95% CI for
  Sharpe of every Window B cell.
- results/tables/subperiod_stability.csv — Sharpe in each half of
  Window B (2022-H1+H2 vs 2023+2024) for stability check.
- results/tables/rolling_sharpe.csv — 6-month rolling Sharpe per cell
  (long-form).

All inputs read from saved cell artifacts (no LLM calls; idempotent).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from evaluation.metrics import sharpe
from evaluation.statistical_tests import benjamini_hochberg, ledoit_wolf_sharpe_test
from pact_logging import get_logger
from scripts._common import RAW_DIR, TABLES_DIR

log = get_logger(__name__)


def _load_returns(cell_id: str) -> pd.Series | None:
    p = RAW_DIR / cell_id / "returns.parquet"
    if not p.exists():
        return None
    return pd.read_parquet(p)["returns"]


def _benchmark_returns(start: date, end: date) -> dict[str, pd.Series]:
    """Compute benchmark return series matching results/tables/benchmarks.csv."""
    from data.fetchers.prices import fetch_panel

    px = fetch_panel(
        ["SPY", "QQQ", "IWM", "IEF", "SHY", "GLD", "USO", "UUP", "EEM", "BTC"],
        start, end, field="Adj Close",
    )
    rets = px.pct_change().fillna(0.0)
    out = {
        "spy_bh": rets["SPY"],
        "equal_weight_bh": rets.mean(axis=1),
        "60_40_spy_ief": 0.6 * rets["SPY"] + 0.4 * rets["IEF"],
    }
    # Inverse-vol weighted
    vol = rets.rolling(63).std() * np.sqrt(252)
    inv = 1.0 / vol
    w = inv.div(inv.sum(axis=1), axis=0).ffill().fillna(0.1)
    out["inverse_vol_weighted"] = (w.shift(1).fillna(0.1) * rets).sum(axis=1)
    return out


def pairwise_sharpe_tests() -> pd.DataFrame:
    """Ledoit-Wolf robust Sharpe-ratio tests with BH correction."""
    cells = {}
    for sub in sorted(RAW_DIR.iterdir()):
        meta_p = sub / "metadata.json"
        if not meta_p.exists():
            continue
        meta = json.loads(meta_p.read_text())
        if meta.get("window") != "b":
            continue
        rets = _load_returns(sub.name)
        if rets is None or len(rets) < 30:
            continue
        cells[sub.name] = rets

    bench = _benchmark_returns(date(2022, 1, 1), date(2024, 12, 31))

    pairs = [
        # H1: coordination > parallelism in frontier?
        ("b__frontier__sequential_pipeline", "b__frontier__independent_ensemble", "H1: seq_pipeline frontier vs ensemble frontier"),
        ("b__frontier__hierarchical", "b__frontier__independent_ensemble", "H1: hierarchical frontier vs ensemble frontier"),
        ("b__frontier__debate", "b__frontier__independent_ensemble", "H1: debate frontier vs ensemble frontier"),
        # Does adding LLM help?
        ("b__frontier__independent_ensemble", "b__none__independent_ensemble", "LLM-effect on ensemble (frontier vs none)"),
        ("b__frontier__sequential_pipeline", "b__none__sequential_pipeline", "LLM-effect on seq_pipeline"),
        ("b__frontier__debate", "b__none__debate", "LLM-effect on debate"),
        # Best matrix cell vs passive benchmarks
        ("b__none__debate", "spy_bh", "best matrix (none debate) vs SPY BAH"),
        ("b__frontier__independent_ensemble", "spy_bh", "best frontier (ensemble) vs SPY BAH"),
        ("b__none__debate", "inverse_vol_weighted", "best matrix vs inverse-vol"),
        ("b__frontier__independent_ensemble", "inverse_vol_weighted", "best frontier vs inverse-vol"),
        # Alt-data: attention adds value?
        ("altdata_plus_attention__b__frontier__sequential_pipeline",
         "altdata_text_only__b__frontier__sequential_pipeline",
         "+attention vs text_only (seq_pipeline frontier)"),
        ("altdata_full__b__frontier__sequential_pipeline",
         "altdata_text_only__b__frontier__sequential_pipeline",
         "+full vs text_only (seq_pipeline frontier)"),
    ]

    rows = []
    for a, b, label in pairs:
        ra = cells[a] if a in cells else bench.get(a)
        rb = cells[b] if b in cells else bench.get(b)
        if ra is None or rb is None:
            log.warning("missing cell for pair %s", label)
            continue
        ra, rb = ra.align(rb, join="inner")
        if len(ra) < 60:
            log.warning("too few obs for pair %s: %d", label, len(ra))
            continue
        result = ledoit_wolf_sharpe_test(ra, rb)
        rows.append({
            "comparison": label,
            "a": a,
            "b": b,
            "n_obs": len(ra),
            "sharpe_a": sharpe(ra),
            "sharpe_b": sharpe(rb),
            "sr_diff": result["sr_diff"],
            "z_stat": result["z"],
            "p_value": result["p_value"],
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    rejects = benjamini_hochberg(df["p_value"].tolist(), fdr=0.05)
    df["reject_h0_at_fdr_5pct"] = rejects
    # BH q-value approximation: rank-based
    sorted_p = df["p_value"].sort_values()
    m = len(sorted_p)
    qvals = (sorted_p * m / np.arange(1, m + 1)).cummin()
    df["q_value"] = df["p_value"].map(dict(zip(sorted_p.values, qvals.values)))
    return df.sort_values("p_value").reset_index(drop=True)


def block_bootstrap_sharpe_ci(returns: pd.Series, n_boot: int = 2000, block_size: int = 21, seed: int = 42) -> tuple[float, float, float]:
    """Stationary block bootstrap (Politis-Romano 1994) for Sharpe CI."""
    rng = np.random.default_rng(seed)
    r = returns.dropna().values
    n = len(r)
    if n < block_size * 2:
        return float("nan"), float("nan"), float("nan")
    boots = []
    for _ in range(n_boot):
        sample = []
        while len(sample) < n:
            start = rng.integers(0, n)
            blk_len = max(1, int(rng.geometric(1.0 / block_size)))
            end = min(start + blk_len, n)
            sample.extend(r[start:end].tolist())
        s = np.array(sample[:n])
        if s.std() > 0:
            boots.append(s.mean() / s.std() * np.sqrt(252))
    if not boots:
        return float("nan"), float("nan"), float("nan")
    arr = np.array(boots)
    return float(np.percentile(arr, 2.5)), float(np.median(arr)), float(np.percentile(arr, 97.5))


def bootstrap_table() -> pd.DataFrame:
    rows = []
    for sub in sorted(RAW_DIR.iterdir()):
        if not (sub / "metadata.json").exists():
            continue
        meta = json.loads((sub / "metadata.json").read_text())
        if meta.get("window") != "b" or sub.name.startswith("altdata_") or sub.name.startswith("attr_"):
            continue
        rets = _load_returns(sub.name)
        if rets is None or len(rets) < 100:
            continue
        lo, med, hi = block_bootstrap_sharpe_ci(rets)
        rows.append({
            "cell_id": sub.name,
            "protocol": meta.get("protocol"),
            "regime": meta.get("regime"),
            "sharpe": sharpe(rets),
            "ci_lo_2_5pct": lo,
            "ci_median": med,
            "ci_hi_97_5pct": hi,
        })
    return pd.DataFrame(rows)


def subperiod_stability() -> pd.DataFrame:
    """Split Window B at midpoint; report Sharpe in each half + stability ratio."""
    rows = []
    for sub in sorted(RAW_DIR.iterdir()):
        if not (sub / "metadata.json").exists():
            continue
        meta = json.loads((sub / "metadata.json").read_text())
        if meta.get("window") != "b" or sub.name.startswith("altdata_") or sub.name.startswith("attr_"):
            continue
        rets = _load_returns(sub.name)
        if rets is None or len(rets) < 200:
            continue
        midpoint = len(rets) // 2
        h1 = rets.iloc[:midpoint]
        h2 = rets.iloc[midpoint:]
        sr_full = sharpe(rets)
        sr_h1 = sharpe(h1)
        sr_h2 = sharpe(h2)
        rows.append({
            "cell_id": sub.name,
            "protocol": meta.get("protocol"),
            "regime": meta.get("regime"),
            "sharpe_full": sr_full,
            "sharpe_h1_2022": sr_h1,
            "sharpe_h2_2023_2024": sr_h2,
            "abs_diff": abs(sr_h1 - sr_h2),
        })
    return pd.DataFrame(rows)


def rolling_sharpe_table(window_days: int = 126) -> pd.DataFrame:
    """6-month rolling Sharpe per cell, long-form."""
    rows = []
    for sub in sorted(RAW_DIR.iterdir()):
        if not (sub / "metadata.json").exists():
            continue
        meta = json.loads((sub / "metadata.json").read_text())
        if meta.get("window") != "b" or sub.name.startswith("altdata_") or sub.name.startswith("attr_"):
            continue
        rets = _load_returns(sub.name)
        if rets is None or len(rets) < window_days:
            continue
        roll = rets.rolling(window_days).apply(
            lambda x: x.mean() / x.std() * np.sqrt(252) if x.std() > 0 else float("nan"),
            raw=False,
        )
        for d, v in roll.dropna().items():
            rows.append({
                "cell_id": sub.name,
                "protocol": meta.get("protocol"),
                "regime": meta.get("regime"),
                "date": d.isoformat() if hasattr(d, 'isoformat') else str(d),
                "rolling_sharpe": float(v),
            })
    return pd.DataFrame(rows)


def main() -> None:
    log.info("running pairwise Sharpe tests")
    pairs = pairwise_sharpe_tests()
    pairs.to_csv(TABLES_DIR / "sharpe_ttests.csv", index=False)
    print("=== Pairwise Sharpe tests (Ledoit-Wolf, HAC-adjusted) ===")
    print(pairs[["comparison", "sharpe_a", "sharpe_b", "sr_diff", "z_stat", "p_value", "q_value", "reject_h0_at_fdr_5pct"]].round(4).to_string(index=False))
    print()

    log.info("computing block-bootstrap Sharpe CIs (n_boot=2000, block=21)")
    boot = bootstrap_table()
    boot.to_csv(TABLES_DIR / "sharpe_bootstrap_ci.csv", index=False)
    print("=== Block-bootstrap 95% CI for Sharpe (matrix cells) ===")
    print(boot.round(4).to_string(index=False))
    print()

    log.info("computing subperiod stability")
    sub = subperiod_stability()
    sub.to_csv(TABLES_DIR / "subperiod_stability.csv", index=False)
    print("=== Sub-period stability (Window B halves) ===")
    print(sub.round(4).to_string(index=False))

    log.info("computing rolling Sharpe (126d window)")
    roll = rolling_sharpe_table()
    roll.to_csv(TABLES_DIR / "rolling_sharpe.csv", index=False)
    print(f"\nrolling sharpe rows: {len(roll)}")


if __name__ == "__main__":
    main()
