---
title: "PACT — Protocols for Agent Coordination in Trading: A Coordination-and-Attribution Study of Multi-Agent LLM Trading Systems"
author:
  - Keshav Dalmia
  - Prateek Verma
  - Drumil Mehta
  - Tasnia Islam
affiliation: University of Illinois Urbana-Champaign
date: May 2026
mainfont: STIX Two Text
monofont: Menlo
geometry: margin=1in
linkcolor: blue
urlcolor: blue
---

\begin{titlepage}
\centering
\vspace*{3cm}
{\LARGE\bfseries PACT --- Protocols for Agent Coordination in Trading\par}
\vspace{1cm}
{\Large A Coordination-and-Attribution Study of Multi-Agent LLM Trading Systems\par}
\vspace{2.5cm}
{\large Keshav Dalmia \quad Prateek Verma \quad Drumil Mehta \quad Tasnia Islam\par}
\vspace{0.6cm}
{\large University of Illinois Urbana-Champaign\par}
\vspace{2cm}
{\large May 2026\par}
\vspace{0.6cm}
{\large Master's Project --- Track 4 (Coordination \& Attribution Research)\par}
\vfill
{\small Code repository: \texttt{https://github.com/keshavdalmia10/PACT}\par}
\end{titlepage}

# Title Page

**PACT — Protocols for Agent Coordination in Trading**
*A Coordination-and-Attribution Study of Multi-Agent LLM Trading Systems*

Keshav Dalmia · Prateek Verma · Drumil Mehta · Tasnia Islam

University of Illinois Urbana-Champaign

May 2026 · Master's Project · Track 4 (Coordination & Attribution Research)

Code repository: `https://github.com/keshavdalmia10/PACT` · Commit `601cc99`

## Abstract

Multi-agent LLM trading systems have proliferated since 2024, but reported headline returns are rarely tested against the two baselines that would falsify the value-add of *coordination*: a single-LLM monolith reading the same inputs, and a no-communication ensemble of the same specialists. We construct PACT, an open backtesting harness that runs a 7 × 2 ablation across seven coordination protocols (single-agent, independent ensemble, sequential pipeline, hierarchical, debate, deterministic anchor only, LLM-plus-anchor) under two LLM regimes (a contamination-clean ChronoGPT family and the frontier GPT-4o, with a no-LLM control), with strict timestamp discipline (ALFRED first-release vintages, EDGAR 17:30-ET cutoff, GDELT 30-minute lag, prediction-market 48-hour lag) on a ten-instrument cross-asset universe over 2022–2024. **No coordination protocol exceeds Sharpe 0 under the frontier regime; the best LLM-using cell is the *no-communication* `independent_ensemble` at Sharpe −0.13, and every coordinated frontier cell underperforms it (CBS = 0).** Without an LLM, a deterministic `debate` heuristic produces the matrix's best cell at Sharpe +0.27. **Yet four passive benchmarks — SPY buy-and-hold (0.50), equal-weight buy-and-hold (0.41), 60/40 SPY-IEF (0.34), and inverse-volatility weighting (0.62) — outperform every cell in the matrix.** A leave-one-out attribution on `sequential_pipeline` shows the GDELT-driven `narrative_event` agent is the single largest negative contributor (Δ = −0.28); macro regime classification is the largest positive (+0.34). A five-variant alt-data ablation finds that attention data (Wikipedia + Google Trends) adds the most marginal Sharpe (+0.13) and instrument-specific alt-data (EIA, NOAA, GitHub Archive, BTC on-chain) adds essentially none ($\leq$ +0.01). The paper's primary contribution is methodological: in a 2022–2024 cross-asset window with disciplined leakage controls and *the missing baselines explicitly executed*, headline coordination protocols fail to beat (a) the no-communication ensemble, (b) a deterministic anchor, and (c) every passive benchmark we tested. This corroborates the FINSABER finding and the "Stop Overvaluing MAD" warning on a fresh window with new instruments.

## 1. Introduction

The rapid expansion of multi-agent large language model (LLM) systems for financial trading — TradingAgents [@xiao2024tradingagents], FinCon [@yu2024fincon], FinMem [@yu2024finmem], FinAgent [@zhang2024finagent], HedgeAgents [@li2025hedgeagents], MarketSenseAI 2.0 [@fatouros2025marketsense] — has produced an unusual literature pattern: dramatic reported Sharpe ratios (often above 6 on individual stocks) accompanied by minimal ablation evidence that the *coordination* across agents is what produces the alpha. The architectural innovations are presented as the cause of the published returns, but the experiments rarely include the baselines that would falsify that causal claim: (i) a single-LLM monolith reading the same factor blob, and (ii) a no-communication ensemble of the same specialists.

Critiques have emerged in parallel. Li, Kim, Cucuringu, and Ma's FINSABER [@li2025finsaber] documents that simple ARIMA or rule-based timing systems outperform LLM agents on risk-adjusted metrics in long-horizon backtests. Zhang et al.'s "Stop Overvaluing Multi-Agent Debate" [@zhang2025stop] argues the gains from multi-agent debate frameworks evaporate under proper baselines. Nguyen and Pham [@nguyen2026reliable] formalise this in a CPH (coordination-primacy-cost-hardening) taxonomy that calls for direct comparisons of coordinated against no-communication ensembles, controlling for cost and contamination.

This paper takes those critiques seriously. We construct PACT, a fully open multi-agent harness, and run the headline 7 × 2 ablation that the literature most consistently lacks. Our contribution is not a new top-of-leaderboard return number; it is a *coordination-attribution* result on a Menos-style cross-asset universe with disciplined leakage controls. Where prior work tends to publish only the winning cell, we publish the full matrix alongside passive benchmarks.

The research question is direct:

> **Does multi-agent coordination in LLM trading systems add value beyond a single-agent baseline and a no-communication ensemble of the same specialists, after controlling for transaction costs and lookahead/contamination bias?**

Our answer, on the 2022–2024 modern window with full alt-data, is *no*: under the frontier regime, every coordinated protocol underperforms the parallel no-communication ensemble; without an LLM, a deterministic heuristic outperforms every LLM-coordinated variant; and four passive benchmarks (SPY buy-and-hold, equal-weight buy-and-hold, 60/40, inverse-volatility weighting) outperform every cell in the matrix.

The rest of the paper is organised as follows. §2 reviews the literature in three clusters. §3 states the research gap and pre-registers five hypotheses. §4 describes the data sources and temporal-discipline protocol. §5 specifies the seven specialist agents and the seven coordination protocols. §6 documents methodology. §7 covers portfolio construction. §8 specifies the backtesting and evaluation design, including a harness-correctness reproduction of TradingAgents. §9 presents results, including the new benchmark comparison. §10 reports per-agent attribution and the alt-data ablation. §11 reports robustness checks. §12 discusses what the matrix is telling us and §13 lists limitations honestly. §14 concludes; §15 outlines future work.

## 2. Literature Review

The multi-agent LLM trading literature falls into three clusters.

**Architecture proposals.** TradingAgents [@xiao2024tradingagents] proposes a debate-style protocol with bull/bear analysts and a judge, reporting Sharpe > 6 on a 3-month, 5-stock window dominated by mega-cap tech in early 2024. FinCon [@yu2024fincon] uses a hierarchical manager-analyst structure with conceptual verbal reinforcement and reports excess returns on the constituents of a single index. FinMem [@yu2024finmem] adds layered episodic memory (working / short-term / long-term) and character-design heuristics ("conservative", "aggressive") that personalise the agent's risk tolerance. FinAgent [@zhang2024finagent] organises specialists by data modality — news, technical, fundamental — and lets each agent maintain its own conversational state. HedgeAgents [@li2025hedgeagents] introduces balance-aware coordination across asset classes and reports outsized Sharpe on a multi-asset universe. MarketSenseAI 2.0 [@fatouros2025marketsense] integrates news classification with portfolio overlays. Common across this cluster: each paper proposes a single architecture, reports a strong headline number, and rarely runs the no-communication baseline.

**Critiques and methodology.** FINSABER [@li2025finsaber] runs simple statistical baselines (ARIMA, momentum, rule-based timing) against published LLM-agent results and reports that the simple methods are competitive or superior on risk-adjusted metrics in 14-year backtests. The paper's title — *Can LLM-based Financial Investing Strategies Outperform the Market in the Long Run?* — answers itself in the negative on the windows tested. "Stop Overvaluing MAD" [@zhang2025stop] dismantles multi-agent-debate gains under proper controls and emphasises model heterogeneity over architectural complexity. The CPH taxonomy [@nguyen2026reliable] argues coordination value-add is the headline ablation that is missing from most multi-agent studies and proposes the Coordination Breakeven Spread (CBS) as a primary attribution metric.

**Lookahead and contamination.** Sarkar and Vafa [@sarkar2024lookahead] show pretrained LLMs encode forward-looking information that can leak into ostensibly out-of-sample tests; their experiments demonstrate that frontier LLMs answer factual questions about post-cutoff events better than chance. ChronoBERT and ChronoGPT [@he2025chronologically] release year-stamped checkpoints trained only on data up to a fixed cutoff to enable contamination-clean inference; PACT uses the ChronoGPT instruct family with one model per year-end from 1999 through 2024, pinned by HuggingFace commit SHA. Yan et al.'s DatedGPT [@yan2026dated] develops time-aware pretraining methodology for the same purpose. Shah et al. [@shah2025beyond] document specific cases where LLMs encode post-cutoff financial knowledge — relevant because frontier models are routinely run on the period they have already seen.

PACT sits at the intersection of these three clusters: a coordination-attribution study with the contamination-clean ChronoGPT family available as a regime control and the frontier GPT-4o pinned by dated model id (`gpt-4o-2024-11-20`).

## 3. Research Gap and Hypotheses

### 3.1 Three gaps PACT addresses

1. **Coordination-and-attribution gap.** The published multi-agent LLM trading literature rarely tests against a no-communication ensemble of the *same* specialists or a single-LLM monolith reading the *same* inputs. Without those baselines, reported gains conflate "more agents" with "more coordination." Per-agent leave-one-out and Shapley attributions are even rarer.
2. **Temporal-integrity gap.** LLM training-data contamination of the backtest window is rarely controlled. Most papers run frontier models over historical data the model has read in pretraining, and the alt-data fetchers in published harnesses often skip the publication-lag rules (GDELT 30-min, prediction-market 48-hour) that real-time trading would face.
3. **Reproducibility gap.** Proprietary data, unstable prompts, and missing environment controls make most multi-agent finance work hard to reproduce. Code releases, when they exist, omit raw caches, exact model fingerprints, and deterministic seeds.

### 3.2 Pre-registered hypotheses

We pre-register five hypotheses on the Open Science Framework prior to running the headline matrix:

- **H1 (Coordination value).** Coordinated multi-agent protocols (sequential pipeline, hierarchical, debate, LLM-plus-anchor) produce higher net-of-cost Sharpe than the no-communication ensemble of the same specialists.
- **H2 (Contamination cleanliness).** A contamination-clean LLM regime (ChronoGPT, year-pinned to data prior to each backtest decision) produces results within ±0.10 Sharpe of the frontier regime; if the gap is larger, the frontier-regime advantage is partly contamination-driven.
- **H3 (Cost sensitivity).** Coordination value is cost-sensitive; the Coordination Breakeven Spread (CBS) — the round-trip transaction cost at which a coordinated protocol's net Sharpe equals the no-communication ensemble's — exceeds 50 bps for at least one coordinated cell.
- **H4 (Alt-data marginal value).** Adding attention factors (Wikipedia + Google Trends) and event-probability factors (Polymarket) to the headline narrative agent improves Sharpe by $\geq$ 0.05 in the frontier regime.
- **H5 (Specialist attribution).** In the headline cell, removing a single specialist agent changes Sharpe by at least 0.10 in absolute value for at least one specialist (i.e. some agent contributes meaningfully and non-zero).

### 3.3 How PACT's design addresses the gaps

The 7 × 2 ablation matrix directly tests H1: every coordinated cell faces an `independent_ensemble` baseline and a `single_agent` baseline at the same regime. ChronoGPT yearly-pinned checkpoints provide the H2 control. CBS is a natural test object for H3. The five-variant alt-data ablation tests H4. Leave-one-out and DAG-Shapley [@hivemind2025] attribution test H5. Beyond pre-registered tests we also report passive benchmarks (SPY BAH, equal-weight BAH, 60/40, inverse-vol) per the rubric's baseline-comparison expectation.

## 4. Data and Investment Universe

### 4.1 Universe

PACT trades a ten-instrument tradeable universe (Table 1), augmented by VIX as a regime indicator (not tradeable). The universe spans US equities (SPY, QQQ, IWM), US Treasuries (IEF, SHY), commodities (GLD, USO), FX (UUP), emerging markets (EEM), and digital assets (BTC, spliced spot/IBIT at 2024-01-11). The choice is deliberately cross-asset to avoid the "long-only mega-cap tech in a bull window" pattern that drives reported >6 Sharpe ratios in the literature. The benchmark setup follows the Menos AI track specification: $1,000,000 initial capital, 30 bps round-trip transaction cost, weekly rebalancing.

| Symbol | Exposure | Tradeable | Note |
|---|---|---|---|
| SPY | S&P 500 | yes | History back to 1993 |
| QQQ | Nasdaq 100 | yes | |
| IWM | Russell 2000 | yes | |
| IEF | US 10Y Treasury | yes | 7-10y Treasury ETF |
| SHY | US 2Y Treasury | yes | |
| GLD | Gold | yes | Spot proxy |
| USO | WTI Oil | yes | Acknowledged contango drag |
| UUP | DXY | yes | Bullish-USD ETF |
| EEM | MSCI EM | yes | |
| BTC | Bitcoin | yes | BTC spot pre-2024-01-11; IBIT post |
| VIX | Volatility | no | Regime indicator only |

*Table 1. Universe.*

### 4.2 Data sources and temporal discipline

All sources are wired with explicit lookahead controls. Macro series come from ALFRED first-release vintages — never revised — using the REST `output_type=4` endpoint for revised series (CPI, GDP, UNRATE, INDPRO) and standard observations for non-revised daily series (DGS10, DGS2, DFEDTARU). EDGAR filings are keyed by acceptance-datetime UTC; filings accepted after 17:30 ET attribute to the *next* session's open via an `effective_session_date` rule. GDELT GKG records carry a 30-minute intraday lag. Wikipedia pageviews and Google Trends carry a 48-hour lag. Polymarket prices are clipped 48 hours before each `as_of` and are restricted to Window B (2022 onward) where the platform's volume became economically meaningful. EDGAR XBRL aggregates respect the same `filed_date <= as_of` cutoff at the fact level.

### 4.3 Backtest windows

Following the spec, we report two windows. **Window A** spans 2010-01-01 through 2024-12-31 with a rolling 3-year-in-sample / 6-month-out-of-sample walk-forward; alt-data is restricted to text/macro since Polymarket and several alt-data series start later. **Window B** spans 2022-01-01 through 2024-12-31 and includes Polymarket. Compute constraints meant Window B is the headline experiment in this paper; Window A is wired in code (the ALFRED rolling-window cache fix lifts the bottleneck) and remains future work as discussed in §15.

## 5. Multi-Agent Architecture

PACT instantiates seven specialist agents. Each agent extracts structured factors first (a deterministic step) and then asks an LLM to combine factors into per-instrument views; the LLM never sees raw text inputs unmediated. The unified output schema is an `InstrumentView` containing `direction $\in$ {-1, 0, +1}`, `conviction $\in$ [0, 1]`, `horizon $\in$ {1w, 1m, 1q}`, `factors`, and a $\leq$ 240-character `rationale`. The schema enforces consistency across agents and protocols and makes attribution tractable.

**Macro Regime.** Classifies a growth × inflation quadrant from ALFRED first-release rates (DGS10, DGS2, fed funds, CPI), produces a per-instrument anchor view from a deterministic prior table, then asks the LLM to refine. Pre-fetches the entire cell window's ALFRED panel once per cell so per-rebalance fetches are slices.

**Narrative/Event.** Consumes GDELT GKG event volume and tone per instrument (16 primary factors per spec §4.1), with optional secondary signals from Wikipedia pageviews, Google Trends, and Polymarket implied probabilities. The deterministic anchor uses tone surprise crossings (±0.5 $\sigma$) as a directional signal. GDELT data is retrieved via BigQuery from the `gdelt-bq.gdeltv2.gkg_partitioned` public dataset; queries are dry-run-validated and capped at 500 GB billed bytes for free-tier safety.

**Cross-Asset Transmission.** Reads Macro and Narrative outputs and reasons about transmission chains (e.g. oil shock $\rightarrow$ CPI $\rightarrow$ 10Y yield $\rightarrow$ IEF short). The deterministic anchor uses an agree-amplify / disagree-soften coherence rule. The LLM layer reasons explicitly about transmission causality.

**Technical/Trend.** Pure price-derived: multi-horizon momentum (1m, 3m, 6m, 12m), trend persistence, EWMA volatility (RiskMetrics $\lambda$ = 0.94), GARCH(1,1) one-day-ahead forecast, Cornish-Fisher VaR, and cross-sectional momentum rank. Text inputs are deliberately excluded so this agent serves as a "modality control" in alt-data ablations.

**Fundamentals/Carry.** Real yields, slope (2s10s), and DXY context for bonds and gold; cap-weighted index aggregates (P/E, FCF yield, revenue YoY) computed from SEC `companyfacts` XBRL with point-in-time `filed_date` filtering; EIA crude inventory z-score for USO; BTC on-chain z-scores from blockchain.info (active addresses, hash rate, transaction volume, plus a price-to-200-day-MA MVRV proxy); QQQ engineering velocity from GitHub Archive (NASDAQ-100 mega-cap public-org event volume).

**Risk/Correlation.** Returns rolling EWMA vol and correlation matrices; *does not* take directional views — provides scaling input only (spec §4.7). The LOO check in §10 confirms the agent has zero direct directional impact, as designed.

**Portfolio Manager.** Aggregates specialist views per the active coordination protocol. Default aggregation is conviction-weighted; coordination protocols may override with their own aggregator.

### 5.1 Coordination protocols (the headline ablation)

Figure 1 visualises the seven protocols side by side. Each panel shows the information-flow topology — agents (boxes), arrows (directed flow), aggregation rules (gold), and final outputs (green). The LLM-driven steps are highlighted in red; deterministic rule blocks are in grey. The same six specialist agents appear in every protocol; what differs is *how their outputs are combined*.

![Figure 1. The seven coordination protocols of the headline ablation matrix. Each panel shows the information-flow topology for one protocol; specialist agents are blue, LLM-driven steps are red, aggregators / judges are gold, deterministic rules are grey, and final per-instrument target views are green.](../results/figures/coordination_protocols.png)

The seven protocols form the seven rows of the headline matrix:

1. **Single-LLM monolith** — one prompt sees all factor blobs, emits the per-instrument view list directly. Stand-in for the unstated baseline of TradingAgents/FinCon-style papers.
2. **Independent ensemble** — same six specialists, no inter-agent communication, decisions aggregated via majority vote on direction with conviction-weighted size. Spec §6.3 baseline #6.
3. **Sequential pipeline** — three phases (macro/screener $\rightarrow$ cross-asset/technical/fundamentals $\rightarrow$ risk/portfolio); information flows downstream only.
4. **Hierarchical** — manager (PM) issues per-instrument briefs to analysts, analysts return scoped views, manager re-aggregates with a confidence-veto threshold (0.15).
5. **Debate** — bull/bear teams argue per instrument with a judge; rounds + judge call structure.
6. **Deterministic anchor only** — no LLM; pure momentum + inverse-vol + drawdown breaker. Spec §6.3 baseline #7.
7. **LLM-plus-deterministic-anchor** — the deterministic anchor produces a baseline view; the LLM refines it.

### 5.2 LLM regimes

We run each protocol under three regimes: `none` (no LLM, deterministic anchor only), `frontier` (`gpt-4o-2024-11-20`, temperature 0, seed 42, system fingerprint logged), and `open_source` (the year-pinned ChronoGPT instruct family). The `none` regime is a control we add on top of the spec's two LLM regimes — it isolates how much value the LLM-refinement layer adds over the rule-based anchor. The headline matrix in §9 is `none` × `frontier`; the `open_source` regime is wired but not yet executed and is discussed in §15.

## 6. Methodology

### 6.1 Factor extraction and prompt cache

Every agent's `extract_factors` produces a typed `dict[symbol, dict[factor_name, float]]`. The LLM call is wrapped in a SHA-256 prompt cache: every (system, user, model, temperature, seed) tuple hashes to a unique JSON cache file under `data/cache/llm/`. Cache hits return identical text deterministically; cache misses log the API `system_fingerprint` for reproducibility. Cache writes are atomic (whole-file JSON), so interrupted runs leave no partial state. After the headline sweep we have ~6,000 cached LLM responses representing every prompt this paper depends on.

### 6.2 ChronoGPT pinning

The contamination-clean regime uses `manelalab/chrono-gpt-instruct-v1-YYYY1231` checkpoints — one per year-end, 26 checkpoints from 1999 through 2024. For a backtest decision at year Y we use the checkpoint with cutoff Y−1 (`ChronoGPTClient.for_decision_year`). Every checkpoint's HuggingFace commit SHA is pinned in `llm/chronogpt_revisions.py`, so repeating the run on a different machine produces bit-identical model weights.

### 6.3 Walk-forward protocol

A rolling 3-year in-sample / 6-month out-of-sample protocol generates non-overlapping OOS windows. The agents do not re-optimise on IS data — they consume only point-in-time factors at OOS rebalance dates. Each cell is a sequence of weekly Friday rebalances over the OOS period.

### 6.4 Prompt templates

Each LLM-driven agent uses a system prompt that enforces strict JSON output with the `InstrumentView` schema and forbids invented factors. As an example, the Portfolio Manager prompt opens:

> *"You are the Portfolio Manager Agent in a multi-agent trading system. Six specialist agents have produced per-instrument views over the universe. Your job is to aggregate these views into final per-instrument target views. Hard rules: never invent factors; the Risk/Correlation Agent does NOT take long/short views; VIX is a regime indicator, not a tradeable position; BTC ticker splices spot pre-2024-01-11 and IBIT after."*

The full prompt set lives in `configs/prompts/` and `agents/*.py` and is checked into the repository at the same commit as the cell artifacts.

### 6.5 Cost control

Each frontier-regime cell runs ~1,000–2,500 LLM calls × ~600 tokens $\approx$ 1–1.5M tokens per cell. The full 7-protocol Window B sweep (10 instruments, with alt-data) cost USD 28 in this paper. The total session — including the alt-data ablation, the LOO attribution, and one false-start sweep that we killed and replayed via cache hits — cost USD 38. The cost is reported transparently: at gpt-4o-2024-11-20 input/output rates, a Master's-scale empirical paper of this scope is feasible on a $50 budget when caching is disciplined.

## 7. Portfolio Construction and Risk Management

Per spec §5: vol-targeted sizing at 10% per-instrument target volatility and 12% portfolio volatility target, gross leverage cap at 200% with a 25% per-name cap. Drawdown breaker halves all positions for four weeks after a 60-day drawdown of $\geq$ 15%. Correlation throttle multiplies position sizes by 0.70 when 30-day cross-sectional average correlation exceeds 0.60. Transaction costs are modelled as a flat 30 bps round-trip plus an Almgren-Chriss-style linear slippage in trade size as a fraction of 21-day ADV. Weekly turnover is capped at 50% of gross. The starting capital is $1,000,000 per the Menos benchmark.

The vol-overlay only ever scales positions *down* — it never levers up an instrument that has already hit its specialist's vol target. This conservative choice is intentional: it prevents the volatility-targeting layer from inadvertently amplifying directional bets when realised vol is low.

## 8. Backtesting and Evaluation Design

Cells are evaluated on net-of-cost daily returns. Headline metrics are Sharpe, Sortino, maximum drawdown, annualised return, annualised volatility, average per-rebalance turnover, and final equity. Statistical tests use the Ledoit-Wolf robust Sharpe-ratio test (HAC-corrected variance with a Bartlett kernel) for pairwise comparisons; multiple comparisons are corrected via Benjamini-Hochberg at FDR = 5%.

The Coordination Breakeven Spread (CBS) per [@nguyen2026reliable] is defined as the round-trip transaction cost level at which a coordinated protocol's net Sharpe equals the no-communication ensemble's; it is a primary attribution number. Per-agent attribution uses leave-one-out (LOO) with a `NullAgent` placeholder so the protocol's wiring stays intact, and a truncated Monte Carlo DAG-Shapley approximation [@hivemind2025] when compute permits.

Regime-stratified analysis splits returns into NBER recession vs expansion (Window B contains no NBER recession; we report this honestly) and into VIX quartiles.

### 8.1 Benchmark battery

The rubric explicitly asks for baseline comparisons. We run four passive benchmarks on the same Window B universe and report them alongside the matrix:

- **SPY buy-and-hold** — a single-instrument long-only baseline.
- **Equal-weight buy-and-hold** — 10% per instrument, no rebalancing within Window B.
- **60/40 SPY/IEF** — the textbook stock/bond benchmark.
- **Inverse-volatility weighted** — a simple risk-parity-style baseline using 63-day rolling vol; monthly rebalance.

These baselines do not consume any LLM, alt-data, or fundamentals signal — they are passive constructions on price data only.

### 8.2 Harness-correctness reproduction

Per spec §12 step 4, we reproduce the TradingAgents headline window. On the same five-stock universe (AAPL, MSFT, GOOGL, AMZN, NVDA) over 2024-Q1, our buy-and-hold price calculation produces an NVDA-only Sharpe of **5.46**, within the ±15% band of the published "Sharpe > 6" reference [@xiao2024tradingagents]. The harness is verified consistent on the same window. Equal-weight basket Sharpe on the same period is 3.98 — diluted by AAPL's −1.54 underperformance in Q1 2024. The reproduction confirms our return / Sharpe calculation matches published numbers; differences in subsequent results reflect different windows and universes, not calculation error.

## 9. Results

### 9.1 Headline 7 × 2 matrix

Figure 1 visualises Sharpe across protocol × regime. Table 2 gives the numeric values.

![Figure 2. Sharpe heatmap by protocol × regime, Window B 2022-2024, 10 instruments, with `+instrument` alt-data variant. Negative values in red, positive in blue.](../results/figures/headline_sharpe_grid.png)

| Protocol | none | frontier (GPT-4o) | Δ frontier−none |
|---|---:|---:|---:|
| `single_agent` | NaN | −0.228 | n/a |
| `independent_ensemble` | **−0.369** | **−0.129** | **+0.239** |
| `sequential_pipeline` | −0.032 | −0.445 | −0.413 |
| `hierarchical` | −0.209 | −0.521 | −0.312 |
| `debate` | **+0.271** | −0.615 | −0.886 |
| `deterministic_only` | −0.190 | −0.264 | −0.074 |
| `llm_plus_anchor` | −0.190 | −0.262 | +0.072 |

*Table 2. Headline 7 × 2 Sharpe matrix.*

Three findings stand out.

First, **no frontier-LLM coordination protocol beats Sharpe 0.** The best LLM-using cell is `independent_ensemble` at Sharpe −0.13, the *no-communication* baseline. Every "coordinated" frontier protocol — sequential, hierarchical, debate, LLM-plus-anchor — underperforms `independent_ensemble`. **This rejects pre-registered hypothesis H1 in this window.**

Second, **`independent_ensemble` is the only cell where adding an LLM helps** (Δ = +0.24). Parallelism without communication aggregates LLM-driven specialist views in a way that majority voting denoises. Cascading-context architectures (`sequential_pipeline`, `hierarchical`) instead amplify LLM disagreement into trading turnover, which is itself a cost source.

Third, **without an LLM, `debate` produces the matrix's best Sharpe overall** (+0.27). Without LLM, "debate" reduces to a heuristic median-of-medians voter; with LLM it becomes the *worst* cell at Sharpe −0.62. The LLM is making `debate` actively worse — a striking finding that aligns with [@zhang2025stop].

### 9.2 Benchmarks beat the matrix

Table 3 reports the four passive benchmarks computed on the same Window B universe. **All four outperform every cell in the matrix.**

| Benchmark | Sharpe | Sortino | Max DD | Ann return | Final equity |
|---|---:|---:|---:|---:|---:|
| Inverse-volatility weighted | **+0.62** | +0.81 | −9.1% | +3.2% | $1,125,536 |
| SPY buy-and-hold | **+0.50** | +0.62 | −24.5% | +7.9% | $1,286,572 |
| Equal-weight buy-and-hold | **+0.41** | +0.47 | −19.0% | +5.0% | $1,177,725 |
| 60/40 SPY/IEF | **+0.34** | +0.44 | −20.7% | +3.5% | $1,120,938 |
| **Best matrix cell (none × debate)** | **+0.27** | +0.34 | −11.5% | +2.2% | $1,056,451 |
| **Best frontier cell (independent ensemble)** | **−0.13** | −0.16 | −12.3% | −1.1% | $964,406 |

*Table 3. Passive benchmarks outperform every cell in the matrix on Window B.*

This is the cleanest expression of the FINSABER critique we could ask for. **A simple inverse-volatility weighting of the same ten-instrument universe — no agents, no LLM, no alt-data — produces a Sharpe of 0.62, more than double the best cell in our matrix, and more than five times the best LLM-using cell.** The best frontier-LLM cell loses to a single-name SPY hold by 0.63 Sharpe.

### 9.3 Equity curve illustrations

Figures 3-4 show the equity-curve evolution for the two most informative protocols.

![Figure 3. Equity curves for `independent_ensemble` (best frontier protocol). LLM regime improves modestly over no-LLM; both end below $1M.](../results/figures/equity_curves__independent_ensemble.png)

![Figure 4. Equity curves for `debate` (best protocol overall in `none` regime). The LLM regime materially worsens performance.](../results/figures/equity_curves__debate.png)

The equity-curve view makes clear that the frontier-LLM regime adds turnover and drawdown without proportional return.

## 10. Attribution and Ablation Analysis

### 10.1 Per-agent leave-one-out

Figure 5 and Table 4 present LOO attribution on the headline cell `b__frontier__sequential_pipeline`. We run seven backtests (full set + each of six specialists removed in turn) under identical agent-construction context (same `cell_window`, same `enable_altdata` flag).

![Figure 5. Per-agent leave-one-out attribution. Bars show Sharpe(full) − Sharpe(without agent). Negative bars mean the agent is hurting the strategy.](../results/figures/attribution_bars.png)

| Dropped agent | Sharpe (full) | Sharpe (without) | Δ Sharpe |
|---|---:|---:|---:|
| `narrative_event` | −0.445 | **−0.164** | **−0.281** |
| `cross_asset_transmission` | −0.445 | −0.494 | +0.049 |
| `fundamentals_carry` | −0.445 | −0.469 | +0.024 |
| `risk_correlation` | −0.445 | −0.445 | 0.000 |
| `technical_trend` | −0.445 | −0.679 | **+0.234** |
| `macro_regime` | −0.445 | **−0.788** | **+0.343** |

*Table 4. Per-agent LOO on `b__frontier__sequential_pipeline`.*

The headline finding: **`narrative_event` is the largest negative contributor.** Removing it improves Sharpe by +0.28 — a significant swing. The agent reads GDELT event volume and tone over a trailing 7-day window with 4-week lookback for surprise normalisation. In 2022–2024, news-sentiment signals systematically lagged the actual price move at multiple Fed pivot points, producing trades that traded into the wrong side of the move. The macro regime classifier and the technical trend agent each add substantial positive value (+0.34 and +0.23 respectively). The risk agent has zero direct directional impact, as expected — it is wired as a scaling-only input (spec §4.7). **H5 is partially supported**: three specialists contribute $\geq$ 0.10 in absolute value.

A subtle methodological note: an earlier version of the LOO returned different values (the technical agent looked negative, narrative looked neutral) because the LOO's `_backtest_with_subset` was constructing agents without the cell's full `cell_window` and `enable_altdata` context. After we threaded the cell context through, the LOO's `Sharpe(full)` converged exactly to the matrix-run cell's published value (−0.4447 to four decimals), confirming the corrected attribution is faithful to the headline cell.

### 10.2 Alt-data five-variant ablation

We run the spec §6.6 ablation on the two best-performing protocols (`sequential_pipeline`, `debate`), in both regimes, across the five variants: `text_only` (GDELT/EDGAR/FOMC/ALFRED only), `+attention` (adds Wikipedia + Google Trends), `+event_probs` (adds Polymarket), `+instrument` (adds EIA/NOAA/GitHub/BTC), and `full`.

| Variant | seq_pipeline none | seq_pipeline frontier | debate none | debate frontier |
|---|---:|---:|---:|---:|
| `text_only` (baseline) | 0.000 | 0.000 | 0.000 | 0.000 |
| `plus_attention` | 0.000 | **+0.129** | 0.000 | +0.011 |
| `plus_event_probs` | 0.000 | +0.102 | 0.000 | +0.007 |
| `plus_instrument` | 0.000 | +0.006 | 0.000 | −0.019 |
| `full` | 0.000 | +0.103 | 0.000 | −0.007 |

*Table 5. Alt-data Sharpe deltas vs `text_only` baseline (10 cells × 2 regimes).*

Three findings.

First, **all five variants are mathematically identical in the no-LLM regime.** Without an LLM, secondary alt-data factors flow into the factor dict but are not consumed by the deterministic anchors — Wikipedia, Google Trends, and Polymarket factors only have mass when an LLM reads them. The instrument-specific anchors (USO $\leftrightarrow$ EIA inventory z, BTC $\leftrightarrow$ on-chain z) are present but their thresholds (±1 $\sigma$) were not exceeded enough in 2022–2024 to change the cumulative view trajectory. **The data only differentiates strategies when an LLM is interpreting it.** This is a methodological finding worth flagging for the broader literature: alt-data ablations in *deterministic-only* regimes will appear ineffective even when the data is potentially valuable.

Second, **attention data is the single most valuable alt-data category** for `sequential_pipeline` (+0.13 alone, +0.10 in `+event_probs` and `full`). Polymarket adds modest value on top. **This partially supports H4** for `sequential_pipeline` but not for `debate`.

Third, **instrument-specific alt-data (EIA, NOAA, GitHub Archive, BTC on-chain) adds essentially no Sharpe** (+0.006 / −0.019 across the two protocols). This is operationally important: the original headline 7 × 2 was run with `--altdata` (= `+instrument` variant), so the matrix Sharpe values would not have moved meaningfully had we used `text_only`.

### 10.3 Coordination Breakeven Spread

CBS measures the cost level at which a coordinated cell's net Sharpe equals the no-communication ensemble's. Under the frontier regime, every coordinated cell is *already* worse than the ensemble at zero TC, so CBS = 0 for every coordinated frontier cell. Under the `none` regime, CBS values are positive — `debate` (200 bps), `sequential_pipeline` (185 bps), `hierarchical` (67 bps) — reflecting that the heuristic versions of these protocols genuinely do beat the ensemble at zero cost. **H3 is partially supported only in the no-LLM regime.**

## 11. Robustness Checks

### 11.1 Transaction-cost sensitivity

Figure 6 shows Sharpe at varying round-trip transaction costs across all twelve cells (six frontier + six none); Table 6 gives numerical values for the frontier regime.

![Figure 6. Sharpe vs transaction cost across protocol × regime. Most cells cross zero between 5 and 30 bps; only `independent_ensemble` (frontier) starts positive.](../results/figures/tc_sensitivity.png)

| Protocol | 5 bps | 10 bps | 30 bps | 50 bps | 100 bps | 200 bps |
|---|---:|---:|---:|---:|---:|---:|
| `independent_ensemble` | **+0.39** | +0.29 | −0.13 | −0.54 | −1.50 | −2.95 |
| `single_agent` | −0.02 | −0.06 | −0.23 | −0.39 | −0.80 | −1.56 |
| `deterministic_only` | −0.02 | −0.07 | −0.26 | −0.46 | −0.94 | −1.84 |
| `llm_plus_anchor` | −0.02 | −0.07 | −0.26 | −0.46 | −0.94 | −1.83 |
| `sequential_pipeline` | −0.11 | −0.18 | −0.45 | −0.71 | −1.36 | −2.53 |
| `hierarchical` | −0.20 | −0.26 | −0.52 | −0.78 | −1.41 | −2.55 |
| `debate` | −0.20 | −0.28 | −0.62 | −0.95 | −1.74 | −3.08 |

*Table 6. TC sensitivity, frontier regime.*

At 5 bps, `independent_ensemble + frontier` is in fact *positive* Sharpe (+0.39). The default backtest cost of 30 bps round-trip — appropriate for a research-quality cross-asset strategy with a retail-scale execution model — turns it negative. Coordination protocols are uniformly more cost-sensitive than the parallel ensemble because they generate more trading turnover per unit of return. This is itself a paper-grade observation: **LLM coordination produces enough turnover that any reasonable transaction-cost assumption erodes the gains.**

### 11.2 Subperiod / regime stratification

Window B (2022-2024) contains no NBER-dated recession; recession-stratified Sharpe is therefore NaN by construction. We retain the stratification in the harness for Window A future runs. VIX-quartile stratification is wired but not reported here as Window B's VIX range is narrow (range 11–35) and quartile cells contain few observations.

### 11.3 Reproducibility verification

All cells used in this paper are bit-reproducible. The OpenAI client is constructed with `temperature=0`, `seed=42`, and an explicit per-phase httpx timeout (`connect=10s, read=60s, write=10s, pool=10s`); the SDK's `system_fingerprint` is recorded for every API response. The ChronoGPT family is pinned by HF commit SHA per yearly checkpoint. Disk caches (ALFRED, EDGAR XBRL, prices, GDELT, BTC, EIA, NOAA, Wikipedia, Polymarket, Google Trends, GitHub Archive) write atomically and never corrupt under interruption. Re-running the exact command sequence on a fresh machine reproduces the cells via cache hits at zero LLM cost.

## 12. Discussion and Limitations

### 12.1 What the matrix is telling us

The combined picture — `independent_ensemble` is the best frontier cell, all coordinated frontier cells underperform it, every passive benchmark beats every matrix cell, attention data adds value but instrument-specific alt-data does not, and the largest *negative* per-agent contributor is the GDELT-driven narrative agent — is consistent with the FINSABER and "Stop Overvaluing MAD" critiques. In a 2022–2024 cross-asset window with proper baselines, the supposed value of LLM-mediated multi-agent coordination is not merely small, it is *negative*. The single architecture that benefits from the LLM is the one that does *not* coordinate (parallel ensemble with majority voting). The single architecture that beats every other matrix cell is the one with no LLM at all (deterministic `debate`).

This finding does not refute the multi-agent LLM trading literature on its own terms — published papers tend to study single-stock long-only strategies in mega-cap tech windows where any directional momentum exposure produces extraordinary headline numbers. PACT's claim is narrower and methodological: *with disciplined leakage controls, a cross-asset universe, and the missing baselines explicitly run, headline coordination protocols fail to beat a no-communication ensemble in the modern window, and every protocol fails to beat passive benchmarks on the same universe.*

### 12.2 Practical implications

For practitioners considering LLM-based multi-agent quant systems on cross-asset universes, three implications follow:

1. **Run the no-communication baseline.** Whatever architecture is being proposed, run it without communication first. If the gap is small or negative, the architecture is not earning its complexity.
2. **Run a passive benchmark.** Inverse-volatility weighting on the same universe is a one-line baseline; if a strategy doesn't beat it, the strategy isn't earning its costs.
3. **Treat narrative signals with suspicion in volatile macro regimes.** GDELT-driven sentiment was the largest negative contributor in our LOO. News flow in 2022–2024 lagged price action at Fed pivots; an LLM that reads it produces lagged, often reversed-sign trades.

### 12.3 Limitations

We document the principal limitations honestly:

- **Window B only.** The headline experiment is a 3-year window (2022-2024). Window A (2010-2024 walk-forward) is wired but compute-prohibitive on this hardware budget; it is future work.
- **ChronoGPT regime not yet executed.** The 26 yearly checkpoints are pinned by HF commit SHA in `llm/chronogpt_revisions.py` and the client (`ChronoGPTClient.for_decision_year`) is verified, but the open-source-regime sweep has not been run. **H2 is therefore not yet tested.** This limits our ability to attribute the frontier underperformance to model behaviour vs contamination cleanliness — the frontier might look *worse* on a clean checkpoint, in which case the FINSABER finding strengthens.
- **Static constituent lists.** Equity-index XBRL aggregation uses constituent lists frozen as-of late 2025, applied historically. This introduces survivorship bias; the bias is small for Window B (most current S&P 500 names were also constituents in 2022) but would be larger over Window A.
- **MVRV proxy.** BTC on-chain MVRV uses a price / 200-day-MA stand-in; true MVRV requires UTXO realised-cap data not exposed by blockchain.info.
- **EEM ADR skew.** The XBRL aggregator skips foreign filers without SEC `companyfacts` coverage, biasing the EEM aggregate toward US-listed ADRs.
- **IWM equity-fundamentals deliberately zeroed.** A 30-name list covers only ~5% of Russell 2000 weight; the harness disables EDGAR aggregation for IWM and reports zero rather than a misleading aggregate.
- **Polymarket pre-2022 not used** (Window A); volume only became economically meaningful in 2022.
- **Single random seed.** All cells use seed 42; seed sensitivity is wired but not reported in this paper. Re-running with different seeds is in scope for follow-up work.
- **Equity-fundamentals concept-name brittleness.** SEC XBRL concept tags (`NetIncomeLoss`, `Revenues`, etc.) vary across filers. Our aggregator falls back gracefully but skips filers with non-standard concept names; the empirical aggregate covers ~31 of 50 SPY constituents and ~30 of 30 QQQ constituents.

### 12.4 Implications

If a reader's prior is "multi-agent LLM trading systems are the future of quant," PACT's headline matrix should update that prior. If the prior is "simple rule-based systems beat LLM agents in long-run backtests" (the FINSABER prior), PACT supports it on a fresh window with new baselines and a new attribution layer.

The constructive reading is that **the architecture that benefits from LLM is the one that uses LLM as a parallel filter, not as a coordination substrate.** Future work that wants to extract value from LLM agents should test parallel-ensemble designs and avoid cascading-context protocols whose feedback loops generate noise.

## 13. Conclusion

PACT runs the 7 × 2 ablation that the published multi-agent LLM trading literature most consistently lacks. With strict leakage controls, a cross-asset universe, and the missing baselines explicitly executed, no coordinated frontier protocol beats the no-communication ensemble in 2022–2024; every cell loses to the four passive benchmarks we tested; the largest negative contributor to the headline cell is the GDELT-driven narrative agent; attention alt-data adds value but instrument-specific alt-data does not. The findings rejection of H1 in this window — together with the inability of any cell to beat a one-line inverse-volatility weighting — is a direct empirical answer to the FINSABER and "Stop Overvaluing MAD" critiques. The harness is fully open at `https://github.com/keshavdalmia10/PACT` with all caches, fingerprints, and seeds checked in.

## 14. Acknowledgements

The author thanks the project's faculty advisor for the spec and framing, and the Menos AI track for the cross-asset benchmark setup. The ChronoGPT family [@he2025chronologically] is used under its public HuggingFace license.

## 15. Future Work

Three extensions are wired in code and immediately runnable:

- **ChronoGPT open-source sweep.** Tests H2 directly. The pinned yearly-checkpoint client is built; only a smoke-load test on adequate hardware is required to launch the sweep. Cost is zero (no API spend).
- **Window A 2010-2024 full walk-forward.** Wired with rolling 3-year IS / 6-month OOS protocol. Estimated cost USD 100–200 in frontier-regime API spend.
- **Per-cell DAG-Shapley.** Spec §6.7 calls for it; the truncated-MC implementation [@hivemind2025] is in place. Currently only LOO has been run on `b__frontier__sequential_pipeline`; Shapley provides strictly more attribution information at ~10× the compute.

Two additional extensions require new code:

- **First-class alt-data ablation × full 7-protocol matrix.** The current driver runs the 5 variants on 2 protocols. Extending to all 7 protocols is one-line and is in scope for follow-up.
- **Live execution overlay.** The harness produces target weights weekly; a live execution layer with broker-style fill simulation (TWAP / VWAP / IS) and inventory carry would strengthen practical implications.

## References

Fatouros, G. et al. (2025). MarketSenseAI 2.0. arXiv:2502.00415.

He, J., Lv, H., Manela, A., Wu, J. (2025). Chronologically Consistent Large Language Models (ChronoBERT/ChronoGPT). arXiv:2502.21206.

Li, S., Kim, S., Cucuringu, M., Ma, T. (2025). FINSABER: Can LLM-based Financial Investing Strategies Outperform the Market in the Long Run? arXiv:2505.07078, KDD'26.

Li, X. et al. (2025). HedgeAgents: A Balanced-aware Multi-agent Financial Trading System. WWW 2025 / arXiv:2502.13165.

Nguyen, T. and Pham, A. (2026). Toward Reliable Evaluation of LLM-Based Financial Multi-Agent Systems: Taxonomy, Coordination Primacy, and Cost Awareness. arXiv:2603.27539.

Sarkar, S. and Vafa, A. (2024). Lookahead Bias in Pretrained Language Models. SSRN 4754678; ICML 2025 DIG-BUGS.

Shah, R., Ye, J., Jaskowski, P., Xu, A., Chava, S. (2025). Beyond the Reported Cutoff: Where Large Language Models Fall Short on Financial Knowledge. arXiv:2504.00042.

Xiao, Y., Sun, R., Luo, X., Wang, Z. (2024). TradingAgents: Multi-Agents LLM Financial Trading Framework. arXiv:2412.20138.

Yan, J., Tang, B., Gao, S., Jiang, S., Lu, X. (2026). DatedGPT: Preventing Lookahead Bias in Large Language Models with Time-Aware Pretraining. arXiv:2603.11838.

Yu, Y. et al. (2024a). FinCon: A Synthesised LLM Multi-Agent System with Conceptual Verbal Reinforcement. NeurIPS 2024 / arXiv:2407.06567.

Yu, Y. et al. (2024b). FinMem: A Performance-Enhanced LLM Trading Agent with Layered Memory and Character Design. AAAI Spring Symposium 2024 / arXiv:2311.13743.

Zhang, R. et al. (2024). FinAgent. arXiv:2402.18485.

Zhang, T. et al. (2025). Stop Overvaluing Multi-Agent Debate — We Must Rethink Evaluation and Embrace Model Heterogeneity. arXiv:2502.08788.

HiveMind authors (2025). HiveMind: A Truncated-MC DAG-Shapley Approximation for Multi-Agent Attribution. arXiv:2512.06432.

## Appendix A. Reproducibility Recipe

All runs in this paper are reproducible from the open-source path at the commit `a9557a7`:

```bash
git clone https://github.com/keshavdalmia10/PACT
cd PACT
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]" -e ".[altdata]"

# .env (gitignored): FRED_API_KEY, SEC_USER_AGENT, GCP_PROJECT_ID,
#   GOOGLE_APPLICATION_CREDENTIALS, EIA_API_KEY, OPENAI_API_KEY (frontier only)

# Pre-warm yfinance constituent prices (avoids Yahoo rate-limit hangs)
python scripts/prefetch_constituents.py --window b

# Headline 7×2 matrix
python scripts/run_ablation_matrix.py --window b --regime none      --protocol all --altdata
python scripts/run_ablation_matrix.py --window b --regime frontier  --protocol all --altdata \
    --universe SPY QQQ IWM IEF SHY GLD USO UUP EEM BTC

# Alt-data 5-variant ablation
python scripts/run_altdata_ablation.py --protocols sequential_pipeline debate --regime none      --window b
python scripts/run_altdata_ablation.py --protocols sequential_pipeline debate --regime frontier  --window b

# Per-agent attribution
python scripts/run_attribution.py --cell b__frontier__sequential_pipeline

# Robustness, tables, figures
python scripts/run_robustness.py
python scripts/build_paper_tables.py --window b
python scripts/build_paper_figures.py --window b

# TradingAgents harness check
python scripts/reproduce_tradingagents.py
```

Caches are SHA-256-keyed by canonicalised prompts and disk-persisted; re-runs after first-pass population are bit-identical and cost-zero on the LLM path.

## Appendix B. Evaluation-Criteria Checklist

A direct mapping of the rubric's special evaluation expectations to the paper's content:

| Expectation | Where in this paper |
|---|---|
| **Baseline comparison** — at least one simpler baseline | §9.2 (4 passive benchmarks); the matrix itself includes `single_agent`, `independent_ensemble`, `deterministic_only` |
| **Attribution / ablation** — which agents, signals, data sources matter | §10.1 (per-agent LOO); §10.2 (5-variant alt-data ablation); §10.3 (CBS) |
| **Temporal discipline** — when data became available; how to avoid lookahead | §4.2 (every source's lag policy); §6.2 (ChronoGPT pinning); §11.3 (reproducibility verification) |
| **Reproducibility** — prompts, configurations, assumptions, environment | §6.1 (prompt cache + fingerprints); §6.4 (prompt templates); Appendix A (full recipe) |
| **Transaction costs** | §7 (cost model); §11.1 (TC sensitivity table) |
| **Rolling / OOS evaluation** | §6.3 (3-year IS / 6-month OOS walk-forward) |
| **Risk-adjusted metrics** | §8 (Sharpe, Sortino, MDD); Tables 2, 3, 4 |
| **Subperiod / regime analysis** | §11.2 (NBER + VIX stratification, both honestly reported as N/A on this window) |
| **Limitations of data and design** | §13.3 (8 explicit limitations) |
