"""
并发测试：导入流程并发执行。

测试多线程/多进程并发导入场景：
- 多线程并发导入
- 数据库连接池压力测试
- 锁竞争检测

Reference: plans/phase_03_e2e_plan.md
"""

from __future__ import annotations

import os
import pytest
import asyncio
import time
import random
from pathlib import Path
from typing import Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent.parent.parent.parent / ".env.test")

from graphskill.storage.graph_db import Neo4jClient
from graphskill.storage.vector_db import MilvusClient
from graphskill.storage.cache import RedisClient
from graphskill.core.models import SkillNode


# ============================================================================
# Test Helpers
# ============================================================================

def generate_test_node(index: int, prefix: str = "concurrent") -> SkillNode:
    """生成测试节点."""
    return SkillNode(
        uid=f"{prefix}:node_{index}",
        version="1.0.0",
        intent_description=f"Concurrent test node for performance testing purposes with index {index} and prefix {prefix}",
        permissions=["fs:read:./repo"],
        execution_success_rate=1.0,
        execution_count=0,
        is_deprecated=False,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        tags=["concurrent", "test"],
        author="ConcurrentTest",
    )


def generate_test_embedding(dimensions: int = 1536) -> list[float]:
    """生成测试向量."""
    return [random.random() for _ in range(dimensions)]


async def create_node_async(client: Neo4jClient, node: SkillNode) -> bool:
    """异步创建节点."""
    try:
        await client.create_node(node)
        return True
    except Exception as e:
        print(f"Error creating node {node.uid}: {e}")
        return False


async def insert_vector_async(client: MilvusClient, id: str, vector: list[float]) -> bool:
    """异步插入向量."""
    try:
        await client.insert(id=id, vector=vector, metadata={"source": "concurrent"})
        return True
    except Exception as e:
        print(f"Error inserting vector {id}: {e}")
        return False


async def set_cache_async(client: RedisClient, key: str, value: str) -> bool:
    """异步设置缓存."""
    try:
        await client.set(key, value, ttl=60)
        return True
    except Exception as e:
        print(f"Error setting cache {key}: {e}")
        return False


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
        collection_name="concurrent_skill_embeddings",
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
# Concurrency Tests
# ============================================================================

