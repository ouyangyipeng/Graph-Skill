"""
Routing gateway — the main orchestrator for the routing pipeline.

VR-First Architecture (Phase 6F):
  STEP 1: VR baseline retrieval — ANN top-5 (vector-only)
  STEP 2: Graph enhancement — 1-hop expansion + MWIS with VR protection
  STEP 3: Fallback guarantee — if enhancement ineffective, return VR baseline (NOT zero-shot)
  STEP 4: Context assembly — VR seed skills protected from budget truncation

Core invariant: GS ≥ VR guarantee. GraphSkill's end-to-end effect MUST NOT
be worse than Vector-RAG baseline. Worst case: fallback to VR results.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Optional
from uuid import UUID

import numpy as np

from graphskill.core.constants import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TOP_K,
    DEFAULT_EXPANSION_DEPTH,
    CACHE_TTL_SECONDS,
)
from graphskill.core.exceptions import (
    NoSkillsFoundError,
    RoutingError,
    RoutingTimeoutError,
)
from graphskill.core.models import (
    RoutingRequest,
    RoutingResponse,
    SelectedSkill,
    RoutingConstraints,
)
from graphskill.routing.models import (
    CandidatePool,
    ConflictGraph,
    RoutingMetrics,
    ScoringConfig,
    AssembledContext,
    EnhancementResult,
    VRSeedProtectionConfig,
)
from graphskill.routing.query_processor import QueryProcessor
from graphskill.routing.embedding_service import EmbeddingService
from graphskill.routing.hybrid_retriever import HybridRetriever
from graphskill.routing.scoring_engine import ScoringEngine
from graphskill.routing.conflict_pruner import ConflictPruner
from graphskill.routing.context_assembler import ContextAssembler

logger = logging.getLogger(__name__)


class RoutingGateway:
    """Main routing gateway orchestrating the VR-first pipeline.

    This is the primary entry point for the GraphSkill routing system.
    It coordinates all sub-modules following the VR-first architecture:

    STEP 1: VR baseline retrieval (ANN top-5)
    STEP 2: Graph enhancement on VR seed (1-hop + MWIS with protection)
    STEP 3: Fallback guarantee (VR baseline if enhancement fails)
    STEP 4: Context assembly (VR seed skills prioritized)

    Core invariant: GS ≥ VR — never return worse than Vector-RAG baseline.

    Args:
        vector_store: MilvusClient instance.
        graph_store: Neo4jClient instance.
        cache_client: Optional RedisClient for result caching.
        embedding_service: EmbeddingService instance (or config to create one).
        scoring_config: Scoring hyperparameters.
        vr_seed_protection: VR seed protection configuration.
        top_k: Default number of seed nodes (VR baseline top-5).
        expansion_depth: Default graph expansion depth (1-hop).
        max_tokens: Default token budget.
    """

    def __init__(
        self,
        vector_store: Any,
        graph_store: Any,
        cache_client: Any = None,
        embedding_service: Optional[EmbeddingService] = None,
        scoring_config: Optional[ScoringConfig] = None,
        vr_seed_protection: Optional[VRSeedProtectionConfig] = None,
        top_k: int = DEFAULT_TOP_K,
        expansion_depth: int = DEFAULT_EXPANSION_DEPTH,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.cache_client = cache_client

        # Initialize sub-modules
        self.query_processor = QueryProcessor()
        self.embedding_service = embedding_service or EmbeddingService()
        self.hybrid_retriever = HybridRetriever(
            vector_store=vector_store,
            graph_store=graph_store,
            top_k=top_k,
            expansion_depth=expansion_depth,
        )
        self.scoring_engine = ScoringEngine(
            config=scoring_config or ScoringConfig(),
            vector_store=vector_store,
            graph_store=graph_store,
        )
        self.conflict_pruner = ConflictPruner(graph_store=graph_store)
        self.context_assembler = ContextAssembler(
            graph_store=graph_store,
        )

        self.top_k = top_k
        self.expansion_depth = expansion_depth
        self.max_tokens = max_tokens
        self.vr_seed_protection = vr_seed_protection or VRSeedProtectionConfig()

    async def route(self, request: RoutingRequest) -> RoutingResponse:
        """Execute the VR-first routing pipeline for a request.

        VR-First 4-Phase Pipeline:
        STEP 1: VR baseline retrieval — ANN top-5 (vector-only)
        STEP 2: Graph enhancement — 1-hop expansion + MWIS with VR protection
        STEP 3: Fallback guarantee — VR baseline if enhancement ineffective
        STEP 4: Context assembly — VR seed skills protected from truncation

        GS ≥ VR guarantee: never return worse than Vector-RAG baseline.
        Worst case: fallback to VR results (NOT zero-shot).

        Args:
            request: Routing request with query and constraints.

        Returns:
            RoutingResponse with selected skills and assembled context.

        Raises:
            RoutingTimeoutError: If pipeline exceeds time limit.
            NoSkillsFoundError: If no skills are found at all.
            RoutingError: For other routing failures.
        """
        metrics = RoutingMetrics()
        fallback_used = False
        start_total = time.perf_counter()

        try:
            # Pre-step: Check cache for previous result
            cache_hit = False
            if self.cache_client is not None:
                cached = await self._check_cache(request.query)
                if cached is not None:
                    cache_hit = True
                    metrics.cache_hit = True
                    logger.info(f"Cache hit for query: {request.query[:50]}...")

            # Pre-step: Query processing (noise reduction)
            t0 = time.perf_counter()
            processed_query = self.query_processor.process(
                raw_query=request.query,
                context_state=request.context,
            )
            metrics.query_processing_ms = int((time.perf_counter() - t0) * 1000)

            # Pre-step: Embedding generation
            t0 = time.perf_counter()
            query_vector = await self.embedding_service.generate(processed_query.enriched)
            metrics.embedding_ms = int((time.perf_counter() - t0) * 1000)

            # STEP 1: VR baseline retrieval — ANN top-5 + 1-hop expansion
            # Single retrieval pass: seed nodes are VR baseline,
            # expanded nodes are graph enhancement candidates.
            t0 = time.perf_counter()
            candidate_pool, retrieval_ms = await self._vr_baseline_retrieve(
                query_vector, request
            )
            metrics.retrieval_ms = retrieval_ms

            # Identify VR seed IDs (the ANN top-5 nodes)
            vr_seed_ids = [n.skill_id for n in candidate_pool.get_seed_nodes()]
            metrics.seed_count = len(vr_seed_ids)
            metrics.expanded_count = len(candidate_pool.nodes)

            # STEP 2: Graph enhancement — scoring + MWIS with VR protection
            enhancement_result, candidate_pool, conflict_graph = await self._graph_enhance(
                candidate_pool, vr_seed_ids, query_vector, request
            )

            # Update metrics from enhancement
            if conflict_graph is not None:
                metrics.conflict_count = len(conflict_graph.conflict_edges) + len(
                    conflict_graph.substitute_edges
                )
                metrics.pruned_count = metrics.expanded_count - len(
                    enhancement_result.final_ids if enhancement_result else vr_seed_ids
                )
                metrics.final_count = len(
                    enhancement_result.final_ids if enhancement_result else vr_seed_ids
                )

            # STEP 3: Fallback guarantee
            # If graph enhancement is ineffective, return VR baseline (NOT zero-shot!)
            if enhancement_result is None or not enhancement_result.improved:
                logger.info(
                    f"Graph enhancement ineffective (score={enhancement_result.enhancement_score if enhancement_result else 'N/A'}), "
                    f"falling back to VR baseline ({len(vr_seed_ids)} skills)"
                )
                return await self._build_vr_response(
                    vr_seed_ids, candidate_pool, request, metrics,
                    start_total, enhancement_result
                )

            # STEP 4: Context assembly with VR seed protection
            max_tokens = request.max_tokens or self.max_tokens
            t0 = time.perf_counter()
            assembled_context, assembly_ms = await self.context_assembler.assemble(
                pruned_skill_ids=enhancement_result.final_ids,
                candidate_pool=candidate_pool,
                max_tokens=max_tokens,
                vr_seed_ids=vr_seed_ids,
            )
            metrics.assembly_ms = assembly_ms

            # Compute quality metrics
            if conflict_graph is not None:
                self._compute_quality_metrics(
                    metrics, candidate_pool, conflict_graph, enhancement_result.final_ids
                )

            # Build enhanced response
            selected_skills = self._build_selected_skills(
                enhancement_result.final_ids, candidate_pool, assembled_context
            )

            if not selected_skills:
                raise NoSkillsFoundError(
                    f"No skills found for query: {request.query[:100]}"
                )

            metrics.total_ms = int((time.perf_counter() - start_total) * 1000)

            response = RoutingResponse(
                request_id=request.request_id,
                selected_skills=selected_skills,
                total_tokens=assembled_context.total_tokens,
                routing_time_ms=metrics.total_ms,
                confidence=self._compute_confidence(selected_skills),
                fallback_used=fallback_used,
                metadata={
                    "metrics": metrics.model_dump(),
                    "enhancement_result": enhancement_result.model_dump(),
                    "assembled_text": assembled_context.assembled_text,
                    "budget_exceeded": assembled_context.budget_exceeded,
                    "skipped_skills": assembled_context.skipped_skills,
                },
            )

            # Cache result
            if self.cache_client is not None and not cache_hit:
                await self._cache_result(request.query, response)

            return response

        except NoSkillsFoundError:
            raise
        except RoutingError:
            raise
        except Exception as e:
            logger.error(f"Routing pipeline failed: {e}", exc_info=True)
            # Attempt fallback — target is VR baseline (NOT zero-shot)
            fallback_response = await self._fallback_route(request, str(e))
            if fallback_response is not None:
                return fallback_response
            raise RoutingError(f"Routing pipeline failed: {e}")

    # ============================================
    # VR-First Pipeline Steps
    # ============================================

    async def _vr_baseline_retrieve(
        self,
        query_vector: np.ndarray,
        request: RoutingRequest,
    ) -> tuple[CandidatePool, int]:
        """STEP 1: VR baseline retrieval — ANN top-5 + 1-hop expansion.

        Single retrieval pass that produces both:
        - VR seed nodes (ANN top-5): the Vector-RAG baseline
        - Expanded nodes (1-hop): graph enhancement candidates

        The hybrid retriever performs ANN search first, then expands
        seed nodes 1-hop. Both phases happen in one call for efficiency.

        Args:
            query_vector: Query embedding vector.
            request: Routing request (for constraint-aware top_k override).

        Returns:
            Tuple of (CandidatePool with seeds + expanded, retrieval_latency_ms).
        """
        effective_top_k = self.top_k
        if request.constraints and request.constraints.max_dependency_depth:
            effective_top_k = request.constraints.max_dependency_depth

        candidate_pool, retrieval_ms = await self.hybrid_retriever.retrieve(
            query_vector=query_vector,
            top_k=effective_top_k,
            expansion_depth=1,  # VR-First: hard limit 1-hop
        )

        vr_seed_ids = [n.skill_id for n in candidate_pool.get_seed_nodes()]
        logger.info(
            f"VR baseline retrieval: {len(vr_seed_ids)} seeds, "
            f"{len(candidate_pool.nodes)} total candidates, "
            f"{retrieval_ms}ms"
        )

        return candidate_pool, retrieval_ms

    async def _graph_enhance(
        self,
        candidate_pool: CandidatePool,
        vr_seed_ids: list[str],
        query_vector: np.ndarray,
        request: RoutingRequest,
    ) -> tuple[Optional[EnhancementResult], CandidatePool, Optional[ConflictGraph]]:
        """STEP 2: Graph enhancement — scoring + MWIS with VR seed protection.

        Takes the candidate pool from _vr_baseline_retrieve (which already
        contains both VR seed and 1-hop expanded nodes), applies:
        1. Constraint filtering
        2. Dynamic composite scoring (α=0.8, β=0.1, γ=0.1)
        3. Enhancement score computation
        4. MWIS pruning with VR seed protection

        Returns EnhancementResult indicating whether graph expansion added
        value beyond VR baseline. If enhancement_score ≤ 0, the result
        will have improved=False, triggering fallback to VR baseline.

        Args:
            candidate_pool: Pool from VR baseline retrieval (seeds + expanded).
            vr_seed_ids: VR baseline skill IDs (ANN top-5).
            query_vector: Query embedding vector.
            request: Routing request with constraints.

        Returns:
            Tuple of (EnhancementResult or None, updated CandidatePool,
            ConflictGraph or None).
        """
        vr_seed_set = set(vr_seed_ids)

        try:
            # Apply constraints (exclude/require skills, min reliability)
            if request.constraints:
                candidate_pool = self._apply_constraints(candidate_pool, request.constraints)

            # Dynamic scoring
            t0 = time.perf_counter()
            candidate_pool, scoring_ms = await self.scoring_engine.score_all(
                candidate_pool, query_vector
            )
            logger.debug(f"Scoring: {scoring_ms}ms for {len(candidate_pool.nodes)} nodes")

            # MWIS pruning with VR seed protection FIRST — then evaluate improvement
            # Key insight: compute_enhancement_score on the un-pruned pool almost always
            # yields a negative value because expanded nodes have lower similarity than seeds.
            # But MWIS is designed to only keep expanded nodes that pass conflict+quality
            # checks, so if it retains extras beyond VR seeds → they add topology value.
            t0 = time.perf_counter()
            pruned_ids, conflict_graph, pruning_ms = await self.conflict_pruner.prune_with_protection(
                candidate_pool, vr_seed_set
            )
            logger.debug(
                f"MWIS with protection: {pruning_ms}ms, "
                f"{len(candidate_pool.nodes)} → {len(pruned_ids)} skills, "
                f"VR seeds preserved={len(vr_seed_set & set(pruned_ids))}/{len(vr_seed_set)}"
            )

            # Determine improvement: MWIS kept expanded nodes beyond VR seeds → topology adds value
            # This is the correct VR-First logic: if MWIS protection + pruning results in
            # more skills than just VR seeds, the graph provided useful context/dependencies.
            expanded_ids = [sid for sid in pruned_ids if sid not in vr_seed_set]
            improved = len(expanded_ids) > 0

            # Compute enhancement_score on the PRUNED result (seeds + surviving expanded)
            # This reflects the actual quality of the final selection, not the raw expansion.
            pruned_out_ids = [
                sid for sid in candidate_pool.get_skill_ids()
                if sid not in set(pruned_ids)
            ]

            # Build a sub-pool of only the pruned_ids for score computation
            pruned_nodes = [
                candidate_pool.nodes[sid] for sid in pruned_ids
                if sid in candidate_pool.nodes
            ]
            seed_nodes_in_pruned = [
                n for n in pruned_nodes if n.skill_id in vr_seed_set
            ]

            if improved and pruned_nodes and seed_nodes_in_pruned:
                avg_pruned = sum(n.score for n in pruned_nodes) / len(pruned_nodes)
                avg_seeds = sum(n.score for n in seed_nodes_in_pruned) / len(seed_nodes_in_pruned)
                enhancement_score = max(0.0, avg_pruned - avg_seeds)
            else:
                enhancement_score = 0.0

            # When not improved, final_ids MUST equal vr_seed_ids (fallback guarantee)
            final_ids = pruned_ids if improved else vr_seed_ids

            enhancement_result = EnhancementResult(
                vr_seed_ids=vr_seed_ids,
                expanded_ids=expanded_ids if improved else [],
                pruned_ids=pruned_out_ids if improved else [],
                final_ids=final_ids,
                improved=improved,
                enhancement_score=enhancement_score,
            )

            logger.info(
                f"Graph enhancement: improved={improved}, "
                f"enhancement_score={enhancement_score:.4f}, "
                f"vr_seeds={len(vr_seed_ids)}, expanded={len(expanded_ids)}, "
                f"final={len(final_ids)}"
            )

            return enhancement_result, candidate_pool, conflict_graph

        except Exception as e:
            logger.warning(f"Graph enhancement failed: {e}", exc_info=True)
            return None, candidate_pool, None

    async def _build_vr_response(
        self,
        vr_seed_ids: list[str],
        candidate_pool: CandidatePool,
        request: RoutingRequest,
        metrics: RoutingMetrics,
        start_total: float,
        enhancement_result: Optional[EnhancementResult],
    ) -> RoutingResponse:
        """STEP 3 fallback: Build response from VR baseline when enhancement is ineffective.

        This is NOT a zero-shot fallback — we always return the VR baseline results.
        The GS ≥ VR guarantee ensures that even when graph enhancement fails,
        the user receives at least the Vector-RAG baseline quality.

        IMPORTANT: We also assemble context text for VR seeds so that the LLM
        receives meaningful skill documentation — NOT just skill metadata summaries.
        Without assembled_text, GS produces zero-shot-like quality (GS ≈ ZS).

        Args:
            vr_seed_ids: VR baseline skill IDs (ANN top-5).
            candidate_pool: Candidate pool (may have scoring data on seed nodes).
            request: Original routing request.
            metrics: Routing metrics to update.
            start_total: Pipeline start timestamp.
            enhancement_result: Enhancement result (improved=False or None).

        Returns:
            RoutingResponse with VR baseline skills AND assembled context text.
        """
        selected_skills: list[SelectedSkill] = []

        for skill_id in vr_seed_ids:
            node = candidate_pool.nodes.get(skill_id)
            if node is None:
                continue

            # Use similarity as the score (VR baseline = vector-only)
            sim_clamped = max(0.0, min(1.0, node.similarity))
            score_clamped = max(0.0, min(1.0, node.score if node.score > 0 else sim_clamped))

            selected_skills.append(
                SelectedSkill(
                    skill_uid=node.skill_id,
                    skill_version=node.version,
                    intent_description=node.intent_description,
                    permissions=node.permissions,
                    score=score_clamped,
                    is_required=False,
                    dependency_depth=0,
                    similarity_score=sim_clamped,
                    pagerank_score=max(0.0, min(1.0, node.pagerank_score)),
                    reliability_score=max(0.0, min(1.0, node.reliability_score)),
                )
            )

        # Assemble context text for VR seeds — critical for GS ≥ VR guarantee!
        # Without assembled_text, the LLM only sees skill metadata summaries,
        # which produces zero-shot-like quality (GS ≈ ZS, far below VR).
        assembled_context = None
        try:
            max_tokens = request.max_tokens or self.max_tokens
            assembled_context, assembly_ms = await self.context_assembler.assemble(
                pruned_skill_ids=vr_seed_ids,
                candidate_pool=candidate_pool,
                max_tokens=max_tokens,
                vr_seed_ids=set(vr_seed_ids),
            )
            metrics.assembly_ms = assembly_ms
        except Exception as e:
            logger.warning(f"Context assembly for VR baseline failed: {e}")

        metrics.total_ms = int((time.perf_counter() - start_total) * 1000)
        metrics.final_count = len(selected_skills)

        # Build EnhancementResult for metadata if not provided
        if enhancement_result is None:
            enhancement_result = EnhancementResult(
                vr_seed_ids=vr_seed_ids,
                expanded_ids=[],
                pruned_ids=[],
                final_ids=vr_seed_ids,
                improved=False,
                enhancement_score=0.0,
            )

        # Include assembled_text in metadata (critical for downstream LLM injection)
        assembled_text = assembled_context.assembled_text if assembled_context else ""

        return RoutingResponse(
            request_id=request.request_id,
            selected_skills=selected_skills,
            total_tokens=assembled_context.total_tokens if assembled_context else 0,
            routing_time_ms=metrics.total_ms,
            confidence=self._compute_confidence(selected_skills),
            fallback_used=False,  # VR baseline is NOT a fallback — it's the guaranteed baseline
            metadata={
                "metrics": metrics.model_dump(),
                "enhancement_result": enhancement_result.model_dump(),
                "assembled_text": assembled_text,
                "mode": "vr_baseline",
            },
        )

    # ============================================
    # Fallback Route (Exception Handling)
    # ============================================

    async def _fallback_route(
        self, request: RoutingRequest, error_message: str
    ) -> Optional[RoutingResponse]:
        """Fallback routing for exception scenarios (e.g., database failure).

        VR-First: fallback target is VR baseline (ANN top-5), NOT zero-shot.
        Per RFC-03 Section 8.3, when the full pipeline fails, the system
        SHOULD degrade gracefully to vector-only retrieval (VR baseline).
        """
        logger.warning(f"Entering fallback mode (VR baseline) due to: {error_message}")

        try:
            processed_query = self.query_processor.process(
                raw_query=request.query,
                context_state=request.context,
            )
            query_vector = await self.embedding_service.generate(processed_query.enriched)

            # VR baseline fallback: vector-only retrieval (ANN top-5)
            search_result = await self.vector_store.search(
                query_vector=query_vector.tolist(),
                top_k=self.top_k,  # VR baseline top-5
                output_fields=["id"],
            )

            selected_skills: list[SelectedSkill] = []
            for hit in search_result.results[:self.top_k]:
                skill_id = hit.get("id", "")
                distance = hit.get("distance", 0.0)
                similarity = max(0.0, min(1.0, 1.0 - distance))

                selected_skills.append(
                    SelectedSkill(
                        skill_uid=skill_id,
                        skill_version="1.0.0",
                        intent_description="",
                        permissions=[],
                        score=similarity,
                        is_required=False,
                        dependency_depth=0,
                        similarity_score=similarity,
                    )
                )

            if not selected_skills:
                return None

            # Build EnhancementResult indicating fallback
            fallback_enhancement = EnhancementResult(
                vr_seed_ids=[s.skill_uid for s in selected_skills],
                expanded_ids=[],
                pruned_ids=[],
                final_ids=[s.skill_uid for s in selected_skills],
                improved=False,
                enhancement_score=0.0,
            )

            return RoutingResponse(
                request_id=request.request_id,
                selected_skills=selected_skills,
                total_tokens=0,
                routing_time_ms=0,
                confidence=0.5,  # Lower confidence for fallback
                fallback_used=True,
                metadata={
                    "fallback_reason": error_message,
                    "mode": "vr_baseline_fallback",
                    "enhancement_result": fallback_enhancement.model_dump(),
                },
            )

        except Exception as fallback_error:
            logger.error(f"VR baseline fallback also failed: {fallback_error}")
            return None

    # ============================================
    # Preserved Helper Methods
    # ============================================

    def _apply_constraints(
        self,
        candidate_pool: CandidatePool,
        constraints: RoutingConstraints,
    ) -> CandidatePool:
        """Apply routing constraints to filter the candidate pool.

        - excluded_skills: Remove these skills
        - required_skills: Ensure these are included (if present in pool)
        - min_reliability: Filter low-reliability skills
        - skill_categories: Filter by category (if tags available)
        """
        nodes_to_remove: set[str] = set()

        # Exclude skills
        if constraints.excluded_skills:
            for skill_id in constraints.excluded_skills:
                nodes_to_remove.add(skill_id)

        # Filter by minimum reliability
        for node in candidate_pool.get_all_nodes():
            if node.execution_success_rate < constraints.min_reliability:
                nodes_to_remove.add(node.skill_id)

        # Remove filtered nodes
        for skill_id in nodes_to_remove:
            candidate_pool.nodes.pop(skill_id, None)

        return candidate_pool

    def _build_selected_skills(
        self,
        pruned_ids: list[str],
        candidate_pool: CandidatePool,
        assembled_context: AssembledContext,
    ) -> list[SelectedSkill]:
        """Build SelectedSkill list from pruned IDs and candidate pool."""
        included_set = set(assembled_context.skills)
        selected: list[SelectedSkill] = []

        for skill_id in pruned_ids:
            node = candidate_pool.nodes.get(skill_id)
            if node is None:
                continue

            # Only include skills that made it through token budget
            if skill_id not in included_set:
                continue

            # Clamp sub-scores to [0, 1] — cosine similarity can be negative
            # but SelectedSkill fields require ge=0.0
            sim_clamped = max(0.0, min(1.0, node.similarity_score))
            pr_clamped = max(0.0, min(1.0, node.pagerank_score))
            rel_clamped = max(0.0, min(1.0, node.reliability_score))
            score_clamped = max(0.0, min(1.0, node.score))

            selected.append(
                SelectedSkill(
                    skill_uid=node.skill_id,
                    skill_version=node.version,
                    intent_description=node.intent_description,
                    permissions=node.permissions,
                    score=score_clamped,
                    is_required=(node.edge_type == "REQUIRES"),
                    dependency_depth=node.depth,
                    similarity_score=sim_clamped,
                    pagerank_score=pr_clamped,
                    reliability_score=rel_clamped,
                )
            )

        return selected

    def _compute_confidence(self, selected_skills: list[SelectedSkill]) -> float:
        """Compute overall routing confidence.

        Based on average score of selected skills.
        """
        if not selected_skills:
            return 0.0

        avg_score = sum(s.score for s in selected_skills) / len(selected_skills)
        return min(1.0, avg_score)

    def _compute_quality_metrics(
        self,
        metrics: RoutingMetrics,
        candidate_pool: CandidatePool,
        conflict_graph: ConflictGraph,
        pruned_ids: list[str],
    ) -> None:
        """Compute routing quality metrics.

        - skill_coverage: fraction of seeds that survived pruning
        - dependency_correctness: fraction of required deps included
        - conflict_resolution: fraction of conflicts resolved by pruning
        """
        # Skill coverage: how many seeds made it to final set
        seed_ids = {n.skill_id for n in candidate_pool.get_seed_nodes()}
        if seed_ids:
            metrics.skill_coverage = len(seed_ids & set(pruned_ids)) / len(seed_ids)
        else:
            metrics.skill_coverage = 0.0

        # Dependency correctness: how many REQUIRES deps are included
        requires_nodes = [
            n for n in candidate_pool.get_all_nodes() if n.edge_type == "REQUIRES"
        ]
        if requires_nodes:
            included_deps = sum(1 for n in requires_nodes if n.skill_id in pruned_ids)
            metrics.dependency_correctness = included_deps / len(requires_nodes)
        else:
            metrics.dependency_correctness = 1.0  # No deps to satisfy

        # Conflict resolution: how many conflicts were resolved
        total_conflicts = len(conflict_graph.conflict_edges) + len(
            conflict_graph.substitute_edges
        )
        if total_conflicts > 0:
            # Count remaining conflicts in pruned set
            pruned_set = set(pruned_ids)
            remaining = 0
            for a, b, _ in conflict_graph.conflict_edges:
                if a in pruned_set and b in pruned_set:
                    remaining += 1
            for a, b, _ in conflict_graph.substitute_edges:
                if a in pruned_set and b in pruned_set:
                    remaining += 1
            metrics.conflict_resolution = (
                (total_conflicts - remaining) / total_conflicts
                if total_conflicts > 0
                else 1.0
            )
        else:
            metrics.conflict_resolution = 1.0

    async def _check_cache(self, query: str) -> Optional[dict]:
        """Check Redis cache for a previous routing result."""
        if self.cache_client is None:
            return None

        try:
            query_hash = self._compute_query_hash(query)
            cache_key = f"routing:{query_hash}"
            cached = await self.cache_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache check failed: {e}")

        return None

    async def _cache_result(self, query: str, response: RoutingResponse) -> None:
        """Cache a routing result in Redis."""
        if self.cache_client is None:
            return

        try:
            query_hash = self._compute_query_hash(query)
            cache_key = f"routing:{query_hash}"
            cache_data = {
                "skills": [s.model_dump() for s in response.selected_skills],
                "token_count": response.total_tokens,
                "cached_at": time.time(),
            }
            await self.cache_client.set(
                key=cache_key,
                value=json.dumps(cache_data),
                ttl=CACHE_TTL_SECONDS,
            )
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")

    @staticmethod
    def _compute_query_hash(query: str) -> str:
        """Compute a stable hash for a query string."""
        return hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]