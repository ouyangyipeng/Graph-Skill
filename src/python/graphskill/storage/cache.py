"""
Redis 缓存客户端。

提供路由结果缓存和会话状态管理。

Reference: RFC-03 Section 8
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any

from graphskill.core.exceptions import DatabaseError
from graphskill.core.constants import (
    REDIS_DEFAULT_HOST as REDIS_HOST,
    REDIS_DEFAULT_PORT as REDIS_PORT,
    REDIS_DEFAULT_DB as REDIS_DB,
    CACHE_TTL_SECONDS as ROUTING_CACHE_TTL_SECONDS,
)


class CacheError(DatabaseError):
    """缓存错误。
    
    Error Code: GS-3002
    """
    
    def __init__(self, message: str, key: Optional[str] = None):
        details = {}
        if key:
            details["key"] = key
        super().__init__(message, details=details)
        self.key = key
    
    def to_dict(self) -> dict:
        result = super().to_dict()
        if self.key:
            result["key"] = self.key
        return result


@dataclass
class CacheEntry:
    """缓存条目。"""
    
    key: str
    value: Any
    ttl: int
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "ttl": self.ttl,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass
class CacheStats:
    """缓存统计。"""
    
    total_keys: int = 0
    memory_used_bytes: int = 0
    hit_rate: float = 0.0
    miss_rate: float = 0.0
    keyspace_hits: int = 0
    keyspace_misses: int = 0
    
    def to_dict(self) -> dict:
        return {
            "total_keys": self.total_keys,
            "memory_used_bytes": self.memory_used_bytes,
            "hit_rate": self.hit_rate,
            "miss_rate": self.miss_rate,
            "keyspace_hits": self.keyspace_hits,
            "keyspace_misses": self.keyspace_misses,
        }


class RedisClient:
    """
    Redis 缓存客户端。
    
    提供路由结果缓存和会话状态管理。
    
    Features:
        - 键值存储
        - TTL 管理
        - 批量操作
        - 分布式锁
        - 发布订阅
    
    Example:
        >>> client = RedisClient(host="localhost", port=6379)
        >>> await client.connect()
        >>> await client.set("routing:result:123", result, ttl=300)
        >>> result = await client.get("routing:result:123")
        >>> await client.close()
    """
    
    # 默认配置
    DEFAULT_HOST = REDIS_HOST
    DEFAULT_PORT = REDIS_PORT
    DEFAULT_DB = REDIS_DB
    DEFAULT_TTL = ROUTING_CACHE_TTL_SECONDS
    
    # 缓存键前缀
    ROUTING_CACHE_PREFIX = "routing:result:"
    SESSION_CACHE_PREFIX = "session:"
    SKILL_CACHE_PREFIX = "skill:"
    EMBEDDING_CACHE_PREFIX = "embedding:"
    
    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        db: int = DEFAULT_DB,
        password: Optional[str] = None,
        default_ttl: int = DEFAULT_TTL,
        max_connections: int = 50,
    ):
        """
        初始化客户端。
        
        Args:
            host: Redis 服务地址
            port: Redis 服务端口
            db: 数据库编号
            password: 密码
            default_ttl: 默认 TTL（秒）
            max_connections: 最大连接数
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.default_ttl = default_ttl
        self.max_connections = max_connections
        
        self._client: Optional[Any] = None
        self._connected = False
        self._mock_mode = False  # True when redis is unavailable
    
    async def connect(self) -> None:
        """
        连接 Redis。
        
        Raises:
            CacheError: 连接失败
        """
        try:
            import redis.asyncio as aioredis
            
            self._client = aioredis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                max_connections=self.max_connections,
                decode_responses=True,
            )
            
            # 验证连接
            await self._client.ping()
            self._connected = True
        
        except ImportError:
            # redis 库未安装，进入 mock 模式
            import logging
            logging.getLogger(__name__).warning(
                "redis not installed — operating in MOCK mode. "
                "All cache operations will return empty/mock results. "
                "Install with: pip install redis"
            )
            self._mock_mode = True
            self._connected = False  # NOT actually connected
        except Exception as e:
            raise CacheError(f"Connection failed: {e}")
    
    def connect_sync(self) -> None:
        """
        同步连接 Redis。
        """
        try:
            import redis
            
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                max_connections=self.max_connections,
                decode_responses=True,
            )
            
            # 验证连接
            self._client.ping()
            self._connected = True
        
        except ImportError:
            self._mock_mode = True
            self._connected = False
        except Exception as e:
            raise CacheError(f"Connection failed: {e}")
    
    async def close(self) -> None:
        """
        关闭连接。
        """
        if self._client:
            await self._client.close()
            self._client = None
        self._connected = False
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        设置键值。
        
        Args:
            key: 键名
            value: 值
            ttl: TTL（秒）
            
        Returns:
            bool: 是否成功
        """
        if self._client is None:
            return True  # 模拟模式
        
        try:
            # 序列化值
            if isinstance(value, (dict, list)):
                serialized_value = json.dumps(value)
            else:
                serialized_value = str(value)
            
            actual_ttl = ttl or self.default_ttl
            
            await self._client.set(key, serialized_value, ex=actual_ttl)
            
            return True
        
        except Exception as e:
            raise CacheError(f"Set failed: {e}", key)
    
    async def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        获取值。
        
        Args:
            key: 键名
            default: 默认值
            
        Returns:
            Any: 值
        """
        if self._client is None:
            return default  # 模拟模式
        
        try:
            value = await self._client.get(key)
            
            if value is None:
                return default
            
            # 尝试反序列化 JSON
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        
        except Exception as e:
            raise CacheError(f"Get failed: {e}", key)
    
    async def delete(
        self,
        key: str,
    ) -> bool:
        """
        删除键。
        
        Args:
            key: 键名
            
        Returns:
            bool: 是否成功
        """
        if self._client is None:
            return True
        
        try:
            await self._client.delete(key)
            return True
        
        except Exception as e:
            raise CacheError(f"Delete failed: {e}", key)
    
    async def exists(
        self,
        key: str,
    ) -> bool:
        """
        检查键是否存在。
        
        Args:
            key: 键名
            
        Returns:
            bool: 是否存在
        """
        if self._client is None:
            return False
        
        try:
            result = await self._client.exists(key)
            return result > 0
        
        except Exception as e:
            raise CacheError(f"Exists check failed: {e}", key)
    
    async def set_ttl(
        self,
        key: str,
        ttl: int,
    ) -> bool:
        """
        设置 TTL。
        
        Args:
            key: 键名
            ttl: TTL（秒）
            
        Returns:
            bool: 是否成功
        """
        if self._client is None:
            return True
        
        try:
            await self._client.expire(key, ttl)
            return True
        
        except Exception as e:
            raise CacheError(f"Set TTL failed: {e}", key)
    
    async def get_ttl(
        self,
        key: str,
    ) -> int:
        """
        获取 TTL。
        
        Args:
            key: 键名
            
        Returns:
            int: TTL（秒），-1 表示无过期，-2 表示不存在
        """
        if self._client is None:
            return -1
        
        try:
            ttl = await self._client.ttl(key)
            return ttl
        
        except Exception as e:
            raise CacheError(f"Get TTL failed: {e}", key)
    
    async def mget(
        self,
        keys: list[str],
    ) -> dict[str, Any]:
        """
        批量获取。
        
        Args:
            keys: 键名列表
            
        Returns:
            dict: 键值映射
        """
        if self._client is None:
            return {}
        
        try:
            values = await self._client.mget(keys)
            
            result: dict[str, Any] = {}
            for key, value in zip(keys, values):
                if value is not None:
                    try:
                        result[key] = json.loads(value)
                    except json.JSONDecodeError:
                        result[key] = value
            
            return result
        
        except Exception as e:
            raise CacheError(f"Mget failed: {e}")
    
    async def mset(
        self,
        mapping: dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """
        批量设置。
        
        Args:
            mapping: 键值映射
            ttl: TTL（秒）
            
        Returns:
            bool: 是否成功
        """
        if self._client is None:
            return True
        
        try:
            # 序列化所有值
            serialized_mapping: dict[str, str] = {}
            for key, value in mapping.items():
                if isinstance(value, (dict, list)):
                    serialized_mapping[key] = json.dumps(value)
                else:
                    serialized_mapping[key] = str(value)
            
            await self._client.mset(serialized_mapping)
            
            # 设置 TTL
            if ttl:
                for key in mapping.keys():
                    await self._client.expire(key, ttl)
            
            return True
        
        except Exception as e:
            raise CacheError(f"Mset failed: {e}")
    
    async def incr(
        self,
        key: str,
        amount: int = 1,
    ) -> int:
        """
        增加计数。
        
        Args:
            key: 键名
            amount: 增加量
            
        Returns:
            int: 新值
        """
        if self._client is None:
            return amount
        
        try:
            result = await self._client.incrby(key, amount)
            return result
        
        except Exception as e:
            raise CacheError(f"Incr failed: {e}", key)
    
    async def acquire_lock(
        self,
        lock_name: str,
        timeout: int = 10,
        blocking_timeout: Optional[float] = None,
    ) -> bool:
        """
        获取分布式锁。
        
        Args:
            lock_name: 锁名称
            timeout: 锁超时（秒）
            blocking_timeout: 阻塞超时（秒）
            
        Returns:
            bool: 是否获取成功
        """
        if self._client is None:
            return True
        
        try:
            lock = self._client.lock(lock_name, timeout=timeout)
            
            if blocking_timeout:
                acquired = await lock.acquire(blocking=True, timeout=blocking_timeout)
            else:
                acquired = await lock.acquire(blocking=False)
            
            return acquired
        
        except Exception as e:
            raise CacheError(f"Lock acquisition failed: {e}", lock_name)
    
    async def release_lock(
        self,
        lock_name: str,
    ) -> bool:
        """
        释放分布式锁。
        
        Args:
            lock_name: 锁名称
            
        Returns:
            bool: 是否释放成功
        """
        if self._client is None:
            return True
        
        try:
            lock = self._client.lock(lock_name)
            await lock.release()
            return True
        
        except Exception as e:
            raise CacheError(f"Lock release failed: {e}", lock_name)
    
    # 路由缓存专用方法
    
    def make_routing_cache_key(
        self,
        request_id: str,
    ) -> str:
        """
        构建路由缓存键。
        
        Args:
            request_id: 请求 ID
            
        Returns:
            str: 缓存键
        """
        return f"{self.ROUTING_CACHE_PREFIX}{request_id}"
    
    async def cache_routing_result(
        self,
        request_id: str,
        result: dict,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        缓存路由结果。
        
        Args:
            request_id: 请求 ID
            result: 路由结果
            ttl: TTL
            
        Returns:
            bool: 是否成功
        """
        key = self.make_routing_cache_key(request_id)
        return await self.set(key, result, ttl or self.default_ttl)
    
    async def get_cached_routing_result(
        self,
        request_id: str,
    ) -> Optional[dict]:
        """
        获取缓存的路由结果。
        
        Args:
            request_id: 请求 ID
            
        Returns:
            Optional[dict]: 路由结果
        """
        key = self.make_routing_cache_key(request_id)
        return await self.get(key)
    
    async def invalidate_routing_cache(
        self,
        request_id: str,
    ) -> bool:
        """
        清除路由缓存。
        
        Args:
            request_id: 请求 ID
            
        Returns:
            bool: 是否成功
        """
        key = self.make_routing_cache_key(request_id)
        return await self.delete(key)
    
    # 技能缓存专用方法
    
    def make_skill_cache_key(
        self,
        skill_uid: str,
    ) -> str:
        """
        构建技能缓存键。
        
        Args:
            skill_uid: 技能 UID
            
        Returns:
            str: 缓存键
        """
        return f"{self.SKILL_CACHE_PREFIX}{skill_uid}"
    
    async def cache_skill(
        self,
        skill_uid: str,
        skill_data: dict,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        缓存技能数据。
        
        Args:
            skill_uid: 技能 UID
            skill_data: 技能数据
            ttl: TTL
            
        Returns:
            bool: 是否成功
        """
        key = self.make_skill_cache_key(skill_uid)
        return await self.set(key, skill_data, ttl or self.default_ttl)
    
    async def get_cached_skill(
        self,
        skill_uid: str,
    ) -> Optional[dict]:
        """
        获取缓存的技能数据。
        
        Args:
            skill_uid: 技能 UID
            
        Returns:
            Optional[dict]: 技能数据
        """
        key = self.make_skill_cache_key(skill_uid)
        return await self.get(key)
    
    # 统计方法
    
    async def get_stats(self) -> CacheStats:
        """
        获取缓存统计。
        
        Returns:
            CacheStats: 统计信息
        """
        if self._client is None:
            return CacheStats()
        
        try:
            info = await self._client.info()
            
            hits = info.get("keyspace_hits", 0)
            misses = info.get("keyspace_misses", 0)
            total = hits + misses
            
            hit_rate = round(hits / total * 100, 2) if total > 0 else 0.0
            miss_rate = round(misses / total * 100, 2) if total > 0 else 0.0
            
            return CacheStats(
                total_keys=info.get("db0", {}).get("keys", 0) if "db0" in info else 0,
                memory_used_bytes=info.get("used_memory", 0),
                hit_rate=hit_rate,
                miss_rate=miss_rate,
                keyspace_hits=hits,
                keyspace_misses=misses,
            )
        
        except Exception as e:
            raise CacheError(f"Get stats failed: {e}")
    
    async def flush_db(self) -> bool:
        """
        清空数据库。
        
        Returns:
            bool: 是否成功
        """
        if self._client is None:
            return True
        
        try:
            await self._client.flushdb()
            return True
        
        except Exception as e:
            raise CacheError(f"Flush DB failed: {e}")
    
    @property
    def is_connected(self) -> bool:
        """是否已连接。"""
        return self._connected
    
    async def health_check(self) -> dict:
        """
        健康检查。
        
        Returns:
            dict: 健康状态
        """
        try:
            if self._client:
                await self._client.ping()
            
            return {
                "status": "healthy",
                "connected": self._connected,
                "host": self.host,
                "port": self.port,
                "db": self.db,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "connected": False,
            }