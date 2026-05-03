"""Smoke tests — pure-python wiring, no network."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from agents.base_agent import InstrumentView
from data.universe import TRADEABLE_SYMBOLS, resolve_btc_ticker
from evaluation.metrics import sharpe, sortino, summary
from evaluation.statistical_tests import benjamini_hochberg, ledoit_wolf_sharpe_test
from llm.base import canonicalize_prompt, prompt_hash
from portfolio.construction import PortfolioConfig, views_to_target_weights


def test_universe_constants():
    assert "VIX" not in TRADEABLE_SYMBOLS
    assert "SPY" in TRADEABLE_SYMBOLS
    assert resolve_btc_ticker(date(2023, 12, 31)) == "BTC-USD"
    assert resolve_btc_ticker(date(2024, 6, 1)) == "IBIT"


def test_instrument_view_validation():
    v = InstrumentView(instrument="spy", direction=1, conviction=0.5, horizon="1w")
    assert v.instrument == "SPY"
    with pytest.raises(Exception):
        InstrumentView(instrument="SPY", direction=2, conviction=0.5, horizon="1w")
    with pytest.raises(Exception):
        InstrumentView(instrument="SPY", direction=1, conviction=1.5, horizon="1w")


def test_prompt_hash_deterministic():
    a = canonicalize_prompt(system="s", user="u", model="m", temperature=0.0, seed=42)
    b = canonicalize_prompt(system="s", user="u", model="m", temperature=0.0, seed=42)
    assert prompt_hash(a) == prompt_hash(b)
    c = canonicalize_prompt(system="s", user="u2", model="m", temperature=0.0, seed=42)
    assert prompt_hash(a) != prompt_hash(c)


def test_views_to_weights_caps_leverage():
    views = [
        InstrumentView(instrument="SPY", direction=1, conviction=1.0, horizon="1w"),
        InstrumentView(instrument="QQQ", direction=1, conviction=1.0, horizon="1w"),
        InstrumentView(instrument="IWM", direction=1, conviction=1.0, horizon="1w"),
        InstrumentView(instrument="GLD", direction=-1, conviction=1.0, horizon="1w"),
    ]
    rv = {"SPY": 0.15, "QQQ": 0.18, "IWM": 0.20, "GLD": 0.14}
    cfg = PortfolioConfig(max_gross_leverage=1.0)
    w = views_to_target_weights(views, rv, cov_matrix=None, cfg=cfg)
    assert sum(abs(v) for v in w.values()) <= cfg.max_gross_leverage + 1e-9


def test_sharpe_and_summary():
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0.0005, 0.01, 504))
    assert not np.isnan(sharpe(r))
    eq = (1 + r).cumprod()
    s = summary(eq, r, pd.Series(np.zeros(len(r))))
    assert "sharpe" in s and "max_drawdown" in s


def test_benjamini_hochberg():
    p = [0.01, 0.04, 0.10, 0.50, 0.001]
    rejects = benjamini_hochberg(p, fdr=0.05)
    assert rejects[4] is True
    assert rejects[3] is False


def test_ledoit_wolf_sharpe_runs():
    rng = np.random.default_rng(1)
    r1 = pd.Series(rng.normal(0.0008, 0.01, 750))
    r2 = pd.Series(rng.normal(0.0002, 0.01, 750))
    out = ledoit_wolf_sharpe_test(r1, r2)
    assert "z" in out and "p_value" in out and "sr_diff" in out
