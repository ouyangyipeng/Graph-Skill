"""Unit tests for routing data models (VR-First architecture).

Tests verify:
  - EnhancementResult data structure (VR-first enhancement tracking)
  - VRSeedProtectionConfig data structure (VR seed protection config)
  - Fallback guarantee validation (GS ≥ VR invariant)
  - Updated ScoringConfig defaults (α=0.8, β=0.1, γ=0.1)
"""

import pytest

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


class TestProcessedQuery:
    """Tests for ProcessedQuery model."""

    def test_basic_creation(self) -> None:
        pq = ProcessedQuery(
            original="I need to commit changes",
            cleaned="i need to commit changes",
            enriched="i need to commit changes context: git repository",
            intent_keywords=["git"],
            previous_skills=[],
            environment={"git_repo": True},
        )
        assert pq.original == "I need to commit changes"
        assert pq.cleaned == "i need to commit changes"
        assert "git repository" in pq.enriched
        assert pq.intent_keywords == ["git"]

    def test_defaults(self) -> None:
        pq = ProcessedQuery(
            original="test query",
            cleaned="test query",
            enriched="test query",
        )
        assert pq.intent_keywords == []
        assert pq.previous_skills == []
        assert pq.environment == {}


class TestSeedNode:
    """Tests for SeedNode model."""

    def test_basic_creation(self) -> None:
        sn = SeedNode(
            skill_id="git:commit",
            vector_id="vec-123",
            similarity=0.92,
        )
        assert sn.skill_id == "git:commit"
        assert sn.similarity == 0.92
        assert sn.expansion_path == []

    def test_similarity_bounds(self) -> None:
        with pytest.raises(Exception):
            SeedNode(skill_id="git:commit", similarity=1.5)
        with pytest.raises(Exception):
            SeedNode(skill_id="git:commit", similarity=-0.1)


class TestCandidateNode:
    """Tests for CandidateNode model."""

    def test_seed_node(self) -> None:
        cn = CandidateNode(
            skill_id="git:commit",
            similarity=0.9,
            depth=0,
            is_seed=True,
        )
        assert cn.is_seed is True
        assert cn.depth == 0
        assert cn.score == 0.0

    def test_expanded_node(self) -> None:
        cn = CandidateNode(
            skill_id="git:config",
            depth=1,
            is_seed=False,
            edge_type="REQUIRES",
            edge_weight=1.0,
        )
        assert cn.is_seed is False
        assert cn.edge_type == "REQUIRES"

    def test_score_defaults(self) -> None:
        cn = CandidateNode(skill_id="git:commit")
        assert cn.score == 0.0
        assert cn.similarity_score == 0.0
        assert cn.pagerank_score == 0.0
        assert cn.reliability_score == 1.0


class TestCandidatePool:
    """Tests for CandidatePool mutable container."""

    def test_add_and_retrieve(self) -> None:
        pool = CandidatePool()
        pool.add_node(CandidateNode(skill_id="a:b", depth=0, is_seed=True))
        pool.add_node(CandidateNode(skill_id="c:d", depth=1, is_seed=False))

        assert len(pool.nodes) == 2
        assert pool.get_all_nodes()[0].skill_id in ("a:b", "c:d")

    def test_get_nodes_at_depth(self) -> None:
        pool = CandidatePool()
        pool.add_node(CandidateNode(skill_id="a:b", depth=0, is_seed=True))
        pool.add_node(CandidateNode(skill_id="c:d", depth=0, is_seed=True))
        pool.add_node(CandidateNode(skill_id="e:f", depth=1, is_seed=False))

        depth_0 = pool.get_nodes_at_depth(0)
        depth_1 = pool.get_nodes_at_depth(1)
        assert len(depth_0) == 2
        assert len(depth_1) == 1

    def test_get_seed_nodes(self) -> None:
        pool = CandidatePool()
        pool.add_node(CandidateNode(skill_id="a:b", depth=0, is_seed=True))
        pool.add_node(CandidateNode(skill_id="c:d", depth=1, is_seed=False))

        seeds = pool.get_seed_nodes()
        assert len(seeds) == 1
        assert seeds[0].skill_id == "a:b"

    def test_get_skill_ids(self) -> None:
        pool = CandidatePool()
        pool.add_node(CandidateNode(skill_id="a:b"))
        pool.add_node(CandidateNode(skill_id="c:d"))

        ids = pool.get_skill_ids()
        assert set(ids) == {"a:b", "c:d"}

    def test_to_dict(self) -> None:
        pool = CandidatePool()
        pool.add_node(CandidateNode(skill_id="a:b", depth=0, is_seed=True))

        d = pool.to_dict()
        assert d["total_nodes"] == 1
        assert d["seed_count"] == 1

    def test_empty_pool(self) -> None:
        pool = CandidatePool()
        assert len(pool.get_all_nodes()) == 0
        assert len(pool.get_seed_nodes()) == 0
        assert pool.get_skill_ids() == []


