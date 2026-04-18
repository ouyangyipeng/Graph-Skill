"""
Hybrid retriever combining semantic seed recall and graph expansion.

Implements RFC-03 Section 4: 拓扑感知混合召回算法.
Phase 1: Semantic Seed Recall (ANN top-k)
Phase 2: Graph Expansion (BFS over REQUIRES/ENHANCES)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import numpy as np

from graphskill.core.constants import DEFAULT_TOP_K, DEFAULT_EXPANSION_DEPTH
from graphskill.core.models import EdgeType
from graphskill.routing.models import SeedNode, CandidateNode, CandidatePool

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Topology-aware hybrid retriever.

    Combines vector ANN search (Phase 1) with graph BFS expansion
    (Phase 2) to produce a candidate pool that includes both
    semantically relevant skills and their topological neighbors.

    Args:
        vector_store: MilvusClient instance for ANN search.
        graph_store: Neo4jClient instance for graph traversal.
        top_k: Number of seed nodes to retrieve from ANN.
        expansion_depth: Maximum BFS expansion depth (default 2).
        similarity_threshold: Minimum similarity for seed nodes.
        filter_deprecated: Whether to exclude deprecated nodes.
    """

    def __init__(
        self,
        vector_store: Any,
        graph_store: Any,
        top_k: int = DEFAULT_TOP_K,
        expansion_depth: int = DEFAULT_EXPANSION_DEPTH,
        similarity_threshold: float = 0.3,
        filter_deprecated: bool = True,
    ) -> None:
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.top_k = top_k
        self.expansion_depth = expansion_depth
        self.similarity_threshold = similarity_threshold
        self.filter_deprecated = filter_deprecated

    async def retrieve(
        self,
        query_vector: np.ndarray,
        top_k: Optional[int] = None,
        expansion_depth: Optional[int] = None,
        vr_only: bool = False,
    ) -> tuple[CandidatePool, int]:
        """Execute hybrid retrieval: seed recall + graph expansion.

        VR-First architecture: when vr_only=True, only perform semantic
        seed recall (ANN top-k) without graph expansion. This is used
        for the VR baseline retrieval phase in the gateway.

        Args:
            query_vector: Query embedding vector.
            top_k: Override default top_k for this request.
            expansion_depth: Override default expansion depth.
            vr_only: If True, skip graph expansion (VR baseline only).

        Returns:
            Tuple of (CandidatePool, retrieval_latency_ms).
        """
        k = top_k or self.top_k
        # VR-First: hard limit expansion depth to 1-hop maximum
        depth = min(expansion_depth or self.expansion_depth, 1)

        start_total = time.perf_counter()

        # Phase 1: Semantic Seed Recall
        seed_nodes = await self._semantic_seed_recall(query_vector, k)

        # Phase 2: Graph Expansion (skipped when vr_only=True)
        if vr_only:
            # Build candidate pool with seed nodes only (no expansion)
            candidate_pool = CandidatePool()
            for seed in seed_nodes:
                props = seed.node_properties
                candidate_pool.add_node(
                    CandidateNode(
                        skill_id=seed.skill_id,
                        similarity=seed.similarity,
                        depth=0,
                        is_seed=True,
                        expansion_path=[seed.skill_id],
                        version=props.get("version", "1.0.0"),
                        intent_description=props.get("intent_description", ""),
                        permissions=props.get("permissions", []),
                        execution_success_rate=props.get("execution_success_rate", 1.0),
                        is_deprecated=props.get("is_deprecated", False),
                        category=props.get("category", ""),
                    )
                )
            elapsed_ms = int((time.perf_counter() - start_total) * 1000)
            logger.info(
                f"VR-only retrieval: {len(seed_nodes)} seeds, "
                f"{elapsed_ms}ms"
            )
            return candidate_pool, elapsed_ms

        candidate_pool = await self._graph_expansion(seed_nodes, depth)

        elapsed_ms = int((time.perf_counter() - start_total) * 1000)
        logger.info(
            f"Hybrid retrieval: {len(seed_nodes)} seeds, "
            f"{len(candidate_pool.nodes)} total candidates, "
            f"{elapsed_ms}ms"
        )

        return candidate_pool, elapsed_ms

    async def _semantic_seed_recall(
        self,
        query_vector: np.ndarray,
        top_k: int,
    ) -> list[SeedNode]:
        """Phase 1: Retrieve seed nodes via ANN vector search.

        Over-retrieves (2x) then filters deprecated nodes and
        low-similarity results before returning top_k.

        VR-First guarantee: seed nodes MUST always be available as the
        Vector-RAG baseline. If similarity_threshold filters out all
        candidates, we fall back to returning top_k without threshold
        filtering — ensuring the GS ≥ VR guarantee is never violated.
        """
        try:
            search_result = await self.vector_store.search(
                query_vector=query_vector.tolist(),
                top_k=top_k * 2,  # Over-retrieve for filtering
                output_fields=["id"],
            )

            # Collect ALL raw hits with computed similarity (pre-threshold)
            raw_hits: list[dict] = []
            for hit in search_result.results:
                skill_id = hit.get("id", "")
                distance = hit.get("distance", 0.0)

                # Milvus COSINE metric returns distance in [0, 2] where
                # lower is more similar for L2, but for COSINE it's
                # actually similarity score. Convert to [0, 1].
                similarity = max(0.0, min(1.0, 1.0 - distance))
                raw_hits.append({"skill_id": skill_id, "similarity": similarity})

            # Sort by similarity descending (highest first)
            raw_hits.sort(key=lambda h: h["similarity"], reverse=True)

            # Phase A: Try to build seed_nodes with similarity_threshold
            seed_nodes: list[SeedNode] = []
            for hit_info in raw_hits:
                similarity = hit_info["similarity"]

                if similarity < self.similarity_threshold:
                    continue

                skill_id = hit_info["skill_id"]

                # Fetch node properties from graph DB
                node_props = await self._get_skill_node(skill_id)
                if node_props is None:
                    continue

                # Filter deprecated nodes
                if self.filter_deprecated and node_props.get("is_deprecated", False):
                    continue

                seed_nodes.append(
                    SeedNode(
                        skill_id=skill_id,
                        vector_id=skill_id,
                        similarity=similarity,
                        node_properties=node_props,
                        expansion_path=[skill_id],
                    )
                )

                if len(seed_nodes) >= top_k:
                    break

            # Phase B: VR-First fallback guarantee
            # If threshold filtering eliminated ALL candidates, return
            # top_k seeds WITHOUT threshold — ensuring GS ≥ VR baseline.
            if len(seed_nodes) == 0 and len(raw_hits) > 0:
                logger.warning(
                    f"Similarity threshold ({self.similarity_threshold}) filtered out "
                    f"all {len(raw_hits)} candidates. Falling back to top_k without "
                    f"threshold to preserve VR-First guarantee."
                )
                for hit_info in raw_hits:
                    skill_id = hit_info["skill_id"]
                    similarity = hit_info["similarity"]

                    node_props = await self._get_skill_node(skill_id)
                    if node_props is None:
                        continue

                    if self.filter_deprecated and node_props.get("is_deprecated", False):
                        continue

                    seed_nodes.append(
                        SeedNode(
                            skill_id=skill_id,
                            vector_id=skill_id,
                            similarity=similarity,
                            node_properties=node_props,
                            expansion_path=[skill_id],
                        )
                    )

                    if len(seed_nodes) >= top_k:
                        break

            return seed_nodes

        except Exception as e:
            logger.error(f"Semantic seed recall failed: {e}")
            return []

    async def _graph_expansion(
        self,
        seed_nodes: list[SeedNode],
        max_depth: int,
    ) -> CandidatePool:
        """Phase 2: BFS graph expansion over REQUIRES and ENHANCES edges.

        Per RFC-03 Section 4.3:
        - Only follow REQUIRES (out) and ENHANCES (out) edges
        - Skip deprecated nodes
        - Track visited to avoid duplicates
        - Maximum depth = 2 hops
        """
        candidate_pool = CandidatePool()
        visited: set[str] = set()

        # Initialize: add seed nodes to pool
        for seed in seed_nodes:
            props = seed.node_properties
            candidate_pool.add_node(
                CandidateNode(
                    skill_id=seed.skill_id,
                    similarity=seed.similarity,
                    depth=0,
                    is_seed=True,
                    expansion_path=[seed.skill_id],
                    version=props.get("version", "1.0.0"),
                    intent_description=props.get("intent_description", ""),
                    permissions=props.get("permissions", []),
                    execution_success_rate=props.get("execution_success_rate", 1.0),
                    is_deprecated=props.get("is_deprecated", False),
                    category=props.get("category", ""),
                )
            )
            visited.add(seed.skill_id)

        # BFS expansion
        for current_depth in range(1, max_depth + 1):
            frontier = candidate_pool.get_nodes_at_depth(current_depth - 1)
            if not frontier:
                break

            for node in frontier:
                neighbors = await self._get_out_neighbors(node.skill_id)

                for neighbor in neighbors:
                    neighbor_id = neighbor["skill_id"]
                    if neighbor_id in visited:
                        continue

                    visited.add(neighbor_id)

                    # Fetch full node properties
                    neighbor_props = await self._get_skill_node(neighbor_id)
                    if neighbor_props is None:
                        continue

                    if self.filter_deprecated and neighbor_props.get("is_deprecated", False):
                        continue

                    candidate_pool.add_node(
                        CandidateNode(
                            skill_id=neighbor_id,
                            similarity=0.0,  # Non-seed: similarity computed later by ScoringEngine
                            depth=current_depth,
                            is_seed=False,
                            expansion_path=node.expansion_path + [neighbor_id],
                            edge_type=neighbor.get("edge_type"),
                            edge_weight=neighbor.get("weight", 1.0),
                            version=neighbor_props.get("version", "1.0.0"),
                            intent_description=neighbor_props.get("intent_description", ""),
                            permissions=neighbor_props.get("permissions", []),
                            execution_success_rate=neighbor_props.get("execution_success_rate", 1.0),
                            is_deprecated=neighbor_props.get("is_deprecated", False),
                            category=neighbor_props.get("category", ""),
                        )
                    )

        return candidate_pool

    async def _get_skill_node(self, skill_id: str) -> Optional[dict[str, Any]]:
        """Fetch skill node properties from graph database.

        Returns None if node not found.
        """
        try:
            result = await self.graph_store.get_node(skill_id)
            return result
        except Exception as e:
            logger.warning(f"Failed to fetch node {skill_id}: {e}")
            return None

    async def _get_out_neighbors(self, skill_id: str) -> list[dict[str, Any]]:
        """Get outgoing REQUIRES and ENHANCES neighbors from graph DB.

        Per RFC-03 Section 4.3.1, expansion MUST only follow
        REQUIRES and ENHANCES out-edges.

        Properly extracts edge_type from graph store results.
        Neo4j variable-length path queries may return edge_type
        as a list; this method normalizes it to a single string.
        """
        try:
            result = await self.graph_store.get_neighbors(
                uid=skill_id,
                edge_types=[EdgeType.REQUIRES, EdgeType.ENHANCES],
                depth=1,
            )
            neighbors = []
            for node in result.nodes:
                # Extract edge_type from graph store result.
                # Neo4j variable-length path queries (e.g. [r*1..1])
                # may return type(r) as a list; normalize to string.
                raw_edge_type = node.get("edge_type")
                if isinstance(raw_edge_type, list):
                    # For variable-length paths, take the last hop's type
                    # (closest to the target node)
                    edge_type = raw_edge_type[-1] if raw_edge_type else EdgeType.REQUIRES.value
                elif raw_edge_type:
                    edge_type = str(raw_edge_type)
                else:
                    logger.warning(
                        f"Missing edge_type for neighbor of {skill_id}, "
                        f"defaulting to REQUIRES"
                    )
                    edge_type = EdgeType.REQUIRES.value

                neighbors.append({
                    "skill_id": node.get("uid", ""),
                    "edge_type": edge_type,
                    "weight": node.get("weight", 1.0),
                })
            return neighbors
        except Exception as e:
            logger.warning(f"Failed to get neighbors for {skill_id}: {e}")
            return []
