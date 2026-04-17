"""
GraphSkill routing engine for dynamic skill selection.

Implements RFC-03: Online Routing Gateway.
Provides topology-aware hybrid retrieval, MWIS conflict pruning,
and token-budget-controlled context assembly.

VR-First Architecture (Phase 6F):
  STEP 1: VR baseline retrieval — ANN top-5 (vector-only)
  STEP 2: Graph enhancement — 1-hop expansion + MWIS with VR protection
  STEP 3: Fallback guarantee — if enhancement ineffective, return VR baseline
  STEP 4: Context assembly — VR seed skills protected from truncation
"""

from graphskill.routing.models import (
    ProcessedQuery,
    SeedNode,
    CandidateNode,
    CandidatePool,
    ConflictGraph,
    ScoringConfig,
    AssembledContext,
    RoutingMetrics,
    EnhancementResult,
    VRSeedProtectionConfig,
)
from graphskill.routing.query_processor import QueryProcessor
from graphskill.routing.embedding_service import EmbeddingService
from graphskill.routing.hybrid_retriever import HybridRetriever
from graphskill.routing.scoring_engine import ScoringEngine
from graphskill.routing.conflict_pruner import (
    ConflictGraphBuilder,
    MWISPruner,
    ConflictPruner,
)
from graphskill.routing.context_assembler import (
    TopologicalSorter,
    TokenBudgetController,
    ContextAssembler,
)
from graphskill.routing.gateway import RoutingGateway

__all__ = [
    # Data models
    "ProcessedQuery",
    "SeedNode",
    "CandidateNode",
    "CandidatePool",
    "ConflictGraph",
    "ScoringConfig",
    "AssembledContext",
    "RoutingMetrics",
    "EnhancementResult",
    "VRSeedProtectionConfig",
    # Pipeline components
    "QueryProcessor",
    "EmbeddingService",
    "HybridRetriever",
    "ScoringEngine",
    "ConflictGraphBuilder",
    "MWISPruner",
    "ConflictPruner",
    "TopologicalSorter",
    "TokenBudgetController",
    "ContextAssembler",
    # Main gateway
    "RoutingGateway",
]
