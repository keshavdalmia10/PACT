"""Two extra charts for the slide deck: benchmarks vs matrix, and alt-data deltas."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parent.parent / "results" / "figures"

NAVY = "#1F4E79"
ACCENT = "#2E75B6"
GRAY = "#6C757D"
HIGHLIGHT = "#E6A700"
RED = "#C0392B"

plt.rcParams.update({
    "figure.dpi": 150,
    "savefig.dpi": 200,
    "font.family": "sans-serif",
    "font.size": 12,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def benchmarks_chart():
    """Horizontal bar showing 4 passive benchmarks vs best matrix cell + best frontier cell."""
    labels = [
        "Inverse-volatility weighted",
        "SPY buy-and-hold",
        "Equal-weight buy-and-hold",
        "60/40 SPY-IEF",
        "Best matrix cell\n(none × debate)",
        "Best frontier cell\n(independent ensemble)",
    ]
    sharpes = [0.62, 0.50, 0.41, 0.34, 0.27, -0.13]
    colors = [ACCENT, ACCENT, ACCENT, ACCENT, GRAY, RED]

    fig, ax = plt.subplots(figsize=(11, 5.2))
    y = np.arange(len(labels))
    bars = ax.barh(y, sharpes, color=colors, edgecolor="white", linewidth=1.2)
    ax.invert_yaxis()
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=12)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Sharpe ratio (Window B 2022-2024)", fontsize=12)
    ax.set_xlim(-0.3, 0.85)

    for bar, sr in zip(bars, sharpes):
        x = sr + (0.015 if sr >= 0 else -0.015)
        ha = "left" if sr >= 0 else "right"
        ax.text(x, bar.get_y() + bar.get_height() / 2, f"{sr:+.2f}",
                va="center", ha=ha, fontsize=12, fontweight="bold",
                color=NAVY if sr >= 0 else RED)

    # Annotation
    ax.annotate(
        "Every passive benchmark\noutperforms every cell in the matrix",
        xy=(0.62, 0), xytext=(0.50, 1.5),
        fontsize=11, color=NAVY, fontweight="bold",
        arrowprops=dict(arrowstyle="->", color=NAVY, lw=1.2),
    )

    fig.tight_layout()
    out = OUT / "benchmarks_vs_matrix.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white"); plt.close(fig)
    print(f"wrote {out}")


def altdata_deltas_chart():
    """Grouped bar chart: Sharpe delta vs text_only baseline, by variant × protocol (frontier only)."""
    variants = ["+attention", "+event_probs", "+full", "+instrument"]
    seq = [0.129, 0.102, 0.103, 0.006]
    deb = [0.011, 0.007, -0.007, -0.019]

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(variants))
    w = 0.36
    b1 = ax.bar(x - w / 2, seq, w, label="sequential_pipeline", color=ACCENT, edgecolor="white")
    b2 = ax.bar(x + w / 2, deb, w, label="debate", color=GRAY, edgecolor="white")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(variants, fontsize=12)
    ax.set_ylabel("Sharpe delta vs text_only baseline", fontsize=12)
    ax.set_ylim(-0.05, 0.18)
    ax.legend(loc="upper right", fontsize=11, frameon=False)

    for bars in (b1, b2):
        for bar in bars:
            v = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2,
                    v + (0.005 if v >= 0 else -0.012),
                    f"{v:+.3f}", ha="center", fontsize=10,
                    color=NAVY if v >= 0 else RED, fontweight="bold")

    # Annotation: attention is the winner
    ax.annotate(
        "Attention data adds the\nmost Sharpe (+0.13)",
        xy=(0, 0.129), xytext=(0.5, 0.165),
        fontsize=11, color=NAVY, fontweight="bold",
        arrowprops=dict(arrowstyle="->", color=NAVY, lw=1.2),
    )

    fig.tight_layout()
    out = OUT / "altdata_deltas.png"
    fig.savefig(out, bbox_inches="tight", facecolor="white"); plt.close(fig)
    print(f"wrote {out}")


if __name__ == "__main__":
    benchmarks_chart()
    altdata_deltas_chart()
