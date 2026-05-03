"""Risk overlays (spec §5.3).

- Drawdown circuit-breaker: 60d DD > 15% → halve positions for next 4 weeks.
- Correlation regime: 30d avg pairwise corr > 0.6 → reduce gross by 30%.

Headline strategy has NO stop-losses (path-dependency complicates attribution).
A robustness variant with stops can be wired separately.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DRAWDOWN_THRESHOLD = -0.15
DRAWDOWN_HALVING_WEEKS = 4
CORR_THRESHOLD = 0.60
CORR_REDUCTION = 0.70  # multiply gross by 0.7 → reduce 30%


def apply_drawdown_breaker(
    weights: dict[str, float],
    rolling_60d_dd: float,
    weeks_since_last_breach: int,
) -> dict[str, float]:
    """Halve positions if breach was within last `DRAWDOWN_HALVING_WEEKS`."""
    breached = rolling_60d_dd <= DRAWDOWN_THRESHOLD
    in_cooldown = weeks_since_last_breach < DRAWDOWN_HALVING_WEEKS
    if breached or in_cooldown:
        return {k: v * 0.5 for k, v in weights.items()}
    return weights


def apply_correlation_throttle(
    weights: dict[str, float],
    avg_pairwise_corr_30d: float,
) -> dict[str, float]:
    if avg_pairwise_corr_30d > CORR_THRESHOLD:
        return {k: v * CORR_REDUCTION for k, v in weights.items()}
    return weights
