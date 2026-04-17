"""
Routing pipeline internal data models.

Defines data structures used within the routing pipeline, complementing
the public API models (RoutingRequest, RoutingResponse, SelectedSkill)
in core/models.py.

Reference: RFC-03 Online Routing Gateway
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


# ============================================
# Query Processing Models
# ============================================


class ProcessedQuery(BaseModel):
    """Processed query after noise reduction and context enrichment.

    Output of QueryProcessor, input to EmbeddingService.
    """

    original: str = Field(..., description="Original raw query text")
    cleaned: str = Field(..., description="Cleaned query text")
    enriched: str = Field(..., description="Context-enriched query for embedding")
    intent_keywords: list[str] = Field(
        default_factory=list,
        description="Extracted intent category keywords",
    )
    previous_skills: list[str] = Field(
        default_factory=list,
        description="Previously used skills in this session",
    )
    environment: dict[str, Any] = Field(
        default_factory=dict,
        description="Environment context (git_repo, database_connected, etc.)",
    )


# ============================================
# Hybrid Retrieval Models
# ============================================


class SeedNode(BaseModel):
    """Seed node from semantic vector recall (ANN top-k).

    Output of SemanticSeedRecaller, input to GraphExpander.
    """

    skill_id: str = Field(..., description="Skill UID (namespace:action)")
    vector_id: str = Field(default="", description="Vector database primary key")
    similarity: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity to query")
    node_properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Node properties fetched from graph DB",
    )
    expansion_path: list[str] = Field(
        default_factory=list,
        description="Expansion path (filled during graph expansion)",
    )


class CandidateNode(BaseModel):
    """Candidate node in the candidate pool after hybrid retrieval.

    Tracks whether the node was a seed (depth=0) or discovered
    via graph expansion (depth>0).
    """

    skill_id: str = Field(..., description="Skill UID")
    similarity: float = Field(default=0.0, ge=0.0, le=1.0, description="Similarity to query")
    depth: int = Field(default=0, ge=0, description="Expansion depth (0 = seed)")
    is_seed: bool = Field(default=False, description="Whether this is a seed node")
    expansion_path: list[str] = Field(default_factory=list, description="BFS expansion path")
    edge_type: Optional[str] = Field(default=None, description="Incoming edge type (REQUIRES/ENHANCES)")
    edge_weight: float = Field(default=1.0, ge=0.0, description="Incoming edge weight")

    # Composite score (filled by ScoringEngine)
    score: float = Field(default=0.0, ge=0.0, description="Composite score")

    # Sub-scores for transparency
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Cosine similarity sub-score")
    pagerank_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Local PageRank sub-score")
    reliability_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Reliability sub-score")

    # Node properties from graph DB (for downstream use)
    version: str = Field(default="1.0.0", description="Skill version")
    intent_description: str = Field(default="", description="Intent description text")
    permissions: list[str] = Field(default_factory=list, description="Permission declarations")
    execution_success_rate: float = Field(default=1.0, ge=0.0, le=1.0, description="EWMA success rate")
    is_deprecated: bool = Field(default=False, description="Soft-delete flag")
    category: str = Field(default="", description="Skill category (e.g., domain_knowledge, code_analysis)")


class CandidatePool:
    """Mutable working structure storing all candidates from hybrid retrieval.

    Not a Pydantic model because it is heavily mutated during the pipeline
    and uses internal indexing data structures.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, CandidateNode] = {}
        self._depth_groups: dict[int, list[str]] = {}

    def add_node(self, node: CandidateNode) -> None:
        """Add a candidate node to the pool."""
        self.nodes[node.skill_id] = node
        if node.depth not in self._depth_groups:
            self._depth_groups[node.depth] = []
        self._depth_groups[node.depth].append(node.skill_id)

    def get_nodes_at_depth(self, depth: int) -> list[CandidateNode]:
        """Get all nodes at a given expansion depth."""
        skill_ids = self._depth_groups.get(depth, [])
        return [self.nodes[sid] for sid in skill_ids if sid in self.nodes]

    def get_all_nodes(self) -> list[CandidateNode]:
        """Get all candidate nodes."""
        return list(self.nodes.values())

    def get_seed_nodes(self) -> list[CandidateNode]:
        """Get all seed nodes (depth=0)."""
        return [n for n in self.nodes.values() if n.is_seed]

    def get_skill_ids(self) -> list[str]:
        """Get all skill IDs in the pool."""
        return list(self.nodes.keys())

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for logging/debugging."""
        return {
            "total_nodes": len(self.nodes),
            "seed_count": len(self.get_seed_nodes()),
            "depth_distribution": {
                str(d): len(ids) for d, ids in self._depth_groups.items()
            },
            "nodes": {sid: n.model_dump() for sid, n in self.nodes.items()},
        }


# ============================================
# Conflict Graph Models
# ============================================


class ConflictGraph:
    """Conflict graph for MWIS pruning.

    Nodes are skill IDs with their composite scores.
    Edges represent CONFLICTS_WITH or SUBSTITUTES relationships.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, float] = {}  # skill_id -> score
        self.conflict_edges: list[tuple[str, str, int]] = []  # (a, b, severity)
        self.substitute_edges: list[tuple[str, str, float]] = []  # (a, b, similarity)
        self._adjacency: dict[str, set[str]] = {}

    def add_node(self, skill_id: str, score: float) -> None:
        """Add a node with its composite score."""
        self.nodes[skill_id] = score
        if skill_id not in self._adjacency:
            self._adjacency[skill_id] = set()

    def add_conflict_edge(self, node_a: str, node_b: str, severity: int = 3) -> None:
        """Add a CONFLICTS_WITH edge."""
        self.conflict_edges.append((node_a, node_b, severity))
        self._ensure_adjacency(node_a, node_b)

    def add_substitute_edge(self, node_a: str, node_b: str, similarity: float = 0.8) -> None:
        """Add a SUBSTITUTES edge (also treated as conflict for MWIS)."""
        self.substitute_edges.append((node_a, node_b, similarity))
        self._ensure_adjacency(node_a, node_b)

    def has_conflict(self, node_a: str, node_b: str) -> bool:
        """Check if two nodes are adjacent in the conflict graph."""
        return node_b in self._adjacency.get(node_a, set())

    def get_neighbors(self, skill_id: str) -> set[str]:
        """Get all conflict neighbors of a node."""
        return self._adjacency.get(skill_id, set())

    def _ensure_adjacency(self, node_a: str, node_b: str) -> None:
        """Ensure both nodes exist in adjacency and add bidirectional edge."""
        if node_a not in self._adjacency:
            self._adjacency[node_a] = set()
        if node_b not in self._adjacency:
            self._adjacency[node_b] = set()
        self._adjacency[node_a].add(node_b)
        self._adjacency[node_b].add(node_a)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for logging/debugging."""
        return {
            "node_count": len(self.nodes),
            "conflict_edge_count": len(self.conflict_edges),
            "substitute_edge_count": len(self.substitute_edges),
            "nodes": self.nodes,
            "adjacency": {k: list(v) for k, v in self._adjacency.items()},
        }


# ============================================
# Scoring Configuration
# ============================================


class ScoringConfig(BaseModel):
    """Scoring engine hyperparameters.

    The composite score is:
        Score(n) = α * CosineSim + β * PageRank_local + γ * Reliability
    Then category_weight is applied as a multiplier:
        FinalScore(n) = Score(n) * category_weight(category(n))
    """

    alpha: float = Field(default=0.8, ge=0.0, le=1.0, description="Similarity weight (VR-first: similarity dominant)")
    beta: float = Field(default=0.1, ge=0.0, le=1.0, description="PageRank weight (VR-first: reduced structural weight)")
    gamma: float = Field(default=0.1, ge=0.0, le=1.0, description="Reliability weight (VR-first: reduced reliability weight)")
    category_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "domain_knowledge": 1.0,
            "debugging": 1.0,
            "code_analysis": 1.0,
            "testing": 1.0,
            "code_editing": 1.0,
            "project_navigation": 1.0,
            "dependency_management": 1.0,
            "git_operations": 1.0,
            "file_operations": 1.0,
            "environment": 1.0,
            "documentation": 1.0,
            "network_operations": 1.0,
        },
        description="Category-based score multiplier. All set to 1.0 (no artificial amplification — VR-first relies on similarity, not category bias).",
    )

    @model_validator(mode="after")
    def validate_weights_sum(self) -> "ScoringConfig":
        """Ensure α + β + γ ≈ 1.0."""
        total = self.alpha + self.beta + self.gamma
        if abs(total - 1.0) > 0.05:
            raise ValueError(f"Scoring weights must sum to ~1.0, got {total:.3f}")
        return self


# ============================================
# Context Assembly Models
# ============================================


class AssembledContext(BaseModel):
    """Assembled context output from the context assembler.

    Contains the final text to inject into the LLM prompt,
    along with metadata about which skills were included/skipped.
    """

    skills: list[str] = Field(..., description="Included skill IDs in topological order")
    skipped_skills: list[str] = Field(
        default_factory=list,
        description="Skill IDs skipped due to token budget",
    )
    total_tokens: int = Field(..., ge=0, description="Total token count including reserved")
    assembled_text: str = Field(..., description="Final assembled context text")
    budget_exceeded: bool = Field(
        default=False,
        description="Whether token budget was exceeded",
    )


# ============================================
# Routing Metrics
# ============================================


class RoutingMetrics(BaseModel):
    """Routing pipeline performance and quality metrics.

    Emitted by RoutingGateway for telemetry and experiment evaluation.
    """

    # Latency breakdown (milliseconds)
    query_processing_ms: int = Field(default=0, ge=0)
    embedding_ms: int = Field(default=0, ge=0)
    retrieval_ms: int = Field(default=0, ge=0)
    expansion_ms: int = Field(default=0, ge=0)
    scoring_ms: int = Field(default=0, ge=0)
    pruning_ms: int = Field(default=0, ge=0)
    assembly_ms: int = Field(default=0, ge=0)
    total_ms: int = Field(default=0, ge=0)

    # Pipeline counts
    seed_count: int = Field(default=0, ge=0, description="Number of seed nodes from ANN")
    expanded_count: int = Field(default=0, ge=0, description="Total nodes after graph expansion")
    conflict_count: int = Field(default=0, ge=0, description="Number of conflict edges found")
    pruned_count: int = Field(default=0, ge=0, description="Nodes removed by MWIS pruning")
    final_count: int = Field(default=0, ge=0, description="Final skill count after pruning")

    # Quality metrics
    skill_coverage: float = Field(default=0.0, ge=0.0, le=1.0, description="Fraction of relevant skills retrieved")
    dependency_correctness: float = Field(default=0.0, ge=0.0, le=1.0, description="Fraction of required deps included")
    conflict_resolution: float = Field(default=0.0, ge=0.0, le=1.0, description="Fraction of conflicts resolved")

    # Operational flags
    cache_hit: bool = Field(default=False, description="Whether cache was hit")
    fallback_used: bool = Field(default=False, description="Whether fallback mode was used")


# ============================================
# VR-First Architecture Models
# ============================================


class EnhancementResult(BaseModel):
    """VR-First 图增强层结果，记录 VR→Graph 的增量变化。

    Core invariant: when improved=False, final_ids MUST equal vr_seed_ids
    (fallback guarantee — never return worse than VR baseline).
    """

    vr_seed_ids: list[str] = Field(..., description="VR baseline skill IDs (ANN top-5)")
    expanded_ids: list[str] = Field(
        default_factory=list,
        description="1-hop expansion 新增的 skill IDs",
    )
    pruned_ids: list[str] = Field(
        default_factory=list,
        description="MWIS+VR protection pruning 移除的 skill IDs",
    )
    final_ids: list[str] = Field(..., description="最终入选的 skill IDs")
    improved: bool = Field(
        ...,
        description="图增强是否产生了有价值的变化",
    )
    enhancement_score: float = Field(
        default=0.0,
        ge=0.0,
        description="增量价值评分 (avg_score(expanded) - avg_score(vr_seed_only))",
    )

    @model_validator(mode="after")
    def validate_fallback_guarantee(self) -> "EnhancementResult":
        """GS ≥ VR guarantee: when not improved, final_ids MUST equal vr_seed_ids."""
        if not self.improved:
            assert set(self.final_ids) == set(self.vr_seed_ids), (
                f"Fallback guarantee violated: improved=False but final_ids != vr_seed_ids"
            )
        return self


class VRSeedProtectionConfig(BaseModel):
    """Configuration for VR seed protection during MWIS pruning.

    VR seed skills are protected from being removed by the MWIS pruner
    unless a higher-scoring VR seed replaces them. This ensures the
    GS ≥ VR guarantee at the conflict resolution stage.
    """

    enabled: bool = Field(
        default=True,
        description="Whether VR seed protection is active",
    )
    allow_vr_seed_replacement: bool = Field(
        default=False,
        description="Allow higher-scoring VR seeds to replace lower-scoring ones",
    )
    fallback_to_vr_baseline: bool = Field(
        default=True,
        description="Fall back to VR baseline when graph enhancement fails",
    )
