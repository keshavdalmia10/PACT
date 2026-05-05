"""Shared helpers for driver scripts (spec §12 deliverable: analysis-output codes).

- `RESULTS_ROOT`, `RAW_DIR`, `TABLES_DIR`, `FIGURES_DIR`: artifact locations
- `build_agents`: instantiates the 7-agent dict for a given universe / LLM
- `build_protocol`: instantiates a coordination protocol from its registry key
- `build_llm_client`: open-source vs frontier regime
- `cell_id` / `cell_dir`: deterministic naming for ablation cells
- `save_backtest_result` / `load_backtest_result`: parquet+JSON serialization
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from agents.cross_asset_transmission import CrossAssetTransmissionAgent
from agents.fundamentals_carry import FundamentalsCarryAgent
from agents.macro_regime import MacroRegimeAgent
from agents.narrative_event import NarrativeEventAgent
from agents.portfolio_manager import PortfolioManagerAgent
from agents.risk_correlation import RiskCorrelationAgent
from agents.technical_trend import TechnicalTrendAgent
from backtest.engine import BacktestResult
from coordination import REGISTRY as PROTOCOL_REGISTRY
from coordination.base import CoordinationProtocol
from pact_logging import get_logger

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_ROOT = REPO_ROOT / "results"
RAW_DIR = RESULTS_ROOT / "raw"
TABLES_DIR = RESULTS_ROOT / "tables"
FIGURES_DIR = RESULTS_ROOT / "figures"
for _d in (RAW_DIR, TABLES_DIR, FIGURES_DIR):
    _d.mkdir(parents=True, exist_ok=True)

CONFIG_DIR = REPO_ROOT / "configs"


def load_config(name: str) -> dict:
    path = CONFIG_DIR / name
    with path.open() as f:
        return yaml.safe_load(f)


# Protocols that need their own llm_client kwarg (separate from the agents' LLM).
_PROTOCOLS_NEEDING_LLM = {"single_agent", "debate", "llm_plus_anchor"}


def build_agents(llm_client, universe: tuple[str, ...]) -> dict[str, object]:
    """Instantiate the full 7-agent set keyed by spec name.

    Risk agent does not take directional views (spec §4.7) but is still
    constructed so protocols that rely on it for scaling have access.
    """
    return {
        "macro_regime": MacroRegimeAgent(llm_client, universe),
        "narrative_event": NarrativeEventAgent(llm_client, universe),
        "cross_asset_transmission": CrossAssetTransmissionAgent(llm_client, universe),
        "technical_trend": TechnicalTrendAgent(llm_client, universe),
        "fundamentals_carry": FundamentalsCarryAgent(llm_client, universe),
        "risk_correlation": RiskCorrelationAgent(llm_client, universe),
        "portfolio_manager": PortfolioManagerAgent(llm_client, universe),
    }


def build_protocol(
    key: str,
    agents: dict[str, object],
    llm_client,
    universe: tuple[str, ...],
) -> CoordinationProtocol:
    """Instantiate a coordination protocol from its registry key."""
    cls = PROTOCOL_REGISTRY[key]
    if key in _PROTOCOLS_NEEDING_LLM:
        return cls(agents=agents, llm_client=llm_client, universe=universe)
    return cls(agents=agents, universe=universe)


def build_llm_client(regime: str, offline: bool = False, cutoff_year: int | None = None):
    """Build the LLM client for a regime, or None for `none` regime.

    `cutoff_year` only applies to ChronoGPT and selects the contamination-
    clean yearly checkpoint. Defaults to the latest available checkpoint when
    not specified. For full contamination cleanliness across a multi-year
    walk-forward, swap the client per rebalance via
    `ChronoGPTClient.for_decision_year(year)`.
    """
    if regime == "none":
        return None
    if regime == "open_source":
        from llm.chronogpt_client import ChronoGPTClient

        if cutoff_year is None:
            return ChronoGPTClient(offline=offline)
        return ChronoGPTClient(cutoff_year=cutoff_year, offline=offline)
    if regime == "frontier":
        from llm.gpt4o_client import GPT4oClient

        return GPT4oClient(offline=offline)
    raise ValueError(f"unknown regime: {regime}")


def cell_id(window: str, regime: str, protocol: str) -> str:
    return f"{window}__{regime}__{protocol}"


def cell_dir(window: str, regime: str, protocol: str) -> Path:
    d = RAW_DIR / cell_id(window, regime, protocol)
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_backtest_result(out_dir: Path, result: BacktestResult, meta_extra: dict) -> None:
    """Persist a backtest cell's artifacts: equity, returns, turnover, weights, meta."""
    result.equity.to_frame("equity").to_parquet(out_dir / "equity.parquet")
    result.returns.to_frame("returns").to_parquet(out_dir / "returns.parquet")
    result.turnover.to_frame("turnover").to_parquet(out_dir / "turnover.parquet")
    result.weights.to_parquet(out_dir / "weights.parquet")
    meta = {
        **{k: _jsonable(v) for k, v in result.metadata.items()},
        **meta_extra,
        "saved_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    with (out_dir / "metadata.json").open("w") as f:
        json.dump(meta, f, indent=2, default=str)


def load_backtest_result(out_dir: Path) -> dict:
    """Load a saved cell. Returns dict with series + metadata."""
    return {
        "equity": pd.read_parquet(out_dir / "equity.parquet")["equity"],
        "returns": pd.read_parquet(out_dir / "returns.parquet")["returns"],
        "turnover": pd.read_parquet(out_dir / "turnover.parquet")["turnover"],
        "weights": pd.read_parquet(out_dir / "weights.parquet"),
        "metadata": json.loads((out_dir / "metadata.json").read_text()),
    }


def _jsonable(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v
