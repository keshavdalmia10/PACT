"""Build the 12-slide PACT presentation deck.

Follows the academic-pptx skill's content rules:
- Action titles (complete sentence stating the takeaway)
- One exhibit per results slide; key finding annotated on the chart
- Single sans-serif font, 3-color palette (navy / accent / gray)
- White content slides; dark navy for title and conclusions
- 20pt body text minimum
- In-slide citations
- Conclusions slide stays on screen

Output: paper/PACT_presentation.pptx
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

# ──────────────── design tokens ────────────────
ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "results" / "figures"
OUT = ROOT / "paper" / "PACT_presentation.pptx"

FONT = "Calibri"
NAVY = RGBColor(0x1F, 0x4E, 0x79)
ACCENT = RGBColor(0x2E, 0x75, 0xB6)
GRAY = RGBColor(0x6C, 0x75, 0x7D)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
NEAR_BLACK = RGBColor(0x2D, 0x2D, 0x2D)
LIGHT_BLUE = RGBColor(0xEB, 0xF3, 0xFA)
HIGHLIGHT_BG = RGBColor(0xFF, 0xF2, 0xCC)
HIGHLIGHT_LINE = RGBColor(0xE6, 0xC8, 0x00)
RULE = RGBColor(0xCC, 0xCC, 0xCC)
TITLE_DARK_LIGHTBLUE = RGBColor(0xA0, 0xBB, 0xDD)


def add_text(slide, x, y, w, h, text, *,
             size=20, bold=False, color=NEAR_BLACK, align=PP_ALIGN.LEFT,
             font=FONT, line_spacing=1.15):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Emu(0)
    tf.margin_right = Emu(0)
    tf.margin_top = Emu(0)
    tf.margin_bottom = Emu(0)
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = line_spacing
    run = p.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return box


def add_bullets(slide, x, y, w, h, items, *, size=20, color=NEAR_BLACK,
                bold_lead=False, font=FONT, line_spacing=1.2,
                space_after=8):
    """`items` is list of strings or list of (lead_bold, rest) tuples."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Emu(0)
    tf.margin_right = Emu(0)
    tf.margin_top = Emu(0)
    tf.margin_bottom = Emu(0)
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.line_spacing = line_spacing
        p.space_after = Pt(space_after)
        # Bullet glyph + indent
        prefix = "• "
        if isinstance(item, tuple):
            lead, rest = item
            r1 = p.add_run()
            r1.text = prefix + lead
            r1.font.name = font; r1.font.size = Pt(size); r1.font.bold = True; r1.font.color.rgb = color
            r2 = p.add_run()
            r2.text = " " + rest
            r2.font.name = font; r2.font.size = Pt(size); r2.font.color.rgb = color
        else:
            r = p.add_run()
            r.text = prefix + item
            r.font.name = font; r.font.size = Pt(size); r.font.bold = False; r.font.color.rgb = color
    return box


def fill_background(slide, color):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_rule(slide, x, y, w, h, color=RULE):
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid(); shp.fill.fore_color.rgb = color
    shp.line.fill.background()
    return shp


def add_callout(slide, x, y, w, h, text, *, fill=LIGHT_BLUE, line_color=ACCENT, text_color=NAVY, size=18):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid(); shp.fill.fore_color.rgb = fill
    shp.line.color.rgb = line_color
    shp.line.width = Pt(1.25)
    tf = shp.text_frame
    tf.margin_left = Inches(0.2); tf.margin_right = Inches(0.2)
    tf.margin_top = Inches(0.1); tf.margin_bottom = Inches(0.1)
    tf.word_wrap = True
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = text
    r.font.name = FONT; r.font.size = Pt(size); r.font.bold = True; r.font.color.rgb = text_color
    return shp


def slide_title(slide, text, *, color=NAVY, size=26, y=0.25, h=0.9):
    add_text(slide, 0.5, y, 9.0, h, text, size=size, bold=True, color=color)
    add_rule(slide, 0.5, y + h + 0.05, 9.0, 0.025)


def cite(slide, text, y=5.1):
    add_text(slide, 0.5, y, 9.0, 0.35, text, size=12, color=GRAY)


# ──────────────── Build the deck ────────────────

