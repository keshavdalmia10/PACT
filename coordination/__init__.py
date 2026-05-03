from coordination.base import CoordinationProtocol, CoordinationResult
from coordination.debate import DebateProtocol
from coordination.deterministic_only import DeterministicOnlyProtocol
from coordination.hierarchical import HierarchicalProtocol
from coordination.independent_ensemble import IndependentEnsembleProtocol
from coordination.llm_plus_anchor import LLMPlusAnchorProtocol
from coordination.sequential_pipeline import SequentialPipelineProtocol
from coordination.single_agent import SingleAgentProtocol

REGISTRY = {
    "single_agent": SingleAgentProtocol,
    "independent_ensemble": IndependentEnsembleProtocol,
    "sequential_pipeline": SequentialPipelineProtocol,
    "hierarchical": HierarchicalProtocol,
    "debate": DebateProtocol,
    "deterministic_only": DeterministicOnlyProtocol,
    "llm_plus_anchor": LLMPlusAnchorProtocol,
}

__all__ = [
    "CoordinationProtocol",
    "CoordinationResult",
    "DebateProtocol",
    "DeterministicOnlyProtocol",
    "HierarchicalProtocol",
    "IndependentEnsembleProtocol",
    "LLMPlusAnchorProtocol",
    "REGISTRY",
    "SequentialPipelineProtocol",
    "SingleAgentProtocol",
]