class TestAsyncConcurrency:
    """异步并发测试."""
    
    @pytest.mark.asyncio
    @pytest.mark.concurrency
    async def test_concurrent_neo4j_creates(
        self,
        neo4j_client: Neo4jClient,
    ) -> None:
        """测试并发 Neo4j 节点创建."""
        num_concurrent = 20
        nodes = [generate_test_node(i, "async_neo4j") for i in range(num_concurrent)]
        
        # Create all nodes concurrently
        start_time = time.perf_counter()
        tasks = [create_node_async(neo4j_client, node) for node in nodes]
        results = await asyncio.gather(*tasks)
        end_time = time.perf_counter()
        
        total_time_ms = (end_time - start_time) * 1000
        
        print(f"\nConcurrent Neo4j Creates ({num_concurrent} nodes):")
        print(f"  Total time: {total_time_ms:.2f} ms")
        print(f"  Per-node time: {total_time_ms / num_concurrent:.2f} ms")
        print(f"  Success rate: {sum(results) / num_concurrent * 100:.1f}%")
        
        # Cleanup
        for node in nodes:
            try:
                await neo4j_client.delete_node(node.uid)
            except Exception:
                pass
        
        # All should succeed
        assert sum(results) >= num_concurrent * 0.9, "At least 90% should succeed"
    
    @pytest.mark.asyncio
    @pytest.mark.concurrency
    async def test_concurrent_milvus_inserts(
        self,
        milvus_client: MilvusClient,
    ) -> None:
        """测试并发 Milvus 向量插入."""
        num_concurrent = 30
        ids = [f"async_milvus:vec_{i}" for i in range(num_concurrent)]
        vectors = [generate_test_embedding(1536) for _ in range(num_concurrent)]
        
        # Insert all vectors concurrently
        start_time = time.perf_counter()
        tasks = [
            insert_vector_async(milvus_client, id, vec)
            for id, vec in zip(ids, vectors)
        ]
        results = await asyncio.gather(*tasks)
        end_time = time.perf_counter()
        
        total_time_ms = (end_time - start_time) * 1000
        
        print(f"\nConcurrent Milvus Inserts ({num_concurrent} vectors):")
        print(f"  Total time: {total_time_ms:.2f} ms")
        print(f"  Per-vector time: {total_time_ms / num_concurrent:.2f} ms")
        print(f"  Success rate: {sum(results) / num_concurrent * 100:.1f}%")
        
        # Cleanup
        try:
            await milvus_client.delete(ids=ids)
        except Exception:
            pass
        
        assert sum(results) >= num_concurrent * 0.9, "At least 90% should succeed"
    
    @pytest.mark.asyncio
    @pytest.mark.concurrency
    async def test_concurrent_redis_operations(
        self,
        redis_client: RedisClient,
    ) -> None:
        """测试并发 Redis 操作."""
        num_concurrent = 50
        keys = [f"async_redis:key_{i}" for i in range(num_concurrent)]
        values = [f"value_{i}" for i in range(num_concurrent)]
        
        # Set all keys concurrently
        start_time = time.perf_counter()
        tasks = [
            set_cache_async(redis_client, key, value)
            for key, value in zip(keys, values)
        ]
        results = await asyncio.gather(*tasks)
        end_time = time.perf_counter()
        
        total_time_ms = (end_time - start_time) * 1000
        
        print(f"\nConcurrent Redis SETs ({num_concurrent} keys):")
        print(f"  Total time: {total_time_ms:.2f} ms")
        print(f"  Per-key time: {total_time_ms / num_concurrent:.2f} ms")
        print(f"  Success rate: {sum(results) / num_concurrent * 100:.1f}%")
        
        # Cleanup
        for key in keys:
            try:
                await redis_client.delete(key)
            except Exception:
                pass
        
        assert sum(results) == num_concurrent, "All should succeed"
    
    @pytest.mark.asyncio
    @pytest.mark.concurrency
    async def test_mixed_concurrent_operations(
        self,
        neo4j_client: Neo4jClient,
        milvus_client: MilvusClient,
        redis_client: RedisClient,
    ) -> None:
        """测试混合并发操作."""
        num_concurrent = 10
        
        # Prepare data
        nodes = [generate_test_node(i, "mixed_async") for i in range(num_concurrent)]
        vectors = [generate_test_embedding(1536) for _ in range(num_concurrent)]
        cache_keys = [f"mixed_async:cache_{i}" for i in range(num_concurrent)]
        
        # Create mixed tasks
        tasks = []
        for i in range(num_concurrent):
            tasks.append(create_node_async(neo4j_client, nodes[i]))
            tasks.append(insert_vector_async(
                milvus_client,
                f"mixed_async:vec_{i}",
                vectors[i]
            ))
            tasks.append(set_cache_async(
                redis_client,
                cache_keys[i],
                str(nodes[i].to_dict())
            ))
        
        # Execute all concurrently
        start_time = time.perf_counter()
        results = await asyncio.gather(*tasks)
        end_time = time.perf_counter()
        
        total_time_ms = (end_time - start_time) * 1000
        
        print(f"\nMixed Concurrent Operations ({len(tasks)} total):")
        print(f"  Total time: {total_time_ms:.2f} ms")
        print(f"  Per-op time: {total_time_ms / len(tasks):.2f} ms")
        print(f"  Success rate: {sum(results) / len(tasks) * 100:.1f}%")
        
        # Cleanup
        for node in nodes:
            try:
                await neo4j_client.delete_node(node.uid)
            except Exception:
                pass
        
        try:
            await milvus_client.delete(ids=[f"mixed_async:vec_{i}" for i in range(num_concurrent)])
        except Exception:
            pass
        
        for key in cache_keys:
            try:
                await redis_client.delete(key)
            except Exception:
                pass
        
        assert sum(results) >= len(tasks) * 0.9, "At least 90% should succeed"


