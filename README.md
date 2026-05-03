# PACT — Protocols for Agent Coordination in Trading

Master's project — Track 4 (Coordination & Attribution Research). The
research question, data sources, agent specs, ablation matrix, and paper
structure all live in `multi_agent_trading_paper_spec.md`. Read that first.

The contribution name comes from the headline ablation: 7 coordination
**protocols** × 2 LLM regimes, tested against single-agent and
no-communication ensemble baselines. PACT = the protocol-level study.

This README only documents how the code is wired.

## Layout

```
agents/                7 trading agents (per spec §4)
coordination/          7 protocols = headline ablation matrix (spec §6.2)
llm/                   GPT-4o + ChronoGPT clients (cached, prompt-hash keyed)
data/fetchers/         Temporal-discipline fetchers (ALFRED, EDGAR, GDELT, FOMC, prices)
data/cache/            On-disk raw-response cache
factors/               Deterministic factor library (momentum, GARCH, VaR)
portfolio/             Vol-targeted sizing + risk overlays (spec §5)
backtest/              Engine + walk-forward (spec §6.5)
evaluation/            Metrics, Ledoit-Wolf, BH, Shapley, regime stratification
configs/               Ablation matrices + per-agent prompts
tests/                 Smoke tests for wiring
```

## Setup

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
# optional alt-data deps
uv pip install -e ".[altdata]"
```

Required environment:
- `OPENAI_API_KEY` — frontier path only
- `FRED_API_KEY`   — ALFRED vintage queries
- `SEC_USER_AGENT` — e.g. `"Your Name your@email"` (SEC requires real contact)

## Run smoke tests

```bash
pytest -q
```

## Reproducibility (spec §8)

- All LLM responses cached as JSON keyed by SHA-256 of the canonicalized
  prompt (`llm/base.py::canonicalize_prompt`).
- Frontier model ID is pinned (default `gpt-4o-2024-11-20`); ChronoGPT
  pinned by HF revision (set in config — currently `null`, must be filled
  before publication).
- All raw fetcher responses cached in `data/cache/store/`.
- ALFRED fetcher returns first-release values only; never revised series.
- EDGAR fetcher exposes `effective_session_date` enforcing the 17:30-ET
  cutoff rule (filings after 17:30 → next session's open).
- "Fully reproducible" applies to the open-source path. Frontier path is
  "conditionally reproducible (snapshot dated [...])".

## Status

Foundation scaffolded: schemas, base agent, all 7 agents (technical, risk,
deterministic-only fully implemented; the others have factor schemas wired
and stub `decide` returning zero-direction views to unblock the harness),
all 7 coordination protocols, portfolio construction, backtest engine,
walk-forward, evaluation metrics, Ledoit-Wolf test, BH correction,
DAG-Shapley + LOO, regime stratification.

Next implementation steps follow spec §12:
1. Pre-register hypotheses on OSF.
2. Fill in real factor extraction in narrative_event, fundamentals_carry,
   macro_regime decide().
3. Set HF revision pin for ChronoGPT.
4. Reproduce TradingAgents-style baseline (±15% of reported metrics) to
   verify harness.
5. Run 14-cell coordination matrix on the Menos universe.
