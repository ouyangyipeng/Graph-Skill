"""
性能基准测试：存储模块。

测试存储层的性能指标：
- Neo4j 节点创建吞吐量
- Milvus 向量插入吞吐量
- Redis 缓存操作吞吐量
- 查询响应时间

Reference: plans/phase_03_e2e_plan.md
"""

from __future__ import annotations

import os
import pytest
import time
import asyncio
import random
from pathlib import Path
from typing import Any
from datetime import datetime
from dataclasses import dataclass

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent.parent.parent.parent / ".env.test")

from graphskill.storage.graph_db import Neo4jClient
from graphskill.storage.vector_db import MilvusClient
from graphskill.storage.cache import RedisClient
from graphskill.core.models import SkillNode


# ============================================================================
# Benchmark Helpers
# ============================================================================

@dataclass
class BenchmarkResult:
    """基准测试结果."""
    name: str
    iterations: int
    total_time_ms: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    throughput: float  # ops per second
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "iterations": self.iterations,
            "total_time_ms": self.total_time_ms,
            "avg_time_ms": self.avg_time_ms,
            "min_time_ms": self.min_time_ms,
            "max_time_ms": self.max_time_ms,
            "throughput": self.throughput,
        }


async def async_benchmark(func, iterations: int = 100) -> BenchmarkResult:
    """
    执行异步基准测试.
    
    Args:
        func: 要测试的异步函数
        iterations: 迭代次数
    
    Returns:
        BenchmarkResult: 测试结果
    """
    times = []
    
    for _ in range(iterations):
        start = time.perf_counter()
        await func()
        end = time.perf_counter()
        times.append((end - start) * 1000)  # Convert to ms
    
    total_time = sum(times)
    avg_time = total_time / iterations
    min_time = min(times)
    max_time = max(times)
    throughput = iterations / (total_time / 1000)  # ops per second
    
    return BenchmarkResult(
        name="async_benchmark",
        iterations=iterations,
        total_time_ms=total_time,
        avg_time_ms=avg_time,
        min_time_ms=min_time,
        max_time_ms=max_time_ms,
        throughput=throughput,
    )


def generate_test_node(index: int) -> SkillNode:
    """生成测试节点."""
    return SkillNode(
        uid=f"bench_test:node_{index}",
        version="1.0.0",
        intent_description=f"Benchmark test node for performance testing purposes with index {index} and random data",
        permissions=["fs:read:./repo"],
        execution_success_rate=1.0,
        execution_count=0,
        is_deprecated=False,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        tags=["benchmark", "test"],
        author="Benchmark",
    )


def generate_test_embedding(dimensions: int = 1536) -> list[float]:
    """生成测试向量."""
    return [random.random() for _ in range(dimensions)]


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
async def neo4j_client() -> Neo4jClient:
    """Neo4j 客户端."""
    client = Neo4jClient(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "password123"),
        database=os.getenv("NEO4J_DATABASE", "neo4j"),
    )
    await client.connect()
    yield client
    await client.close()


@pytest.fixture
async def milvus_client() -> MilvusClient:
    """Milvus 客户端."""
    client = MilvusClient(
        host=os.getenv("MILVUS_HOST", "localhost"),
        port=int(os.getenv("MILVUS_PORT", "19530")),
        collection_name="bench_skill_embeddings",
    )
    await client.connect()
    yield client
    await client.close()


@pytest.fixture
async def redis_client() -> RedisClient:
    """Redis 客户端."""
    client = RedisClient(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD", None),
    )
    await client.connect()
    yield client
    await client.close()


# ============================================================================
# Benchmark Tests
# ============================================================================

