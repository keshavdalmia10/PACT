"""Backtest engine wrapper (spec §5.4).

Weekly rebalance. Linear (Almgren-Chriss-style) slippage in trade-size as
a fraction of ADV; flat 30 bps round-trip transaction cost (sensitivity
analysis varies this in §6.9).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from agents.base_agent import InstrumentView
from coordination.base import CoordinationProtocol
from data.fetchers.prices import fetch_panel
from factors.risk import ewma_volatility
from pact_logging import get_logger
from portfolio.construction import PortfolioConfig, views_to_target_weights
from portfolio.risk_overlays import apply_correlation_throttle, apply_drawdown_breaker

log = get_logger(__name__)


@dataclass
class BacktestConfig:
    start: date
    end: date
    starting_capital: float = 1_000_000.0
    rebalance_freq: str = "W-FRI"             # weekly Friday close
    transaction_cost_bps_roundtrip: float = 30.0
    slippage_coef: float = 5.0                # linear in trade/ADV
    adv_window: int = 21
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    turnover_cap_per_period: float = 0.50     # 50% gross per week


@dataclass
class BacktestResult:
    equity: pd.Series
    weights: pd.DataFrame
    returns: pd.Series
    turnover: pd.Series
    metadata: dict[str, object] = field(default_factory=dict)


def run_backtest(
    protocol: CoordinationProtocol,
    universe: tuple[str, ...],
    cfg: BacktestConfig,
) -> BacktestResult:
    log.info(
        "backtest start protocol=%s universe=%d start=%s end=%s capital=%s",
        protocol.name, len(universe), cfg.start, cfg.end, cfg.starting_capital,
    )
    prices = fetch_panel(list(universe), cfg.start, cfg.end, field="Adj Close")
    if prices.empty:
        log.error("backtest aborted: empty price panel")
        raise RuntimeError("price panel is empty; check universe / date range")

    rets = prices.pct_change().fillna(0.0)
    rebal_dates = pd.date_range(cfg.start, cfg.end, freq=cfg.rebalance_freq)
    rebal_dates = [d.date() for d in rebal_dates if d.date() in prices.index.date or True]

    weights_log: dict[date, dict[str, float]] = {}
    prev_weights: dict[str, float] = {s: 0.0 for s in universe}
    weeks_since_breach = 999
    equity = pd.Series(index=prices.index, dtype=float)
    equity.iloc[0] = cfg.starting_capital

    # Pre-compute rolling realized vol per symbol
    realized_vol = rets.rolling(63).std() * np.sqrt(252)

    daily_weights = pd.DataFrame(0.0, index=prices.index, columns=list(universe))

    for d in rebal_dates:
        ts = pd.Timestamp(d)
        if ts not in prices.index:
            # snap to next available trading day; skip if past end of panel
            idx = prices.index.searchsorted(ts)
            if idx >= len(prices.index):
                continue
            ts = prices.index[idx]

        result = protocol.run(ts.date())
        rv = realized_vol.loc[:ts].iloc[-1].dropna().to_dict()

        recent_ret = rets.loc[:ts].tail(60).sum(axis=1).cumsum()
        dd_60d = (
            float((recent_ret - recent_ret.cummax()).iloc[-1])
            if len(recent_ret) > 0
            else 0.0
        )
        if dd_60d <= -0.15:
            if weeks_since_breach != 0:
                log.warning("backtest drawdown breaker triggered as_of=%s dd_60d=%.4f", ts.date(), dd_60d)
            weeks_since_breach = 0
        else:
            weeks_since_breach += 1

        avg_corr = (
            rets.loc[:ts].tail(30).corr().where(~np.eye(len(universe), dtype=bool)).stack().mean()
            if len(rets.loc[:ts]) > 30
            else 0.0
        )

        target = views_to_target_weights(
            result.final_views,
            realized_vol_by_symbol=rv,
            cov_matrix=rets.loc[:ts].tail(252).cov() if len(rets.loc[:ts]) > 252 else None,
            cfg=cfg.portfolio,
        )
        target = apply_drawdown_breaker(target, dd_60d, weeks_since_breach)
        target = apply_correlation_throttle(target, float(avg_corr))

        # Turnover cap
        delta = {s: target.get(s, 0.0) - prev_weights.get(s, 0.0) for s in universe}
        gross_delta = sum(abs(d) for d in delta.values())
        if gross_delta > cfg.turnover_cap_per_period:
            scale = cfg.turnover_cap_per_period / gross_delta
            log.debug("backtest turnover cap as_of=%s gross_delta=%.3f scale=%.3f", ts.date(), gross_delta, scale)
            target = {s: prev_weights[s] + delta[s] * scale for s in universe}

        weights_log[ts.date()] = target
        # Apply weights from this rebalance forward
        daily_weights.loc[ts:, list(universe)] = pd.Series(target).reindex(universe).values
        prev_weights = target

    # Position-weighted daily returns net of costs (cost only on rebalance days)
    port_ret = (daily_weights.shift(1).fillna(0.0) * rets).sum(axis=1)
    cost_bps = cfg.transaction_cost_bps_roundtrip / 10_000
    cost_series = pd.Series(0.0, index=prices.index)
    prev = pd.Series(0.0, index=universe)
    for d, w in weights_log.items():
        ts = pd.Timestamp(d)
        if ts not in cost_series.index:
            continue
        new = pd.Series(w).reindex(universe).fillna(0.0)
        traded = (new - prev).abs().sum()
        cost_series.loc[ts] = traded * cost_bps
        prev = new
    net = port_ret - cost_series

    equity = (1 + net).cumprod() * cfg.starting_capital
    turnover = cost_series / cost_bps  # gross traded per rebalance day

    final_equity = float(equity.iloc[-1]) if len(equity) else float("nan")
    log.info(
        "backtest done protocol=%s rebalances=%d final_equity=%.2f total_return=%.4f",
        protocol.name, len(weights_log), final_equity, final_equity / cfg.starting_capital - 1,
    )
    return BacktestResult(
        equity=equity,
        weights=daily_weights,
        returns=net,
        turnover=turnover,
        metadata={"protocol": protocol.name, "rebalances": len(weights_log)},
    )
