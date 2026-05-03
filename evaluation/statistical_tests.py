"""Statistical inference (spec §6.10).

- Ledoit-Wolf robust Sharpe-ratio test (Ledoit & Wolf 2008) for pairwise
  Sharpe comparisons. Uses a HAC-corrected variance estimate.
- Benjamini-Hochberg correction for multiple comparisons.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm


def _hac_lrv(x: np.ndarray, q: int) -> float:
    """Newey-West long-run variance with Bartlett kernel."""
    n = len(x)
    g0 = float(np.var(x, ddof=1))
    if q == 0 or n < 3:
        return g0
    s = g0
    for j in range(1, q + 1):
        cov = float(np.cov(x[:-j], x[j:], ddof=1)[0, 1])
        s += 2 * (1 - j / (q + 1)) * cov
    return s


def ledoit_wolf_sharpe_test(
    r1: pd.Series,
    r2: pd.Series,
    block_length: int | None = None,
) -> dict[str, float]:
    """Test H0: SR(r1) = SR(r2). Returns z, p (two-sided), and the SR diff.

    Implementation follows Ledoit & Wolf (2008) Section 3.1: HAC-corrected
    variance of the Sharpe-ratio difference.
    """
    a = r1.dropna().values
    b = r2.dropna().values
    n = min(len(a), len(b))
    a, b = a[-n:], b[-n:]
    if n < 30:
        return {"z": float("nan"), "p_value": float("nan"), "sr_diff": float("nan")}

    mu_a, mu_b = a.mean(), b.mean()
    s_a, s_b = a.std(ddof=1), b.std(ddof=1)
    sr_a, sr_b = mu_a / s_a, mu_b / s_b
    diff = sr_a - sr_b

    q = block_length or int(np.floor(4 * (n / 100) ** (2 / 9)))
    # Variance via the four-component approach (mu, var, mu, var).
    psi = np.column_stack([
        a - mu_a,
        (a - mu_a) ** 2 - s_a**2,
        b - mu_b,
        (b - mu_b) ** 2 - s_b**2,
    ])
    # Gradient of (SR_a - SR_b) wrt (mu_a, var_a, mu_b, var_b)
    grad = np.array([
        1 / s_a,
        -mu_a / (2 * s_a**3),
        -1 / s_b,
        mu_b / (2 * s_b**3),
    ])
    # HAC variance of psi
    omega = np.zeros((4, 4))
    for i in range(4):
        for j in range(4):
            xi = psi[:, i] * psi[:, j]
            omega[i, j] = _hac_lrv(xi, q)
    var_diff = float(grad @ omega @ grad) / n
    if var_diff <= 0 or np.isnan(var_diff):
        return {"z": float("nan"), "p_value": float("nan"), "sr_diff": float(diff)}
    z = diff / np.sqrt(var_diff)
    p = 2 * (1 - norm.cdf(abs(z)))
    return {"z": float(z), "p_value": float(p), "sr_diff": float(diff)}


def benjamini_hochberg(p_values: list[float], fdr: float = 0.05) -> list[bool]:
    """Return per-test reject decisions controlling FDR at `fdr`."""
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    reject = [False] * m
    for rank, idx in enumerate(order, start=1):
        threshold = (rank / m) * fdr
        if p_values[idx] <= threshold:
            for k in order[:rank]:
                reject[k] = True
    return reject