class TestNeo4jBenchmark:
    """Neo4j 性能基准测试."""
    
    @pytest.mark.asyncio
    @pytest.mark.benchmark
    @pytest.mark.storage
    async def test_neo4j_create_node_benchmark(
        self,
        neo4j_client: Neo4jClient,
    ) -> None:
        """Neo4j 节点创建基准测试."""
        created_uids = []
        
        async def create_node():
            node = generate_test_node(len(created_uids))
            await neo4j_client.create_node(node)
            created_uids.append(node.uid)
        
        result = await async_benchmark(create_node, iterations=20)
        
        print(f"\nNeo4j Create Node Benchmark:")
        print(f"  Iterations: {result.iterations}")
        print(f"  Avg time: {result.avg_time_ms:.2f} ms")
        print(f"  Min time: {result.min_time_ms:.2f} ms")
        print(f"  Max time: {result.max_time_ms:.2f} ms")
        print(f"  Throughput: {result.throughput:.2f} nodes/sec")
        
        # Cleanup
        for uid in created_uids:
            try:
                await neo4j_client.delete_node(uid)
            except Exception:
                pass
        
        assert result.avg_time_ms < 100, "Node creation should be < 100ms"
    
    @pytest.mark.asyncio
    @pytest.mark.benchmark
    @pytest.mark.storage
    async def test_neo4j_get_node_benchmark(
        self,
        neo4j_client: Neo4jClient,
    ) -> None:
        """Neo4j 节点查询基准测试."""
        # Create test node first
        test_node = generate_test_node(0)
        await neo4j_client.create_node(test_node)
        
        async def get_node():
            await neo4j_client.get_node(test_node.uid)
        
        result = await async_benchmark(get_node, iterations=50)
        
        print(f"\nNeo4j Get Node Benchmark:")
        print(f"  Avg time: {result.avg_time_ms:.2f} ms")
        print(f"  Throughput: {result.throughput:.2f} queries/sec")
        
        # Cleanup
        await neo4j_client.delete_node(test_node.uid)
        
        assert result.avg_time_ms < 50, "Node query should be < 50ms"
    
    @pytest.mark.asyncio
    @pytest.mark.benchmark
    @pytest.mark.storage
    async def test_neo4j_batch_create_benchmark(
        self,
        neo4j_client: Neo4jClient,
    ) -> None:
        """Neo4j 批量创建基准测试."""
        nodes = [generate_test_node(i) for i in range(10)]
        created_uids = [n.uid for n in nodes]
        
        async def batch_create():
            for node in nodes:
                await neo4j_client.create_node(node)
        
        result = await async_benchmark(batch_create, iterations=5)
        
        print(f"\nNeo4j Batch Create Benchmark (10 nodes):")
        print(f"  Avg time: {result.avg_time_ms:.2f} ms")
        print(f"  Per-node time: {result.avg_time_ms / 10:.2f} ms")
        
        # Cleanup
        for uid in created_uids:
            try:
                await neo4j_client.delete_node(uid)
            except Exception:
                pass
        
        assert result.avg_time_ms < 1000, "Batch create should be < 1s"


class TestMilvusBenchmark:
    """Milvus 性能基准测试."""
    
    @pytest.mark.asyncio
    @pytest.mark.benchmark
    @pytest.mark.storage
    async def test_milvus_insert_benchmark(
        self,
        milvus_client: MilvusClient,
    ) -> None:
        """Milvus 向量插入基准测试."""
        inserted_ids = []
        
        async def insert_vector():
            id = f"bench_test:vec_{len(inserted_ids)}"
            vector = generate_test_embedding(1536)
            await milvus_client.insert(
                id=id,
                vector=vector,
                metadata={"source": "benchmark"}
            )
            inserted_ids.append(id)
        
        result = await async_benchmark(insert_vector, iterations=20)
        
        print(f"\nMilvus Insert Benchmark:")
        print(f"  Avg time: {result.avg_time_ms:.2f} ms")
        print(f"  Throughput: {result.throughput:.2f} inserts/sec")
        
        # Cleanup
        try:
            await milvus_client.delete(ids=inserted_ids)
        except Exception:
            pass
        
        assert result.avg_time_ms < 100, "Vector insert should be < 100ms"
    
    @pytest.mark.asyncio
    @pytest.mark.benchmark
    @pytest.mark.storage
    async def test_milvus_search_benchmark(
        self,
        milvus_client: MilvusClient,
    ) -> None:
        """Milvus 向量搜索基准测试."""
        # Insert test vector first
        test_id = "bench_test:search_target"
        test_vector = generate_test_embedding(1536)
        await milvus_client.insert(
            id=test_id,
            vector=test_vector,
            metadata={"source": "benchmark"}
        )
        
        async def search_vector():
            await milvus_client.search(
                query_vector=test_vector,
                top_k=10,
            )
        
        result = await async_benchmark(search_vector, iterations=50)
        
        print(f"\nMilvus Search Benchmark:")
        print(f"  Avg time: {result.avg_time_ms:.2f} ms")
        print(f"  Throughput: {result.throughput:.2f} searches/sec")
        
        # Cleanup
        try:
            await milvus_client.delete(ids=[test_id])
        except Exception:
            pass
        
        assert result.avg_time_ms < 50, "Vector search should be < 50ms"
    
    @pytest.mark.asyncio
    @pytest.mark.benchmark
    @pytest.mark.storage
    async def test_milvus_batch_insert_benchmark(
        self,
        milvus_client: MilvusClient,
    ) -> None:
        """Milvus 批量插入基准测试."""
        vectors = []
        ids = []
        for i in range(50):
            ids.append(f"bench_test:batch_{i}")
            vectors.append(generate_test_embedding(1536))
        
        async def batch_insert():
            await milvus_client.batch_insert(
                ids=ids,
                vectors=vectors,
                metadata={"source": "benchmark_batch"}
            )
        
        result = await async_benchmark(batch_insert, iterations=5)
        
        print(f"\nMilvus Batch Insert Benchmark (50 vectors):")
        print(f"  Avg time: {result.avg_time_ms:.2f} ms")
        print(f"  Per-vector time: {result.avg_time_ms / 50:.2f} ms")
        
        # Cleanup
        try:
            await milvus_client.delete(ids=ids)
        except Exception:
            pass
        
        assert result.avg_time_ms < 500, "Batch insert should be < 500ms"


