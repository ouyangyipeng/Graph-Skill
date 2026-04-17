"""
Conflict graph builder and MWIS pruner.

Implements RFC-03 Section 6: 最大权重独立集冲突剪枝算法.
Ensures the output skill subset has zero internal conflicts.

Two phases:
  1. Build conflict graph from CONFLICTS_WITH and SUBSTITUTES edges
  2. Greedy MWIS algorithm to select maximum-weight independent set
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from graphskill.core.exceptions import ConflictResolutionError
from graphskill.core.models import EdgeType
from graphskill.routing.models import CandidatePool, ConflictGraph

logger = logging.getLogger(__name__)


class ConflictPruningError(ConflictResolutionError):
    """Raised when the MWIS result contains internal conflicts (should never happen)."""

    def __init__(self, message: str, conflict_pair: tuple[str, str] | None = None):
        details = {"conflict_pair": conflict_pair} if conflict_pair else {}
        super().__init__(message, details=details)
        self.conflict_pair = conflict_pair


class ConflictGraphBuilder:
    """Builds a conflict graph from the candidate pool.

    Queries the graph database for CONFLICTS_WITH and SUBSTITUTES
    edges among candidate nodes and constructs the conflict graph
    used by the MWIS pruner.

    Args:
        graph_store: Neo4jClient instance for querying edges.
    """

    def __init__(self, graph_store: Any) -> None:
        self.graph_store = graph_store

    async def build(self, candidate_pool: CandidatePool) -> ConflictGraph:
        """Build conflict graph from candidate pool.

        Args:
            candidate_pool: Pool of scored candidate nodes.

        Returns:
            ConflictGraph with nodes and conflict/substitute edges.
        """
        conflict_graph = ConflictGraph()

        # Add all candidate nodes with their scores
        for node in candidate_pool.get_all_nodes():
            conflict_graph.add_node(node.skill_id, node.score)

        skill_ids = candidate_pool.get_skill_ids()
        if not skill_ids:
            return conflict_graph

        # Fetch CONFLICTS_WITH edges
        conflicts = await self._fetch_conflicts_edges(skill_ids)
        for edge in conflicts:
            node_a = edge.get("node_a", "")
            node_b = edge.get("node_b", "")
            severity = edge.get("severity", 3)
            if node_a in conflict_graph.nodes and node_b in conflict_graph.nodes:
                conflict_graph.add_conflict_edge(node_a, node_b, severity=severity)

        # Fetch SUBSTITUTES edges (also treated as conflicts for MWIS)
        substitutes = await self._fetch_substitutes_edges(skill_ids)
        for edge in substitutes:
            node_a = edge.get("node_a", "")
            node_b = edge.get("node_b", "")
            similarity = edge.get("similarity", 0.8)
            if node_a in conflict_graph.nodes and node_b in conflict_graph.nodes:
                conflict_graph.add_substitute_edge(node_a, node_b, similarity=similarity)

        logger.info(
            f"Conflict graph built: {len(conflict_graph.nodes)} nodes, "
            f"{len(conflict_graph.conflict_edges)} conflicts, "
            f"{len(conflict_graph.substitute_edges)} substitutes"
        )

        return conflict_graph

    async def _fetch_conflicts_edges(self, skill_ids: list[str]) -> list[dict[str, Any]]:
        """Fetch CONFLICTS_WITH edges among candidates from graph DB."""
        if self.graph_store is None:
            return []

        try:
            if hasattr(self.graph_store, "_execute_query"):
                query = """
                MATCH (a:SkillNode)-[r:CONFLICTS_WITH]-(b:SkillNode)
                WHERE a.uid IN $skill_ids AND b.uid IN $skill_ids
                RETURN a.uid as node_a, b.uid as node_b, r.weight as severity
                """
                return await self.graph_store._execute_query(query, {"skill_ids": skill_ids})
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch CONFLICTS_WITH edges: {e}")
            return []

    async def _fetch_substitutes_edges(self, skill_ids: list[str]) -> list[dict[str, Any]]:
        """Fetch SUBSTITUTES edges among candidates from graph DB."""
        if self.graph_store is None:
            return []

        try:
            if hasattr(self.graph_store, "_execute_query"):
                query = """
                MATCH (a:SkillNode)-[r:SUBSTITUTES]-(b:SkillNode)
                WHERE a.uid IN $skill_ids AND b.uid IN $skill_ids
                RETURN a.uid as node_a, b.uid as node_b, r.weight as similarity
                """
                return await self.graph_store._execute_query(query, {"skill_ids": skill_ids})
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch SUBSTITUTES edges: {e}")
            return []


class MWISPruner:
    """Maximum Weight Independent Set pruner using greedy algorithm.

    Implements RFC-03 Section 6.3: Greedy MWIS.

    VR-First extension: prune_with_protection() ensures VR seed skills
    are protected from removal unless a higher-scoring VR seed replaces them.
    This guarantees GS ≥ VR at the conflict resolution stage.

    Algorithm:
    1. Sort all nodes by composite score descending
    2. Greedily select nodes that don't conflict with already-selected nodes
    3. Validate the result has zero internal conflicts

    Time complexity: O(|P| × |S|) where |S| ≤ |P|
    Space complexity: O(|G|) for conflict graph storage
    """

    def prune(self, conflict_graph: ConflictGraph) -> list[str]:
        """Execute MWIS pruning on the conflict graph.

        Args:
            conflict_graph: Conflict graph with scored nodes and edges.

        Returns:
            List of skill IDs forming a zero-conflict subset.

        Raises:
            ConflictPruningError: If the result contains internal conflicts
                (indicates a bug in the algorithm).
        """
        if not conflict_graph.nodes:
            return []

        # Step 1: Sort nodes by score descending
        sorted_nodes = sorted(
            conflict_graph.nodes.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        # Step 2: Greedy selection
        final_set: set[str] = set()

        for skill_id, score in sorted_nodes:
            # Check if this node conflicts with any already-selected node
            has_conflict = any(
                conflict_graph.has_conflict(skill_id, selected)
                for selected in final_set
            )

            if not has_conflict:
                final_set.add(skill_id)

        # Step 3: Validate zero conflicts (safety invariant)
        self._validate_no_conflicts(final_set, conflict_graph)

        logger.info(
            f"MWIS pruning: {len(conflict_graph.nodes)} candidates -> "
            f"{len(final_set)} selected, "
            f"{len(conflict_graph.nodes) - len(final_set)} pruned"
        )

        return list(final_set)

    def prune_with_protection(
        self,
        conflict_graph: ConflictGraph,
        vr_seed_ids: set[str],
    ) -> list[str]:
        """Execute MWIS pruning with VR seed protection.

        VR seed skills are marked as protected. During greedy selection:
        - If a protected skill conflicts with an already-selected non-protected
          skill → remove the non-protected one, keep the protected one.
        - If two protected skills conflict → keep the higher-scoring one
          (this is the only case a VR seed can be removed).
        - This guarantees all VR seeds are preserved unless replaced by
          a higher-scoring VR seed.

        Args:
            conflict_graph: Conflict graph with scored nodes and edges.
            vr_seed_ids: Set of VR baseline skill IDs to protect.

        Returns:
            List of skill IDs forming a zero-conflict subset with
            VR seed protection applied.
        """
        if not conflict_graph.nodes:
            return []

        # Step 1: Sort nodes by score descending
        sorted_nodes = sorted(
            conflict_graph.nodes.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        # Step 2: Greedy selection with VR seed protection
        final_set: set[str] = set()

        for skill_id, score in sorted_nodes:
            is_protected = skill_id in vr_seed_ids

            # Check conflicts with already-selected nodes
            conflicting_selected: list[str] = []
            for selected in final_set:
                if conflict_graph.has_conflict(skill_id, selected):
                    conflicting_selected.append(selected)

            if not conflicting_selected:
                # No conflict → add directly
                final_set.add(skill_id)
                continue

            # Has conflicts → resolve based on protection status
            can_add = True
            for conflicting_id in conflicting_selected:
                conflicting_is_protected = conflicting_id in vr_seed_ids

                if is_protected and not conflicting_is_protected:
                    # Protected (VR seed) vs non-protected: remove non-protected
                    final_set.discard(conflicting_id)
                elif is_protected and conflicting_is_protected:
                    # Two VR seeds conflict: keep higher score
                    # Since we iterate in descending score order, current node
                    # has lower score → keep the already-selected one
                    can_add = False
                    break
                elif not is_protected and conflicting_is_protected:
                    # Non-protected conflicts with protected → skip non-protected
                    can_add = False
                    break
                else:
                    # Two non-protected nodes conflict: standard greedy
                    # Already-selected has higher score → skip current
                    can_add = False
                    break

            if can_add:
                final_set.add(skill_id)

        # Step 3: Validate zero conflicts
        self._validate_no_conflicts(final_set, conflict_graph)

        logger.info(
            f"MWIS pruning with VR protection: "
            f"{len(conflict_graph.nodes)} candidates -> {len(final_set)} selected, "
            f"protected seeds={len(vr_seed_ids & final_set)}/{len(vr_seed_ids)}"
        )

        return list(final_set)

    def _validate_no_conflicts(
        self,
        final_set: set[str],
        conflict_graph: ConflictGraph,
    ) -> None:
        """Validate that the final set has zero internal conflicts.

        This is a safety check per RFC-03 Section 6.5: the output
        MUST contain no logical conflicts or functional substitutes.
        """
        final_list = list(final_set)
        for i in range(len(final_list)):
            for j in range(i + 1, len(final_list)):
                node_a = final_list[i]
                node_b = final_list[j]
                if conflict_graph.has_conflict(node_a, node_b):
                    raise ConflictPruningError(
                        f"Conflict detected in final set: {node_a} <-> {node_b}",
                        conflict_pair=(node_a, node_b),
                    )


class ConflictPruner:
    """High-level conflict pruner combining graph building and MWIS.

    Provides `prune` and `prune_with_protection` methods that:
    1. Build the conflict graph from the candidate pool
    2. Run greedy MWIS (with optional VR seed protection)
    3. Return the pruned skill IDs with timing info

    Args:
        graph_store: Neo4jClient instance.
    """

    def __init__(self, graph_store: Any) -> None:
        self.graph_builder = ConflictGraphBuilder(graph_store)
        self.mwis_pruner = MWISPruner()

    async def prune(
        self,
        candidate_pool: CandidatePool,
    ) -> tuple[list[str], ConflictGraph, int]:
        """Build conflict graph and run MWIS pruning.

        Args:
            candidate_pool: Scored candidate pool.

        Returns:
            Tuple of (pruned_skill_ids, conflict_graph, pruning_latency_ms).
        """
        start = time.perf_counter()

        # Build conflict graph
        conflict_graph = await self.graph_builder.build(candidate_pool)

        # Run MWIS
        pruned_ids = self.mwis_pruner.prune(conflict_graph)

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return pruned_ids, conflict_graph, elapsed_ms

    async def prune_with_protection(
        self,
        candidate_pool: CandidatePool,
        vr_seed_ids: set[str],
    ) -> tuple[list[str], ConflictGraph, int]:
        """Build conflict graph and run MWIS pruning with VR seed protection.

        VR-First architecture: ensures VR seed skills are protected from
        removal during conflict resolution, unless a higher-scoring VR
        seed replaces them. This enforces the GS ≥ VR guarantee.

        Args:
            candidate_pool: Scored candidate pool.
            vr_seed_ids: Set of VR baseline skill IDs to protect.

        Returns:
            Tuple of (pruned_skill_ids, conflict_graph, pruning_latency_ms).
        """
        start = time.perf_counter()

        # Build conflict graph
        conflict_graph = await self.graph_builder.build(candidate_pool)

        # Run MWIS with VR seed protection
        pruned_ids = self.mwis_pruner.prune_with_protection(conflict_graph, vr_seed_ids)

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        return pruned_ids, conflict_graph, elapsed_ms
