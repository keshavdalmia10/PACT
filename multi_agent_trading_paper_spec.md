# Multi-Agent LLM Trading System — Master's Project Specification

**Track declaration:** Track 4 (Coordination & Attribution Research) primary. Track 2 (Menos AI Narrative-to-Portfolio) universe and benchmarks as the experimental setting.

**Constraint:** All data sources open-source. LLM stack mixed (open-weights ChronoGPT/ChronoBERT for contamination-clean path; one frontier API for capability ceiling, with full response caching).

**Goal:** Strongest possible research paper. Optimize for paper rigor over competition prize.

---

## 1. Research framing

### 1.1 Research question

> Does multi-agent coordination in LLM trading systems add value beyond a single-agent baseline and a no-communication ensemble of the same specialists, after controlling for transaction costs and lookahead/contamination bias?

### 1.2 Gaps addressed (from project brief)

1. **Coordination and attribution gap** — recent literature (Nguyen & Pham CPH survey; Zhang et al. "Stop Overvaluing MAD"; Li et al. FINSABER) calls out that coordination value-add is rarely tested against clean single-agent and no-communication baselines.
2. **Temporal-integrity / leakage gap** — most multi-agent finance papers don't control for LLM training-data contamination of the backtest period (Sarkar & Vafa 2024; ChronoBERT paper 2025).
3. **Reproducibility gap** — proprietary data, unstable prompts, missing environment controls.

(We do not directly address the multimodal-integration gap as the headline contribution; alt-data is tested as a secondary ablation axis.)

### 1.3 Headline pre-registered hypotheses

To be drafted as a separate OSF pre-registration document. Placeholder list:

- **H1**: Coordinated multi-agent systems produce higher net-of-cost Sharpe than the no-communication ensemble of the same specialists.
- **H2**: Coordination value-add disappears when transaction costs exceed a critical threshold (Coordination Breakeven Spread).
- **H3**: ChronoGPT-based agents underperform frontier-LLM agents by < 0.3 Sharpe on the post-cutoff window (contamination effect bounded).
- **H4**: Per-agent Shapley contribution is concentrated in 2–3 agents, not uniform across 7.
- **H5**: Adding signal-edge alt-data (attention + event probabilities) to the headline text-data stack adds at most marginal Sharpe.

---

## 2. Investment universe

11 instruments per Menos AI track specification, traded via liquid ETF/futures proxies.

| Exposure | Instrument | Notes |
|---|---|---|
| S&P 500 | SPY | Liquidity, history back to 1993 |
| Nasdaq 100 | QQQ | |
| Russell 2000 | IWM | |
| US 10Y Treasury | IEF | 7–10y Treasury ETF |
| US 2Y Treasury | SHY | |
| Gold | GLD | Spot proxy |
| WTI Oil | USO | Acknowledge contango drag in paper |
| DXY | UUP | Bullish-USD ETF |
| VIX | Used as regime indicator only, not a tradeable position. Document this. |
| MSCI EM | EEM | |
| Bitcoin | BTC spot pre-2024; IBIT post-2024 | Document the splice |

---

## 3. Data architecture

### 3.1 Final agent-data table (LOCKED)

| Agent | Primary | Secondary |
|---|---|---|
| Macro Regime | ALFRED (vintage), FOMC text | GDELT macro themes |
| Narrative/Event | GDELT GKG, EDGAR 8-Ks | Wikipedia pageviews, Google Trends, Polymarket |
| Cross-Asset Transmission | ALFRED + GDELT consumed jointly | — |
| Technical/Trend | Price data (yfinance/CRSP-style) | — |
| Fundamentals/Carry | EDGAR 10-K/Q, earnings transcripts | GitHub Archive, on-chain (BTC), NOAA (oil) |
| Risk/Correlation | Price data + macro | Polymarket (event risk) |
| Portfolio Manager | Aggregates the above | — |

### 3.2 Data sources — usage rules

#### ALFRED (vintage FRED)
- Use `fredapi.get_series_first_release()` or ALFRED vintage queries — **NEVER** revised series.
- Used by: Macro Regime Agent (primary), Cross-Asset Transmission Agent.

