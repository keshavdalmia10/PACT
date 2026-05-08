"""Draw the 7 coordination protocols as a single PNG figure for the paper.

Each protocol gets a sub-panel showing its information-flow topology:
- agents as boxes (specialists in blue, PM in green, judge/aggregator in gold)
- arrows showing direction of flow
- annotations describing the aggregation rule

Output: results/figures/coordination_protocols.png
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent.parent / "results" / "figures" / "coordination_protocols.png"

# Colours
SPECIALIST = "#cfe2ff"
SPECIALIST_EDGE = "#0d6efd"
PM = "#d1e7dd"
PM_EDGE = "#198754"
JUDGE = "#fff3cd"
JUDGE_EDGE = "#ffc107"
ANCHOR = "#e2e3e5"
ANCHOR_EDGE = "#6c757d"
LLM = "#f8d7da"
LLM_EDGE = "#dc3545"


def box(ax, x, y, w, h, label, fc, ec, fontsize=8):
    """Draw a rounded rectangle with centered label."""
    box = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.06",
        linewidth=1.0, facecolor=fc, edgecolor=ec,
    )
    ax.add_patch(box)
    ax.text(x, y, label, ha="center", va="center", fontsize=fontsize, wrap=True)


def arrow(ax, x1, y1, x2, y2, color="#444", style="-|>", lw=0.8):
    a = FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle=style, mutation_scale=8,
        linewidth=lw, color=color, shrinkA=4, shrinkB=4,
    )
    ax.add_patch(a)


def setup_panel(ax, title):
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    # NOTE: do not set_aspect("equal") — it compresses horizontal scale
    # when the gridspec cell is wider than tall, causing label overlap.
    ax.axis("off")
    ax.set_title(title, fontsize=11, fontweight="bold", pad=4)


# ────────────────── Protocol drawings ──────────────────


def draw_single_agent(ax):
    setup_panel(ax, "1. Single-LLM monolith")
    # Inputs box
    box(ax, 5, 8.3, 7, 1.0, "All factor blobs\n(macro · narrative · technical · fundamentals · risk)",
        SPECIALIST, SPECIALIST_EDGE, fontsize=7)
    # Big LLM
    box(ax, 5, 5, 4.5, 1.4, "Single LLM call\n(reads everything, emits view list)",
        LLM, LLM_EDGE, fontsize=8)
    # Output
    box(ax, 5, 1.7, 4, 1.0, "Per-instrument target views", PM, PM_EDGE, fontsize=8)
    arrow(ax, 5, 7.7, 5, 5.8)
    arrow(ax, 5, 4.2, 5, 2.3)


def draw_independent_ensemble(ax):
    setup_panel(ax, "2. Independent ensemble (no comm)")
    # 2 rows × 3 cols of agents — easier to read than 1×6
    row1 = [("Macro", 1.7), ("Narrative", 5.0), ("Cross-Asset", 8.3)]
    row2 = [("Technical", 1.7), ("Fundamentals", 5.0), ("Risk*", 8.3)]
    for name, x in row1:
        box(ax, x, 8.4, 2.6, 0.8, name, SPECIALIST, SPECIALIST_EDGE, fontsize=10)
    for name, x in row2:
        box(ax, x, 7.0, 2.6, 0.8, name, SPECIALIST, SPECIALIST_EDGE, fontsize=10)
    box(ax, 5, 4.2, 5, 1.0, "Median vote\n(direction · conviction-weighted)",
        ANCHOR, ANCHOR_EDGE, fontsize=10)
    box(ax, 5, 1.6, 4.5, 0.9, "Per-instrument target views", PM, PM_EDGE, fontsize=10)
    # Arrows: from row1 + row2 → median vote
    for _, x in row1 + row2:
        arrow(ax, x, 6.6, 5, 4.7)
    arrow(ax, 5, 3.7, 5, 2.05)
    ax.text(5, 0.6, "*Risk = scaling input only (no direction)",
            fontsize=8, style="italic", ha="center")


def draw_sequential_pipeline(ax):
    setup_panel(ax, "3. Sequential pipeline (3 phases)")
    # Phase 1
    box(ax, 4.2, 8.5, 2.4, 0.7, "Macro", SPECIALIST, SPECIALIST_EDGE, fontsize=10)
    box(ax, 7.4, 8.5, 2.4, 0.7, "Narrative", SPECIALIST, SPECIALIST_EDGE, fontsize=10)
    ax.text(1.4, 8.5, "Phase 1\nScreener", fontsize=9, ha="center", va="center",
            style="italic", color="#555")
    # Phase 2
    box(ax, 3.5, 6.0, 2.0, 0.7, "Cross-Asset", SPECIALIST, SPECIALIST_EDGE, fontsize=10)
    box(ax, 6.0, 6.0, 2.0, 0.7, "Technical", SPECIALIST, SPECIALIST_EDGE, fontsize=10)
    box(ax, 8.5, 6.0, 2.0, 0.7, "Fundamentals", SPECIALIST, SPECIALIST_EDGE, fontsize=9)
    ax.text(1.4, 6.0, "Phase 2\nDeep\nanalysis", fontsize=9, ha="center", va="center",
            style="italic", color="#555")
    # Phase 3
    box(ax, 4.2, 3.5, 2.0, 0.7, "Risk*", SPECIALIST, SPECIALIST_EDGE, fontsize=10)
    box(ax, 6.8, 3.5, 2.0, 0.7, "PM", PM, PM_EDGE, fontsize=10)
    ax.text(1.4, 3.5, "Phase 3\nRisk +\nportfolio", fontsize=9, ha="center", va="center",
            style="italic", color="#555")
    box(ax, 5.5, 1.4, 4.5, 0.85, "Per-instrument target views", PM, PM_EDGE, fontsize=10)
    # arrows
    arrow(ax, 4.2, 8.15, 4.0, 6.4)
    arrow(ax, 7.4, 8.15, 7.0, 6.4)
    for x in [3.5, 6.0, 8.5]:
        arrow(ax, x, 5.65, 4.2, 3.9)
        arrow(ax, x, 5.65, 6.8, 3.9)
    arrow(ax, 4.2, 3.15, 6.8, 3.15)
    arrow(ax, 6.8, 3.15, 5.5, 1.85)


def draw_hierarchical(ax):
    setup_panel(ax, "4. Hierarchical (manager-analyst)")
    box(ax, 5, 8.5, 3.4, 0.9, "PM (manager)\nbriefs · veto", PM, PM_EDGE, fontsize=10)
    # 2 rows × 3 cols of analysts
    row1 = [("Macro", 1.7), ("Narrative", 5.0), ("Cross-Asset", 8.3)]
    row2 = [("Technical", 1.7), ("Fundamentals", 5.0), ("Risk*", 8.3)]
    for name, x in row1:
        box(ax, x, 6.0, 2.6, 0.7, name, SPECIALIST, SPECIALIST_EDGE, fontsize=10)
        arrow(ax, 5, 8.05, x, 6.35, color="#888", lw=0.6, style="<|-|>")
    for name, x in row2:
        box(ax, x, 4.7, 2.6, 0.7, name, SPECIALIST, SPECIALIST_EDGE, fontsize=10)
        arrow(ax, 5, 8.05, x, 5.05, color="#888", lw=0.6, style="<|-|>")
    box(ax, 5, 2.7, 4.0, 0.85, "Confidence-veto (threshold 0.15)",
        JUDGE, JUDGE_EDGE, fontsize=10)
    box(ax, 5, 0.9, 4.5, 0.85, "Per-instrument target views",
        PM, PM_EDGE, fontsize=10)
    arrow(ax, 5, 4.35, 5, 3.15)
    arrow(ax, 5, 2.25, 5, 1.35)


def draw_debate(ax):
    setup_panel(ax, "5. Debate (bull/bear + judge)")
    box(ax, 2.5, 7, 2.5, 1.0, "Bull team\n(2 analysts)", SPECIALIST, SPECIALIST_EDGE, fontsize=7)
    box(ax, 7.5, 7, 2.5, 1.0, "Bear team\n(2 analysts)", SPECIALIST, SPECIALIST_EDGE, fontsize=7)
    arrow(ax, 3.7, 7, 6.3, 7, style="<|-|>", color="#dc3545", lw=1.0)
    ax.text(5, 7.7, "rounds", fontsize=7, ha="center", style="italic", color="#dc3545")
    box(ax, 5, 4.4, 3.5, 1.0, "Judge LLM\n(synthesises)", JUDGE, JUDGE_EDGE, fontsize=8)
    arrow(ax, 2.5, 6.5, 5, 4.9, color="#888")
    arrow(ax, 7.5, 6.5, 5, 4.9, color="#888")
    box(ax, 5, 1.8, 4, 0.9, "Per-instrument target views", PM, PM_EDGE, fontsize=8)
    arrow(ax, 5, 3.9, 5, 2.3)


def draw_deterministic(ax):
    setup_panel(ax, "6. Deterministic anchor only (no LLM)")
    box(ax, 5, 8.7, 6.5, 1.0,
        "Multi-horizon momentum\n(1m · 3m · 6m · 12m)",
        ANCHOR, ANCHOR_EDGE, fontsize=10)
    box(ax, 2.4, 5.7, 3.6, 1.2,
        "Inverse-volatility\n(EWMA λ = 0.94)",
        ANCHOR, ANCHOR_EDGE, fontsize=10)
    box(ax, 7.6, 5.7, 3.6, 1.2,
        "Drawdown breaker\n(60-day MDD ≥ 15%)",
        ANCHOR, ANCHOR_EDGE, fontsize=10)
    box(ax, 5, 3.0, 4.5, 1.0,
        "Vol-targeted weights\n(rule-based)",
        PM, PM_EDGE, fontsize=10)
    box(ax, 5, 1.0, 4.5, 0.85,
        "Per-instrument target views", PM, PM_EDGE, fontsize=10)
    arrow(ax, 5, 8.15, 2.4, 6.35)
    arrow(ax, 5, 8.15, 7.6, 6.35)
    arrow(ax, 2.4, 5.05, 5, 3.55)
    arrow(ax, 7.6, 5.05, 5, 3.55)
    arrow(ax, 5, 2.45, 5, 1.45)


def draw_llm_plus_anchor(ax):
    setup_panel(ax, "7. LLM + deterministic anchor")
    box(ax, 5, 8.3, 5, 1.0, "Deterministic anchor\n(rules → baseline view)", ANCHOR, ANCHOR_EDGE, fontsize=8)
    box(ax, 5, 5.5, 4.5, 1.2, "LLM refinement\n(reads anchor + factors)", LLM, LLM_EDGE, fontsize=8)
    box(ax, 5, 2.5, 4.5, 1.0, "Refined view per instrument\n(may flip / soften / amplify)", PM, PM_EDGE, fontsize=7)
    box(ax, 5, 0.7, 4, 0.7, "Per-instrument target views", PM, PM_EDGE, fontsize=7)
    arrow(ax, 5, 7.7, 5, 6.2)
    arrow(ax, 5, 4.8, 5, 3.1)
    arrow(ax, 5, 1.9, 5, 1.1)


# ────────────────── Build the figure ──────────────────

def main():
    fig = plt.figure(figsize=(11, 11.5))
    gs = fig.add_gridspec(4, 2, hspace=0.40, wspace=0.10)

    drawers = [
        draw_single_agent,
        draw_independent_ensemble,
        draw_sequential_pipeline,
        draw_hierarchical,
        draw_debate,
        draw_deterministic,
        draw_llm_plus_anchor,
    ]
    for i, fn in enumerate(drawers):
        ax = fig.add_subplot(gs[i // 2, i % 2])
        fn(ax)

    # Legend in the unused 8th cell
    ax = fig.add_subplot(gs[3, 1])
    ax.axis("off")
    ax.set_title("Legend", fontsize=10, fontweight="bold", pad=4)
    legend_items = [
        (SPECIALIST, SPECIALIST_EDGE, "Specialist agent"),
        (PM, PM_EDGE, "Portfolio manager / final view"),
        (LLM, LLM_EDGE, "LLM-driven step"),
        (JUDGE, JUDGE_EDGE, "Judge / aggregation"),
        (ANCHOR, ANCHOR_EDGE, "Deterministic rule"),
    ]
    for i, (fc, ec, label) in enumerate(legend_items):
        y = 0.75 - i * 0.13
        box(ax, 0.15, y, 0.18, 0.08, "", fc, ec)
        ax.text(0.30, y, label, fontsize=10, va="center")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    fig.suptitle(
        "PACT — Seven Coordination Protocols (rows of the headline ablation matrix)",
        fontsize=13, fontweight="bold", y=0.995,
    )
    fig.savefig(OUT, dpi=180, bbox_inches="tight", facecolor="white")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
