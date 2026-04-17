"""
Context assembler with topological sorting and token budget control.

Implements RFC-03 Section 7: 上下文拼装与 Token 截断.
- Topological sort based on REQUIRES dependencies
- Token budget control using tiktoken
- Truncation strategy prioritizing hard dependencies and seed nodes
- Structured XML output format
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from graphskill.routing.models import (
    CandidatePool,
    CandidateNode,
    AssembledContext,
)

logger = logging.getLogger(__name__)

# Default tokenizer encoding for OpenAI models
_DEFAULT_TOKENIZER = "cl100k_base"


class TopologicalSorter:
    """Topological sorter for skill dependency ordering.

    Per RFC-03 Section 7.1, skills MUST be sorted so that
    depended-upon skills appear before their dependents.
    """

    def __init__(self, graph_store: Any = None) -> None:
        self.graph_store = graph_store

    async def sort(
        self,
        skill_ids: list[str],
        candidate_pool: Optional[CandidatePool] = None,
        vr_seed_ids: list[str] = [],
    ) -> list[str]:
        """Topologically sort skill IDs based on REQUIRES edges.

        Uses networkx for topological sort. Falls back to original
        order if a cycle is detected (should not happen due to DAG
        validation in ingestion).

        Args:
            skill_ids: Skill IDs to sort.
            candidate_pool: Optional candidate pool for local edge lookup.

        Returns:
            Sorted skill IDs with dependencies first.
        """
        if len(skill_ids) <= 1:
            return list(skill_ids)

        # VR-First: ensure VR seed skills always appear first in the sort
        # regardless of topological dependencies
        vr_seed_set = set(vr_seed_ids)

        try:
            import networkx as nx
        except ImportError:
            logger.warning("networkx not installed, returning original order")
            return list(skill_ids)

        # Build dependency graph
        graph = nx.DiGraph()
        for skill_id in skill_ids:
            graph.add_node(skill_id)

        # Fetch REQUIRES edges within the skill set
        # Edge direction in Neo4j: (source)-[:REQUIRES]->(target) means
        # source depends on target. For topological sort (dependencies first),
        # we reverse the edge: target -> source.
        edges = await self._fetch_requires_edges(skill_ids, candidate_pool)
        for source, target in edges:
            if source in skill_ids and target in skill_ids:
                graph.add_edge(target, source)

        # Topological sort
        try:
            sorted_ids = list(nx.topological_sort(graph))

            # VR-First: reorder so VR seed skills come first
            if vr_seed_set:
                seed_sorted = [sid for sid in sorted_ids if sid in vr_seed_set]
                non_seed_sorted = [sid for sid in sorted_ids if sid not in vr_seed_set]
                return seed_sorted + non_seed_sorted

            return sorted_ids
        except nx.NetworkXUnfeasible:
            # Cycle detected (should not happen with proper DAG validation)
            logger.warning(f"Cycle detected in skill dependencies for: {skill_ids}")
            return list(skill_ids)

    async def _fetch_requires_edges(
        self,
        skill_ids: list[str],
        candidate_pool: Optional[CandidatePool] = None,
    ) -> list[tuple[str, str]]:
        """Fetch REQUIRES edges among the given skill IDs.

        Tries graph_store first, then falls back to candidate_pool
        expansion paths.
        """
        edges: list[tuple[str, str]] = []

        # Try graph_store
        if self.graph_store is not None and hasattr(self.graph_store, "_execute_query"):
            try:
                query = """
                MATCH (a:SkillNode)-[r:REQUIRES]->(b:SkillNode)
                WHERE a.uid IN $skill_ids AND b.uid IN $skill_ids
                RETURN a.uid as source, b.uid as target
                """
                results = await self.graph_store._execute_query(
                    query, {"skill_ids": skill_ids}
                )
                for r in results:
                    edges.append((r["source"], r["target"]))
            except Exception as e:
                logger.warning(f"Failed to fetch REQUIRES edges for topo sort: {e}")

        # Fallback: infer from candidate pool expansion paths
        if not edges and candidate_pool is not None:
            for node in candidate_pool.get_all_nodes():
                if node.edge_type == "REQUIRES" and len(node.expansion_path) >= 2:
                    # The last two elements in expansion_path give the edge
                    source = node.expansion_path[-2]
                    target = node.skill_id
                    if source in skill_ids and target in skill_ids:
                        edges.append((source, target))

        return edges


class TokenBudgetController:
    """Token budget controller using tiktoken.

    Per RFC-03 Section 7.2, the system MUST respect token budget
    limits using the same tokenizer as the downstream LLM.
    """

    def __init__(self, tokenizer_name: str = _DEFAULT_TOKENIZER) -> None:
        self._tokenizer_name = tokenizer_name
        self._tokenizer: Any = None

    def _ensure_tokenizer(self) -> None:
        """Lazy-initialize the tokenizer."""
        if self._tokenizer is not None:
            return

        try:
            import tiktoken
            self._tokenizer = tiktoken.get_encoding(self._tokenizer_name)
        except ImportError:
            logger.warning("tiktoken not installed, using approximate word-count tokenization")
            self._tokenizer = None
        except Exception as e:
            logger.warning(f"Failed to load tiktoken tokenizer: {e}, using approximation")
            self._tokenizer = None

    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in text.

        Uses tiktoken if available, otherwise falls back to
        approximate word-based counting.
        """
        self._ensure_tokenizer()

        if self._tokenizer is not None:
            return len(self._tokenizer.encode(text))

        # Approximate: ~1.3 tokens per word for English
        return int(len(text.split()) * 1.3)

    def assemble_with_budget(
        self,
        sorted_skills: list[str],
        skill_contents: dict[str, str],
        max_tokens: int,
        reserved_tokens: int = 500,
        candidate_pool: Optional[CandidatePool] = None,
        vr_seed_ids: list[str] = [],
    ) -> AssembledContext:
        """Assemble context within token budget.

        Per RFC-03 Section 7.2 and 7.3:
        - Skills are added in topological order
        - Hard dependencies and seed nodes are prioritized
        - ENHANCES nodes are deprioritized when budget is tight
        - Budget overflow is logged as a warning

        Args:
            sorted_skills: Topologically sorted skill IDs.
            skill_contents: Mapping from skill ID to content text.
            max_tokens: Maximum token budget.
            reserved_tokens: Tokens reserved for system prompt.
            candidate_pool: Optional pool for priority calculation.

        Returns:
            AssembledContext with included/skipped skills and text.
        """
        available_tokens = max_tokens - reserved_tokens
        if available_tokens <= 0:
            logger.warning(f"Token budget too small: max={max_tokens}, reserved={reserved_tokens}")
            return AssembledContext(
                skills=[],
                skipped_skills=list(sorted_skills),
                total_tokens=reserved_tokens,
                assembled_text="",
                budget_exceeded=True,
            )

        # Re-prioritize skills if candidate_pool is available
        # VR-First: VR seed skills get absolute priority (never dropped)
        prioritized = self._prioritize_skills(sorted_skills, candidate_pool, vr_seed_ids)

        assembled_skills: list[str] = []
        total_tokens = 0
        skipped_skills: list[str] = []

        for skill_id in prioritized:
            content = skill_contents.get(skill_id, "")
            if not content:
                # Skill with no content: include with minimal overhead
                assembled_skills.append(skill_id)
                continue

            skill_tokens = self.count_tokens(content)

            if total_tokens + skill_tokens <= available_tokens:
                assembled_skills.append(skill_id)
                total_tokens += skill_tokens
            else:
                skipped_skills.append(skill_id)

        # Re-sort assembled skills back to topological order
        topo_order = {sid: idx for idx, sid in enumerate(sorted_skills)}
        assembled_skills.sort(key=lambda x: topo_order.get(x, 999))

        # Assemble text
        assembled_text = self._assemble_text(assembled_skills, skill_contents)

        budget_exceeded = len(skipped_skills) > 0
        if budget_exceeded:
            logger.warning(
                f"Token budget exceeded: {len(skipped_skills)} skills skipped "
                f"({total_tokens + reserved_tokens}/{max_tokens} tokens)"
            )

        return AssembledContext(
            skills=assembled_skills,
            skipped_skills=skipped_skills,
            total_tokens=total_tokens + reserved_tokens,
            assembled_text=assembled_text,
            budget_exceeded=budget_exceeded,
        )

    def _prioritize_skills(
        self,
        skill_ids: list[str],
        candidate_pool: Optional[CandidatePool] = None,
        vr_seed_ids: list[str] = [],
    ) -> list[str]:
        """Re-prioritize skills for budget-constrained inclusion.

        Per RFC-03 Section 7.3:
        1. VR seed skills — highest (never dropped by budget truncation)
        2. Hard dependency nodes (REQUIRES is_hard=true) — very high
        3. Seed nodes — high
        4. High composite score — medium
        5. ENHANCES-only nodes — low (first to drop)

        VR-First: VR seed skills have absolute priority — they cannot
        be removed by token budget truncation.
        """
        if candidate_pool is None:
            return list(skill_ids)

        vr_seed_set = set(vr_seed_ids)
        priorities: dict[str, float] = {}
        for skill_id in skill_ids:
            node = candidate_pool.nodes.get(skill_id)
            if node is None:
                priorities[skill_id] = 0.0
                continue

            priority = 0.0

            # VR seed absolute priority — cannot be dropped
            if skill_id in vr_seed_set:
                priority += 200.0

            # Seed node bonus
            if node.is_seed:
                priority += 50.0

            # Hard dependency bonus (edge_type == REQUIRES means this node
            # was reached via a REQUIRES edge, implying it's a dependency)
            if node.edge_type == "REQUIRES":
                priority += 100.0

            # Composite score bonus
            priority += node.score * 10.0

            # ENHANCES penalty (deprioritize)
            if node.edge_type == "ENHANCES" and not node.is_seed and skill_id not in vr_seed_set:
                priority -= 20.0

            priorities[skill_id] = priority

        return sorted(skill_ids, key=lambda x: priorities.get(x, 0.0), reverse=True)

    def _assemble_text(
        self,
        skill_ids: list[str],
        skill_contents: dict[str, str],
    ) -> str:
        """Assemble skill content into concise bullet point format.

        Each skill occupies a single line to minimize token consumption
        while preserving core intent information for LLM reference.
        Format: Relevant knowledge:
                • skill_id: one-line core description
        """
        if not skill_ids:
            return ""

        lines: list[str] = ["Relevant knowledge:"]
        for skill_id in skill_ids:
            content = skill_contents.get(skill_id, "")
            if content:
                # Take first line as core description, truncate to ~80 chars
                core_desc = content.split("\n")[0][:80]
                lines.append(f"• {skill_id}: {core_desc}")

        return "\n".join(lines)