def build():
    pres = Presentation()
    pres.slide_width = Inches(10)
    pres.slide_height = Inches(5.625)
    blank = pres.slide_layouts[6]

    # ───── Slide 1: Title ─────
    s = pres.slides.add_slide(blank)
    fill_background(s, NAVY)
    add_text(s, 0.7, 1.0, 8.6, 1.6,
             "PACT — Protocols for Agent Coordination in Trading",
             size=32, bold=True, color=WHITE)
    add_text(s, 0.7, 2.1, 8.6, 0.6,
             "A Coordination-and-Attribution Study of Multi-Agent LLM Trading Systems",
             size=18, color=TITLE_DARK_LIGHTBLUE)
    # Accent rule
    add_rule(s, 0.7, 3.0, 2.0, 0.05, color=ACCENT)
    add_text(s, 0.7, 3.15, 8.6, 0.5,
             "Keshav Dalmia · Prateek Verma · Drumil Mehta · Tasnia Islam",
             size=16, color=WHITE)
    add_text(s, 0.7, 3.7, 8.6, 0.4,
             "Gies College of Business · University of Illinois Urbana-Champaign",
             size=14, color=TITLE_DARK_LIGHTBLUE)
    add_text(s, 0.7, 4.55, 8.6, 0.35,
             "Master's Project — Track 4 (Coordination & Attribution Research)  ·  May 2026",
             size=13, color=TITLE_DARK_LIGHTBLUE)
    add_text(s, 0.7, 4.95, 8.6, 0.35,
             "Code: github.com/keshavdalmia10/PACT",
             size=12, color=TITLE_DARK_LIGHTBLUE)

    # ───── Slide 2: Motivation ─────
    s = pres.slides.add_slide(blank)
    slide_title(s, "Multi-agent LLM trading systems report Sharpe > 6 — but rarely test against the no-communication baseline")
    add_bullets(s, 0.5, 1.4, 9.0, 3.5, [
        ("TradingAgents (2024):", "debate-style, Sharpe 6+ on a 3-month, 5-stock window"),
        ("FinCon, FinMem, HedgeAgents, MarketSenseAI 2.0:", "each proposes one architecture, reports one strong number"),
        ("FINSABER (2025):", "simple ARIMA / rule-based timing competes with LLM agents on long horizons"),
        ("Stop Overvaluing MAD (2025):", "multi-agent debate gains evaporate under proper baselines"),
        ("CPH taxonomy (2026):", "calls for direct comparison of coordinated vs no-communication ensembles"),
    ], size=18)
    cite(s, "Xiao et al. (2024); Yu et al. (2024); Li et al. (2025); Zhang et al. (2025); Nguyen and Pham (2026).")

    # ───── Slide 3: Research Question ─────
    s = pres.slides.add_slide(blank)
    slide_title(s, "We ask: does coordination add value beyond a no-communication ensemble of the same specialists?")
    add_callout(s, 1.0, 1.5, 8.0, 1.7,
                "Does multi-agent coordination in LLM trading systems\n"
                "add value beyond a single-agent baseline and a no-communication\n"
                "ensemble of the same specialists, after controlling for transaction\n"
                "costs and lookahead bias?",
                size=18)
    add_bullets(s, 0.5, 3.5, 9.0, 1.3, [
        ("H1:", "coordinated multi-agent > no-communication ensemble (net of cost)"),
        ("H4:", "attention + event-probability alt-data improves Sharpe by ≥ 0.05 (frontier)"),
        ("H5:", "removing one specialist changes Sharpe by ≥ 0.10 for at least one agent"),
    ], size=17)
    cite(s, "Pre-registered on the Open Science Framework before running the headline matrix.")

    # ───── Slide 4: Architecture ─────
    s = pres.slides.add_slide(blank)
    slide_title(s, "PACT runs a 7 × 2 ablation across coordination protocols and LLM regimes")
    s.shapes.add_picture(str(FIG / "coordination_protocols.png"),
                         Inches(0.5), Inches(1.2), width=Inches(7.5), height=Inches(4.0))
    add_bullets(s, 8.2, 1.3, 1.6, 3.5, [
        "7 protocols",
        "× 2 LLM regimes\n   (frontier / none)",
        "× 10-instrument\n   universe",
        "× weekly rebal\n   2022-2024",
    ], size=13, line_spacing=1.1, space_after=6)
    cite(s, "Specialist agents in blue; LLM steps red; aggregators gold; deterministic rules grey; final views green.")

    # ───── Slide 5: Methodology ─────
    s = pres.slides.add_slide(blank)
    slide_title(s, "Cross-asset universe with strict leakage controls and rolling walk-forward")
    add_text(s, 0.5, 1.3, 4.4, 0.4, "Universe (10 instruments)", size=18, bold=True, color=ACCENT)
    add_bullets(s, 0.5, 1.7, 4.4, 2.4, [
        "Equities: SPY, QQQ, IWM",
        "Treasuries: IEF, SHY",
        "Commodities: GLD, USO",
        "FX / EM / BTC: UUP, EEM, BTC",
    ], size=16)
    add_text(s, 5.1, 1.3, 4.4, 0.4, "Leakage controls", size=18, bold=True, color=ACCENT)
    add_bullets(s, 5.1, 1.7, 4.4, 2.6, [
        ("ALFRED:", "first-release vintages only"),
        ("EDGAR:", "17:30-ET cutoff rule"),
        ("GDELT:", "30-minute intraday lag"),
        ("Wikipedia / Polymarket:", "48-hour lag"),
        ("ChronoGPT:", "year-pinned commit SHA"),
    ], size=15)
    cite(s, "Walk-forward: rolling 3-year IS / 6-month OOS; $1M capital; 30 bps round-trip; weekly Friday rebalance.")

    # ───── Slide 6: Headline result ─────
    s = pres.slides.add_slide(blank)
    slide_title(s, "No frontier-LLM coordination protocol beats Sharpe 0; the best LLM cell is the no-communication ensemble")
    s.shapes.add_picture(str(FIG / "headline_sharpe_grid.png"),
                         Inches(0.4), Inches(1.2), width=Inches(5.6), height=Inches(3.8))
    add_text(s, 6.2, 1.2, 3.5, 0.4, "What to take away", size=18, bold=True, color=ACCENT)
    add_bullets(s, 6.2, 1.6, 3.5, 3.4, [
        ("Best frontier:", "ind. ensemble at −0.13"),
        ("Every coord. protocol:", "below the ensemble"),
        ("Best matrix overall:", "none + debate at +0.27"),
        ("H1 rejected", "in this window"),
    ], size=14, line_spacing=1.2)
    cite(s, "Window B 2022-2024, 10 instruments, with +instrument alt-data variant active.")

    # ───── Slide 7: Benchmarks ─────
    s = pres.slides.add_slide(blank)
    slide_title(s, "Four passive benchmarks outperform every cell in the matrix")
    s.shapes.add_picture(str(FIG / "benchmarks_vs_matrix.png"),
                         Inches(0.5), Inches(1.2), width=Inches(9.0), height=Inches(3.5))
    add_text(s, 0.5, 4.75, 9.0, 0.4,
             "A one-line inverse-volatility weighting of the same universe (Sharpe 0.62) beats every matrix cell.",
             size=14, bold=True, color=NAVY)
    cite(s, "Same Window B universe; no LLM, alt-data, or fundamentals signal — passive constructions on price data only.")

    # ───── Slide 8: Attribution ─────
    s = pres.slides.add_slide(blank)
    slide_title(s, "Narrative agent hurts most (Δ = −0.28); macro regime helps most (+0.34)")
    s.shapes.add_picture(str(FIG / "attribution_bars.png"),
                         Inches(0.4), Inches(1.2), width=Inches(5.8), height=Inches(3.8))
    add_text(s, 6.4, 1.2, 3.3, 0.4, "Per-agent LOO", size=18, bold=True, color=ACCENT)
    add_bullets(s, 6.4, 1.6, 3.3, 3.4, [
        ("narrative_event:", "−0.28 (hurts)"),
        ("macro_regime:", "+0.34 (helps)"),
        ("technical_trend:", "+0.23 (helps)"),
        ("risk_correlation:", "0 (scaling-only)"),
    ], size=14, line_spacing=1.2)
    cite(s, "LOO on b__frontier__sequential_pipeline; Sharpe(full) = −0.4447 reproduces the matrix-run cell.")

    # ───── Slide 9: Alt-data ablation ─────
    s = pres.slides.add_slide(blank)
    slide_title(s, "Attention data adds Sharpe (+0.13); instrument-specific alt-data does not")
    s.shapes.add_picture(str(FIG / "altdata_deltas.png"),
                         Inches(0.5), Inches(1.2), width=Inches(8.0), height=Inches(3.8))
    cite(s, "5 variants × 2 protocols × frontier regime; deltas vs text_only baseline. None matters in regime=none.")

    # ───── Slide 10: Robustness ─────
    s = pres.slides.add_slide(blank)
    slide_title(s, "All differences significant at FDR 5%, but bootstrap CIs and sub-period instability flag short-sample uncertainty")
    s.shapes.add_picture(str(FIG / "tc_sensitivity.png"),
                         Inches(0.4), Inches(1.2), width=Inches(5.5), height=Inches(3.8))
    add_text(s, 6.1, 1.2, 3.5, 0.4, "Statistical signals", size=18, bold=True, color=ACCENT)
    add_bullets(s, 6.1, 1.6, 3.5, 3.4, [
        ("LW Sharpe test:", "12/12 reject H₀ at FDR 5%"),
        ("Bootstrap 95% CIs:", "wide; span 0 for most cells"),
        ("Sub-period:", "no-LLM cells flip sign 2022 → 2023-24"),
        ("Cost sensitivity:", "all but ind. ensemble negative ≥ 30 bps"),
    ], size=13, line_spacing=1.2)
    cite(s, "Ledoit-Wolf (2008) HAC + Benjamini-Hochberg (1995) FDR; Politis-Romano (1994) block bootstrap.")

    # ───── Slide 11: Discussion ─────
    s = pres.slides.add_slide(blank)
    slide_title(s, "The architecture that benefits from LLM is the one that does NOT coordinate")
    add_bullets(s, 0.5, 1.4, 9.0, 3.4, [
        ("Parallel filter > coordination substrate:", "ind. ensemble + LLM is the only frontier cell where adding LLM helps (Δ = +0.24)"),
        ("Cascading context amplifies disagreement:", "sequential and hierarchical generate more turnover, no extra return"),
        ("Narrative LLM in volatile macro regimes:", "GDELT-driven sentiment lagged price action at every Fed pivot"),
        ("FINSABER alignment:", "simple beats complex on this window's risk-adjusted metrics"),
        ("Practical implication:", "always run the no-communication baseline and a passive benchmark"),
    ], size=17, line_spacing=1.25, space_after=10)
    cite(s, "FINSABER: Li et al. (2025); Stop Overvaluing MAD: Zhang et al. (2025).")

    # ───── Slide 12: Conclusions (sandwich back to dark navy) ─────
    s = pres.slides.add_slide(blank)
    fill_background(s, NAVY)
    add_text(s, 0.5, 0.3, 9.0, 0.5, "Conclusions",
             size=22, color=TITLE_DARK_LIGHTBLUE)
    add_rule(s, 0.5, 0.85, 9.0, 0.05, color=ACCENT)
    add_bullets(s, 0.5, 1.05, 9.0, 3.6, [
        ("1. H1 rejected on Window B:", "every coordinated frontier protocol underperforms the no-communication ensemble"),
        ("2. Passive beats every cell:", "inverse-vol (0.62), SPY BAH (0.50), 60/40 (0.34) all > best matrix cell (0.27)"),
        ("3. Narrative-LLM combination hurts:", "removing the GDELT-driven narrative agent improves Sharpe by +0.28"),
        ("4. Attention data is the most useful alt-data axis:", "+0.13 on sequential_pipeline; instrument-specific alt-data ≈ 0"),
    ], size=18, color=WHITE, line_spacing=1.3, space_after=12)
    add_text(s, 0.5, 4.85, 6.5, 0.35,
             "github.com/keshavdalmia10/PACT  ·  dalmia4@illinois.edu",
             size=14, color=TITLE_DARK_LIGHTBLUE)
    add_text(s, 0.5, 5.20, 9.0, 0.35,
             "Open dataset · pinned model SHAs · all caches reproducible bit-for-bit",
             size=12, color=TITLE_DARK_LIGHTBLUE)

    pres.save(str(OUT))
    print(f"saved {OUT}")
    print(f"{len(pres.slides)} slides")


if __name__ == "__main__":
    build()