class TestThreadPoolConcurrency:
    """线程池并发测试."""
    
    @pytest.mark.concurrency
    def test_thread_pool_neo4j_creates(self) -> None:
        """测试线程池 Neo4j 节点创建."""
        num_concurrent = 10
        
        def create_node_sync(index: int) -> bool:
            """同步创建节点."""
            from neo4j import GraphDatabase
            
            driver = GraphDatabase.driver(
                os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                auth=(
                    os.getenv("NEO4J_USER", "neo4j"),
                    os.getenv("NEO4J_PASSWORD", "password123")
                )
            )
            
            node = generate_test_node(index, "thread_pool")
            
            try:
                with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
                    session.run(
                        """
                        CREATE (n:SkillNode {
                            uid: $uid,
                            version: $version,
                            intent_description: $intent_description,
                            permissions: $permissions,
                            execution_success_rate: $execution_success_rate,
                            execution_count: $execution_count,
                            is_deprecated: $is_deprecated,
                            created_at: datetime(),
                            updated_at: datetime(),
                            tags: $tags,
                            author: $author
                        })
                        """,
                        uid=node.uid,
                        version=node.version,
                        intent_description=node.intent_description,
                        permissions=node.permissions,
                        execution_success_rate=node.execution_success_rate,
                        execution_count=node.execution_count,
                        is_deprecated=node.is_deprecated,
                        tags=node.tags,
                        author=node.author,
                    )
                return True
            except Exception as e:
                print(f"Error: {e}")
                return False
            finally:
                driver.close()
        
        # Execute in thread pool
        start_time = time.perf_counter()
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_node_sync, i) for i in range(num_concurrent)]
            results = [f.result() for f in futures]
        end_time = time.perf_counter()
        
        total_time_ms = (end_time - start_time) * 1000
        
        print(f"\nThread Pool Neo4j Creates ({num_concurrent} nodes):")
        print(f"  Total time: {total_time_ms:.2f} ms")
        print(f"  Success rate: {sum(results) / num_concurrent * 100:.1f}%")
        
        # Cleanup
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password123"))
        )
        
        try:
            with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
                session.run(
                    "MATCH (n:SkillNode) WHERE n.uid STARTS WITH 'thread_pool:' DELETE n"
                )
        finally:
            driver.close()
        
        assert sum(results) >= num_concurrent * 0.8, "At least 80% should succeed"
    
    @pytest.mark.concurrency
    def test_thread_pool_redis_operations(self) -> None:
        """测试线程池 Redis 操作."""
        import redis
        
        num_concurrent = 20
        client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
        )
        
        def set_key_sync(index: int) -> bool:
            """同步设置键."""
            try:
                client.set(f"thread_pool:key_{index}", f"value_{index}", ex=60)
                return True
            except Exception:
                return False
        
        # Execute in thread pool
        start_time = time.perf_counter()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(set_key_sync, i) for i in range(num_concurrent)]
            results = [f.result() for f in futures]
        end_time = time.perf_counter()
        
        total_time_ms = (end_time - start_time) * 1000
        
        print(f"\nThread Pool Redis SETs ({num_concurrent} keys):")
        print(f"  Total time: {total_time_ms:.2f} ms")
        print(f"  Success rate: {sum(results) / num_concurrent * 100:.1f}%")
        
        # Cleanup
        for i in range(num_concurrent):
            try:
                client.delete(f"thread_pool:key_{i}")
            except Exception:
                pass
        
        assert sum(results) == num_concurrent, "All should succeed"


class TestConnectionPoolStress:
    """连接池压力测试."""
    
    @pytest.mark.asyncio
    @pytest.mark.concurrency
    @pytest.mark.stress
    async def test_neo4j_connection_pool_stress(
        self,
        neo4j_client: Neo4jClient,
    ) -> None:
        """测试 Neo4j 连接池压力."""
        num_operations = 50
        
        # Rapid create/delete operations
        async def rapid_operation(index: int) -> bool:
            node = generate_test_node(index, "stress_test")
            try:
                await neo4j_client.create_node(node)
                await neo4j_client.get_node(node.uid)
                await neo4j_client.delete_node(node.uid)
                return True
            except Exception as e:
                print(f"Error in operation {index}: {e}")
                return False
        
        # Execute all operations
        start_time = time.perf_counter()
        tasks = [rapid_operation(i) for i in range(num_operations)]
        results = await asyncio.gather(*tasks)
        end_time = time.perf_counter()
        
        total_time_ms = (end_time - start_time) * 1000
        
        print(f"\nNeo4j Connection Pool Stress ({num_operations} ops):")
        print(f"  Total time: {total_time_ms:.2f} ms")
        print(f"  Per-op time: {total_time_ms / num_operations:.2f} ms")
        print(f"  Success rate: {sum(results) / num_operations * 100:.1f}%")
        
        assert sum(results) >= num_operations * 0.85, "At least 85% should succeed"
    
    @pytest.mark.asyncio
    @pytest.mark.concurrency
    @pytest.mark.stress
    async def test_redis_connection_pool_stress(
        self,
        redis_client: RedisClient,
    ) -> None:
        """测试 Redis 连接池压力."""
        num_operations = 100
        
        # Rapid set/get/delete operations
        async def rapid_operation(index: int) -> bool:
            key = f"stress_test:key_{index}"
            try:
                await redis_client.set(key, f"value_{index}", ttl=30)
                await redis_client.get(key)
                await redis_client.delete(key)
                return True
            except Exception as e:
                print(f"Error in operation {index}: {e}")
                return False
        
        # Execute all operations
        start_time = time.perf_counter()
        tasks = [rapid_operation(i) for i in range(num_operations)]
        results = await asyncio.gather(*tasks)
        end_time = time.perf_counter()
        
        total_time_ms = (end_time - start_time) * 1000
        
        print(f"\nRedis Connection Pool Stress ({num_operations} ops):")
        print(f"  Total time: {total_time_ms:.2f} ms")
        print(f"  Per-op time: {total_time_ms / num_operations:.2f} ms")
        print(f"  Success rate: {sum(results) / num_operations * 100:.1f}%")
        
        assert sum(results) >= num_operations * 0.95, "At least 95% should succeed"