class TestRedisBenchmark:
    """Redis 性能基准测试."""
    
    @pytest.mark.asyncio
    @pytest.mark.benchmark
    @pytest.mark.storage
    async def test_redis_set_benchmark(
        self,
        redis_client: RedisClient,
    ) -> None:
        """Redis SET 基准测试."""
        keys = []
        
        async def set_value():
            key = f"bench:test:{len(keys)}"
            await redis_client.set(key, "test_value", ttl=60)
            keys.append(key)
        
        result = await async_benchmark(set_value, iterations=100)
        
        print(f"\nRedis SET Benchmark:")
        print(f"  Avg time: {result.avg_time_ms:.2f} ms")
        print(f"  Throughput: {result.throughput:.2f} sets/sec")
        
        # Cleanup
        for key in keys:
            try:
                await redis_client.delete(key)
            except Exception:
                pass
        
        assert result.avg_time_ms < 5, "Redis SET should be < 5ms"
    
    @pytest.mark.asyncio
    @pytest.mark.benchmark
    @pytest.mark.storage
    async def test_redis_get_benchmark(
        self,
        redis_client: RedisClient,
    ) -> None:
        """Redis GET 基准测试."""
        # Set test key first
        test_key = "bench:test:get_target"
        await redis_client.set(test_key, "test_value", ttl=60)
        
        async def get_value():
            await redis_client.get(test_key)
        
        result = await async_benchmark(get_value, iterations=200)
        
        print(f"\nRedis GET Benchmark:")
        print(f"  Avg time: {result.avg_time_ms:.2f} ms")
        print(f"  Throughput: {result.throughput:.2f} gets/sec")
        
        # Cleanup
        await redis_client.delete(test_key)
        
        assert result.avg_time_ms < 2, "Redis GET should be < 2ms"
    
    @pytest.mark.asyncio
    @pytest.mark.benchmark
    @pytest.mark.storage
    async def test_redis_mget_benchmark(
        self,
        redis_client: RedisClient,
    ) -> None:
        """Redis MGET 基准测试."""
        # Set multiple keys
        keys = [f"bench:test:mget_{i}" for i in range(10)]
        for key in keys:
            await redis_client.set(key, f"value_{key}", ttl=60)
        
        async def mget_values():
            await redis_client.mget(keys)
        
        result = await async_benchmark(mget_values, iterations=100)
        
        print(f"\nRedis MGET Benchmark (10 keys):")
        print(f"  Avg time: {result.avg_time_ms:.2f} ms")
        print(f"  Per-key time: {result.avg_time_ms / 10:.2f} ms")
        
        # Cleanup
        for key in keys:
            await redis_client.delete(key)
        
        assert result.avg_time_ms < 10, "Redis MGET should be < 10ms"


class TestCrossStorageBenchmark:
    """跨存储性能基准测试."""
    
    @pytest.mark.asyncio
    @pytest.mark.benchmark
    @pytest.mark.storage
    @pytest.mark.slow
    async def test_full_storage_workflow_benchmark(
        self,
        neo4j_client: Neo4jClient,
        milvus_client: MilvusClient,
        redis_client: RedisClient,
    ) -> None:
        """完整存储流程基准测试."""
        created_uids = []
        inserted_ids = []
        cached_keys = []
        
        async def full_workflow():
            index = len(created_uids)
            
            # Create node in Neo4j
            node = generate_test_node(index)
            await neo4j_client.create_node(node)
            created_uids.append(node.uid)
            
            # Insert vector in Milvus
            vector_id = f"bench:workflow:{index}"
            vector = generate_test_embedding(1536)
            await milvus_client.insert(
                id=vector_id,
                vector=vector,
                metadata={"skill_uid": node.uid}
            )
            inserted_ids.append(vector_id)
            
            # Cache in Redis
            cache_key = f"skill:bench:{index}"
            await redis_client.set(cache_key, str(node.to_dict()), ttl=60)
            cached_keys.append(cache_key)
        
        result = await async_benchmark(full_workflow, iterations=10)
        
        print(f"\nFull Storage Workflow Benchmark:")
        print(f"  Avg time: {result.avg_time_ms:.2f} ms")
        print(f"  Throughput: {result.throughput:.2f} workflows/sec")
        
        # Cleanup
        for uid in created_uids:
            try:
                await neo4j_client.delete_node(uid)
            except Exception:
                pass
        
        try:
            await milvus_client.delete(ids=inserted_ids)
        except Exception:
            pass
        
        for key in cached_keys:
            try:
                await redis_client.delete(key)
            except Exception:
                pass
        
        assert result.avg_time_ms < 500, "Full workflow should be < 500ms"


# ============================================================================
# Test Markers
# ============================================================================

def pytest_configure(config):
    config.addinivalue_line("markers", "benchmark: Performance benchmark tests")
    config.addinivalue_line("markers", "storage: Storage layer tests")
    config.addinivalue_line("markers", "slow: Slow running tests")