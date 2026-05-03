"""Coordination protocol interface.

Each cell of the headline 7×2 ablation matrix (spec §6.2) is a subclass
of `CoordinationProtocol`. The harness calls `run(as_of)` and gets back
the same `CoordinationResult` shape regardless of protocol.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

from agents.base_agent import AgentDecision, InstrumentView


@dataclass
class CoordinationResult:
    protocol: str
    as_of: date
    final_views: list[InstrumentView]
    per_agent_decisions: list[AgentDecision] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


class CoordinationProtocol(ABC):
    name: str = "base"

    def __init__(self, agents: dict[str, object]) -> None:
        # `agents` keyed by agent name; protocol picks what it needs.
        self.agents = agents

    @abstractmethod
    def run(self, as_of: date) -> CoordinationResult: ...
