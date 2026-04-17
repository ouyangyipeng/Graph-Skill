"""
Dynamic scoring engine for candidate node weight computation.

Implements RFC-03 Section 5: 动态打分与节点权重计算.
Score(n) = α * CosineSim(V_q, V_n) + β * PageRank_local(n) + γ * Reliability(n)

VR-First architecture: computes enhancement_score to determine whether
graph expansion adds value beyond the VR baseline.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import numpy as np

from graphskill.routing.models import CandidatePool, CandidateNode, ScoringConfig

logger = logging.getLogger(__name__)


class ScoringEngine:
    """Dynamic scoring engine computing composite weights for candidate nodes.

    The composite score combines three dimensions:
    - Cosine similarity between query and skill vectors
    - Local PageRank centrality within the candidate subgraph
    - Historical reliability (EWMA success rate)

    Args:
        config: Scoring hyperparameters (α, β, γ).
        vector_store: MilvusClient for fetching node vectors (non-seed similarity).
        graph_store: Neo4jClient for fetching REQUIRES edges (PageRank).
    """

    def __init__(
        self,
        config: Optional[ScoringConfig] = None,
        vector_store: Any = None,
        graph_store: Any = None,
    ) -> None:
        self.config = config or ScoringConfig()
        self.vector_store = vector_store
        self.graph_store = graph_store

    async def score_all(
        self,
        candidate_pool: CandidatePool,
        query_vector: np.ndarray,
    ) -> tuple[CandidatePool, int]:
        """Compute composite scores for all candidate nodes.

        Args:
            candidate_pool: Pool of candidates from hybrid retrieval.
            query_vector: Query embedding vector.

        Returns:
            Tuple of (updated CandidatePool, scoring_latency_ms).
        """
        start = time.perf_counter()

        nodes = candidate_pool.get_all_nodes()
        if not nodes:
            return candidate_pool, 0

        # Compute sub-scores
        similarity_scores = await self._compute_similarity_scores(nodes, query_vector)
        pagerank_scores = await self._compute_local_pagerank(nodes)
        reliability_scores = self._compute_reliability_scores(nodes)

        # Combine into composite score
        # Clamp all sub-scores to [0, 1]: cosine similarity can be negative
        # but downstream models (CandidateNode, SelectedSkill) require ge=0.0
        # Then apply category-based weight multiplier:
        #   domain_knowledge boosted (×1.5), tool categories reduced (×0.6-0.8)
        cat_weights = self.config.category_weights
        default_cat_weight = 1.0

        for node in nodes:
            sim = max(0.0, min(1.0, similarity_scores.get(node.skill_id, 0.0)))
            pr = max(0.0, min(1.0, pagerank_scores.get(node.skill_id, 0.0)))
            rel = max(0.0, min(1.0, reliability_scores.get(node.skill_id, 0.0)))

            node.similarity_score = sim
            node.pagerank_score = pr
            node.reliability_score = rel

            base_score = (
                self.config.alpha * sim
                + self.config.beta * pr
                + self.config.gamma * rel
            )

            # Apply category weight multiplier
            cat = node.category if node.category else ""
            cat_mult = cat_weights.get(cat, default_cat_weight) if cat else default_cat_weight
            node.score = base_score * cat_mult

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.debug(
            f"Scoring completed: {len(nodes)} nodes, {elapsed_ms}ms, "
            f"weights=({self.config.alpha}, {self.config.beta}, {self.config.gamma})"
        )

        return candidate_pool, elapsed_ms

    async def _compute_similarity_scores(
        self,
        nodes: list[CandidateNode],
        query_vector: np.ndarray,
    ) -> dict[str, float]:
        """Compute cosine similarity scores for all nodes.

        Seed nodes already have similarity from ANN retrieval.
        Non-seed nodes require fetching their vector from the vector store.
        """
        scores: dict[str, float] = {}

        for node in nodes:
            if node.is_seed and node.similarity > 0.0:
                # Seed nodes already have similarity from ANN
                scores[node.skill_id] = node.similarity
            else:
                # Non-seed nodes: fetch vector and compute similarity
                sim = await self._compute_node_similarity(node.skill_id, query_vector)
                scores[node.skill_id] = sim

        return scores

    async def _compute_node_similarity(
        self,
        skill_id: str,
        query_vector: np.ndarray,
    ) -> float:
        """Compute cosine similarity between query and a single node's vector."""
        if self.vector_store is None:
            return 0.0

        try:
            # Fetch vector from Milvus
            result = await self.vector_store.get(
                uid=skill_id,
                output_fields=["id", "vector"],
            )
            if result is None:
                return 0.0

            node_vector = np.array(result.get("vector", []), dtype=np.float32)
            if node_vector.size == 0:
                return 0.0

            return self._cosine_similarity(query_vector, node_vector)

        except Exception as e:
            logger.warning(f"Failed to compute similarity for {skill_id}: {e}")
            return 0.0

    async def _compute_local_pagerank(
        self,
        nodes: list[CandidateNode],
    ) -> dict[str, float]:
        """Compute local PageRank within the candidate subgraph.

        Builds a directed graph from REQUIRES edges among candidates
        and runs networkx.pagerank on it. Normalizes to [0, 1].
        """
        try:
            import networkx as nx
        except ImportError:
            logger.warning("networkx not installed, PageRank scores default to 0.0")
            return {n.skill_id: 0.0 for n in nodes}

        skill_ids = [n.skill_id for n in nodes]
        graph = nx.DiGraph()

        # Add all candidate nodes
        for skill_id in skill_ids:
            graph.add_node(skill_id)

        # Fetch REQUIRES edges within the candidate set
        if self.graph_store is not None:
            edges = await self._fetch_requires_edges(skill_ids)
            for edge in edges:
                source = edge.get("source", "")
                target = edge.get("target", "")
                weight = edge.get("weight", 1.0)
                if source in skill_ids and target in skill_ids:
                    graph.add_edge(source, target, weight=weight)

        # Compute PageRank
        if len(graph.edges) == 0:
            # No edges: uniform PageRank
            uniform_score = 1.0 / len(skill_ids) if skill_ids else 0.0
            return {sid: uniform_score for sid in skill_ids}

        try:
            pagerank_scores = nx.pagerank(graph, weight="weight", max_iter=100, tol=1e-06)
        except Exception as e:
            logger.warning(f"PageRank computation failed: {e}")
            return {n.skill_id: 0.0 for n in nodes}

        # Normalize to [0, 1]
        max_score = max(pagerank_scores.values()) if pagerank_scores else 1.0
        if max_score == 0.0:
            max_score = 1.0

        normalized = {k: v / max_score for k, v in pagerank_scores.items()}

        # Ensure all skill_ids have a score
        for sid in skill_ids:
            if sid not in normalized:
                normalized[sid] = 0.0

        return normalized

    async def _fetch_requires_edges(self, skill_ids: list[str]) -> list[dict[str, Any]]:
        """Fetch REQUIRES edges among candidate nodes from graph DB."""
        if self.graph_store is None:
            return []

        try:
            # Use the graph_store's query interface
            # Neo4jClient doesn't have a direct method for this,
            # so we use _execute_query if available
            if hasattr(self.graph_store, "_execute_query"):
                query = """
                MATCH (a:SkillNode)-[r:REQUIRES]->(b:SkillNode)
                WHERE a.uid IN $skill_ids AND b.uid IN $skill_ids
                RETURN a.uid as source, b.uid as target, r.weight as weight
                """
                return await self.graph_store._execute_query(query, {"skill_ids": skill_ids})
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch REQUIRES edges: {e}")
            return []

    def _compute_reliability_scores(
        self,
        nodes: list[CandidateNode],
    ) -> dict[str, float]:
        """Compute reliability scores from historical execution success rate.

        Uses the EWMA-decayed success_rate already stored on each node.
        """
        scores: dict[str, float] = {}
        for node in nodes:
            scores[node.skill_id] = node.execution_success_rate
        return scores

    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def compute_enhancement_score(
        self,
        candidate_pool: CandidatePool,
        vr_seed_ids: set[str],
    ) -> float:
        """Compute the enhancement score: incremental value of graph expansion.

        VR-First architecture: enhancement_score measures whether graph
        expansion on top of VR seeds adds value. It is the difference
        between the average score of expanded skills (seed + 1-hop) and
        the average score of VR seeds alone.

        If enhancement_score ≤ 0, the graph enhancement did not improve
        beyond VR baseline → should fallback to VR result.

        Args:
            candidate_pool: Scored candidate pool (must have scores computed).
            vr_seed_ids: Set of VR baseline skill IDs (ANN top-5 seeds).

        Returns:
            Enhancement score (positive = improvement, ≤0 = no improvement).
        """
        nodes = candidate_pool.get_all_nodes()
        if not nodes:
            return 0.0

        # Average score of VR seed nodes
        seed_nodes = [n for n in nodes if n.skill_id in vr_seed_ids]
        if not seed_nodes:
            return 0.0

        avg_seed_score = sum(n.score for n in seed_nodes) / len(seed_nodes)

        # Average score of all nodes (seed + expanded)
        avg_all_score = sum(n.score for n in nodes) / len(nodes)

        # Enhancement score = avg(all) - avg(seed_only)
        # Positive means expanded nodes add value beyond seeds alone
        enhancement_score = avg_all_score - avg_seed_score

        logger.debug(
            f"Enhancement score: {enhancement_score:.4f} "
            f"(avg_seed={avg_seed_score:.4f}, avg_all={avg_all_score:.4f})"
        )

        return enhancement_score