class TestConflictGraph:
    """Tests for ConflictGraph."""

    def test_add_nodes(self) -> None:
        cg = ConflictGraph()
        cg.add_node("a:b", 0.9)
        cg.add_node("c:d", 0.7)
        assert len(cg.nodes) == 2

    def test_add_conflict_edge(self) -> None:
        cg = ConflictGraph()
        cg.add_node("a:b", 0.9)
        cg.add_node("c:d", 0.7)
        cg.add_conflict_edge("a:b", "c:d", severity=3)

        assert cg.has_conflict("a:b", "c:d")
        assert cg.has_conflict("c:d", "a:b")  # Bidirectional
        assert len(cg.conflict_edges) == 1

    def test_add_substitute_edge(self) -> None:
        cg = ConflictGraph()
        cg.add_node("a:b", 0.9)
        cg.add_node("c:d", 0.7)
        cg.add_substitute_edge("a:b", "c:d", similarity=0.85)

        assert cg.has_conflict("a:b", "c:d")
        assert len(cg.substitute_edges) == 1

    def test_no_conflict(self) -> None:
        cg = ConflictGraph()
        cg.add_node("a:b", 0.9)
        cg.add_node("c:d", 0.7)
        assert not cg.has_conflict("a:b", "c:d")

    def test_get_neighbors(self) -> None:
        cg = ConflictGraph()
        cg.add_node("a:b", 0.9)
        cg.add_node("c:d", 0.7)
        cg.add_node("e:f", 0.5)
        cg.add_conflict_edge("a:b", "c:d")
        cg.add_conflict_edge("a:b", "e:f")

        neighbors = cg.get_neighbors("a:b")
        assert neighbors == {"c:d", "e:f"}

    def test_to_dict(self) -> None:
        cg = ConflictGraph()
        cg.add_node("a:b", 0.9)
        cg.add_conflict_edge("a:b", "c:d")

        d = cg.to_dict()
        assert d["node_count"] == 1  # Only a:b was added as node
        assert d["conflict_edge_count"] == 1


class TestScoringConfig:
    """Tests for ScoringConfig validation (VR-First defaults)."""

    def test_default_weights_vr_first(self) -> None:
        """VR-First: default weights are α=0.8, β=0.1, γ=0.1."""
        config = ScoringConfig()
        assert config.alpha == 0.8  # VR-First: similarity dominant
        assert config.beta == 0.1   # VR-First: reduced structural weight
        assert config.gamma == 0.1  # VR-First: reduced reliability weight
        assert abs(config.alpha + config.beta + config.gamma - 1.0) < 0.001

    def test_custom_weights(self) -> None:
        """Test that custom weights are still accepted (sum ≈ 1.0)."""
        config = ScoringConfig(alpha=0.8, beta=0.1, gamma=0.1)
        assert abs(config.alpha + config.beta + config.gamma - 1.0) < 0.001

    def test_invalid_weights(self) -> None:
        """Weights that don't sum to ~1.0 should be rejected."""
        with pytest.raises(Exception):
            ScoringConfig(alpha=0.5, beta=0.5, gamma=0.5)  # Sum = 1.5

    def test_category_weights_all_1_0(self) -> None:
        """VR-First: all category_weights default to 1.0 (no artificial amplification)."""
        config = ScoringConfig()
        for category, weight in config.category_weights.items():
            assert weight == 1.0, (
                f"Category '{category}' has weight {weight}, expected 1.0 "
                "(VR-First: no category bias, similarity is dominant)"
            )

    def test_category_weights_has_standard_categories(self) -> None:
        """Verify that all standard skill categories are covered."""
        config = ScoringConfig()
        expected_categories = [
            "domain_knowledge", "debugging", "code_analysis",
            "testing", "code_editing", "project_navigation",
            "dependency_management", "git_operations",
            "file_operations", "environment", "documentation",
            "network_operations",
        ]
        for cat in expected_categories:
            assert cat in config.category_weights, (
                f"Missing category '{cat}' in category_weights"
            )


class TestAssembledContext:
    """Tests for AssembledContext."""

    def test_basic_creation(self) -> None:
        ctx = AssembledContext(
            skills=["a:b", "c:d"],
            skipped_skills=["e:f"],
            total_tokens=1500,
            assembled_text="<Skill>...</Skill>",
            budget_exceeded=True,
        )
        assert len(ctx.skills) == 2
        assert ctx.budget_exceeded is True

    def test_no_skip(self) -> None:
        ctx = AssembledContext(
            skills=["a:b"],
            total_tokens=500,
            assembled_text="text",
        )
        assert ctx.skipped_skills == []
        assert ctx.budget_exceeded is False


