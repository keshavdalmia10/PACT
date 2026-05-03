"""Cell #3 — Sequential 3-phase pipeline (spec §6.2).

Phase 1: Macro / screener (macro_regime + narrative_event in parallel)
Phase 2: Deep analysis (cross_asset_transmission, technical_trend, fundamentals_carry)
Phase 3: Risk + portfolio aggregation (risk_correlation → portfolio_manager)

Information flows downstream only — no debate, no voting.
"""

from __future__ import annotations

from datetime import date

from agents.base_agent import AgentDecision
from coordination.base import CoordinationProtocol, CoordinationResult


class SequentialPipelineProtocol(CoordinationProtocol):
    name = "sequential_pipeline"

    def __init__(self, agents, universe: tuple[str, ...]):
        super().__init__(agents)
        self.universe = universe

    def run(self, as_of: date) -> CoordinationResult:
        decisions: list[AgentDecision] = []

        # Phase 1
        macro = self.agents["macro_regime"].run(as_of)
        narrative = self.agents["narrative_event"].run(as_of)
        decisions.extend([macro, narrative])

        # Phase 2
        xat = self.agents["cross_asset_transmission"]
        if hasattr(xat, "set_upstream"):
            xat.set_upstream(macro, narrative)
        decisions.append(xat.run(as_of))
        decisions.append(self.agents["technical_trend"].run(as_of))
        decisions.append(self.agents["fundamentals_carry"].run(as_of))

        # Phase 3
        decisions.append(self.agents["risk_correlation"].run(as_of))
        pm = self.agents["portfolio_manager"]
        if hasattr(pm, "set_inputs"):
            pm.set_inputs(decisions)
        pm_decision = pm.run(as_of)

        return CoordinationResult(
            protocol=self.name,
            as_of=as_of,
            final_views=pm_decision.views,
            per_agent_decisions=decisions + [pm_decision],
        )
