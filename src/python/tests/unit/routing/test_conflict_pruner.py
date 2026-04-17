"""Unit tests for ConflictPruner (ConflictGraphBuilder + MWISPruner).

VR-First architecture adds:
  - prune_with_protection() method that protects VR seed skills from MWIS pruning
  - VR seed skills are NEVER removed unless a higher-scoring VR seed replaces them
  - When a VR seed conflicts with an expansion skill, the expansion skill is removed
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from graphskill.routing.models import CandidatePool, CandidateNode, ConflictGraph
from graphskill.routing.conflict_pruner import (
    ConflictGraphBuilder,
    MWISPruner,
    ConflictPruner,
    ConflictPruningError,
)


def _make_pool_with_scores() -> CandidatePool:
    """Create a candidate pool with scored nodes."""
    pool = CandidatePool()
    pool.add_node(CandidateNode(
        skill_id="git:commit", score=0.9, depth=0, is_seed=True,
    ))
    pool.add_node(CandidateNode(
        skill_id="git:push", score=0.8, depth=0, is_seed=True,
    ))
    pool.add_node(CandidateNode(
        skill_id="git:config", score=0.7, depth=1, is_seed=False,
    ))
    pool.add_node(CandidateNode(
        skill_id="svn:commit", score=0.6, depth=0, is_seed=True,
    ))
    return pool


class TestMWISPruner:
    """Tests for the MWISPruner greedy algorithm."""

    def test_no_conflicts(self) -> None:
        """All nodes should be selected when there are no conflicts."""
        cg = ConflictGraph()
        cg.add_node("a:b", 0.9)
        cg.add_node("c:d", 0.7)

        pruner = MWISPruner()
        result = pruner.prune(cg)

        assert set(result) == {"a:b", "c:d"}

    def test_conflict_removes_lower_score(self) -> None:
        """When two nodes conflict, the higher-scored one should be kept."""
        cg = ConflictGraph()
        cg.add_node("a:b", 0.9)
        cg.add_node("c:d", 0.5)
        cg.add_conflict_edge("a:b", "c:d")

        pruner = MWISPruner()
        result = pruner.prune(cg)

        assert "a:b" in result
        assert "c:d" not in result

    def test_substitute_treated_as_conflict(self) -> None:
        """SUBSTITUTES edges should also cause pruning."""
        cg = ConflictGraph()
        cg.add_node("git:commit", 0.9)
        cg.add_node("svn:commit", 0.6)
        cg.add_substitute_edge("git:commit", "svn:commit")

        pruner = MWISPruner()
        result = pruner.prune(cg)

        assert "git:commit" in result
        assert "svn:commit" not in result

    def test_multiple_conflicts(self) -> None:
        """Node conflicting with multiple selected nodes is excluded."""
        cg = ConflictGraph()
        cg.add_node("a:b", 0.9)
        cg.add_node("c:d", 0.8)
        cg.add_node("e:f", 0.7)
        cg.add_conflict_edge("a:b", "e:f")
        cg.add_conflict_edge("c:d", "e:f")

        pruner = MWISPruner()
        result = pruner.prune(cg)

        assert "a:b" in result
        assert "c:d" in result
        assert "e:f" not in result

    def test_empty_graph(self) -> None:
        """Empty conflict graph returns empty result."""
        cg = ConflictGraph()
        pruner = MWISPruner()
        result = pruner.prune(cg)
        assert result == []

    def test_single_node(self) -> None:
        """Single node with no conflicts is always selected."""
        cg = ConflictGraph()
        cg.add_node("a:b", 0.5)

        pruner = MWISPruner()
        result = pruner.prune(cg)
        assert result == ["a:b"]

    def test_chain_conflicts(self) -> None:
        """In a chain of conflicts, greedy selects alternating nodes by score."""
        cg = ConflictGraph()
        cg.add_node("a:b", 0.9)
        cg.add_node("c:d", 0.7)
        cg.add_node("e:f", 0.5)
        # a-b conflicts with c-d, c-d conflicts with e-f
        cg.add_conflict_edge("a:b", "c:d")
        cg.add_conflict_edge("c:d", "e:f")

        pruner = MWISPruner()
        result = pruner.prune(cg)

        # a:b (0.9) selected first, c:d conflicts with a:b so skipped,
        # e:f doesn't conflict with a:b so selected
        assert "a:b" in result
        assert "c:d" not in result
        assert "e:f" in result

    def test_validation_catches_bug(self) -> None:
        """Verify that _validate_no_conflicts would catch an invalid result."""
        cg = ConflictGraph()
        cg.add_node("a:b", 0.9)
        cg.add_node("c:d", 0.5)
        cg.add_conflict_edge("a:b", "c:d")

        pruner = MWISPruner()
        # Manually inject a bad final set to test validation
        with pytest.raises(ConflictPruningError):
            pruner._validate_no_conflicts({"a:b", "c:d"}, cg)


class TestMWISPrunerWithProtection:
    """Tests for MWISPruner.prune_with_protection() (VR-First)."""

    def test_no_conflicts_with_protection(self) -> None:
        """All nodes should be selected when there are no conflicts."""
        cg = ConflictGraph()
        cg.add_node("a:b", 0.9)
        cg.add_node("c:d", 0.7)

        pruner = MWISPruner()
        result = pruner.prune_with_protection(cg, vr_seed_ids={"a:b", "c:d"})

        assert set(result) == {"a:b", "c:d"}

    def test_vr_seed_never_removed_by_mwis(self) -> None:
        """VR seed skills are NEVER removed by MWIS pruning.

        When a VR seed conflicts with a non-protected (expansion) skill,
        the expansion skill must be removed, and the VR seed must remain.
        """
        cg = ConflictGraph()
        # VR seed with lower score than expansion skill
        cg.add_node("vr:seed", 0.5)      # VR seed (protected)
        cg.add_node("exp:skill", 0.9)     # Expansion skill (non-protected)
        cg.add_conflict_edge("vr:seed", "exp:skill")

        pruner = MWISPruner()
        result = pruner.prune_with_protection(cg, vr_seed_ids={"vr:seed"})

        # VR seed MUST survive even though it has lower score
        assert "vr:seed" in result
        # Expansion skill is removed because it conflicts with protected VR seed
        assert "exp:skill" not in result

    def test_vr_seed_removes_conflicting_expansion(self) -> None:
        """When a VR seed conflicts with an expansion skill, expansion is removed."""
        cg = ConflictGraph()
        cg.add_node("git:commit", 0.85)   # VR seed (protected)
        cg.add_node("svn:commit", 0.6)    # Expansion skill (non-protected)
        cg.add_conflict_edge("git:commit", "svn:commit")

        pruner = MWISPruner()
        result = pruner.prune_with_protection(cg, vr_seed_ids={"git:commit"})

        # VR seed MUST be preserved
        assert "git:commit" in result
        # Expansion skill removed because it conflicts with VR seed
        assert "svn:commit" not in result

    def test_two_vr_seeds_conflict_keep_higher(self) -> None:
        """When two VR seeds conflict, keep the higher-scoring one.

        This is the ONLY case a VR seed can be removed: by another
        higher-scoring VR seed.
        """
        cg = ConflictGraph()
        cg.add_node("vr:seed_a", 0.9)   # Higher-scoring VR seed
        cg.add_node("vr:seed_b", 0.5)   # Lower-scoring VR seed
        cg.add_conflict_edge("vr:seed_a", "vr:seed_b")

        pruner = MWISPruner()
        result = pruner.prune_with_protection(
            cg, vr_seed_ids={"vr:seed_a", "vr:seed_b"}
        )

        # Higher-scoring VR seed must survive
        assert "vr:seed_a" in result
        # Lower-scoring VR seed is removed by higher-scoring VR seed
        # (only case a VR seed can be removed)
        assert "vr:seed_b" not in result

    def test_multiple_vr_seeds_preserved(self) -> None:
        """Multiple non-conflicting VR seeds are all preserved."""
        cg = ConflictGraph()
        cg.add_node("vr:a", 0.7)
        cg.add_node("vr:b", 0.8)
        cg.add_node("exp:c", 0.6)     # Expansion skill

        pruner = MWISPruner()
        result = pruner.prune_with_protection(
            cg, vr_seed_ids={"vr:a", "vr:b"}
        )

        # Both VR seeds should survive (no conflicts between them)
        assert "vr:a" in result
        assert "vr:b" in result
        # Expansion skill also survives (no conflicts)
        assert "exp:c" in result

    def test_empty_graph_with_protection(self) -> None:
        """Empty conflict graph returns empty result even with protection."""
        cg = ConflictGraph()
        pruner = MWISPruner()
        result = pruner.prune_with_protection(cg, vr_seed_ids={"vr:a"})
        assert result == []

    def test_protection_with_no_vr_seeds(self) -> None:
        """prune_with_protection with empty vr_seed_ids behaves like regular prune."""
        cg = ConflictGraph()
        cg.add_node("a:b", 0.9)
        cg.add_node("c:d", 0.5)
        cg.add_conflict_edge("a:b", "c:d")

        pruner = MWISPruner()
        protected_result = pruner.prune_with_protection(cg, vr_seed_ids=set())
        regular_result = pruner.prune(cg)

        # Should behave identically without VR seeds
        assert set(protected_result) == set(regular_result)


class TestConflictGraphBuilder:
    """Tests for ConflictGraphBuilder."""

    @pytest.mark.asyncio
    async def test_build_no_conflicts(self) -> None:
        """Build conflict graph when there are no conflict edges."""
        graph_store = AsyncMock()
        graph_store._execute_query = AsyncMock(return_value=[])

        builder = ConflictGraphBuilder(graph_store)
        pool = _make_pool_with_scores()

        cg = await builder.build(pool)

        assert len(cg.nodes) == 4
        assert len(cg.conflict_edges) == 0
        assert len(cg.substitute_edges) == 0

    @pytest.mark.asyncio
    async def test_build_with_conflicts(self) -> None:
        """Build conflict graph with CONFLICTS_WITH edges."""
        graph_store = AsyncMock()

        # Mock: first call returns conflicts, second returns substitutes
        call_count = 0

        async def mock_execute(query, params):
            nonlocal call_count
            call_count += 1
            if "CONFLICTS_WITH" in query:
                return [{"node_a": "git:commit", "node_b": "svn:commit", "severity": 3}]
            return []

        graph_store._execute_query = mock_execute

        builder = ConflictGraphBuilder(graph_store)
        pool = _make_pool_with_scores()

        cg = await builder.build(pool)

        assert len(cg.conflict_edges) == 1
        assert cg.has_conflict("git:commit", "svn:commit")

    @pytest.mark.asyncio
    async def test_build_with_substitutes(self) -> None:
        """Build conflict graph with SUBSTITUTES edges."""
        graph_store = AsyncMock()

        async def mock_execute(query, params):
            if "SUBSTITUTES" in query:
                return [{"node_a": "git:commit", "node_b": "svn:commit", "similarity": 0.85}]
            return []

        graph_store._execute_query = mock_execute

        builder = ConflictGraphBuilder(graph_store)
        pool = _make_pool_with_scores()

        cg = await builder.build(pool)

        assert len(cg.substitute_edges) == 1
        assert cg.has_conflict("git:commit", "svn:commit")

    @pytest.mark.asyncio
    async def test_build_no_graph_store(self) -> None:
        """Build with None graph store returns empty conflict graph."""
        builder = ConflictGraphBuilder(None)
        pool = _make_pool_with_scores()

        cg = await builder.build(pool)

        assert len(cg.nodes) == 4
        assert len(cg.conflict_edges) == 0


class TestConflictPruner:
    """Tests for the high-level ConflictPruner."""

    @pytest.mark.asyncio
    async def test_prune_no_conflicts(self) -> None:
        """All nodes survive when there are no conflicts."""
        graph_store = AsyncMock()
        graph_store._execute_query = AsyncMock(return_value=[])

        pruner = ConflictPruner(graph_store)
        pool = _make_pool_with_scores()

        result_ids, cg, latency_ms = await pruner.prune(pool)

        assert len(result_ids) == 4
        assert latency_ms >= 0

    @pytest.mark.asyncio
    async def test_prune_with_conflicts(self) -> None:
        """Conflicting nodes are pruned correctly."""
        graph_store = AsyncMock()

        async def mock_execute(query, params):
            if "CONFLICTS_WITH" in query:
                return [{"node_a": "git:commit", "node_b": "svn:commit", "severity": 3}]
            return []

        graph_store._execute_query = mock_execute

        pruner = ConflictPruner(graph_store)
        pool = _make_pool_with_scores()

        result_ids, cg, _ = await pruner.prune(pool)

        # git:commit (0.9) should beat svn:commit (0.6)
        assert "git:commit" in result_ids
        assert "svn:commit" not in result_ids

    @pytest.mark.asyncio
    async def test_prune_with_protection_no_conflicts(self) -> None:
        """prune_with_protection: all nodes survive when there are no conflicts."""
        graph_store = AsyncMock()
        graph_store._execute_query = AsyncMock(return_value=[])

        pruner = ConflictPruner(graph_store)
        pool = _make_pool_with_scores()

        vr_seed_ids = {"git:commit", "git:push"}
        result_ids, cg, latency_ms = await pruner.prune_with_protection(pool, vr_seed_ids)

        assert len(result_ids) == 4
        assert latency_ms >= 0
        # VR seeds should all survive
        assert "git:commit" in result_ids
        assert "git:push" in result_ids

    @pytest.mark.asyncio
    async def test_prune_with_protection_vr_seed_survives(self) -> None:
        """prune_with_protection: VR seed skills are protected from removal.

        When a VR seed conflicts with an expansion skill, the expansion
        skill is removed and the VR seed survives.
        """
        graph_store = AsyncMock()

        async def mock_execute(query, params):
            if "CONFLICTS_WITH" in query:
                return [{"node_a": "git:commit", "node_b": "svn:commit", "severity": 3}]
            return []

        graph_store._execute_query = mock_execute

        pruner = ConflictPruner(graph_store)
        pool = _make_pool_with_scores()

        # git:commit is a VR seed, svn:commit is a non-seed conflict
        vr_seed_ids = {"git:commit", "git:push"}
        result_ids, cg, _ = await pruner.prune_with_protection(pool, vr_seed_ids)

        # VR seed git:commit MUST survive despite conflict
        assert "git:commit" in result_ids
        # svn:commit removed because it conflicts with protected VR seed
        assert "svn:commit" not in result_ids