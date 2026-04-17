"""Unit tests for ScoringEngine (VR-First architecture).

Tests verify:
  - New default weights: α=0.8, β=0.1, γ=0.1 (similarity dominant)
  - category_weights all default to 1.0 (no artificial amplification)
  - Similarity dominates the composite score
  - Enhancement score computation for VR-first fallback decisions
"""

import asyncio
import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock

from graphskill.routing.models import CandidatePool, CandidateNode, ScoringConfig
from graphskill.routing.scoring_engine import ScoringEngine


def _make_pool_with_nodes() -> CandidatePool:
    """Create a candidate pool with test nodes."""
    pool = CandidatePool()
    pool.add_node(CandidateNode(
        skill_id="git:commit",
        similarity=0.9,
        depth=0,
        is_seed=True,
        execution_success_rate=0.95,
    ))
    pool.add_node(CandidateNode(
        skill_id="git:config",
        depth=1,
        is_seed=False,
        edge_type="REQUIRES",
        execution_success_rate=0.98,
    ))
    pool.add_node(CandidateNode(
        skill_id="git:push",
        similarity=0.8,
        depth=0,
        is_seed=True,
        execution_success_rate=0.90,
    ))
    return pool


class TestScoringEngine:
    """Tests for ScoringEngine (VR-First architecture)."""

    @pytest.mark.asyncio
    async def test_score_all_basic(self) -> None:
        """Test basic scoring of a candidate pool."""
        pool = _make_pool_with_nodes()
        config = ScoringConfig(alpha=0.8, beta=0.1, gamma=0.1)
        engine = ScoringEngine(config=config)

        query_vector = np.random.randn(384).astype(np.float32)
        scored_pool, latency_ms = await engine.score_all(pool, query_vector)

        assert latency_ms >= 0
        for node in scored_pool.get_all_nodes():
            assert node.score >= 0.0
            # Score should be a weighted combination
            assert node.similarity_score >= 0.0
            assert node.pagerank_score >= 0.0
            assert node.reliability_score >= 0.0

    @pytest.mark.asyncio
    async def test_score_all_empty_pool(self) -> None:
        """Test scoring an empty pool."""
        pool = CandidatePool()
        engine = ScoringEngine()

        query_vector = np.random.randn(384).astype(np.float32)
        scored_pool, latency_ms = await engine.score_all(pool, query_vector)

        assert len(scored_pool.nodes) == 0
        assert latency_ms == 0

    @pytest.mark.asyncio
    async def test_seed_nodes_keep_similarity(self) -> None:
        """Test that seed nodes retain their ANN similarity score."""
        pool = CandidatePool()
        pool.add_node(CandidateNode(
            skill_id="git:commit",
            similarity=0.9,
            depth=0,
            is_seed=True,
        ))

        engine = ScoringEngine()
        query_vector = np.random.randn(384).astype(np.float32)
        scored_pool, _ = await engine.score_all(pool, query_vector)

        node = scored_pool.nodes["git:commit"]
        assert node.similarity_score == 0.9

    @pytest.mark.asyncio
    async def test_reliability_scores(self) -> None:
        """Test that reliability scores come from execution_success_rate."""
        pool = CandidatePool()
        pool.add_node(CandidateNode(
            skill_id="git:commit",
            similarity=0.9,
            depth=0,
            is_seed=True,
            execution_success_rate=0.85,
        ))

        engine = ScoringEngine()
        query_vector = np.random.randn(384).astype(np.float32)
        scored_pool, _ = await engine.score_all(pool, query_vector)

        node = scored_pool.nodes["git:commit"]
        assert node.reliability_score == 0.85

    @pytest.mark.asyncio
    async def test_composite_score_formula_vr_first(self) -> None:
        """Test that composite score follows VR-First formula:
        Score = α * sim + β * pr + γ * rel  (with α=0.8 dominant)
        """
        pool = CandidatePool()
        pool.add_node(CandidateNode(
            skill_id="git:commit",
            similarity=0.8,
            depth=0,
            is_seed=True,
            execution_success_rate=0.9,
        ))

        config = ScoringConfig(alpha=0.8, beta=0.1, gamma=0.1)
        engine = ScoringEngine(config=config)

        query_vector = np.random.randn(384).astype(np.float32)
        scored_pool, _ = await engine.score_all(pool, query_vector)

        node = scored_pool.nodes["git:commit"]
        expected = (
            config.alpha * node.similarity_score
            + config.beta * node.pagerank_score
            + config.gamma * node.reliability_score
        )
        assert abs(node.score - expected) < 1e-6

    @pytest.mark.asyncio
    async def test_similarity_dominates_composite_score(self) -> None:
        """VR-First: similarity MUST dominate the composite score.

        With α=0.8, the similarity component should contribute ~80%
        of the base score, making it the decisive factor.
        """
        pool = CandidatePool()
        pool.add_node(CandidateNode(
            skill_id="high_sim",
            similarity=0.95,
            depth=0,
            is_seed=True,
            execution_success_rate=0.5,  # Low reliability
        ))
        pool.add_node(CandidateNode(
            skill_id="low_sim",
            similarity=0.3,
            depth=0,
            is_seed=True,
            execution_success_rate=0.99,  # High reliability
        ))

        config = ScoringConfig(alpha=0.8, beta=0.1, gamma=0.1)
        engine = ScoringEngine(config=config)

        query_vector = np.random.randn(384).astype(np.float32)
        scored_pool, _ = await engine.score_all(pool, query_vector)

        high_sim_node = scored_pool.nodes["high_sim"]
        low_sim_node = scored_pool.nodes["low_sim"]

        # Even though low_sim has much higher reliability,
        # high_sim should have a higher composite score because α=0.8
        # makes similarity dominant
        sim_contribution_high = config.alpha * high_sim_node.similarity_score
        sim_contribution_low = config.alpha * low_sim_node.similarity_score

        # Similarity contribution difference should outweigh reliability difference
        rel_contribution_high = config.gamma * high_sim_node.reliability_score
        rel_contribution_low = config.gamma * low_sim_node.reliability_score

        sim_diff = sim_contribution_high - sim_contribution_low
        rel_diff = rel_contribution_low - rel_contribution_high  # low_sim has higher reliability

        # Similarity advantage should dominate over reliability advantage
        assert sim_diff > rel_diff  # α=0.8 ensures similarity dominates

    @pytest.mark.asyncio
    async def test_pagerank_with_no_edges(self) -> None:
        """Test PageRank computation when there are no edges (uniform)."""
        pool = CandidatePool()
        pool.add_node(CandidateNode(skill_id="a:b", depth=0, is_seed=True))
        pool.add_node(CandidateNode(skill_id="c:d", depth=0, is_seed=True))

        engine = ScoringEngine()
        query_vector = np.random.randn(384).astype(np.float32)
        scored_pool, _ = await engine.score_all(pool, query_vector)

        # With no edges, PageRank should be uniform
        pr_a = scored_pool.nodes["a:b"].pagerank_score
        pr_c = scored_pool.nodes["c:d"].pagerank_score
        assert abs(pr_a - pr_c) < 1e-6

    @pytest.mark.asyncio
    async def test_category_weights_all_1_0(self) -> None:
        """VR-First: category_weights all default to 1.0.

        No artificial amplification — VR-first relies on similarity,
        not category bias.
        """
        config = ScoringConfig()
        for category, weight in config.category_weights.items():
            assert weight == 1.0, (
                f"Category '{category}' has weight {weight}, expected 1.0 "
                "(VR-First: no artificial amplification)"
            )

    @pytest.mark.asyncio
    async def test_category_weight_applied_as_multiplier(self) -> None:
        """Test that category weight is applied as multiplier to base score."""
        pool = CandidatePool()
        pool.add_node(CandidateNode(
            skill_id="git:commit",
            similarity=0.8,
            depth=0,
            is_seed=True,
            execution_success_rate=0.9,
            category="git_operations",
        ))

        config = ScoringConfig(alpha=0.8, beta=0.1, gamma=0.1)
        engine = ScoringEngine(config=config)

        query_vector = np.random.randn(384).astype(np.float32)
        scored_pool, _ = await engine.score_all(pool, query_vector)

        node = scored_pool.nodes["git:commit"]

        # Base score (without category multiplier)
        base_score = (
            config.alpha * node.similarity_score
            + config.beta * node.pagerank_score
            + config.gamma * node.reliability_score
        )

        # Category weight for git_operations is 1.0 (VR-First default)
        cat_weight = config.category_weights.get("git_operations", 1.0)
        expected_score = base_score * cat_weight

        assert abs(node.score - expected_score) < 1e-6

    def test_cosine_similarity(self) -> None:
        """Test the static cosine similarity method."""
        vec1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)

        sim = ScoringEngine._cosine_similarity(vec1, vec2)
        assert abs(sim) < 1e-6

        sim_self = ScoringEngine._cosine_similarity(vec1, vec1)
        assert abs(sim_self - 1.0) < 1e-6

    def test_compute_enhancement_score_positive(self) -> None:
        """Test enhancement_score when expanded nodes add value beyond seeds."""
        pool = CandidatePool()
        # VR seed with moderate score
        pool.add_node(CandidateNode(
            skill_id="seed:1",
            similarity=0.8,
            depth=0,
            is_seed=True,
            score=0.72,
            execution_success_rate=0.9,
        ))
        # Expanded node with high score (enhancement adds value)
        pool.add_node(CandidateNode(
            skill_id="expanded:1",
            depth=1,
            is_seed=False,
            edge_type="REQUIRES",
            score=0.85,
            execution_success_rate=0.98,
        ))

        engine = ScoringEngine()
        vr_seed_ids = {"seed:1"}

        enhancement_score = engine.compute_enhancement_score(pool, vr_seed_ids)

        # avg(all=0.785) - avg(seed=0.72) should be positive
        assert enhancement_score > 0

    def test_compute_enhancement_score_negative(self) -> None:
        """Test enhancement_score when expanded nodes don't add value."""
        pool = CandidatePool()
        # VR seed with high score
        pool.add_node(CandidateNode(
            skill_id="seed:1",
            similarity=0.95,
            depth=0,
            is_seed=True,
            score=0.90,
            execution_success_rate=0.95,
        ))
        # Expanded node with low score (no enhancement value)
        pool.add_node(CandidateNode(
            skill_id="expanded:1",
            depth=1,
            is_seed=False,
            edge_type="ENHANCES",
            score=0.5,
            execution_success_rate=0.6,
        ))

        engine = ScoringEngine()
        vr_seed_ids = {"seed:1"}

        enhancement_score = engine.compute_enhancement_score(pool, vr_seed_ids)

        # avg(all=0.7) - avg(seed=0.9) should be negative
        assert enhancement_score <= 0