class TestLockCompetition:
    """锁竞争测试."""
    
    @pytest.mark.asyncio
    @pytest.mark.concurrency
    async def test_redis_lock_competition(
        self,
        redis_client: RedisClient,
    ) -> None:
        """测试 Redis 锁竞争."""
        lock_key = "test:shared_lock"
        num_competitors = 10
        
        acquired_count = 0
        release_count = 0
        
        async def compete_for_lock(index: int) -> tuple[bool, bool]:
            """竞争锁."""
            acquired = False
            released = False
            
            try:
                # Try to acquire lock
                acquired = await redis_client.acquire_lock(
                    lock_key,
                    timeout=5,
                    retry_interval=0.1
                )
                
                if acquired:
                    # Hold lock briefly
                    await asyncio.sleep(0.1)
                    
                    # Release lock
                    released = await redis_client.release_lock(lock_key)
            
            except Exception as e:
                print(f"Error in competitor {index}: {e}")
            
            return (acquired, released)
        
        # Execute all competitors
        tasks = [compete_for_lock(i) for i in range(num_competitors)]
        results = await asyncio.gather(*tasks)
        
        acquired_count = sum(1 for a, r in results if a)
        release_count = sum(1 for a, r in results if r)
        
        print(f"\nRedis Lock Competition ({num_competitors} competitors):")
        print(f"  Locks acquired: {acquired_count}")
        print(f"  Locks released: {release_count}")
        
        # At least some should have acquired the lock
        assert acquired_count > 0, "At least one should acquire lock"
        # All acquired should be released
        assert release_count == acquired_count, "All acquired should be released"
    
    @pytest.mark.asyncio
    @pytest.mark.concurrency
    async def test_concurrent_node_update(
        self,
        neo4j_client: Neo4jClient,
    ) -> None:
        """测试并发节点更新."""
        # Create initial node
        test_node = generate_test_node(0, "concurrent_update")
        await neo4j_client.create_node(test_node)
        
        num_updaters = 5
        success_count = 0
        
        async def update_node(index: int) -> bool:
            """更新节点."""
            try:
                # Update with different data
                updates = {
                    "execution_count": index * 10,
                    "execution_success_rate": 0.9 - index * 0.05,
                }
                await neo4j_client.update_node(test_node.uid, updates)
                return True
            except Exception as e:
                print(f"Error in updater {index}: {e}")
                return False
        
        # Execute all updaters
        tasks = [update_node(i) for i in range(num_updaters)]
        results = await asyncio.gather(*tasks)
        success_count = sum(results)
        
        print(f"\nConcurrent Node Update ({num_updaters} updaters):")
        print(f"  Success rate: {success_count / num_updaters * 100:.1f}%")
        
        # Verify final state
        final_node = await neo4j_client.get_node(test_node.uid)
        assert final_node is not None
        
        # Cleanup
        await neo4j_client.delete_node(test_node.uid)
        
        # Most updates should succeed
        assert success_count >= num_updaters * 0.8, "At least 80% should succeed"


# ============================================================================
# Test Markers
# ============================================================================

def pytest_configure(config):
    config.addinivalue_line("markers", "concurrency: Concurrency tests")
    config.addinivalue_line("markers", "stress: Stress tests")
    config.addinivalue_line("markers", "slow: Slow running tests")