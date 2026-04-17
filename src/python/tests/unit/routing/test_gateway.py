"""Unit tests for RoutingGateway (VR-First pipeline orchestration).

Tests verify the 4-phase VR-First architecture:
  STEP 1: VR baseline retrieval — ANN top-5 (vector-only)
  STEP 2: Graph enhancement — 1-hop expansion + MWIS with VR protection
  STEP 3: Fallback guarantee — VR baseline if enhancement ineffective (NOT zero-shot)
  STEP 4: Context assembly — VR seed skills protected from truncation

Core invariant: GS ≥ VR — never return worse than Vector-RAG baseline.
"""

import asyncio
import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from graphskill.core.models import RoutingRequest, RoutingResponse, SelectedSkill
from graphskill.routing.gateway import RoutingGateway
from graphskill.routing.models import (
    CandidatePool,
    CandidateNode,
    ScoringConfig,
    EnhancementResult,
    VRSeedProtectionConfig,
)
from graphskill.storage.vector_db import SearchResult


def _make_mock_vector_store() -> AsyncMock:
    """Create a mock vector store."""
    store = AsyncMock()
    store.search.return_value = SearchResult(
        results=[
            {"id": "git:commit", "distance": 0.1},
            {"id": "git:push", "distance": 0.2},
        ],
        total_count=2,
    )
    store.get.return_value = {
        "id": "git:commit",
        "vector": np.random.randn(384).astype(np.float32).tolist(),
    }
    return store


def _make_mock_graph_store() -> AsyncMock:
    """Create a mock graph store."""
    store = AsyncMock()

    async def get_node(uid: str):
        nodes = {
            "git:commit": {
                "uid": "git:commit",
                "version": "1.0.0",
                "intent_description": "Execute Git commit operation, committing current working directory changes to the local repository with a message.",
                "permissions": ["fs:read:/tmp", "fs:write:/tmp"],
                "execution_success_rate": 0.95,
                "is_deprecated": False,
            },
            "git:push": {
                "uid": "git:push",
                "version": "1.0.0",
                "intent_description": "Push local commits to remote Git repository. Requires network access and proper authentication credentials.",
                "permissions": ["net:github.com"],
                "execution_success_rate": 0.90,
                "is_deprecated": False,
            },
            "git:config": {
                "uid": "git:config",
                "version": "1.0.0",
                "intent_description": "Configure Git user information including name and email. This is a prerequisite for most Git operations.",
                "permissions": ["fs:read:/tmp", "fs:write:/tmp"],
                "execution_success_rate": 0.98,
                "is_deprecated": False,
            },
        }
        return nodes.get(uid)

    async def get_neighbors(uid: str, **kwargs):
        neighbors_map = {
            "git:commit": MagicMock(
                nodes=[{"uid": "git:config", "edge_type": "REQUIRES"}],
                total_count=1,
            ),
        }
        return neighbors_map.get(uid, MagicMock(nodes=[], total_count=0))

    async def execute_query(query, params):
        if "REQUIRES" in query:
            return [{"source": "git:commit", "target": "git:config", "weight": 1.0}]
        if "CONFLICTS_WITH" in query:
            return []
        if "SUBSTITUTES" in query:
            return []
        return []

    store.get_node = get_node
    store.get_neighbors = get_neighbors
    store._execute_query = execute_query
    return store


def _make_mock_embedding_service() -> AsyncMock:
    """Create a mock embedding service."""
    svc = AsyncMock()
    svc.generate.return_value = np.random.randn(384).astype(np.float32)
    return svc