class TestRoutingMetrics:
    """Tests for RoutingMetrics."""

    def test_defaults(self) -> None:
        m = RoutingMetrics()
        assert m.total_ms == 0
        assert m.seed_count == 0
        assert m.cache_hit is False
        assert m.fallback_used is False

    def test_with_values(self) -> None:
        m = RoutingMetrics(
            total_ms=150,
            seed_count=5,
            expanded_count=12,
            conflict_count=3,
            pruned_count=2,
            final_count=10,
            skill_coverage=0.8,
            conflict_resolution=1.0,
        )
        assert m.total_ms == 150
        assert m.skill_coverage == 0.8


class TestEnhancementResult:
    """Tests for EnhancementResult (VR-First enhancement tracking)."""

    def test_basic_creation_improved(self) -> None:
        """Create EnhancementResult when graph enhancement improved results."""
        er = EnhancementResult(
            vr_seed_ids=["git:commit", "git:push"],
            expanded_ids=["git:config"],
            pruned_ids=["svn:commit"],
            final_ids=["git:commit", "git:push", "git:config"],
            improved=True,
            enhancement_score=0.05,
        )
        assert er.improved is True
        assert len(er.vr_seed_ids) == 2
        assert len(er.expanded_ids) == 1
        assert len(er.final_ids) == 3
        assert er.enhancement_score == 0.05

    def test_not_improved_fallback_guarantee(self) -> None:
        """GS ≥ VR guarantee: when not improved, final_ids MUST equal vr_seed_ids.

        This enforces the core invariant: never return worse than VR baseline.
        """
        er = EnhancementResult(
            vr_seed_ids=["git:commit", "git:push"],
            expanded_ids=[],
            pruned_ids=[],
            final_ids=["git:commit", "git:push"],  # MUST equal vr_seed_ids
            improved=False,
            enhancement_score=0.0,
        )
        assert set(er.final_ids) == set(er.vr_seed_ids)
        assert er.improved is False

    def test_fallback_guarantee_violation_raises(self) -> None:
        """Validation MUST reject final_ids != vr_seed_ids when improved=False.

        This is a safety check that enforces GS ≥ VR guarantee at the
        data structure level.
        """
        with pytest.raises(Exception):
            EnhancementResult(
                vr_seed_ids=["git:commit", "git:push"],
                expanded_ids=[],
                pruned_ids=[],
                final_ids=["git:commit"],  # MISSING git:push — violates guarantee
                improved=False,
                enhancement_score=0.0,
            )

    def test_enhancement_score_positive_when_improved(self) -> None:
        """When improved=True, enhancement_score should be positive."""
        er = EnhancementResult(
            vr_seed_ids=["git:commit"],
            expanded_ids=["git:config"],
            pruned_ids=["svn:commit"],
            final_ids=["git:commit", "git:config"],
            improved=True,
            enhancement_score=0.05,
        )
        assert er.improved is True
        assert er.enhancement_score > 0

    def test_enhancement_score_zero_when_not_improved(self) -> None:
        """When improved=False, enhancement_score is 0.0 (no value added).

        Note: EnhancementResult.enhancement_score has ge=0.0 constraint.
        When not improved, the score is 0.0 (not negative), indicating
        zero incremental value from graph expansion.
        """
        er = EnhancementResult(
            vr_seed_ids=["git:commit"],
            expanded_ids=[],
            pruned_ids=[],
            final_ids=["git:commit"],
            improved=False,
            enhancement_score=0.0,
        )
        assert er.improved is False
        assert er.enhancement_score == 0.0


class TestVRSeedProtectionConfig:
    """Tests for VRSeedProtectionConfig (VR seed protection configuration)."""

    def test_default_config(self) -> None:
        """Default config: protection enabled, no replacement, fallback to VR."""
        config = VRSeedProtectionConfig()
        assert config.enabled is True
        assert config.allow_vr_seed_replacement is False
        assert config.fallback_to_vr_baseline is True

    def test_custom_config(self) -> None:
        """Test custom VR seed protection configuration."""
        config = VRSeedProtectionConfig(
            enabled=True,
            allow_vr_seed_replacement=True,
            fallback_to_vr_baseline=True,
        )
        assert config.enabled is True
        assert config.allow_vr_seed_replacement is True
        assert config.fallback_to_vr_baseline is True

    def test_disabled_protection(self) -> None:
        """Test that protection can be disabled (for testing/debugging)."""
        config = VRSeedProtectionConfig(enabled=False)
        assert config.enabled is False

    def test_fallback_to_vr_baseline_default_true(self) -> None:
        """fallback_to_vr_baseline MUST default to True (GS ≥ VR guarantee)."""
        config = VRSeedProtectionConfig()
        assert config.fallback_to_vr_baseline is True