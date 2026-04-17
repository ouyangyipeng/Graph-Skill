"""
MilvusClient 单元测试。

测试 Milvus 向量数据库客户端的基本功能（数据结构和初始化）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from graphskill.storage.vector_db import (
    VectorDBError,
    SearchResult,
    VectorInfo,
    MilvusClient,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def milvus_client() -> MilvusClient:
    """创建 Milvus 客户端。"""
    return MilvusClient(
        host="localhost",
        port=19530,
        collection_name="test_collection",
        vector_dimension=1536,
    )


@pytest.fixture
def milvus_client_custom() -> MilvusClient:
    """创建自定义配置的 Milvus 客户端。"""
    return MilvusClient(
        host="milvus.example.com",
        port=19531,
        collection_name="custom_collection",
        vector_dimension=768,
        index_type="IVF_FLAT",
        metric_type="L2",
    )


@pytest.fixture
def search_result() -> SearchResult:
    """创建搜索结果。"""
    return SearchResult(
        results=[
            {"id": "skill:test:1", "distance": 0.1, "entity": {"uid": "skill:test:1"}},
            {"id": "skill:test:2", "distance": 0.2, "entity": {"uid": "skill:test:2"}},
        ],
        total_count=2,
        query_time_ms=10,
    )


@pytest.fixture
def vector_info() -> VectorInfo:
    """创建向量信息。"""
    return VectorInfo(
        uid="skill:test:skill",
        embedding=[0.1] * 1536,
        metadata={"intent": "test"},
    )


# ============================================================================
# VectorDBError Tests
# ============================================================================


class TestVectorDBError:
    """VectorDBError 异常测试。"""
    
    def test_create_vector_db_error(self) -> None:
        """测试创建向量数据库错误。"""
        error = VectorDBError("Insert failed")
        assert error.message == "Insert failed"
        assert error.code == "GS-4002"
        assert error.collection is None
    
    def test_vector_db_error_with_collection(self) -> None:
        """测试带 collection 的错误。"""
        error = VectorDBError("Collection not found", collection="test_collection")
        assert error.collection == "test_collection"
    
    def test_vector_db_error_to_dict(self) -> None:
        """测试错误转换为字典。"""
        error = VectorDBError("Query failed", collection="test_collection")
        result = error.to_dict()
        
        assert "error" in result
        assert result["error"]["code"] == "GS-4002"
        assert result["collection"] == "test_collection"
    
    def test_vector_db_error_inheritance(self) -> None:
        """测试错误继承关系。"""
        error = VectorDBError("Test error")
        from graphskill.core.exceptions import DatabaseError
        assert isinstance(error, DatabaseError)
        assert isinstance(error, Exception)


# ============================================================================
# SearchResult Tests
# ============================================================================


class TestSearchResult:
    """SearchResult 数据结构测试。"""
    
    def test_create_search_result(self, search_result: SearchResult) -> None:
        """测试创建搜索结果。"""
        assert len(search_result.results) == 2
        assert search_result.total_count == 2
        assert search_result.query_time_ms == 10
    
    def test_search_result_defaults(self) -> None:
        """测试搜索结果默认值。"""
        result = SearchResult()
        assert result.results == []
        assert result.total_count == 0
        assert result.query_time_ms == 0
    
    def test_search_result_to_dict(self, search_result: SearchResult) -> None:
        """测试搜索结果转换为字典。"""
        result = search_result.to_dict()
        
        assert "results" in result
        assert result["total_count"] == 2
        assert result["query_time_ms"] == 10
    
    def test_search_result_empty_results(self) -> None:
        """测试空搜索结果。"""
        result = SearchResult(results=[], total_count=0)
        assert result.results == []
        assert result.total_count == 0


# ============================================================================
# VectorInfo Tests
# ============================================================================


class TestVectorInfo:
    """VectorInfo 数据结构测试。"""
    
    def test_create_vector_info(self, vector_info: VectorInfo) -> None:
        """测试创建向量信息。"""
        assert vector_info.uid == "skill:test:skill"
        assert len(vector_info.embedding) == 1536
        assert vector_info.metadata == {"intent": "test"}
    
    def test_vector_info_defaults(self) -> None:
        """测试向量信息默认值。"""
        info = VectorInfo(uid="test", embedding=[0.1, 0.2])
        assert info.metadata == {}
    
    def test_vector_info_to_dict(self, vector_info: VectorInfo) -> None:
        """测试向量信息转换为字典。"""
        result = vector_info.to_dict()
        
        assert result["uid"] == "skill:test:skill"
        assert result["embedding_dim"] == 1536
        assert result["metadata"] == {"intent": "test"}
    
    def test_vector_info_embedding_dimension(self) -> None:
        """测试向量维度计算。"""
        info = VectorInfo(uid="test", embedding=[0.1] * 768)
        result = info.to_dict()
        assert result["embedding_dim"] == 768


# ============================================================================
# MilvusClient Init Tests
# ============================================================================


class TestMilvusClientInit:
    """MilvusClient 初始化测试。"""
    
    def test_init_default_config(self, milvus_client: MilvusClient) -> None:
        """测试默认配置初始化。"""
        assert milvus_client.host == "localhost"
        assert milvus_client.port == 19530
        assert milvus_client.collection_name == "test_collection"
        assert milvus_client.vector_dimension == 1536
        assert milvus_client._client is None
        assert milvus_client._connected == False
    
    def test_init_custom_config(self, milvus_client_custom: MilvusClient) -> None:
        """测试自定义配置初始化。"""
        assert milvus_client_custom.host == "milvus.example.com"
        assert milvus_client_custom.port == 19531
        assert milvus_client_custom.collection_name == "custom_collection"
        assert milvus_client_custom.vector_dimension == 768
        assert milvus_client_custom.index_type == "IVF_FLAT"
        assert milvus_client_custom.metric_type == "L2"
    
    def test_init_default_constants(self) -> None:
        """测试使用常量默认值初始化。"""
        client = MilvusClient()
        # 使用常量中的默认值
        assert client.host == "localhost"
        assert client.port == 19530
    
    def test_init_index_metric_defaults(self) -> None:
        """测试索引和度量类型默认值。"""
        client = MilvusClient()
        assert client.index_type == "HNSW"
        assert client.metric_type == "COSINE"


# ============================================================================
# MilvusClient Connection Tests (Mock Mode)
# ============================================================================


class TestMilvusClientConnection:
    """MilvusClient 连接测试。"""
    
    @pytest.mark.asyncio
    async def test_connect_mock_mode(self, milvus_client: MilvusClient) -> None:
        """测试模拟模式连接（无 pymilvus 库）。
        
        修复后：_connected=False, _mock_mode=True（不再静默伪装已连接）。
        """
        with patch.dict('sys.modules', {'pymilvus': None}):
            await milvus_client.connect()
            assert milvus_client._connected == False
            assert milvus_client._mock_mode == True
    
    def test_connect_sync_mock_mode(self, milvus_client: MilvusClient) -> None:
        """测试同步模拟模式连接。"""
        with patch.dict('sys.modules', {'pymilvus': None}):
            milvus_client.connect_sync()
            assert milvus_client._connected == False
            assert milvus_client._mock_mode == True
    
    @pytest.mark.asyncio
    async def test_close_without_client(self, milvus_client: MilvusClient) -> None:
        """测试无客户端时关闭。"""
        milvus_client._connected = True
        milvus_client._client = None
        
        await milvus_client.close()
        assert milvus_client._connected == False
        assert milvus_client._client is None
    
    @pytest.mark.asyncio
    async def test_close_already_closed(self, milvus_client: MilvusClient) -> None:
        """测试已关闭时再次关闭。"""
        milvus_client._connected = False
        milvus_client._client = None
        
        await milvus_client.close()
        assert milvus_client._connected == False


# ============================================================================
# MilvusClient Mock Mode Operations Tests
# ============================================================================


class TestMilvusClientMockMode:
    """MilvusClient 模拟模式操作测试。"""
    
    @pytest.mark.asyncio
    async def test_insert_mock_mode(self, milvus_client: MilvusClient) -> None:
        """测试模拟模式下插入向量。"""
        milvus_client._client = None  # 模拟模式
        
        result = await milvus_client.insert("skill:test", [0.1] * 1536, {"intent": "test"})
        # 模拟模式返回空结果
        assert result is not None
        assert result["status"] == "mock_inserted"
    
    @pytest.mark.asyncio
    async def test_upsert_mock_mode(self, milvus_client: MilvusClient) -> None:
        """测试模拟模式下更新向量。"""
        milvus_client._client = None  # 模拟模式
        
        result = await milvus_client.upsert("skill:test", [0.1] * 1536, {"intent": "test"})
        assert result is not None
        assert result["status"] == "mock_upserted"
    
    @pytest.mark.asyncio
    async def test_delete_mock_mode(self, milvus_client: MilvusClient) -> None:
        """测试模拟模式下删除向量。"""
        milvus_client._client = None  # 模拟模式
        
        result = await milvus_client.delete("skill:test")
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_search_mock_mode(self, milvus_client: MilvusClient) -> None:
        """测试模拟模式下搜索向量。"""
        milvus_client._client = None  # 模拟模式
        
        result = await milvus_client.search([0.1] * 1536, top_k=10)
        assert result is not None
        assert isinstance(result, SearchResult)
    
    @pytest.mark.asyncio
    async def test_batch_insert_mock_mode(self, milvus_client: MilvusClient) -> None:
        """测试模拟模式下批量插入。"""
        milvus_client._client = None  # 模拟模式
        
        vectors = [
            VectorInfo(uid="skill:1", embedding=[0.1] * 1536),
            VectorInfo(uid="skill:2", embedding=[0.2] * 1536),
        ]
        result = await milvus_client.batch_insert(vectors)
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_get_mock_mode(self, milvus_client: MilvusClient) -> None:
        """测试模拟模式下获取向量。"""
        milvus_client._client = None  # 模拟模式
        
        result = await milvus_client.get("skill:test")
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_query_mock_mode(self, milvus_client: MilvusClient) -> None:
        """测试模拟模式下查询向量。"""
        milvus_client._client = None  # 模拟模式
        
        # query 方法使用 filter_expr 参数名
        result = await milvus_client.query(filter_expr="uid == 'skill:test'")
        assert result is not None
        assert result.total_count == 0
    
    @pytest.mark.asyncio
    async def test_health_check_mock_mode(self, milvus_client: MilvusClient) -> None:
        """测试模拟模式下健康检查。"""
        milvus_client._client = None  # 模拟模式
        milvus_client._connected = True
        
        result = await milvus_client.health_check()
        assert result["status"] == "healthy"
    
    def test_get_collection_stats_mock_mode(self, milvus_client: MilvusClient) -> None:
        """测试模拟模式下获取集合统计。"""
        milvus_client._client = None  # 模拟模式
        
        result = milvus_client.get_collection_stats()
        assert result is not None


# ============================================================================
# Edge Cases Tests
# ============================================================================


class TestEdgeCases:
    """边界条件测试。"""
    
    def test_milvus_client_with_large_dimension(self) -> None:
        """测试大维度配置。"""
        client = MilvusClient(vector_dimension=4096)
        assert client.vector_dimension == 4096
    
    def test_milvus_client_with_small_dimension(self) -> None:
        """测试小维度配置。"""
        client = MilvusClient(vector_dimension=128)
        assert client.vector_dimension == 128
    
    def test_milvus_client_with_custom_collection_name(self) -> None:
        """测试自定义集合名称。"""
        client = MilvusClient(collection_name="my_custom_skills")
        assert client.collection_name == "my_custom_skills"
    
    def test_vector_info_with_large_embedding(self) -> None:
        """测试大向量。"""
        info = VectorInfo(uid="test", embedding=[0.1] * 4096)
        result = info.to_dict()
        assert result["embedding_dim"] == 4096
    
    def test_vector_info_with_empty_metadata(self) -> None:
        """测试空元数据。"""
        info = VectorInfo(uid="test", embedding=[0.1] * 128, metadata={})
        assert info.metadata == {}
    
    def test_search_result_with_many_results(self) -> None:
        """测试多结果搜索。"""
        results = [{"id": f"skill:{i}", "distance": 0.1 * i} for i in range(100)]
        search_result = SearchResult(results=results, total_count=100)
        assert len(search_result.results) == 100
    
    def test_milvus_client_different_index_types(self) -> None:
        """测试不同索引类型。"""
        client = MilvusClient(index_type="IVF_FLAT")
        assert client.index_type == "IVF_FLAT"
        
        client2 = MilvusClient(index_type="HNSW")
        assert client2.index_type == "HNSW"
    
    def test_milvus_client_different_metric_types(self) -> None:
        """测试不同度量类型。"""
        client = MilvusClient(metric_type="L2")
        assert client.metric_type == "L2"
        
        client2 = MilvusClient(metric_type="IP")
        assert client2.metric_type == "IP"


# ============================================================================
# Integration Tests (Mock Mode)
# ============================================================================


class TestIntegration:
    """集成测试。"""
    
    @pytest.mark.asyncio
    async def test_full_mock_workflow(self, milvus_client: MilvusClient) -> None:
        """测试模拟模式完整工作流。"""
        milvus_client._client = None  # 模拟模式
        
        # 插入向量（需要 metadata 参数）
        result = await milvus_client.insert("skill:test", [0.1] * 1536, {"intent": "test"})
        assert result is not None
        assert result["status"] == "mock_inserted"
        
        # 搜索向量
        result = await milvus_client.search([0.1] * 1536, top_k=10)
        assert result is not None
        
        # 删除向量
        result = await milvus_client.delete("skill:test")
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_batch_workflow(self, milvus_client: MilvusClient) -> None:
        """测试模拟模式批量工作流。"""
        milvus_client._client = None  # 模拟模式
        
        # 批量插入
        vectors = [
            VectorInfo(uid="skill:1", embedding=[0.1] * 1536),
            VectorInfo(uid="skill:2", embedding=[0.2] * 1536),
            VectorInfo(uid="skill:3", embedding=[0.3] * 1536),
        ]
        result = await milvus_client.batch_insert(vectors)
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_health_check_workflow(self, milvus_client: MilvusClient) -> None:
        """测试模拟模式健康检查工作流。"""
        milvus_client._client = None  # 模拟模式
        milvus_client._connected = True
        
        # 健康检查
        health = await milvus_client.health_check()
        assert health["status"] == "healthy"
        
        # 集合统计
        stats = milvus_client.get_collection_stats()
        assert stats is not None