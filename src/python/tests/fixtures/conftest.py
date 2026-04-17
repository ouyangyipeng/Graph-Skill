"""
Integration tests fixtures.

提供真实数据库连接的 fixtures。
"""

from __future__ import annotations

import os
import pytest
import asyncio
from typing import Optional, Any

# 加载测试环境变量
from dotenv import load_dotenv
load_dotenv(".env.test")


# ============================================================================
# Redis Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def redis_client():
    """创建真实的 Redis 客户端连接。"""
    from graphskill.storage.cache import RedisClient
    
    client = RedisClient(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
    )
    
    # 同步连接
    client.connect_sync()
    
    yield client
    
    # 清理
    client._connected = False
    if client._client:
        client._client.close()


@pytest.fixture(scope="session")
async def redis_client_async():
    """创建真实的异步 Redis 客户端连接。"""
    from graphskill.storage.cache import RedisClient
    
    client = RedisClient(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
    )
    
    await client.connect()
    
    yield client
    
    await client.close()


# ============================================================================
# Neo4j Fixtures
# ============================================================================


@pytest.fixture(scope="session")
async def neo4j_client():
    """创建真实的 Neo4j 客户端连接。"""
    from graphskill.storage.graph_db import Neo4jClient
    
    client = Neo4jClient(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "password123"),
    )
    
    await client.connect()
    
    yield client
    
    await client.close()


# ============================================================================
# Milvus Fixtures
# ============================================================================


@pytest.fixture(scope="session")
async def milvus_client():
    """创建真实的 Milvus 客户端连接。"""
    from graphskill.storage.vector_db import MilvusClient
    
    client = MilvusClient(
        host=os.getenv("MILVUS_HOST", "localhost"),
        port=int(os.getenv("MILVUS_PORT", "19530")),
        collection_name=os.getenv("MILVUS_COLLECTION_NAME", "test_skill_embeddings"),
    )
    
    await client.connect()
    
    yield client
    
    await client.close()


# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest.fixture
def test_skill_node():
    """创建测试技能节点。"""
    from graphskill.core.models import SkillNode
    from datetime import datetime
    
    return SkillNode(
        uid="test:skill_node",
        version="1.0.0",
        intent_description="A test skill node for integration testing with sufficient length description",
        permissions=["fs:read", "fs:write"],
        tags=["test", "integration"],
        execution_success_rate=0.95,
        execution_count=100,
        is_deprecated=False,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@pytest.fixture
def test_skill_edge():
    """创建测试技能边。"""
    from graphskill.core.models import SkillEdge, EdgeType
    from datetime import datetime
    
    return SkillEdge(
        source_uid="test:skill_a",
        target_uid="test:skill_b",
        edge_type=EdgeType.REQUIRES,
        weight=0.8,
        confidence=0.9,
        is_implicit=False,
        discovered_at=datetime.now(),
        discovery_source="integration_test",
    )


@pytest.fixture
def test_embedding():
    """创建测试向量嵌入。"""
    # 使用 1536 维向量（OpenAI text-embedding-3-small）
    import random
    random.seed(42)
    return [random.gauss(0, 0.1) for _ in range(1536)]


# ============================================================================
# Cleanup Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
async def cleanup_redis(redis_client_async):
    """每个测试后清理 Redis 测试数据。"""
    yield
    
    # 清理测试键
    try:
        # 删除所有 test:* 键
        if redis_client_async._client:
            keys = await redis_client_async._client.keys("test:*")
            if keys:
                await redis_client_async._client.delete(*keys)
    except Exception:
        pass


@pytest.fixture(autouse=True)
async def cleanup_neo4j(neo4j_client):
    """每个测试后清理 Neo4j 测试数据。"""
    yield
    
    # 清理测试节点和边
    try:
        if neo4j_client._driver:
            async with neo4j_client._driver.session() as session:
                await session.run("MATCH (n:SkillNode) WHERE n.uid STARTS WITH 'test:' DETACH DELETE n")
    except Exception:
        pass


@pytest.fixture(autouse=True)
async def cleanup_milvus(milvus_client):
    """每个测试后清理 Milvus 测试数据。"""
    yield
    
    # 清理测试向量
    try:
        if milvus_client._client:
            # 删除 test:* 的向量
            await milvus_client.delete("test:skill_node")
    except Exception:
        pass