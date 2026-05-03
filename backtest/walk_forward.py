"""Walk-forward protocol (spec §6.5).

Rolling 3y IS / 6m OOS windows. No re-optimization on OOS. The harness
exposes the IS/OOS window pair to the protocol; what to do with IS is
protocol-specific (deterministic anchors usually ignore it).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd


@dataclass
class WalkForwardConfig:
    train_years: int = 3
    test_months: int = 6


@dataclass
class WalkForwardWindow:
    is_start: date
    is_end: date
    oos_start: date
    oos_end: date


def walk_forward(start: date, end: date, cfg: WalkForwardConfig) -> list[WalkForwardWindow]:
    """Generate rolling IS/OOS windows over [start, end]."""
    windows: list[WalkForwardWindow] = []
    cursor = start
    train_delta = timedelta(days=cfg.train_years * 365)
    test_delta = timedelta(days=cfg.test_months * 30)
    while cursor + train_delta + test_delta <= end:
        is_start = cursor
        is_end = cursor + train_delta
        oos_start = is_end
        oos_end = oos_start + test_delta
        windows.append(WalkForwardWindow(is_start, is_end, oos_start, oos_end))
        cursor = oos_start  # roll forward by OOS length
    return windows