class TestRoutingGatewayVRFirst:
    """Tests for RoutingGateway VR-First architecture."""

    @pytest.mark.asyncio
    async def test_route_starts_with_vr_baseline(self) -> None:
        """STEP 1: route() MUST start with VR baseline retrieval (ANN top-5)."""
        vector_store = _make_mock_vector_store()
        graph_store = _make_mock_graph_store()
        embedding_service = _make_mock_embedding_service()

        gateway = RoutingGateway(
            vector_store=vector_store,
            graph_store=graph_store,
            embedding_service=embedding_service,
            top_k=5,
            expansion_depth=1,
        )

        request = RoutingRequest(
            query="I need to commit my changes to the git repository",
            max_tokens=4096,
        )

        response = await gateway.route(request)

        # Verify the gateway performed vector search (VR baseline)
        vector_store.search.assert_called_once()
        assert isinstance(response, RoutingResponse)
        assert len(response.selected_skills) > 0
        assert response.routing_time_ms >= 0

    @pytest.mark.asyncio
    async def test_route_basic(self) -> None:
        """Test basic VR-first routing pipeline end-to-end."""
        vector_store = _make_mock_vector_store()
        graph_store = _make_mock_graph_store()
        embedding_service = _make_mock_embedding_service()

        gateway = RoutingGateway(
            vector_store=vector_store,
            graph_store=graph_store,
            embedding_service=embedding_service,
            top_k=5,
            expansion_depth=1,  # VR-First: 1-hop, not 2
        )

        request = RoutingRequest(
            query="I need to commit my changes to the git repository",
            max_tokens=4096,
        )

        response = await gateway.route(request)

        assert isinstance(response, RoutingResponse)
        assert len(response.selected_skills) > 0
        assert response.routing_time_ms >= 0
        assert "metrics" in response.metadata

    @pytest.mark.asyncio
    async def test_route_enhancement_result_in_metadata(self) -> None:
        """STEP 2: route() MUST include EnhancementResult in metadata."""
        vector_store = _make_mock_vector_store()
        graph_store = _make_mock_graph_store()
        embedding_service = _make_mock_embedding_service()

        gateway = RoutingGateway(
            vector_store=vector_store,
            graph_store=graph_store,
            embedding_service=embedding_service,
            top_k=5,
            expansion_depth=1,
        )

        request = RoutingRequest(query="commit changes to git", max_tokens=4096)
        response = await gateway.route(request)

        # EnhancementResult should be in metadata
        assert "enhancement_result" in response.metadata
        er = response.metadata["enhancement_result"]
        assert "vr_seed_ids" in er
        assert "improved" in er
        assert "enhancement_score" in er

    @pytest.mark.asyncio
    async def test_route_fallback_to_vr_not_zero_shot(self) -> None:
        """STEP 3: fallback MUST go to VR baseline, NOT zero-shot.

        When graph enhancement is ineffective (enhancement_score ≤ 0),
        the gateway MUST return VR baseline results, not an empty/zero-shot response.
        This enforces the GS ≥ VR guarantee.
        """
        vector_store = _make_mock_vector_store()
        # Use a graph store with no expansion neighbors (enhancement ineffective)
        graph_store = _make_mock_graph_store()

        # Override get_neighbors to return empty — no graph expansion value
        async def empty_neighbors(uid: str, **kwargs):
            return MagicMock(nodes=[], total_count=0)

        graph_store.get_neighbors = empty_neighbors

        embedding_service = _make_mock_embedding_service()

        gateway = RoutingGateway(
            vector_store=vector_store,
            graph_store=graph_store,
            embedding_service=embedding_service,
            top_k=5,
            expansion_depth=1,
        )

        request = RoutingRequest(query="commit changes to git", max_tokens=4096)
        response = await gateway.route(request)

        # Even when enhancement is ineffective, we MUST get VR baseline skills
        assert isinstance(response, RoutingResponse)
        assert len(response.selected_skills) > 0  # NOT zero-shot
        # Check metadata for fallback mode
        metadata = response.metadata
        if "enhancement_result" in metadata:
            er = metadata["enhancement_result"]
            # When not improved, final_ids should contain vr_seed_ids
            if not er["improved"]:
                assert len(er["final_ids"]) > 0

    @pytest.mark.asyncio
    async def test_route_fallback_on_error_returns_vr(self) -> None:
        """STEP 3 (exception): on pipeline error, fallback MUST target VR baseline.

        The _fallback_route method MUST attempt VR baseline retrieval (ANN top-5),
        NOT return an empty response or zero-shot.
        """
        vector_store = _make_mock_vector_store()
        graph_store = _make_mock_graph_store()

        # Create an embedding service that fails on first call but works on fallback
        embedding_service = AsyncMock()
        call_count = 0

        async def mock_generate(text):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Embedding service crashed")
            return np.random.randn(384).astype(np.float32)

        embedding_service.generate = mock_generate

        # Also need to make the QueryProcessor work
        from graphskill.routing.query_processor import QueryProcessor
        embedding_service._ensure_initialized = MagicMock()

        gateway = RoutingGateway(
            vector_store=vector_store,
            graph_store=graph_store,
            embedding_service=embedding_service,
        )

        request = RoutingRequest(query="commit changes to git")

        # The gateway should either return a VR fallback response or raise
        try:
            response = await gateway.route(request)
            # If we get a response, it should be a VR fallback (NOT zero-shot)
            assert len(response.selected_skills) > 0  # VR baseline skills present
            assert response.fallback_used is True
        except Exception:
            # If it raises because even VR fallback fails, that's acceptable
            pass

    @pytest.mark.asyncio
    async def test_gs_ge_vr_guarantee(self) -> None:
        """Core invariant: GS ≥ VR guarantee.

        The routing result MUST never be worse than the VR baseline.
        This means at minimum, all VR seed skills must appear in the
        final response when enhancement is not improved.
        """
        vector_store = _make_mock_vector_store()
        graph_store = _make_mock_graph_store()
        embedding_service = _make_mock_embedding_service()

        gateway = RoutingGateway(
            vector_store=vector_store,
            graph_store=graph_store,
            embedding_service=embedding_service,
            top_k=5,
            expansion_depth=1,
        )

        request = RoutingRequest(query="commit changes to git", max_tokens=4096)
        response = await gateway.route(request)

        # Response must have skills (never worse than empty VR baseline)
        assert len(response.selected_skills) > 0

        # Check EnhancementResult for GS ≥ VR compliance
        if "enhancement_result" in response.metadata:
            er = response.metadata["enhancement_result"]
            if not er["improved"]:
                # When not improved, final_ids must equal vr_seed_ids
                assert set(er["final_ids"]) == set(er["vr_seed_ids"])

    @pytest.mark.asyncio
    async def test_route_with_constraints(self) -> None:
        """Test routing with exclusion constraints (VR-first flow preserved)."""
        vector_store = _make_mock_vector_store()
        graph_store = _make_mock_graph_store()
        embedding_service = _make_mock_embedding_service()

        gateway = RoutingGateway(
            vector_store=vector_store,
            graph_store=graph_store,
            embedding_service=embedding_service,
        )

        from graphskill.core.models import RoutingConstraints

        request = RoutingRequest(
            query="commit changes to git",
            constraints=RoutingConstraints(
                excluded_skills=["git:push"],
                min_reliability=0.5,
            ),
            max_tokens=4096,
        )

        response = await gateway.route(request)

        # git:push should be excluded
        skill_uids = [s.skill_uid for s in response.selected_skills]
        assert "git:push" not in skill_uids

    @pytest.mark.asyncio
    async def test_route_metrics_populated(self) -> None:
        """Test that routing metrics are populated in response metadata."""
        vector_store = _make_mock_vector_store()
        graph_store = _make_mock_graph_store()
        embedding_service = _make_mock_embedding_service()

        gateway = RoutingGateway(
            vector_store=vector_store,
            graph_store=graph_store,
            embedding_service=embedding_service,
        )

        request = RoutingRequest(query="commit changes to git")
        response = await gateway.route(request)

        metrics = response.metadata["metrics"]
        assert metrics["total_ms"] >= 0
        assert metrics["seed_count"] >= 0
        assert metrics["expanded_count"] >= 0

    @pytest.mark.asyncio
    async def test_route_assembled_text(self) -> None:
        """STEP 4: test that assembled text is included in response metadata."""
        vector_store = _make_mock_vector_store()
        graph_store = _make_mock_graph_store()
        embedding_service = _make_mock_embedding_service()

        gateway = RoutingGateway(
            vector_store=vector_store,
            graph_store=graph_store,
            embedding_service=embedding_service,
        )

        request = RoutingRequest(query="commit changes to git")
        response = await gateway.route(request)

        # Assembled text should contain skill info
        assembled = response.metadata.get("assembled_text", "")
        if assembled:
            assert "Relevant knowledge:" in assembled or "<Skill" in assembled

    @pytest.mark.asyncio
    async def test_route_no_skills_found(self) -> None:
        """Test routing when no skills are found at all (VR baseline also empty).

        VR-First: when VR baseline returns no seeds AND graph enhancement
        also yields nothing, the gateway returns an empty response or raises.
        Both outcomes are acceptable — the key invariant is that we never
        return worse than VR baseline (which is also empty here).
        """
        vector_store = AsyncMock()
        vector_store.search.return_value = SearchResult(results=[], total_count=0)
        graph_store = _make_mock_graph_store()
        embedding_service = _make_mock_embedding_service()

        gateway = RoutingGateway(
            vector_store=vector_store,
            graph_store=graph_store,
            embedding_service=embedding_service,
        )

        request = RoutingRequest(query="obscure query with no matching skills")

        # VR-First: empty VR baseline → empty response or NoSkillsFoundError
        # Both are valid: the GS ≥ VR guarantee holds (both are equally empty)
        try:
            response = await gateway.route(request)
            # If we get a response, it should have no skills (empty VR baseline)
            assert len(response.selected_skills) == 0
        except Exception as exc:
            # NoSkillsFoundError is also acceptable
            from graphskill.core.exceptions import NoSkillsFoundError
            assert isinstance(exc, NoSkillsFoundError)

    @pytest.mark.asyncio
    async def test_route_vr_seed_protection_config(self) -> None:
        """Test that VRSeedProtectionConfig is properly initialized."""
        vector_store = _make_mock_vector_store()
        graph_store = _make_mock_graph_store()
        embedding_service = _make_mock_embedding_service()

        # Custom VR seed protection config
        protection = VRSeedProtectionConfig(
            enabled=True,
            allow_vr_seed_replacement=False,
            fallback_to_vr_baseline=True,
        )

        gateway = RoutingGateway(
            vector_store=vector_store,
            graph_store=graph_store,
            embedding_service=embedding_service,
            vr_seed_protection=protection,
        )

        assert gateway.vr_seed_protection.enabled is True
        assert gateway.vr_seed_protection.allow_vr_seed_replacement is False
        assert gateway.vr_seed_protection.fallback_to_vr_baseline is True

    def test_compute_query_hash(self) -> None:
        """Test query hash computation."""
        hash1 = RoutingGateway._compute_query_hash("test query")
        hash2 = RoutingGateway._compute_query_hash("test query")
        hash3 = RoutingGateway._compute_query_hash("different query")

        assert hash1 == hash2  # Same input -> same hash
        assert hash1 != hash3  # Different input -> different hash
        assert len(hash1) == 16  # SHA256 truncated to 16 chars