#### FOMC corpus (statements, minutes, speeches)
- Sources: federalreserve.gov; supplementary corpora on Kaggle/GitHub.
- Statements: at meeting end (precise time per Fed's published schedule).
- Minutes: 2 p.m. ET, exactly 3 weeks after the meeting (ALFRED Release ID 101).
- Speeches: at the time delivered.
- Used by: Macro Regime Agent (primary).

#### GDELT 2.0 GKG
- Free via Google BigQuery (`gdelt-bq.gdeltv2`) or direct download.
- Use file timestamp, NOT event date.
- Lag by 30 minutes for any intraday work.
- Used by: Narrative/Event Agent (primary), Macro Regime (secondary, macro themes only), Cross-Asset Transmission.

#### SEC EDGAR
- Full filings via SEC's own API at `data.sec.gov`. No third party.
- Use **EDGAR acceptance datetime UTC**, NOT filing date.
- Filings accepted after 17:30 ET attribute to next business day's open.
- 8-Ks → Narrative/Event Agent; 10-K/Q + transcripts → Fundamentals/Carry Agent.

#### Earnings transcripts
- Source: Hugging Face datasets (`kurry/sp500_earnings_transcripts`, MIT license), 2005–2025.
- **Cross-reference each transcript to its 8-K acceptance datetime on EDGAR.** Never trust dataset's own timestamp.
- Used by: Fundamentals/Carry Agent (primary).

#### Wikipedia pageviews
- Wikimedia REST API. Free, no key.
- Hourly since July 2015; daily since 2008.
- **Lag by 48 hours** (backfill stabilization).
- Pre-commit page list per instrument BEFORE looking at returns. Use log abnormal pageviews (today's log views minus 30-day average), not raw counts.
- Used by: Narrative/Event Agent (secondary).

#### Google Trends
- Library: `pytrends` (unofficial; expect rate limits).
- Weekly for windows >9 months; daily for windows ≤9 months.
- **Critical**: relative-scaling problem. Returns are normalized to max in query window. Use rolling-overlap-window technique to stitch annual queries (#1 reason Google Trends papers fail to replicate).
- `geo='US'` for US-focused signals.
- Lag by 48 hours.
- Used by: Narrative/Event Agent (secondary).

#### Polymarket (Gamma API)
- Free, no auth.
- Meaningful liquidity from late 2021. Headline data starts 2022.
- Filter for minimum daily volume (>$10K) and orderbook depth (>$5K).
- Use **trade timestamps**, not market-creation dates.
- Need historical orderbook snapshots — use open repo `Jon-Becker/prediction-market-analysis` parquet snapshots.
- Used by: Narrative/Event Agent (secondary), Risk/Correlation Agent (secondary).
- **History limitation**: only meaningful from 2022. See §6.4 two-window experimental design.

#### GitHub Archive
- BigQuery public dataset (`bigquery-public-data.github_repos`, `githubarchive.day`).
- Use **committer timestamp** (not author timestamp).
- Map ~20 large tech firms to GitHub orgs (NOT all 500 S&P firms — that's the trap).
- Compute weekly aggregate metrics (commits, contributors, releases, stars).
- Derive log-abnormal series (this week vs 13-week trailing average).
- **Scoped to QQQ specifically** (Nasdaq 100 is ~50% tech by weight; constituent overlap with SPY is large).
- Used by: Fundamentals/Carry Agent (secondary, equity-index instruments only).

#### On-chain BTC
- Sources: blockchain.com charts API, Etherscan free tier, Glassnode free-tier endpoints.
- Metrics: active addresses, transaction count/volume, exchange inflows/outflows, hashrate, MVRV, NUPL, SOPR, coin-days-destroyed, stablecoin supply, LTH/STH supply distribution.
- Block timestamps are reliable.
- **Scoped to BTC instrument only.** Does NOT inform views on equities or other instruments.
- Used by: Fundamentals/Carry Agent (secondary, BTC only).

#### NOAA weather
- NWS API (free, no key); NOAA Climate Data Online API.
- Heating-degree-days, hurricane tracks, precipitation.
- Use observation timestamps (reliable); for forecasts, use issuance time, not forecast valid time.
- **Scoped to USO instrument only.**
- Used by: Fundamentals/Carry Agent (secondary, oil only).

#### yfinance / price data
- Standard. Used by Technical/Trend Agent (primary), Risk/Correlation Agent (primary).

### 3.3 Sources DELIBERATELY excluded

- NewsAPI (paywall, not historically reproducible)
- Twitter/X (closed API since 2023)
- Bloomberg / Refinitiv / RavenPack / FactSet (proprietary)
- Satellite / geospatial (free Sentinel-2 imagery requires geospatial-engineering work out of scope)
- Reddit/Pushshift (limited to pre-2023; not headline)
- Kalshi (kept out for now; could add if Polymarket integration goes well)

---

## 4. Agent specifications

### 4.1 Per-agent factor extraction

Each agent extracts **structured factors** from its inputs, then uses LLM reasoning to combine factors into a per-instrument view. This is the rigorous "Approach B" — never dump raw text into the LLM context. Always extract structured factors first, log them, then feed factor summaries to the LLM.

#### Macro Regime Agent
**Factors extracted:**
- ALFRED first-release values for: fed funds rate, 10Y-2Y spread, CPI YoY (first release), unemployment, GDP growth (first release), industrial production
- Surprise vs consensus (where available from prior releases)
- FOMC tone score (hawkish/dovish, computed by LLM from statement/minutes text vs prior meeting)
- Forward-guidance change indicator
- Speech sentiment aggregated by speaker
- (Secondary) GDELT macro theme intensity

**Output**: regime classification (growth-up/down × inflation-up/down quadrant) + per-instrument view.

#### Narrative/Event Agent
**Factors extracted (16 total):**
1. GDELT event volume (log-normalized)
2. GDELT tone score
3. GDELT tone surprise (week-over-week change)
4. GDELT theme intensity (across instrument-relevant theme codes)
5. GDELT geographic concentration
6. GDELT event novelty
7. EDGAR 8-K filing volume
8. EDGAR 8-K item-type distribution
9. Earnings-surprise sentiment (Item 2.02 filings)
10. Guidance-change signal
11. (Secondary) Wikipedia abnormal attention
12. (Secondary) Wikipedia attention persistence
13. (Secondary) Google Trends abnormal level
14. (Secondary) Google Trends momentum
15. (Secondary) Polymarket event-implied probabilities
16. (Secondary) Polymarket probability change

**Output**: per-instrument narrative classification + view.

#### Cross-Asset Transmission Agent
**Inputs**: outputs from Macro Regime + Narrative/Event Agent + joint ALFRED+GDELT.
**Job**: reason about narrative→instrument transmission chains (e.g., "oil shock → inflation expectations up → 10Y yield up → IEF short → DXY up → EM equity down").
**Output**: cross-asset coherence check + adjusted per-instrument views.

#### Technical/Trend Agent
**Factors extracted:**
- Multi-horizon momentum (1m, 3m, 6m, 12m)
- Volatility regime (GARCH(1,1) forecast vs realized; classify high/normal/low)
- EWMA volatility
- Trend persistence indicators
- Cornish-Fisher VaR (fat-tail adjusted)
- Cross-sectional momentum rank within universe

**Output**: per-instrument technical view. **Pure price-derived — no text inputs by design.** This is one of the variables in the modality ablation; keeping it pure preserves attribution.

#### Fundamentals/Carry Agent
**Factors extracted:**
- For equity indices: aggregated P/E, forward earnings yield, revenue growth, FCF yield (from EDGAR 10-K/Q across constituents)
- For bonds: real yields, term premium, slope
- For gold: real-yield-vs-gold relationship, USD context
- For oil: EIA inventories (free), NOAA weather signals (HDD, hurricane, precipitation)
- For BTC: on-chain metrics (active addresses, exchange flows, MVRV, hashrate)
- For QQQ: GitHub Archive aggregate engineering velocity (commits, contributors, releases)
- Earnings-call-transcript-derived guidance/sentiment per quarter

**Output**: per-instrument fundamental/carry view.

#### Risk/Correlation Agent
**Factors extracted:**
- Rolling correlation matrix (60-day, 252-day)
- VIX-quartile regime classification
- Cross-sectional volatility
- Stress scenarios (drawdown under historical regime analogs)
- VaR (parametric and Cornish-Fisher)
- (Secondary) Polymarket-implied probabilities of macro tail events (recession, Fed surprise, geopolitical shock)

**Output**: per-instrument risk score + portfolio-level risk overlay.

#### Portfolio Manager Agent
**Job**: aggregate views from agents 1–6 according to the active coordination protocol (varies across ablation cells). Apply portfolio construction rules (§5).

**Output**: final per-instrument target weights.

### 4.2 Per-agent output schema (Pydantic)

Every agent outputs the same structure for each of the 11 instruments:

```python
class InstrumentView(BaseModel):
    instrument: str  # e.g., "SPY"
    direction: int  # -1, 0, +1
    conviction: float  # [0, 1]
    horizon: Literal["1w", "1m", "1q"]
    factors: dict[str, float]  # logged numeric factors
    rationale: str  # for attribution audit
```

---

## 5. Portfolio construction

### 5.1 Signal-to-position mapping

```
For each instrument i at rebalance t:
  raw_signal_i = aggregate_views_per_coordination_protocol({agent_views})
                 # output ∈ [-1, +1]
  
  vol_target_i = annual_vol_target / realized_vol_i
                 # vol-targeted sizing, target = 10% annual vol per instrument
  
  position_i = raw_signal_i × vol_target_i × cross_asset_risk_scaler
```

### 5.2 Constraints

- Sum of |position_i| capped at max_gross_leverage = 200%
- Per-instrument weight cap: 25% gross
- Cross-asset risk parity overlay: rescale to target portfolio vol of 12% annualized

### 5.3 Risk management

- Ex-ante portfolio vol target: 12% annualized
- Drawdown circuit-breaker: rolling 60-day drawdown > 15% → halve all positions for next 4 weeks
- Correlation regime detection: 30-day average pairwise correlation > 0.6 → reduce gross by 30%
- **No stop-losses in headline strategy** (introduces path-dependency that complicates attribution). Run a robustness version with stops.

### 5.4 Trading mechanics

- Starting capital: $1,000,000 (Menos benchmark)
- Transaction cost: 30 bps round-trip per Menos benchmark; sensitivity at 15/30/60 bps
- Slippage: linear in trade-size-as-fraction-of-ADV (Almgren-Chriss-style)
- Rebalance: **weekly** for headline; daily as robustness on one coordination condition
- Turnover cap: 50% gross per week

---

## 6. Experimental design

### 6.1 LLM dual-path (Option B from discussion)

**Open-source / contamination-clean path:**
- Primary: ChronoGPT (manelalab/chrono-gpt-v1-realtime on Hugging Face), pinned by HF commit hash
- Secondary encoder: ChronoBERT for sentiment/classification subtasks
- Optional: Llama 3.1 70B Instruct for "modern open-weights" comparison, post-cutoff sample only

**Frontier path:**
- **GPT-4o**, pinned to a specific dated model ID (e.g., `gpt-4o-2024-11-20`). Verify and lock the exact ID at experiment start; document in paper.
- OpenAI Python SDK (current repo already uses OpenAI-compatible client; minimal changes needed).
- **Strict post-cutoff sample window only.** Verify GPT-4o's documented training cutoff at submission time and start the OOS test window strictly after it.
- **Cache every API response to disk as JSON keyed by prompt hash (SHA-256 of canonicalized prompt + system message + temperature + seed).** Replay from cache; never re-call the API for the same prompt within the experiment.
- Document the date range over which all frontier API calls were made (state explicitly in paper: "All GPT-4o API calls were made between [date] and [date]").
- Set `temperature=0` and `seed=<fixed_int>` where supported for maximum determinism. Run 5 seeds per cell, report median + IQR.
- Cost-budget: estimate ~$3,000–$6,000 across the 14 frontier-path cells at weekly rebalance. Daily rebalance only as robustness on a single coordination condition to control cost.

### 6.2 Coordination protocol matrix (the headline ablation)

7 conditions × 2 LLM regimes = 14 cells:

| # | Coordination protocol | Description |
|---|---|---|
| 1 | Single-LLM monolith | One prompt, all data, one decision. The baseline TradingAgents/FinCon never properly publish. |
| 2 | Independent ensemble | Same N specialists, no communication, decisions averaged or majority-voted. The real test of coordination > parallelism. |
| 3 | Sequential pipeline | Existing 3-phase architecture (macro/screener → parallel deep analysis → risk/portfolio) |
| 4 | Hierarchical / manager-analyst | FinCon-style |
| 5 | Debate / bull-bear | TradingAgents-style |
| 6 | Deterministic-anchor only | Piotroski + GARCH + momentum, no LLM |
| 7 | LLM + deterministic anchor | LLM with anchor inputs |

Each cell run under both LLM regimes. Total: 14 cells.

### 6.3 Baselines (8 total)

1. Buy-and-hold equal-weighted 9-asset universe (Menos benchmark)
2. Risk-parity, monthly rebalance
3. 60/40 SPY/IEF
4. Fama-French 5-factor + momentum factor model alpha
5. Single-LLM monolith (matrix cell #1, doubles as baseline)
6. No-communication ensemble (matrix cell #2, doubles as baseline)
7. Deterministic anchor-only (matrix cell #6, doubles as baseline)
8. ARIMA / rule-based timing (FINSABER's surprising winner)

Baselines 5–7 are the intellectually critical ones missing from the published literature.

### 6.4 Two-window design (handles Polymarket history limitation)

- **Window A (full)**: 2010–2024 walk-forward, alt-data ablation runs WITHOUT Polymarket
- **Window B (modern)**: 2022–2024 sub-experiment, includes Polymarket
- Reported as two findings, not one

### 6.5 Walk-forward protocol

- Rolling 3-year IS / 6-month OOS windows
- No re-optimization on OOS data
- For ChronoGPT: training cutoff matched to test-period start, per HF commit-hash version
- For frontier LLM: only run on post-cutoff sample (verify cutoff with vendor at submission time)

### 6.6 Alt-data ablation (5 variants)

Cross-cutting axis. Run within the best-performing 1–2 coordination protocols (not all 7, for cost reasons):

1. **Text-only (headline minus secondary)**: GDELT + EDGAR + FOMC + transcripts + ALFRED. No Wikipedia, no Google Trends, no Polymarket, no GitHub Archive, no on-chain, no NOAA.
2. **+ Attention data**: add Wikipedia + Google Trends to Narrative/Event Agent.
3. **+ Event probabilities**: add Polymarket to Narrative/Event and Risk/Correlation Agents (Window B only).
4. **+ Instrument-specific**: add GitHub Archive (QQQ) + on-chain (BTC) + NOAA (oil) to Fundamentals/Carry Agent.
5. **Full alt-data stack**: all secondary sources on.

### 6.7 Per-agent attribution

- DAG-Shapley approximation (per HiveMind/arXiv 2512.06432) for per-agent contribution. Reduces LLM calls by >80% vs full Shapley.
- Leave-one-out across the 7 specialists as a sanity check.

### 6.8 Additional ablations

- **Communication-channel ablation**: replace agent messages with structured numeric summaries vs. free-text vs. no message
- **Memory ablation**: with/without FinMem-style layered memory
- **Anchor ablation**: deterministic pre-scores in/out
- **Modality ablation**: text-only / fundamentals-only / technical-only / all

### 6.9 Robustness

- Cost sensitivity: 15 / 30 / 60 bps round-trip
- Rebalance frequency: daily / weekly / monthly
- Regime stratification: NBER recessions + VIX-quartile
- Seed sensitivity: 5 runs per cell, report median + IQR

### 6.10 Statistical inference

- Ledoit-Wolf robust Sharpe-ratio test for pairwise comparisons (cited by ChronoBERT paper as standard)
- Benjamini-Hochberg correction for multiple comparisons
- Coordination Breakeven Spread (CBS) per Nguyen & Pham as a primary attribution metric
- Regime-stratified Sharpe à la FINSABER

---

## 7. Temporal-discipline checklist

**Mandatory protocol — appears as a section in the paper.**

1. Test period strictly after frontier-LLM training cutoff (verified at submission). For ChronoGPT runs, training cutoff matched to test-period start.
2. All macro data via ALFRED first-release vintages. **NEVER revised series.**
3. EDGAR events keyed off acceptance-datetime UTC. Filings after 17:30 ET → next business day's open.
4. GDELT GKG lagged 30 minutes. Daily aggregates use prior-day close-to-close.
5. Earnings transcripts attributed to corresponding 8-K filing time, not call time.
6. Wikipedia pageviews lagged 48 hours.
7. Google Trends lagged 48 hours; rolling-overlap-window normalization for multi-year stitching.
8. Polymarket data uses trade timestamps, not market-creation dates.
9. Universe constructed point-in-time (delisted tickers retained until delisting date; index constituents reconstructed from EDGAR DEF 14A/N-Q quarterly filings).
10. Walk-forward 3y IS / 6m OOS. No re-optimization on OOS.
11. Transaction costs: 30 bps round-trip per Menos; sensitivity at 15/30/60 bps.
12. Slippage: linear in trade-size-as-fraction-of-ADV.

---

## 8. Reproducibility checklist

**Mandatory protocol — appears as a section in the paper.**

- All LLM prompts, temperatures, seeds, full message histories logged
- LLM versions pinned: GPT-4o by dated API model ID (e.g., `gpt-4o-2024-11-20`); ChronoGPT pinned by Hugging Face commit hash
- Containerized environment (Docker + uv lockfile)
- All data fetchers cache raw responses with timestamps; pipeline deterministic on second run
- Backtest engine: `vectorbt` or `nautilus-trader` (NOT custom). Configs as code.
- Pre-register ablation matrix and primary hypotheses on OSF BEFORE OOS window opens
- Code released MIT/Apache. Weights not required (all LLMs are public).
- README with one-command reproduction target
- GPT-4o API responses cached as JSON keyed by SHA-256 prompt hash. Replay from cache.
- Document date range of all GPT-4o API calls in paper
- For GPT-4o calls: `temperature=0`, fixed `seed`, log `system_fingerprint` returned by API

**Honest framing**: "Fully reproducible" applies to the open-source path. "Conditionally reproducible (snapshot dated [date])" applies to the frontier path. State this explicitly.

---

## 9. Repo structure (target)

```
project_root/
├── agents/
│   ├── __init__.py
│   ├── base_agent.py
│   ├── macro_regime.py
│   ├── narrative_event.py
│   ├── cross_asset_transmission.py
│   ├── technical_trend.py
│   ├── fundamentals_carry.py
│   ├── risk_correlation.py
│   └── portfolio_manager.py
├── coordination/
│   ├── __init__.py
│   ├── single_agent.py          # Cell #1
│   ├── independent_ensemble.py  # Cell #2
│   ├── sequential_pipeline.py   # Cell #3
│   ├── hierarchical.py          # Cell #4
│   ├── debate.py                # Cell #5
│   ├── deterministic_only.py    # Cell #6
│   └── llm_plus_anchor.py       # Cell #7
├── llm/
│   ├── __init__.py
│   ├── gpt4o_client.py          # OpenAI SDK, cached API calls, prompt-hash keyed
│   └── chronogpt_client.py      # Local HF inference
├── data/
│   ├── fetchers/
│   │   ├── alfred.py
│   │   ├── edgar.py
│   │   ├── gdelt.py
│   │   ├── fomc.py
│   │   ├── transcripts.py
│   │   ├── wikipedia.py
│   │   ├── google_trends.py
│   │   ├── polymarket.py
│   │   ├── github_archive.py
│   │   ├── onchain_btc.py
│   │   └── noaa.py
│   ├── factors/                  # Factor extraction logic per agent
│   ├── cache/                    # Raw response cache
│   └── universe.py               # Point-in-time universe construction
├── factors/                      # Deterministic factor library (Piotroski, GARCH, momentum, etc.)
├── portfolio/
│   ├── construction.py           # Signal→position, vol-targeting
│   └── risk_overlays.py          # Drawdown circuit-breaker, correlation regime
├── backtest/
│   ├── engine.py                 # vectorbt or nautilus-trader wrapper
│   └── walk_forward.py
├── evaluation/
│   ├── metrics.py                # Sharpe, Sortino, MDD, turnover, CBS
│   ├── statistical_tests.py      # Ledoit-Wolf, BH correction
│   ├── attribution.py            # DAG-Shapley, leave-one-out
│   └── regime_stratification.py
├── configs/
│   ├── ablation_matrix.yaml      # 14-cell coordination matrix
│   ├── altdata_ablation.yaml     # 5-variant alt-data matrix
│   └── prompts/                  # Per-agent prompt templates
├── tests/
├── docs/
│   ├── temporal_discipline.md
│   └── reproducibility.md
├── pyproject.toml
├── Dockerfile
├── uv.lock
└── README.md
```

---

## 10. Paper structure (locked)

Per brief's recommended structure:

| Section | Content |
|---|---|
| Title Page | Track 4 (Coordination & Attribution), Track 2 universe |
| Abstract | ~250 words: gap → method → ablation matrix → finding → contribution |
| Introduction | Four gaps; preview which addressed |
| Literature Review | TradingAgents, FinCon, FinMem, FinAgent, HedgeAgents, MarketSenseAI 2.0; FINSABER, "Stop Overvaluing MAD", CPH; ChronoBERT, Sarkar & Vafa |
| Research Gap and Hypotheses | 3 gaps + H1–H5 |
| Data and Investment Universe | Menos universe + ETF mapping + 2010–2024 walk-forward + temporal-discipline protocol |
| Multi-Agent Architecture | 7 agents + 7 coordination protocols + dual LLM regime |
| Methodology | Factor extraction, signal aggregation per protocol, signal-to-position mapping, Pydantic schemas |
| Portfolio Construction and Risk Management | Vol-targeting, gross leverage cap, drawdown circuit-breaker, correlation regime, transaction costs |
| Backtesting and Evaluation Design | Walk-forward, dual LLM regime, Ledoit-Wolf + BH, regime-stratified |
| Results | 7×2 ablation matrix as headline figure; per-protocol Sharpe/Sortino/MDD/turnover/CBS table |
| Attribution and Ablation Analysis | DAG-Shapley + leave-one-out + comm channel + memory + anchor + modality + alt-data |
| Robustness Checks | Cost sensitivity, rebalance frequency, regime stratification, seed sensitivity |
| Discussion and Limitations | What the matrix tells us; fragility findings; generalization caveats |
| Conclusion | 1–2 paragraphs |
| References | All cited papers + own additions |
| Appendix | Full prompt corpus, message logs, raw API response date range, per-cell metrics |

**Word limit: 7,000.**

---

## 11. Key papers to cite

### Multi-agent LLM trading (the architectures we compare against)
- Xiao, Sun, Luo, Wang. **TradingAgents: Multi-Agents LLM Financial Trading Framework.** arXiv 2412.20138 (Dec 2024).
- Yu et al. **FinCon: A Synthesized LLM Multi-Agent System with Conceptual Verbal Reinforcement.** NeurIPS 2024 / arXiv 2407.06567.
- Yu et al. **FinMem: A Performance-Enhanced LLM Trading Agent with Layered Memory and Character Design.** AAAI Spring Symposium 2024 / arXiv 2311.13743.
- Zhang et al. **FinAgent.** 2024.
- Li et al. **HedgeAgents: A Balanced-aware Multi-agent Financial Trading System.** WWW 2025 / arXiv 2502.13165.
- Fatouros et al. **MarketSenseAI 2.0.** arXiv 2502.00415.

### Critiques / methodology (the gap-defining papers)
- Li, Kim, Cucuringu, Ma. **Can LLM-based Financial Investing Strategies Outperform the Market in Long Run? (FINSABER).** arXiv 2505.07078, KDD'26.
- Nguyen & Pham. **Toward Reliable Evaluation of LLM-Based Financial Multi-Agent Systems: Taxonomy, Coordination Primacy, and Cost Awareness.** arXiv 2603.27539.
- Zhang et al. **Stop Overvaluing Multi-Agent Debate — We Must Rethink Evaluation and Embrace Model Heterogeneity.** arXiv 2502.08788.

### Lookahead bias and contamination
- Sarkar & Vafa. **Lookahead Bias in Pretrained Language Models.** SSRN 4754678 (2024); ICML 2025 DIG-BUGS workshop.
- He, Lv, Manela, Wu. **Chronologically Consistent Large Language Models (ChronoBERT/ChronoGPT).** arXiv 2502.21206 (2025).
- Yan, Tang, Gao, Jiang, Lu. **DatedGPT: Preventing Lookahead Bias in Large Language Models with Time-Aware Pretraining.** arXiv 2603.11838.
- Shah, Ye, Jaskowski, Xu, Chava. **Beyond the Reported Cutoff: Where Large Language Models Fall Short on Financial Knowledge.** arXiv 2504.00042.
- Lopez-Lira, Tang, Zhu. **Can ChatGPT Forecast Stock Price Movements?** (2025 update).

### Alt-data
- Behrendt & Zimmermann. **Wikipedia Search Momentum and Stock Returns.** SSRN 3220053.
- Da, Engelberg, Gao. **In Search of Attention.** Journal of Finance, 2011.
- Buz & de Melo. **WSB and Pushshift archives.** arXiv 2301.00170 (2023).

### Attribution
- HiveMind / DAG-Shapley. arXiv 2512.06432.

---

## 12. Implementation priority order

Recommended order of work:

1. **Pre-register hypotheses on OSF** (1 day; do BEFORE touching data)
2. **Build temporal-discipline data layer** (3 weeks): ALFRED, EDGAR, GDELT, FOMC corpus, transcripts. Wikipedia + Google Trends + Polymarket as secondary.
3. **Refactor existing repo** into config-driven harness with coordination protocol as swappable layer (1 week)
4. **Set up dual LLM backbones**: frontier API with response caching + local ChronoGPT/ChronoBERT inference (1 week)
5. **Reproduce TradingAgents-style baseline** (1 week) to verify harness correctness — must reproduce within ±15% of reported metrics
6. **Run 14-cell coordination matrix** on Menos universe, walk-forward 2018–2024 (2 weeks compute + monitoring)
7. **Run per-agent leave-one-out + DAG-Shapley** (1 week)
8. **Run 5-variant alt-data ablation** (1 week)
9. **Robustness**: regime stratification, cost sensitivity, rebalance frequency (1 week)
10. **Write paper + polish reproducibility artifact** (2 weeks)

---

## 13. Hard caveats

1. **Polymarket only has meaningful history from 2022.** Two-window experimental design handles this.
2. **Google Trends rolling-overlap-window normalization is the #1 implementation pitfall.** Document carefully.
3. **LLM API non-determinism**: even at temperature 0, frontier APIs are not perfectly deterministic. Cache responses, run 5 seeds per cell, report median + IQR.
4. **Cost-budget the ablation matrix up front.** 14 cells × 7 years walk-forward × ~20 LLM calls/decision × weekly decisions × 11 instruments hits low-five-figure API bills. Weekly headline; daily as robustness on subset only.
5. **If frontier-LLM contamination appears bounded** (consistent with ChronoBERT findings), pre-register that as a possible result rather than a failure.
6. **GitHub Archive scoped to QQQ only.** Do not try to map all 500 S&P firms — that's the trap.
7. **Wikipedia and Google Trends page/query lists must be pre-committed** before looking at returns. P-hacking risk otherwise.
8. **VIX is a regime indicator, NOT a tradeable position** in our universe. Document this in the methodology.
9. **TradingAgents' published Sharpe > 6 is on a 3-month, 5-stock window.** Do not benchmark against headline numbers from the literature uncritically; cite the FINSABER warning ("simple models like ARIMA or rule-based systems often outperform LLMs on risk-adjusted metrics").
10. **The "Bian et al." reference in the project brief could not be confirmed.** Closest match is R&D-Agent-Quant (Li et al., MSRA, arXiv 2505.15155), which is constructive not critical. Confirm with instructor.