class ContextAssembler:
    """High-level context assembler combining topological sort and budget control.

    Provides a single `assemble` method that:
    1. Topologically sorts the pruned skill set
    2. Fetches skill content
    3. Applies token budget control
    4. Returns assembled context

    Args:
        graph_store: Neo4jClient for dependency queries.
        tokenizer_name: tiktoken encoding name.
    """

    def __init__(
        self,
        graph_store: Any = None,
        tokenizer_name: str = _DEFAULT_TOKENIZER,
    ) -> None:
        self.sorter = TopologicalSorter(graph_store)
        self.budget_controller = TokenBudgetController(tokenizer_name)

    async def assemble(
        self,
        pruned_skill_ids: list[str],
        candidate_pool: CandidatePool,
        max_tokens: int = 4096,
        reserved_tokens: int = 500,
        vr_seed_ids: list[str] = [],
    ) -> tuple[AssembledContext, int]:
        """Assemble context from pruned skills.

        VR-First: VR seed skills are prioritized in topological sort
        and cannot be dropped by token budget truncation.

        Args:
            pruned_skill_ids: Skill IDs after MWIS pruning.
            candidate_pool: Candidate pool with node metadata.
            max_tokens: Maximum token budget.
            reserved_tokens: Tokens reserved for system prompt.
            vr_seed_ids: VR baseline skill IDs (protected from budget truncation).

        Returns:
            Tuple of (AssembledContext, assembly_latency_ms).
        """
        start = time.perf_counter()

        # Step 1: Topological sort (VR seed skills appear first)
        sorted_ids = await self.sorter.sort(
            pruned_skill_ids, candidate_pool, vr_seed_ids=vr_seed_ids
        )

        # Step 2: Build skill contents from candidate pool
        skill_contents = self._build_skill_contents(sorted_ids, candidate_pool)

        # Step 3: Assemble with budget (VR seed skills protected)
        context = self.budget_controller.assemble_with_budget(
            sorted_skills=sorted_ids,
            skill_contents=skill_contents,
            max_tokens=max_tokens,
            reserved_tokens=reserved_tokens,
            candidate_pool=candidate_pool,
            vr_seed_ids=vr_seed_ids,
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return context, elapsed_ms

    def _build_skill_contents(
        self,
        skill_ids: list[str],
        candidate_pool: CandidatePool,
    ) -> dict[str, str]:
        """Build skill content strings from candidate pool metadata.

        Generates a structured description for each skill using
        intent_description, permissions, and dependency info.
        """
        contents: dict[str, str] = {}

        for skill_id in skill_ids:
            node = candidate_pool.nodes.get(skill_id)
            if node is None:
                continue

            parts: list[str] = []

            # Description — the primary content for LLM knowledge reference
            if node.intent_description:
                parts.append(f"{node.intent_description}")

            # Category tag (if available from node metadata)
            # Note: We deliberately omit Permissions and Dependency type
            # to avoid the LLM interpreting skills as callable tools.
            # Per RFC-03, assembled context should serve as knowledge
            # reference, not as a tool/function specification.

            contents[skill_id] = "\n".join(parts) if parts else f"Skill: {skill_id}"

        return contents
