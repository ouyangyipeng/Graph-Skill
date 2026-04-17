"""
Storage 模块单元测试。

测试缓存、图数据库和向量数据库客户端的数据结构。
"""

from __future__ import annotations

import pytest
from datetime import datetime

from graphskill.storage.cache import (
    CacheError,
    CacheEntry,
    CacheStats,
)
from graphskill.storage.graph_db import (
    GraphDBError,
)
from graphskill.storage.vector_db import (
    VectorDBError,
)


# ============================================================================
# CacheError Tests
# ============================================================================


class TestCacheError:
    """CacheError 异常测试。"""
    
    def test_create_cache_error(self) -> None:
        """测试创建缓存错误。"""
        error = CacheError("Cache connection failed", key="test:key")
        
        assert error.key == "test:key"
        assert "Cache connection failed" in str(error)
    
    def test_cache_error_without_key(self) -> None:
        """测试无 key 的缓存错误。"""
        error = CacheError("Generic cache error")
        
        assert error.key is None
    
    def test_cache_error_to_dict(self) -> None:
        """测试转换为字典。"""
        error = CacheError("Cache error", key="test:key")
        
        result = error.to_dict()
        
        assert result["key"] == "test:key"
    
    def test_cache_error_to_dict_without_key(self) -> None:
        """测试无 key 时转换为字典。"""
        error = CacheError("Cache error")
        
        result = error.to_dict()
        
        assert "key" not in result or result.get("key") is None


# ============================================================================
# CacheEntry Tests
# ============================================================================


class TestCacheEntry:
    """CacheEntry 数据结构测试。"""
    
    def test_create_cache_entry(self) -> None:
        """测试创建缓存条目。"""
        entry = CacheEntry(
            key="test:key",
            value={"data": "test"},
            ttl=300,
        )
        
        assert entry.key == "test:key"
        assert entry.value == {"data": "test"}
        assert entry.ttl == 300
        assert entry.created_at is not None
    
    def test_cache_entry_with_expires_at(self) -> None:
        """测试带过期时间的缓存条目。"""
        expires = datetime.now()
        entry = CacheEntry(
            key="test:key",
            value="test",
            ttl=300,
            expires_at=expires,
        )
        
        assert entry.expires_at == expires
    
    def test_cache_entry_to_dict(self) -> None:
        """测试转换为字典。"""
        entry = CacheEntry(
            key="test:key",
            value={"data": "test"},
            ttl=300,
        )
        
        result = entry.to_dict()
        
        assert result["key"] == "test:key"
        assert result["value"] == {"data": "test"}
        assert result["ttl"] == 300
        assert "created_at" in result
        assert "expires_at" in result


# ============================================================================
# CacheStats Tests
# ============================================================================


class TestCacheStats:
    """CacheStats 数据结构测试。"""
    
    def test_create_cache_stats(self) -> None:
        """测试创建缓存统计。"""
        stats = CacheStats(
            total_keys=100,
            memory_used_bytes=1024,
            hit_rate=0.8,
            miss_rate=0.2,
            keyspace_hits=80,
            keyspace_misses=20,
        )
        
        assert stats.total_keys == 100
        assert stats.memory_used_bytes == 1024
        assert stats.hit_rate == 0.8
        assert stats.miss_rate == 0.2
        assert stats.keyspace_hits == 80
        assert stats.keyspace_misses == 20
    
    def test_cache_stats_defaults(self) -> None:
        """测试默认值。"""
        stats = CacheStats()
        
        assert stats.total_keys == 0
        assert stats.memory_used_bytes == 0
        assert stats.hit_rate == 0.0
        assert stats.miss_rate == 0.0
        assert stats.keyspace_hits == 0
        assert stats.keyspace_misses == 0
    
    def test_cache_stats_to_dict(self) -> None:
        """测试转换为字典。"""
        stats = CacheStats(
            total_keys=100,
            hit_rate=0.8,
            miss_rate=0.2,
        )
        
        result = stats.to_dict()
        
        assert result["total_keys"] == 100
        assert result["hit_rate"] == 0.8
        assert result["miss_rate"] == 0.2


# ============================================================================
# GraphDBError Tests
# ============================================================================


class TestGraphDBError:
    """GraphDBError 异常测试。"""
    
    def test_create_graph_db_error(self) -> None:
        """测试创建图数据库错误。"""
        error = GraphDBError("Connection failed")
        
        assert "Connection failed" in str(error)
    
    def test_graph_db_error_inheritance(self) -> None:
        """测试继承关系。"""
        error = GraphDBError("Test error")
        
        # GraphDBError 应该继承自 DatabaseError
        from graphskill.core.exceptions import DatabaseError
        assert isinstance(error, DatabaseError)


# ============================================================================
# VectorDBError Tests
# ============================================================================


class TestVectorDBError:
    """VectorDBError 异常测试。"""
    
    def test_create_vector_db_error(self) -> None:
        """测试创建向量数据库错误。"""
        error = VectorDBError("Insert failed")
        
        assert "Insert failed" in str(error)
    
    def test_vector_db_error_inheritance(self) -> None:
        """测试继承关系。"""
        error = VectorDBError("Test error")
        
        # VectorDBError 应该继承自 DatabaseError
        from graphskill.core.exceptions import DatabaseError
        assert isinstance(error, DatabaseError)


# ============================================================================
# Edge Cases Tests
# ============================================================================


class TestEdgeCases:
    """边界条件测试。"""
    
    def test_cache_entry_large_value(self) -> None:
        """测试大值缓存条目。"""
        large_value = {"data": "x" * 10000}
        entry = CacheEntry(
            key="test:large",
            value=large_value,
            ttl=3600,
        )
        
        assert entry.value == large_value
    
    def test_cache_stats_zero_values(self) -> None:
        """测试零值统计。"""
        stats = CacheStats(
            total_keys=0,
            hit_rate=0.0,
            miss_rate=0.0,
        )
        
        assert stats.total_keys == 0
        assert stats.hit_rate == 0.0
    
    def test_cache_entry_ttl_zero(self) -> None:
        """测试 TTL 为零。"""
        entry = CacheEntry(
            key="test:key",
            value="test",
            ttl=0,
        )
        
        assert entry.ttl == 0


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """集成测试。"""
    
    def test_error_workflow(self) -> None:
        """测试错误工作流。"""
        # 创建缓存错误
        cache_error = CacheError("Cache failed", key="test:key")
        
        # 转换为字典
        error_dict = cache_error.to_dict()
        
        assert error_dict["key"] == "test:key"
    
    def test_stats_workflow(self) -> None:
        """测试统计工作流。"""
        # 创建统计
        stats = CacheStats(
            total_keys=100,
            keyspace_hits=80,
            keyspace_misses=20,
        )
        
        # 计算命中率
        hit_rate = stats.keyspace_hits / (stats.keyspace_hits + stats.keyspace_misses)
        
        assert hit_rate == 0.8