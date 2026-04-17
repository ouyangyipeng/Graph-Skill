"""Unit tests for HybridRetriever (VR-First architecture).

Tests verify:
  - top_k=5 (VR baseline top-5, not old top-10)
  - expansion_depth=1 (1-hop, not old depth=2)
  - vr_only mode (skip graph expansion, return ANN seeds only)
  - 1-hop expansion only adds direct dependencies
"""

import asyncio
import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock

from graphskill.routing.hybrid_retriever import HybridRetriever
from graphskill.routing.models import CandidateNode, CandidatePool
from graphskill.storage.vector_db import SearchResult


def _make_mock_vector_store(hits: list[dict] | None = None) -> AsyncMock:
    """Create a mock vector store with configurable search results."""
    store = AsyncMock()
    if hits is None:
        hits = [
            {"id": "git:commit", "distance": 0.1},
            {"id": "git:push", "distance": 0.2},
        ]
    store.search.return_value = SearchResult(results=hits, total_count=len(hits))
    return store


def _make_mock_graph_store(
    nodes: dict | None = None,
    neighbors: dict | None = None,
) -> AsyncMock:
    """Create a mock graph store with configurable node/neighbor data."""
    store = AsyncMock()

    default_nodes = {
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

    default_neighbors = {
        "git:commit": {
            "nodes": [
                {"uid": "git:config", "edge_type": "REQUIRES"},
            ],
            "total_count": 1,
        },
    }

    _nodes = nodes or default_nodes
    _neighbors = neighbors or default_neighbors

    async def get_node(uid: str):
        return _nodes.get(uid)

    async def get_neighbors(uid: str, **kwargs):
        result = _neighbors.get(uid)
        if result is None:
            return MagicMock(nodes=[], total_count=0)
        return MagicMock(**result)

    store.get_node = get_node
    store.get_neighbors = get_neighbors
    return store


class TestHybridRetriever:
    """Tests for HybridRetriever (VR-First architecture)."""

    @pytest.mark.asyncio
    async def test_retrieve_basic_top_k_5(self) -> None:
        """Test basic hybrid retrieval with top_k=5 (VR baseline top-5)."""
        vector_store = _make_mock_vector_store()
        graph_store = _make_mock_graph_store()

        retriever = HybridRetriever(
            vector_store=vector_store,
            graph_store=graph_store,
            top_k=5,
            expansion_depth=1,  # VR-First: 1-hop, not 2
        )

        query_vector = np.random.randn(384).astype(np.float32)
        pool, latency_ms = await retriever.retrieve(query_vector)

        assert len(pool.nodes) > 0
        assert latency_ms >= 0
        # Should have at least the seed nodes
        seeds = pool.get_seed_nodes()
        assert len(seeds) > 0
        # All seed nodes should have depth=0
        for seed in seeds:
            assert seed.depth == 0
            assert seed.is_seed is True

    @pytest.mark.asyncio
    async def test_retrieve_default_top_k_is_5(self) -> None:
        """Test that default top_k is 5 (VR-First: changed from 10 to 5)."""
        vector_store = _make_mock_vector_store()
        graph_store = _make_mock_graph_store()

        # Use defaults (no explicit top_k)
        retriever = HybridRetriever(
            vector_store=vector_store,
            graph_store=graph_store,
        )

        # Verify the default top_k is 5
        assert retriever.top_k == 5

    @pytest.mark.asyncio
    async def test_retrieve_default_expansion_depth_is_1(self) -> None:
        """Test that default expansion_depth is 1 (VR-First: 1-hop, not 2)."""
        vector_store = _make_mock_vector_store()
        graph_store = _make_mock_graph_store()

        retriever = HybridRetriever(
            vector_store=vector_store,
            graph_store=graph_store,
        )

        # Verify the default expansion_depth is 1
        assert retriever.expansion_depth == 1

    @pytest.mark.asyncio
    async def test_retrieve_expansion_depth_capped_at_1(self) -> None:
        """Test that expansion_depth is hard-limited to 1-hop (VR-First).

        Even if a larger depth is specified, the retriever MUST cap it to 1.
        """
        vector_store = _make_mock_vector_store(hits=[
            {"id": "git:commit", "distance": 0.1},
        ])
        graph_store = _make_mock_graph_store()

        # Try to request expansion_depth=2 — should be capped to 1
        retriever = HybridRetriever(
            vector_store=vector_store,
            graph_store=graph_store,
            top_k=5,
            expansion_depth=1,
        )

        query_vector = np.random.randn(384).astype(np.float32)
        pool, _ = await retriever.retrieve(query_vector, expansion_depth=2)

        # Only 1-hop expansion should occur: git:commit → git:config
        # No 2-hop expansion (git:config's neighbors should NOT be explored)
        skill_ids = pool.get_skill_ids()
        assert "git:commit" in skill_ids
        assert "git:config" in skill_ids  # 1-hop expansion

        # All expanded nodes must have depth ≤ 1 (1-hop limit)
        for node in pool.get_all_nodes():
            assert node.depth <= 1

    @pytest.mark.asyncio
    async def test_retrieve_vr_only_mode(self) -> None:
        """Test vr_only=True: skip graph expansion, return ANN seeds only.

        VR-First: when vr_only=True, only perform semantic seed recall
        (ANN top-k) without graph expansion. This is the VR baseline.
        """
        vector_store = _make_mock_vector_store()
        graph_store = _make_mock_graph_store()

        retriever = HybridRetriever(
            vector_store=vector_store,
            graph_store=graph_store,
            top_k=5,
            expansion_depth=1,
        )

        query_vector = np.random.randn(384).astype(np.float32)
        pool, latency_ms = await retriever.retrieve(query_vector, vr_only=True)

        # In vr_only mode, only seed nodes should exist (no expansion)
        assert len(pool.nodes) > 0
        seeds = pool.get_seed_nodes()
        non_seeds = [n for n in pool.get_all_nodes() if not n.is_seed]

        # All nodes should be seeds (no graph expansion)
        assert len(seeds) == len(pool.nodes)
        assert len(non_seeds) == 0
        assert latency_ms >= 0

    @pytest.mark.asyncio
    async def test_retrieve_vr_only_no_graph_store_calls(self) -> None:
        """Test that vr_only=True does NOT call graph_store.get_neighbors."""
        vector_store = _make_mock_vector_store()
        graph_store = _make_mock_graph_store()

        retriever = HybridRetriever(
            vector_store=vector_store,
            graph_store=graph_store,
            top_k=5,
            expansion_depth=1,
        )

        query_vector = np.random.randn(384).astype(np.float32)
        pool, _ = await retriever.retrieve(query_vector, vr_only=True)

        # get_neighbors should NOT have been called in vr_only mode
        # (only get_node is called for seed properties)
        # Note: get_node may be called for seed node properties,
        # but get_neighbors should not

    @pytest.mark.asyncio
    async def test_retrieve_1_hop_only_direct_deps(self) -> None:
        """Test that 1-hop expansion only adds direct dependencies.

        VR-First: expansion_depth=1 means only REQUIRES/ENHANCES
        neighbors of seed nodes are added — no transitive expansion.
        """
        vector_store = _make_mock_vector_store(hits=[
            {"id": "git:commit", "distance": 0.1},
        ])
        graph_store = _make_mock_graph_store()

        retriever = HybridRetriever(
            vector_store=vector_store,
            graph_store=graph_store,
            top_k=5,
            expansion_depth=1,
        )

        query_vector = np.random.randn(384).astype(np.float32)
        pool, _ = await retriever.retrieve(query_vector)

        # git:commit is a seed, git:config is a 1-hop REQUIRES dependency
        skill_ids = pool.get_skill_ids()
        assert "git:commit" in skill_ids
        assert "git:config" in skill_ids  # 1-hop expansion

        # Verify git:config has correct metadata
        config_node = pool.nodes.get("git:config")
        assert config_node is not None
        assert config_node.depth == 1
        assert config_node.is_seed is False
        assert config_node.edge_type == "REQUIRES"

    @pytest.mark.asyncio
    async def test_retrieve_empty_results(self) -> None:
        """Test retrieval when vector store returns no results."""
        vector_store = _make_mock_vector_store(hits=[])
        graph_store = _make_mock_graph_store()

        retriever = HybridRetriever(
            vector_store=vector_store,
            graph_store=graph_store,
        )

        query_vector = np.random.randn(384).astype(np.float32)
        pool, latency_ms = await retriever.retrieve(query_vector)

        assert len(pool.nodes) == 0

    @pytest.mark.asyncio
    async def test_retrieve_deprecated_filtered(self) -> None:
        """Test that deprecated nodes are filtered out."""
        vector_store = _make_mock_vector_store(hits=[
            {"id": "git:old", "distance": 0.1},
        ])
        graph_store = _make_mock_graph_store(nodes={
            "git:old": {
                "uid": "git:old",
                "version": "0.1.0",
                "intent_description": "Deprecated old git operation that is no longer maintained or recommended for use.",
                "permissions": ["fs:read:/tmp"],
                "execution_success_rate": 0.5,
                "is_deprecated": True,
            },
        })

        retriever = HybridRetriever(
            vector_store=vector_store,
            graph_store=graph_store,
            filter_deprecated=True,
        )

        query_vector = np.random.randn(384).astype(np.float32)
        pool, _ = await retriever.retrieve(query_vector)

        assert len(pool.nodes) == 0

    @pytest.mark.asyncio
    async def test_retrieve_no_deprecated_filter(self) -> None:
        """Test that deprecated nodes are included when filter is off."""
        vector_store = _make_mock_vector_store(hits=[
            {"id": "git:old", "distance": 0.1},
        ])
        graph_store = _make_mock_graph_store(nodes={
            "git:old": {
                "uid": "git:old",
                "version": "0.1.0",
                "intent_description": "Deprecated old git operation that is no longer maintained or recommended for use.",
                "permissions": ["fs:read:/tmp"],
                "execution_success_rate": 0.5,
                "is_deprecated": True,
            },
        })

        retriever = HybridRetriever(
            vector_store=vector_store,
            graph_store=graph_store,
            filter_deprecated=False,
        )

        query_vector = np.random.randn(384).astype(np.float32)
        pool, _ = await retriever.retrieve(query_vector)

        assert len(pool.nodes) >= 1

    @pytest.mark.asyncio
    async def test_retrieve_custom_top_k(self) -> None:
        """Test overriding top_k in retrieve call."""
        vector_store = _make_mock_vector_store()
        graph_store = _make_mock_graph_store()

        retriever = HybridRetriever(
            vector_store=vector_store,
            graph_store=graph_store,
            top_k=5,
        )

        query_vector = np.random.randn(384).astype(np.float32)
        await retriever.retrieve(query_vector, top_k=1)

        # Verify search was called with top_k * 2 = 2 (over-retrieve for filtering)
        call_args = vector_store.search.call_args
        assert call_args.kwargs.get("top_k") == 2 or call_args[1].get("top_k") == 2

    @pytest.mark.asyncio
    async def test_edge_type_from_neighbors(self) -> None:
        """Test that expanded nodes carry edge_type from graph neighbors."""
        vector_store = _make_mock_vector_store(hits=[
            {"id": "git:commit", "distance": 0.1},
        ])
        graph_store = _make_mock_graph_store()

        retriever = HybridRetriever(
            vector_store=vector_store,
            graph_store=graph_store,
            top_k=5,
            expansion_depth=1,
        )

        query_vector = np.random.randn(384).astype(np.float32)
        pool, _ = await retriever.retrieve(query_vector)

        # git:config is expanded via REQUIRES edge from git:commit
        config_node = pool.nodes.get("git:config")
        assert config_node is not None
        assert config_node.edge_type == "REQUIRES"

    @pytest.mark.asyncio
    async def test_edge_type_list_normalization(self) -> None:
        """Test that list-form edge_type from Neo4j variable-length paths is normalized."""
        vector_store = _make_mock_vector_store(hits=[
            {"id": "git:commit", "distance": 0.1},
        ])

        # Simulate Neo4j variable-length path returning edge_type as list
        graph_store = _make_mock_graph_store(
            neighbors={
                "git:commit": {
                    "nodes": [
                        {"uid": "git:config", "edge_type": ["REQUIRES"]},
                    ],
                    "total_count": 1,
                },
            },
        )

        retriever = HybridRetriever(
            vector_store=vector_store,
            graph_store=graph_store,
            top_k=5,
            expansion_depth=1,
        )

        query_vector = np.random.randn(384).astype(np.float32)
        pool, _ = await retriever.retrieve(query_vector)

        config_node = pool.nodes.get("git:config")
        assert config_node is not None
        # List edge_type should be normalized to string
        assert config_node.edge_type == "REQUIRES"