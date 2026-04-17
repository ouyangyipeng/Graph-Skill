"""
RedisClient 单元测试。

测试 Redis 缓存客户端的基本功能（数据结构和初始化）。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from graphskill.storage.cache import (
    CacheError,
    CacheEntry,
    CacheStats,
    RedisClient,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def redis_client() -> RedisClient:
    """创建 Redis 客户端。"""
    return RedisClient(
        host="localhost",
        port=6379,
        db=0,
        default_ttl=300,
    )


@pytest.fixture
def redis_client_custom() -> RedisClient:
    """创建自定义配置的 Redis 客户端。"""
    return RedisClient(
        host="redis.example.com",
        port=6380,
        db=1,
        password="secret",
        default_ttl=600,
        max_connections=100,
    )


@pytest.fixture
def cache_stats() -> CacheStats:
    """创建缓存统计。"""
    return CacheStats(
        total_keys=100,
        memory_used_bytes=1024000,
        hit_rate=0.85,
        miss_rate=0.15,
        keyspace_hits=850,
        keyspace_misses=150,
    )


# ============================================================================
# RedisClient Init Tests
# ============================================================================


class TestRedisClientInit:
    """RedisClient 初始化测试。"""
    
    def test_init_default_config(self, redis_client: RedisClient) -> None:
        """测试默认配置初始化。"""
        assert redis_client.host == "localhost"
        assert redis_client.port == 6379
        assert redis_client.db == 0
        assert redis_client.password is None
        assert redis_client.default_ttl == 300
        assert redis_client.max_connections == 50
        assert redis_client._client is None
        assert redis_client._connected == False
    
    def test_init_custom_config(self, redis_client_custom: RedisClient) -> None:
        """测试自定义配置初始化。"""
        assert redis_client_custom.host == "redis.example.com"
        assert redis_client_custom.port == 6380
        assert redis_client_custom.db == 1
        assert redis_client_custom.password == "secret"
        assert redis_client_custom.default_ttl == 600
        assert redis_client_custom.max_connections == 100
    
    def test_init_default_host_constant(self) -> None:
        """测试默认主机来自常量。"""
        client = RedisClient()
        assert client.host == "localhost"
        assert client.port == 6379
    
    def test_cache_key_prefixes(self, redis_client: RedisClient) -> None:
        """测试缓存键前缀。"""
        assert redis_client.ROUTING_CACHE_PREFIX == "routing:result:"
        assert redis_client.SESSION_CACHE_PREFIX == "session:"
        assert redis_client.SKILL_CACHE_PREFIX == "skill:"
        assert redis_client.EMBEDDING_CACHE_PREFIX == "embedding:"


# ============================================================================
# RedisClient Connection Tests (Mock Mode)
# ============================================================================


class TestRedisClientConnection:
    """RedisClient 连接测试。"""
    
    @pytest.mark.asyncio
    async def test_connect_mock_mode(self, redis_client: RedisClient) -> None:
        """测试模拟模式连接（无 redis 库）。
        
        修复后：_connected=False, _mock_mode=True（不再静默伪装已连接）。
        """
        with patch.dict('sys.modules', {'redis.asyncio': None}):
            await redis_client.connect()
            assert redis_client._connected == False
            assert redis_client._mock_mode == True
    
    def test_connect_sync_mock_mode(self, redis_client: RedisClient) -> None:
        """测试同步模拟模式连接。"""
        with patch.dict('sys.modules', {'redis': None}):
            redis_client.connect_sync()
            assert redis_client._connected == False
            assert redis_client._mock_mode == True
    
    @pytest.mark.asyncio
    async def test_close_without_client(self, redis_client: RedisClient) -> None:
        """测试无客户端时关闭。"""
        redis_client._connected = True
        redis_client._client = None
        
        await redis_client.close()
        assert redis_client._connected == False
        assert redis_client._client is None
    
    @pytest.mark.asyncio
    async def test_close_already_closed(self, redis_client: RedisClient) -> None:
        """测试已关闭时再次关闭。"""
        redis_client._connected = False
        redis_client._client = None
        
        await redis_client.close()
        assert redis_client._connected == False


# ============================================================================
# RedisClient Mock Mode Operations Tests
# ============================================================================


class TestRedisClientMockMode:
    """RedisClient 模拟模式操作测试。"""
    
    @pytest.mark.asyncio
    async def test_set_in_mock_mode(self, redis_client: RedisClient) -> None:
        """测试模拟模式下设置值。"""
        redis_client._client = None  # 模拟模式
        
        result = await redis_client.set("test:key", {"data": "value"})
        assert result == True  # 模拟模式返回 True
    
    @pytest.mark.asyncio
    async def test_get_in_mock_mode(self, redis_client: RedisClient) -> None:
        """测试模拟模式下获取值。"""
        redis_client._client = None  # 模拟模式
        
        result = await redis_client.get("test:key")
        assert result is None  # 模拟模式返回 default
    
    @pytest.mark.asyncio
    async def test_get_with_default_in_mock_mode(self, redis_client: RedisClient) -> None:
        """测试模拟模式下获取值带默认值。"""
        redis_client._client = None  # 模拟模式
        
        result = await redis_client.get("test:key", default="default_value")
        assert result == "default_value"
    
    @pytest.mark.asyncio
    async def test_delete_in_mock_mode(self, redis_client: RedisClient) -> None:
        """测试模拟模式下删除值。"""
        redis_client._client = None  # 模拟模式
        
        result = await redis_client.delete("test:key")
        assert result == True  # 模拟模式返回 True
    
    @pytest.mark.asyncio
    async def test_exists_in_mock_mode(self, redis_client: RedisClient) -> None:
        """测试模拟模式下检查键存在。"""
        redis_client._client = None  # 模拟模式
        
        result = await redis_client.exists("test:key")
        assert result == False  # 模拟模式返回 False
    
    @pytest.mark.asyncio
    async def test_set_ttl_in_mock_mode(self, redis_client: RedisClient) -> None:
        """测试模拟模式下设置 TTL。"""
        redis_client._client = None  # 模拟模式
        
        result = await redis_client.set_ttl("test:key", 600)
        assert result == True  # 模拟模式返回 True
    
    @pytest.mark.asyncio
    async def test_get_ttl_in_mock_mode(self, redis_client: RedisClient) -> None:
        """测试模拟模式下获取 TTL。"""
        redis_client._client = None  # 模拟模式
        
        result = await redis_client.get_ttl("test:key")
        assert result == -1  # 模拟模式返回 -1
    
    @pytest.mark.asyncio
    async def test_mget_in_mock_mode(self, redis_client: RedisClient) -> None:
        """测试模拟模式下批量获取。"""
        redis_client._client = None  # 模拟模式
        
        result = await redis_client.mget(["key1", "key2"])
        assert result == {}  # 模拟模式返回空字典
    
    @pytest.mark.asyncio
    async def test_mset_in_mock_mode(self, redis_client: RedisClient) -> None:
        """测试模拟模式下批量设置。"""
        redis_client._client = None  # 模拟模式
        
        result = await redis_client.mset({"key1": "value1", "key2": "value2"})
        assert result == True  # 模拟模式返回 True
    
    @pytest.mark.asyncio
    async def test_incr_in_mock_mode(self, redis_client: RedisClient) -> None:
        """测试模拟模式下递增计数器。"""
        redis_client._client = None  # 模拟模式
        
        result = await redis_client.incr("counter:test", amount=5)
        assert result == 5  # 模拟模式返回 amount
    
    @pytest.mark.asyncio
    async def test_acquire_lock_in_mock_mode(self, redis_client: RedisClient) -> None:
        """测试模拟模式下获取锁。"""
        redis_client._client = None  # 模拟模式
        
        result = await redis_client.acquire_lock("test:lock", timeout=10)
        assert result == True  # 模拟模式返回 True
    
    @pytest.mark.asyncio
    async def test_release_lock_in_mock_mode(self, redis_client: RedisClient) -> None:
        """测试模拟模式下释放锁。"""
        redis_client._client = None  # 模拟模式
        
        result = await redis_client.release_lock("test:lock")
        assert result == True  # 模拟模式返回 True


# ============================================================================
# RedisClient Cache Helpers Tests
# ============================================================================


class TestRedisClientCacheHelpers:
    """RedisClient 缓存辅助方法测试。"""
    
    def test_make_routing_cache_key(self, redis_client: RedisClient) -> None:
        """测试生成路由缓存键。"""
        key = redis_client.make_routing_cache_key("request_123")
        assert key == "routing:result:request_123"
    
    def test_make_skill_cache_key(self, redis_client: RedisClient) -> None:
        """测试生成技能缓存键。"""
        key = redis_client.make_skill_cache_key("skill:test:skill")
        assert key == "skill:skill:test:skill"
    
    @pytest.mark.asyncio
    async def test_cache_routing_result_mock(self, redis_client: RedisClient) -> None:
        """测试模拟模式下缓存路由结果。"""
        redis_client._client = None  # 模拟模式
        
        result = {"selected_skills": ["skill1", "skill2"]}
        success = await redis_client.cache_routing_result("request_123", result)
        assert success == True
    
    @pytest.mark.asyncio
    async def test_get_cached_routing_result_mock(self, redis_client: RedisClient) -> None:
        """测试模拟模式下获取缓存的路由结果。"""
        redis_client._client = None  # 模拟模式
        
        result = await redis_client.get_cached_routing_result("request_123")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_invalidate_routing_cache_mock(self, redis_client: RedisClient) -> None:
        """测试模拟模式下清除路由缓存。"""
        redis_client._client = None  # 模拟模式
        
        result = await redis_client.invalidate_routing_cache("request_123")
        assert result == True
    
    @pytest.mark.asyncio
    async def test_cache_skill_mock(self, redis_client: RedisClient) -> None:
        """测试模拟模式下缓存技能。"""
        redis_client._client = None  # 模拟模式
        
        skill_data = {"uid": "skill:test:skill", "intent": "test"}
        success = await redis_client.cache_skill("skill:test:skill", skill_data)
        assert success == True
    
    @pytest.mark.asyncio
    async def test_get_cached_skill_mock(self, redis_client: RedisClient) -> None:
        """测试模拟模式下获取缓存的技能。"""
        redis_client._client = None  # 模拟模式
        
        result = await redis_client.get_cached_skill("skill:test:skill")
        assert result is None


# ============================================================================
# RedisClient Stats Tests
# ============================================================================


class TestRedisClientStats:
    """RedisClient 统计测试。"""
    
    @pytest.mark.asyncio
    async def test_get_stats_mock(self, redis_client: RedisClient) -> None:
        """测试模拟模式下获取统计信息。"""
        redis_client._client = None  # 模拟模式
        
        stats = await redis_client.get_stats()
        assert stats.total_keys == 0
        assert stats.memory_used_bytes == 0
    
    @pytest.mark.asyncio
    async def test_flush_db_mock(self, redis_client: RedisClient) -> None:
        """测试模拟模式下清空数据库。"""
        redis_client._client = None  # 模拟模式
        
        result = await redis_client.flush_db()
        assert result == True
    
    @pytest.mark.asyncio
    async def test_health_check_mock(self, redis_client: RedisClient) -> None:
        """测试模拟模式下健康检查。"""
        redis_client._client = None  # 模拟模式
        redis_client._connected = True
        
        health = await redis_client.health_check()
        assert health["status"] == "healthy"


# ============================================================================
# Edge Cases Tests
# ============================================================================


class TestEdgeCases:
    """边界条件测试。"""
    
    def test_make_cache_key_with_special_chars(self, redis_client: RedisClient) -> None:
        """测试特殊字符的缓存键。"""
        key = redis_client.make_routing_cache_key("request with spaces")
        assert "request with spaces" in key
    
    def test_make_cache_key_with_unicode(self, redis_client: RedisClient) -> None:
        """测试 Unicode 缓存键。"""
        key = redis_client.make_routing_cache_key("请求_123")
        assert "请求_123" in key
    
    @pytest.mark.asyncio
    async def test_set_with_zero_ttl_mock(self, redis_client: RedisClient) -> None:
        """测试模拟模式下设置零 TTL。"""
        redis_client._client = None  # 模拟模式
        
        result = await redis_client.set("test:key", "value", ttl=0)
        assert result == True
    
    @pytest.mark.asyncio
    async def test_mset_empty_mapping_mock(self, redis_client: RedisClient) -> None:
        """测试模拟模式下批量设置空映射。"""
        redis_client._client = None  # 模拟模式
        
        result = await redis_client.mset({})
        assert result == True
    
    @pytest.mark.asyncio
    async def test_mget_empty_list_mock(self, redis_client: RedisClient) -> None:
        """测试模拟模式下批量获取空列表。"""
        redis_client._client = None  # 模拟模式
        
        result = await redis_client.mget([])
        assert result == {}
    
    def test_redis_client_with_large_max_connections(self) -> None:
        """测试大连接数配置。"""
        client = RedisClient(max_connections=10000)
        assert client.max_connections == 10000
    
    def test_redis_client_with_zero_db(self) -> None:
        """测试零数据库编号。"""
        client = RedisClient(db=0)
        assert client.db == 0


# ============================================================================
# Integration Tests (Mock Mode)
# ============================================================================


class TestIntegration:
    """集成测试。"""
    
    @pytest.mark.asyncio
    async def test_full_mock_workflow(self, redis_client: RedisClient) -> None:
        """测试模拟模式完整工作流。"""
        redis_client._client = None  # 模拟模式
        
        # 设置值
        result = await redis_client.set("test:key", {"data": "test"})
        assert result == True
        
        # 获取值（模拟模式返回 None）
        value = await redis_client.get("test:key")
        assert value is None
        
        # 删除值
        result = await redis_client.delete("test:key")
        assert result == True
    
    @pytest.mark.asyncio
    async def test_routing_cache_mock_workflow(self, redis_client: RedisClient) -> None:
        """测试模拟模式路由缓存工作流。"""
        redis_client._client = None  # 模拟模式
        
        # 缓存路由结果
        result = await redis_client.cache_routing_result("req_123", {"skills": ["skill1"]})
        assert result == True
        
        # 获取缓存（模拟模式返回 None）
        result = await redis_client.get_cached_routing_result("req_123")
        assert result is None
        
        # 清除缓存
        result = await redis_client.invalidate_routing_cache("req_123")
        assert result == True
    
    @pytest.mark.asyncio
    async def test_skill_cache_mock_workflow(self, redis_client: RedisClient) -> None:
        """测试模拟模式技能缓存工作流。"""
        redis_client._client = None  # 模拟模式
        
        # 缓存技能
        result = await redis_client.cache_skill("skill:test", {"uid": "skill:test"})
        assert result == True
        
        # 获取缓存（模拟模式返回 None）
        result = await redis_client.get_cached_skill("skill:test")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_lock_mock_workflow(self, redis_client: RedisClient) -> None:
        """测试模拟模式锁工作流。"""
        redis_client._client = None  # 模拟模式
        
        # 获取锁
        result = await redis_client.acquire_lock("test:lock", timeout=10)
        assert result == True
        
        # 释放锁
        result = await redis_client.release_lock("test:lock")
        assert result == True