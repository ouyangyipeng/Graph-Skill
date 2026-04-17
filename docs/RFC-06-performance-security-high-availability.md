# RFC-06: 性能安全与高可用规范

**文档编号:** RFC-06  
**版本:** 1.0.0  
**状态:** 正式发布  
**最后更新:** 2026-04-12  
**作者:** GraphSkill Architecture Team  
**分类:** 架构规范 - 性能与安全  
**依赖:** RFC-00, RFC-03, RFC-05

---

## 目录

1. [概述](#1-概述)
2. [性能基准与 SLA 定义](#2-性能基准与-sla-定义)
3. [缓存策略与降级机制](#3-缓存策略与降级机制)
4. [高并发隔离与连接池管理](#4-高并发隔离与连接池管理)
5. [请求限流与熔断策略](#5-请求限流与熔断策略)
6. [安全边界隔离规范](#6-安全边界隔离规范)
7. [不可信载荷处理规范](#7-不可信载荷处理规范)
8. [容灾恢复流程](#8-容灾恢复流程)
9. [混沌工程与故障演练](#9-混沌工程与故障演练)
10. [版本历史](#10-版本历史)

---

## 1. 概述

### 1.1 文档目的

本文档定义 GraphSkill 系统的性能安全与高可用规范，涵盖性能基准与 SLA 定义、缓存策略与降级机制、高并发隔离与连接池管理、请求限流与熔断策略、安全边界隔离规范、不可信载荷处理规范、容灾恢复流程以及混沌工程与故障演练。

### 1.2 适用范围

本文档适用于：
- 后端开发工程师：实现性能优化与安全隔离
- DevOps 工程师：配置高可用与容灾策略
- 安全工程师：设计安全边界与防护措施
- SRE 工程师：规划混沌工程与故障演练

### 1.3 设计原则

| 原则 | 描述 |
|------|------|
| **性能优先** | 路由请求 MUST 在 SLA 规定时间内完成 |
| **安全隔离** | 技能代码 MUST NOT 在 GraphSkill 进程内执行 |
| **优雅降级** | 故障时 MUST 无缝降级，保证系统可用性 |
| **快速恢复** | 容灾恢复 MUST 在规定时间内完成 |

### 1.4 高可用架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        High Availability Architecture                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Load Balancer Layer                              │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐  │   │
│  │  │ Nginx       │  │ HAProxy     │  │ Kubernetes Ingress          │  │   │
│  │  │ (Layer 7)   │  │ (Layer 4)   │  │                             │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Service Layer (多副本)                           │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ Routing     │  │ Routing     │  │ Routing     │  │ Routing     │ │   │
│  │  │ Gateway-01  │  │ Gateway-02  │  │ Gateway-03  │  │ Gateway-04  │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Data Layer (主从架构)                            │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ Neo4j       │  │ Neo4j       │  │ Milvus      │  │ Milvus      │ │   │
│  │  │ (Primary)   │──│ (Replica)   │  │ (Primary)   │──│ (Replica)   │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ Redis       │  │ Redis       │  │ Kafka       │  │ Kafka       │ │   │
│  │  │ (Cluster)   │  │ (Sentinel)  │  │ (Cluster)   │  │ (Mirror)    │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Cross-Region DR Layer                           │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐  │   │
│  │  │ Region A    │──│ Region B    │──│ Async Data Replication      │  │   │
│  │  │ (Active)    │  │ (Standby)   │  │                             │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 性能基准与 SLA 定义

### 2.1 SLA 指标定义

系统 MUST 满足以下 SLA 指标：

| 指标类别 | 指标名称 | 目标值 | 测量方法 | 告警阈值 |
|----------|----------|--------|----------|----------|
| **可用性** | 系统可用性 | 99.9% | 月度统计 | < 99.5% |
| **可用性** | 数据持久性 | 99.999% | 年度统计 | < 99.99% |
| **延迟** | 路由延迟 P50 | < 200ms | 实时监控 | > 300ms |
| **延迟** | 路由延迟 P99 | < 500ms | 实时监控 | > 800ms |
| **吞吐量** | 单节点 QPS | > 1000 | 压测验证 | < 800 |
| **吞吐量** | 集群 QPS | > 5000 | 压测验证 | < 4000 |
| **错误率** | 路由错误率 | < 0.1% | 实时监控 | > 0.5% |
| **错误率** | 降级率 | < 5% | 实时监控 | > 10% |

### 2.2 性能基准测试规范

系统 MUST 定期执行性能基准测试，验证 SLA 达标：

```python
class PerformanceBenchmark:
    """
    性能基准测试套件。
    """
    
    def __init__(self, routing_gateway, config: BenchmarkConfig):
        self.gateway = routing_gateway
        self.config = config
    
    async def run_full_benchmark(self) -> BenchmarkReport:
        """
        执行完整性能基准测试。
        """
        report = BenchmarkReport(
            timestamp=datetime.utcnow(),
            test_cases=[]
        )
        
        # 1. 延迟测试
        latency_result = await self._test_latency()
        report.test_cases.append(latency_result)
        
        # 2. 吞吐量测试
        throughput_result = await self._test_throughput()
        report.test_cases.append(throughput_result)
        
        # 3. 并发测试
        concurrency_result = await self._test_concurrency()
        report.test_cases.append(concurrency_result)
        
        # 4. 降级测试
        fallback_result = await self._test_fallback()
        report.test_cases.append(fallback_result)
        
        # 5. 长时间稳定性测试
        stability_result = await self._test_stability()
        report.test_cases.append(stability_result)
        
        return report
    
    async def _test_latency(self) -> TestCaseResult:
        """
        延迟测试。
        """
        latencies = []
        
        for _ in range(1000):
            start_time = time.time()
            result = await self.gateway.route(
                query="test query",
                context_state={},
                max_tokens=4000
            )
            latency = (time.time() - start_time) * 1000
            latencies.append(latency)
        
        # 计算统计值
        p50 = np.percentile(latencies, 50)
        p90 = np.percentile(latencies, 90)
        p99 = np.percentile(latencies, 99)
        max_latency = max(latencies)
        
        return TestCaseResult(
            name="latency_test",
            passed=p99 < 500,
            metrics={
                "p50_ms": p50,
                "p90_ms": p90,
                "p99_ms": p99,
                "max_ms": max_latency
            }
        )
    
    async def _test_throughput(self) -> TestCaseResult:
        """
        吞吐量测试。
        """
        duration_seconds = 60
        request_count = 0
        
        start_time = time.time()
        
        while time.time() - start_time < duration_seconds:
            await self.gateway.route(
                query="test query",
                context_state={},
                max_tokens=4000
            )
            request_count += 1
        
        qps = request_count / duration_seconds
        
        return TestCaseResult(
            name="throughput_test",
            passed=qps > 1000,
            metrics={
                "qps": qps,
                "total_requests": request_count,
                "duration_seconds": duration_seconds
            }
        )
    
    async def _test_concurrency(self) -> TestCaseResult:
        """
        并发测试。
        """
        concurrent_requests = 100
        errors = 0
        
        async def single_request():
            try:
                await self.gateway.route(
                    query="test query",
                    context_state={},
                    max_tokens=4000
                )
                return True
            except Exception:
                return False
        
        results = await asyncio.gather(
            *[single_request() for _ in range(concurrent_requests)]
        )
        
        errors = sum(1 for r in results if not r)
        error_rate = errors / concurrent_requests
        
        return TestCaseResult(
            name="concurrency_test",
            passed=error_rate < 0.01,
            metrics={
                "concurrent_requests": concurrent_requests,
                "errors": errors,
                "error_rate": error_rate
            }
        )
```

### 2.3 性能基准报告格式

```json
{
  "benchmark_report": {
    "timestamp": "2026-04-12T10:00:00Z",
    "environment": {
      "node_count": 4,
      "cpu_cores": 8,
      "memory_gb": 32,
      "region": "cn-east-1"
    },
    "test_cases": [
      {
        "name": "latency_test",
        "passed": true,
        "metrics": {
          "p50_ms": 185.2,
          "p90_ms": 320.5,
          "p99_ms": 485.3,
          "max_ms": 650.1
        },
        "sla_target": {
          "p99_ms": 500,
          "status": "PASS"
        }
      },
      {
        "name": "throughput_test",
        "passed": true,
        "metrics": {
          "qps": 1250,
          "total_requests": 75000,
          "duration_seconds": 60
        },
        "sla_target": {
          "qps": 1000,
          "status": "PASS"
        }
      }
    ],
    "overall_status": "PASS",
    "recommendations": []
  }
}
```

---

## 3. 缓存策略与降级机制

### 3.1 多层缓存架构

系统 MUST 实现多层缓存策略：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Multi-Layer Cache Architecture                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Layer 1: Local Cache (进程内)                                              │
│  ┌─────────────┐                                                            │
│  │ LRU Cache   │  容量: 1000 条, TTL: 60s                                   │
│  │ (内存)      │  命中率目标: 20%                                            │
│  └─────────────┘                                                            │
│                                                                             │
│  Layer 2: Distributed Cache (Redis)                                         │
│  ┌─────────────┐                                                            │
│  │ Redis       │  容量: 10000 条, TTL: 3600s                                │
│  │ Cluster     │  命中率目标: 50%                                            │
│  └─────────────┘                                                            │
│                                                                             │
│  Layer 3: Data Store (Graph + Vector DB)                                    │
│  ┌─────────────┐                                                            │
│  │ Graph-Vector│  持久化存储                                                │
│  │ Store       │                                                            │
│  └─────────────┘                                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 缓存策略配置

```yaml
# config/cache.yaml
cache:
  # Layer 1: 本地缓存
  local:
    enabled: true
    max_entries: 1000
    ttl_seconds: 60
    eviction_policy: "lru"
    
  # Layer 2: 分布式缓存
  distributed:
    enabled: true
    redis_cluster:
      nodes:
        - "redis-01:6379"
        - "redis-02:6379"
        - "redis-03:6379"
      max_entries: 10000
      ttl_seconds: 3600
      eviction_policy: "volatile-ttl"
    
  # 缓存键策略
  key_strategy:
    type: "query_hash"  # query_hash | semantic_similarity
    hash_algorithm: "sha256"
    key_prefix: "graphskill:route:"
    
  # 缓存预热
  warmup:
    enabled: true
    schedule: "0 */6 * * *"  # 每 6 小时
    top_queries: 100
    
  # 缓存穿透防护
  penetration_protection:
    enabled: true
    empty_cache_ttl: 30
    bloom_filter: true
```

### 3.3 缓存管理器实现

```python
class MultiLayerCacheManager:
    """
    多层缓存管理器。
    """
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self.local_cache = LocalLRUCache(config.local)
        self.redis_cache = RedisClusterCache(config.distributed)
    
    async def get(self, key: str) -> Optional[CacheEntry]:
        """
        从缓存获取数据（先查本地，再查 Redis）。
        """
        # Layer 1: 本地缓存
        entry = self.local_cache.get(key)
        if entry:
            entry.hit_layer = 1
            return entry
        
        # Layer 2: Redis 缓存
        entry = await self.redis_cache.get(key)
        if entry:
            # 回填本地缓存
            self.local_cache.set(key, entry)
            entry.hit_layer = 2
            return entry
        
        return None
    
    async def set(self, key: str, value: dict, ttl: int = None) -> None:
        """
        设置缓存（同时写入本地和 Redis）。
        """
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=datetime.utcnow(),
            ttl=ttl or self.config.distributed.ttl_seconds
        )
        
        # 写入本地缓存
        self.local_cache.set(key, entry)
        
        # 写入 Redis 缓存
        await self.redis_cache.set(key, entry)
    
    async def invalidate(self, key: str) -> None:
        """
        失效缓存。
        """
        self.local_cache.delete(key)
        await self.redis_cache.delete(key)
    
    async def warmup(self, top_queries: List[dict]) -> None:
        """
        缓存预热。
        """
        for query_data in top_queries:
            key = self._compute_key(query_data["query"])
            result = await self._execute_routing(query_data)
            await self.set(key, result)
    
    def _compute_key(self, query: str) -> str:
        """
        计算缓存键。
        """
        import hashlib
        hash_value = hashlib.sha256(query.encode()).hexdigest()[:16]
        return f"{self.config.key_prefix}{hash_value}"


class LocalLRUCache:
    """
    本地 LRU 缓存实现。
    """
    
    def __init__(self, config: LocalCacheConfig):
        self.config = config
        self.cache = {}
        self.access_order = []
        self.max_entries = config.max_entries
    
    def get(self, key: str) -> Optional[CacheEntry]:
        """
        获取缓存条目。
        """
        if key in self.cache:
            entry = self.cache[key]
            
            # 检查 TTL
            if entry.is_expired():
                self.delete(key)
                return None
            
            # 更新访问顺序
            self.access_order.remove(key)
            self.access_order.append(key)
            
            return entry
        
        return None
    
    def set(self, key: str, entry: CacheEntry) -> None:
        """
        设置缓存条目。
        """
        # 检查容量，执行淘汰
        while len(self.cache) >= self.max_entries:
            oldest_key = self.access_order.pop(0)
            self.cache.pop(oldest_key, None)
        
        self.cache[key] = entry
        self.access_order.append(key)
    
    def delete(self, key: str) -> None:
        """
        删除缓存条目。
        """
        self.cache.pop(key, None)
        if key in self.access_order:
            self.access_order.remove(key)
```

### 3.4 降级机制规范

当图数据库宕机或响应超时时，系统 MUST 无缝降级为纯向量检索：

```python
class FallbackManager:
    """
    降级管理器，处理故障场景下的降级响应。
    """
    
    def __init__(self, config: FallbackConfig):
        self.config = config
        self.graph_timeout_threshold = config.graph_timeout_ms  # 默认 500ms
        self.fallback_mode_active = False
        self.fallback_start_time = None
    
    async def check_graph_health(self) -> GraphHealthStatus:
        """
        检查图数据库健康状态。
        """
        try:
            start_time = time.time()
            
            # 执行健康检查查询
            result = await self.graph_store.execute_query("RETURN 1")
            
            latency = (time.time() - start_time) * 1000
            
            is_healthy = latency < self.graph_timeout_threshold
            
            return GraphHealthStatus(
                is_healthy=is_healthy,
                latency_ms=latency,
                last_check=datetime.utcnow()
            )
            
        except Exception as e:
            return GraphHealthStatus(
                is_healthy=False,
                error=str(e),
                last_check=datetime.utcnow()
            )
    
    async def execute_with_fallback(
        self,
        routing_request: RoutingRequest
    ) -> RoutingResult:
        """
        执行路由请求，支持自动降级。
        """
        health = await self.check_graph_health()
        
        if health.is_healthy:
            # 正常模式
            return await self._normal_routing(routing_request)
        else:
            # 降级模式
            return await self._fallback_routing(routing_request, health)
    
    async def _normal_routing(
        self,
        request: RoutingRequest
    ) -> RoutingResult:
        """
        正常路由流程。
        """
        result = await self.full_routing_pipeline(request)
        result.routing_mode = "normal"
        
        # 如果之前处于降级模式，记录恢复
        if self.fallback_mode_active:
            self.fallback_mode_active = False
            await self._log_fallback_recovery()
        
        return result
    
    async def _fallback_routing(
        self,
        request: RoutingRequest,
        health: GraphHealthStatus
    ) -> RoutingResult:
        """
        降级路由流程：纯向量检索，放弃冲突消解。
        """
        # 记录降级开始
        if not self.fallback_mode_active:
            self.fallback_mode_active = True
            self.fallback_start_time = datetime.utcnow()
            await self._log_fallback_start(health)
        
        # 仅执行向量检索
        seed_nodes = await self.vector_recaller.recall(
            request.query_vector,
            top_k=10
        )
        
        # 直接返回种子节点（无冲突消解）
        skills = [n.skill_id for n in seed_nodes]
        
        result = RoutingResult(
            skills=skills,
            routing_mode="fallback",
            token_count=self._estimate_tokens(skills),
            warnings=[
                "Graph database unavailable, conflict resolution skipped",
                f"Graph health: {health.error or 'timeout'}"
            ]
        )
        
        return result
    
    async def _log_fallback_start(self, health: GraphHealthStatus) -> None:
        """
        记录降级开始事件。
        """
        event = {
            "event_type": "FALLBACK_STARTED",
            "timestamp": datetime.utcnow().isoformat(),
            "reason": health.error or "timeout",
            "graph_latency_ms": health.latency_ms
        }
        
        await self.kafka_producer.send(
            topic="graphskill_alerts",
            key="fallback",
            value=json.dumps(event)
        )
    
    async def _log_fallback_recovery(self) -> None:
        """
        记录降级恢复事件。
        """
        duration = (datetime.utcnow() - self.fallback_start_time).total_seconds()
        
        event = {
            "event_type": "FALLBACK_RECOVERED",
            "timestamp": datetime.utcnow().isoformat(),
            "fallback_duration_seconds": duration
        }
        
        await self.kafka_producer.send(
            topic="graphskill_alerts",
            key="fallback",
            value=json.dumps(event)
        )
```

### 3.5 降级响应标记规范

降级响应 MUST 在响应 Header 和 Body 中明确标记：

```python
# 响应 Header 规范
response_headers = {
    "x-routing-mode": "normal|fallback|cached",
    "x-routing-latency-ms": "285",
    "x-graph-health": "healthy|degraded|unavailable",
    "x-fallback-reason": "timeout|error|maintenance"  # 仅降级时
}

# 响应 Body 规范
{
  "skills": [...],
  "routing_mode": "fallback",
  "token_count": 2850,
  "warnings": [
    "Graph database unavailable, conflict resolution skipped"
  ],
  "fallback_info": {
    "reason": "graph_timeout",
    "fallback_duration_seconds": 120,
    "estimated_recovery_time": "2026-04-12T10:05:00Z"
  }
}
```

---

## 4. 高并发隔离与连接池管理

### 4.1 连接池配置规范

系统 MUST 实现严格的连接池管理：

```yaml
# config/connection_pool.yaml
connection_pool:
  # 图数据库连接池
  graph_db:
    max_connections: 50
    min_connections: 10
    connection_timeout_ms: 100
    idle_timeout_seconds: 300
    max_lifetime_seconds: 1800
    validation_query: "RETURN 1"
    
  # 向量数据库连接池
  vector_db:
    max_connections: 30
    min_connections: 5
    connection_timeout_ms: 50
    idle_timeout_seconds: 300
    
  # Redis 连接池
  redis:
    max_connections: 100
    min_connections: 20
    connection_timeout_ms: 50
    idle_timeout_seconds: 300
    
  # Kafka 连接池
  kafka:
    max_producers: 10
    max_consumers: 20
    connection_timeout_ms: 100
```

### 4.2 连接池管理器实现

```python
class ConnectionPoolManager:
    """
    连接池管理器，管理所有数据库连接。
    """
    
    def __init__(self, config: ConnectionPoolConfig):
        self.config = config
        self.pools = {}
    
    async def initialize(self) -> None:
        """
        初始化所有连接池。
        """
        # 图数据库连接池
        self.pools["graph"] = await self._create_graph_pool()
        
        # 向量数据库连接池
        self.pools["vector"] = await self._create_vector_pool()
        
        # Redis 连接池
        self.pools["redis"] = await self._create_redis_pool()
    
    async def _create_graph_pool(self) -> ConnectionPool:
        """
        创建图数据库连接池。
        """
        return ConnectionPool(
            creator=self._create_graph_connection,
            max_size=self.config.graph_db.max_connections,
            min_size=self.config.graph_db.min_connections,
            timeout=self.config.graph_db.connection_timeout_ms,
            idle_timeout=self.config.graph_db.idle_timeout_seconds,
            max_lifetime=self.config.graph_db.max_lifetime_seconds,
            validation_query=self.config.graph_db.validation_query
        )
    
    async def acquire(self, pool_name: str) -> Connection:
        """
        获取连接。
        """
        pool = self.pools.get(pool_name)
        if not pool:
            raise PoolNotFoundError(f"Pool '{pool_name}' not found")
        
        connection = await pool.acquire()
        
        # 记录借用时间
        connection.acquired_at = time.time()
        
        return connection
    
    async def release(self, pool_name: str, connection: Connection) -> None:
        """
        释放连接。
        """
        pool = self.pools.get(pool_name)
        
        # 检查借用时间是否超限
        borrow_time = (time.time() - connection.acquired_at) * 1000
        
        if borrow_time > self.config.graph_db.connection_timeout_ms:
            logger.warning(
                f"Connection borrowed for {borrow_time}ms, "
                f"exceeds threshold {self.config.graph_db.connection_timeout_ms}ms"
            )
        
        await pool.release(connection)
    
    async def health_check(self) -> Dict[str, PoolHealthStatus]:
        """
        检查所有连接池健康状态。
        """
        status = {}
        
        for pool_name, pool in self.pools.items():
            status[pool_name] = PoolHealthStatus(
                pool_name=pool_name,
                active_connections=pool.active_count,
                idle_connections=pool.idle_count,
                max_connections=pool.max_size,
                utilization=pool.active_count / pool.max_size,
                is_healthy=pool.active_count < pool.max_size * 0.8
            )
        
        return status


class ConnectionPool:
    """
    连接池实现。
    """
    
    def __init__(
        self,
        creator: Callable,
        max_size: int,
        min_size: int,
        timeout: int,
        idle_timeout: int,
        max_lifetime: int,
        validation_query: str
    ):
        self.creator = creator
        self.max_size = max_size
        self.min_size = min_size
        self.timeout = timeout
        self.idle_timeout = idle_timeout
        self.max_lifetime = max_lifetime
        self.validation_query = validation_query
        
        self.active_connections = []
        self.idle_connections = []
        self.semaphore = asyncio.Semaphore(max_size)
    
    async def acquire(self) -> Connection:
        """
        获取连接。
        """
        # 等待信号量
        await asyncio.wait_for(
            self.semaphore.acquire(),
            timeout=self.timeout / 1000
        )
        
        # 尝试从空闲池获取
        if self.idle_connections:
            connection = self.idle_connections.pop()
            
            # 验证连接有效性
            if await self._validate_connection(connection):
                self.active_connections.append(connection)
                return connection
        
        # 创建新连接
        connection = await self.creator()
        connection.created_at = time.time()
        self.active_connections.append(connection)
        
        return connection
    
    async def release(self, connection: Connection) -> None:
        """
        释放连接。
        """
        self.active_connections.remove(connection)
        
        # 检查连接生命周期
        lifetime = time.time() - connection.created_at
        
        if lifetime > self.max_lifetime:
            # 超过最大生命周期，关闭连接
            await connection.close()
        else:
            # 放入空闲池
            self.idle_connections.append(connection)
        
        self.semaphore.release()
    
    async def _validate_connection(self, connection: Connection) -> bool:
        """
        验证连接有效性。
        """
        try:
            await connection.execute(self.validation_query)
            return True
        except Exception:
            await connection.close()
            return False
    
    @property
    def active_count(self) -> int:
        return len(self.active_connections)
    
    @property
    def idle_count(self) -> int:
        return len(self.idle_connections)
```

### 4.3 资源隔离规范

系统 MUST 实现严格的资源隔离：

| 隔离维度 | 规范 | 实现方式 |
|----------|------|----------|
| **请求隔离** | 单请求图遍历时间 < 100ms | 超时快速失败 |
| **连接隔离** | 单连接借用时间 < 100ms | 连接池超时检测 |
| **线程隔离** | 不同优先级请求使用不同线程池 | 线程池分级 |
| **数据隔离** | 不同租户数据物理隔离 | 多租户架构 |

```python
class ResourceIsolationManager:
    """
    资源隔离管理器。
    """
    
    def __init__(self, config: IsolationConfig):
        self.config = config
        
        # 分级线程池
        self.thread_pools = {
            "high_priority": ThreadPoolExecutor(max_workers=20),
            "normal_priority": ThreadPoolExecutor(max_workers=50),
            "low_priority": ThreadPoolExecutor(max_workers=10)
        }
    
    async def execute_with_isolation(
        self,
        task: Callable,
        priority: str = "normal",
        timeout_ms: int = 100
    ) -> Any:
        """
        在隔离环境中执行任务。
        """
        pool = self.thread_pools.get(priority)
        
        try:
            result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(pool, task),
                timeout=timeout_ms / 1000
            )
            return result
            
        except asyncio.TimeoutError:
            raise ResourceTimeoutError(
                f"Task exceeded timeout {timeout_ms}ms"
            )
```

---

## 5. 请求限流与熔断策略

### 5.1 限流策略配置

```yaml
# config/rate_limit.yaml
rate_limit:
  # 全局限流
  global:
    enabled: true
    max_requests_per_second: 5000
    burst_size: 1000
    
  # 单节点限流
  per_node:
    enabled: true
    max_requests_per_second: 1000
    burst_size: 200
    
  # 单 Session 限流
  per_session:
    enabled: true
    max_requests_per_minute: 100
    burst_size: 20
    
  # 限流算法
  algorithm: "token_bucket"  # token_bucket | sliding_window | leaky_bucket
  
  # 限流响应
  response:
    status_code: 429
    retry_after_seconds: 5
    message: "Rate limit exceeded, please retry later"
```

### 5.2 限流器实现

```python
class RateLimiter:
    """
    请求限流器，使用 Token Bucket 算法。
    """
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.tokens = config.burst_size
        self.max_tokens = config.burst_size
        self.refill_rate = config.max_requests_per_second
        self.last_refill = time.time()
    
    async def acquire(self, tokens: int = 1) -> bool:
        """
        尝试获取令牌。
        
        Returns:
            bool: 是否成功获取
        """
        # 补充令牌
        self._refill_tokens()
        
        # 检查令牌数量
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        
        return False
    
    def _refill_tokens(self) -> None:
        """
        补充令牌。
        """
        now = time.time()
        elapsed = now - self.last_refill
        
        # 计算应补充的令牌数
        refill_amount = elapsed * self.refill_rate
        
        # 补充令牌（不超过最大值）
        self.tokens = min(self.max_tokens, self.tokens + refill_amount)
        
        self.last_refill = now
    
    async def wait_for_token(self, timeout_seconds: int = 5) -> bool:
        """
        等待获取令牌。
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            if await self.acquire():
                return True
            
            await asyncio.sleep(0.1)
        
        return False


class RateLimitMiddleware:
    """
    限流中间件。
    """
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.global_limiter = RateLimiter(config.global)
        self.node_limiters = {}
        self.session_limiters = {}
    
    async def check_rate_limit(
        self,
        request: Request,
        node_id: str,
        session_id: str
    ) -> RateLimitResult:
        """
        检查请求是否超过限流阈值。
        """
        # 全局限流检查
        if not await self.global_limiter.acquire():
            return RateLimitResult(
                allowed=False,
                reason="global_rate_limit_exceeded",
                retry_after=self.config.response.retry_after_seconds
            )
        
        # 单节点限流检查
        node_limiter = self._get_node_limiter(node_id)
        if not await node_limiter.acquire():
            return RateLimitResult(
                allowed=False,
                reason="node_rate_limit_exceeded",
                retry_after=self.config.response.retry_after_seconds
            )
        
        # 单 Session 限流检查
        session_limiter = self._get_session_limiter(session_id)
        if not await session_limiter.acquire():
            return RateLimitResult(
                allowed=False,
                reason="session_rate_limit_exceeded",
                retry_after=self.config.response.retry_after_seconds
            )
        
        return RateLimitResult(allowed=True)
    
    def _get_node_limiter(self, node_id: str) -> RateLimiter:
        """
        获取节点限流器。
        """
        if node_id not in self.node_limiters:
            self.node_limiters[node_id] = RateLimiter(self.config.per_node)
        
        return self.node_limiters[node_id]
    
    def _get_session_limiter(self, session_id: str) -> RateLimiter:
        """
        获取 Session 限流器。
        """
        if session_id not in self.session_limiters:
            self.session_limiters[session_id] = RateLimiter(self.config.per_session)
        
        return self.session_limiters[session_id]
```

### 5.3 熔断策略配置

```yaml
# config/circuit_breaker.yaml
circuit_breaker:
  # 状态定义
  states:
    closed:      # 正常状态
      failure_threshold: 5
      timeout_seconds: 10
    open:        # 熔断状态
      recovery_timeout_seconds: 30
      half_open_requests: 3
    half_open:   # 半开状态
      success_threshold: 3
      failure_threshold: 1
  
  # 熔断目标
  targets:
    graph_db:
      enabled: true
      failure_threshold: 5
      recovery_timeout_seconds: 30
    vector_db:
      enabled: true
      failure_threshold: 3
      recovery_timeout_seconds: 20
    redis:
      enabled: true
      failure_threshold: 5
      recovery_timeout_seconds: 15
```

### 5.4 熔断器实现

```python
class CircuitBreaker:
    """
    熔断器实现，保护下游服务。
    """
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = "closed"
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = datetime.utcnow()
    
    async def execute(self, operation: Callable) -> Any:
        """
        在熔断器保护下执行操作。
        """
        # 检查当前状态
        if self.state == "open":
            # 检查是否可以进入半开状态
            if self._should_attempt_recovery():
                self.state = "half_open"
                self.last_state_change = datetime.utcnow()
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is open, retry after {self._get_recovery_time()}s"
                )
        
        try:
            result = await operation()
            
            # 成功处理
            await self._on_success()
            
            return result
            
        except Exception as e:
            # 失败处理
            await self._on_failure()
            
            raise e
    
    async def _on_success(self) -> None:
        """
        成功回调。
        """
        self.failure_count = 0
        
        if self.state == "half_open":
            self.success_count += 1
            
            if self.success_count >= self.config.states.half_open.success_threshold:
                self.state = "closed"
                self.success_count = 0
                self.last_state_change = datetime.utcnow()
    
    async def _on_failure(self) -> None:
        """
        失败回调。
        """
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.state == "half_open":
            self.state = "open"
            self.success_count = 0
            self.last_state_change = datetime.utcnow()
        
        elif self.state == "closed":
            if self.failure_count >= self.config.states.closed.failure_threshold:
                self.state = "open"
                self.last_state_change = datetime.utcnow()
    
    def _should_attempt_recovery(self) -> bool:
        """
        检查是否应该尝试恢复。
        """
        if not self.last_failure_time:
            return False
        
        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.config.states.open.recovery_timeout_seconds
    
    def _get_recovery_time(self) -> int:
        """
        获取预计恢复时间。
        """
        if not self.last_failure_time:
            return self.config.states.open.recovery_timeout_seconds
        
        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        remaining = self.config.states.open.recovery_timeout_seconds - elapsed
        
        return max(0, int(remaining))
    
    def get_status(self) -> CircuitBreakerStatus:
        """
        获取熔断器状态。
        """
        return CircuitBreakerStatus(
            state=self.state,
            failure_count=self.failure_count,
            success_count=self.success_count,
            last_failure_time=self.last_failure_time,
            last_state_change=self.last_state_change,
            recovery_time=self._get_recovery_time()
        )


class CircuitBreakerManager:
    """
    熔断器管理器，管理所有下游服务的熔断器。
    """
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.breakers = {}
    
    def get_breaker(self, target: str) -> CircuitBreaker:
        """
        获取指定目标的熔断器。
        """
        if target not in self.breakers:
            target_config = self.config.targets.get(target)
            if target_config and target_config.enabled:
                self.breakers[target] = CircuitBreaker(target_config)
        
        return self.breakers.get(target)
    
    async def execute_with_breaker(
        self,
        target: str,
        operation: Callable
    ) -> Any:
        """
        在熔断器保护下执行操作。
        """
        breaker = self.get_breaker(target)
        
        if breaker:
            return await breaker.execute(operation)
        else:
            return await operation()
```

---

## 6. 安全边界隔离规范

### 6.1 安全边界定义

系统 MUST 定义严格的安全边界：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Security Boundary Architecture                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Trusted Zone (GraphSkill Core)                   │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ Routing     │  │ Graph-Vector│  │ Permission  │  │ Telemetry   │ │   │
│  │  │ Gateway     │  │ Store       │  │ Interceptor │  │ Tracer      │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  │                                                                     │   │
│  │  [安全边界] ─────────────────────────────────────────────────────── │   │
│  │                                                                     │   │
│  │  [禁止执行任何技能代码]                                              │   │
│  │  [禁止直接访问外部网络]                                              │   │
│  │  [禁止修改系统配置]                                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Untrusted Zone (Agent Sandbox)                   │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐  │   │
│  │  │ Skill       │  │ External    │  │ Agent Execution Environment │  │   │
│  │  │ Execution   │  │ Network     │  │ (Docker / gVisor)           │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────────┘  │   │
│  │                                                                     │   │
│  │  [技能代码在此执行]                                                  │   │
│  │  [网络请求在此发起]                                                  │   │
│  │  [文件系统在此访问]                                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 安全边界规则

| 规则 | Trusted Zone | Untrusted Zone |
|------|--------------|----------------|
| 执行技能代码 | **MUST NOT** | MAY |
| 访问外部网络 | **MUST NOT** | MAY（受限） |
| 修改系统配置 | **MUST NOT** | **MUST NOT** |
| 访问敏感数据 | **MUST NOT** | MAY（受限） |
| 调用系统命令 | **MUST NOT** | MAY（受限） |

### 6.3 安全边界检查器

```python
class SecurityBoundaryChecker:
    """
    安全边界检查器，确保 Trusted Zone 不执行危险操作。
    """
    
    FORBIDDEN_OPERATIONS = [
        "execute_skill_code",
        "access_external_network",
        "modify_system_config",
        "access_sensitive_data",
        "call_system_command"
    ]
    
    def check_operation(self, operation: str, zone: str) -> bool:
        """
        检查操作是否允许在指定 Zone 执行。
        """
        if zone == "trusted":
            if operation in self.FORBIDDEN_OPERATIONS:
                raise SecurityBoundaryViolationError(
                    f"Operation '{operation}' is forbidden in Trusted Zone"
                )
        
        return True
    
    def validate_skill_payload(self, skill_data: dict) -> bool:
        """
        验证技能载荷不包含危险内容。
        """
        # 检查代码块
        code_blocks = skill_data.get("code_blocks", [])
        
        for block in code_blocks:
            # 检查是否包含危险模式
            if self._contains_dangerous_pattern(block["content"]):
                logger.warning(
                    f"Skill '{skill_data['skill_id']}' contains dangerous code pattern"
                )
        
        return True
    
    def _contains_dangerous_pattern(self, code: str) -> bool:
        """
        检查代码是否包含危险模式。
        """
        dangerous_patterns = [
            r"eval\s*\(",
            r"exec\s*\(",
            r"__import__\s*\(",
            r"subprocess\.",
            r"os\.system",
            r"rm\s+-rf",
            r"chmod\s+777"
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, code):
                return True
        
        return False
```

---

## 7. 不可信载荷处理规范

### 7.1 载荷处理原则

所有被解析的 `SKILL.md`，其执行体（Python 脚本、Bash 指令等）对于系统而言是**不可信的（Untrusted Payload）**。

**核心原则：**
- GraphSkill 只负责调度其文本描述和元数据
- **绝对禁止**在 GraphSkill 自身的服务进程或容器内去试运行任何技能代码
- 代码的执行必须推移至最外层的 Agent 沙箱环境

### 7.2 载荷处理流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  SKILL.md   │────▶│  Parser     │────▶│  Metadata   │────▶│  Routing    │
│  (文件)     │     │  (解析)     │     │  (提取)     │     │  (调度)     │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  [原始文件]          [AST 结构]          [元数据]            [上下文注入]
                                            │
                                            │ 不包含执行代码
                                            │
                                            ▼
                                    ┌─────────────┐
                                    │  Agent      │
                                    │  Sandbox    │  ← 代码在此执行
                                    └─────────────┘
```

### 7.3 载荷隔离实现

```python
class UntrustedPayloadHandler:
    """
    不可信载荷处理器，确保代码不在 GraphSkill 进程内执行。
    """
    
    def extract_safe_metadata(self, skill_data: dict) -> SafeMetadata:
        """
        提取安全元数据，排除执行代码。
        """
        # 仅提取元数据
        safe_metadata = SafeMetadata(
            skill_id=skill_data["skill_id"],
            version=skill_data["version"],
            intent_description=skill_data["intent_description"],
            permissions=skill_data["permissions"],
            trigger_conditions=skill_data.get("trigger_conditions"),
            topology_hints=skill_data.get("topology_hints"),
            # 代码块仅保留元信息，不保留内容
            code_block_info=[
                {
                    "language": block["language"],
                    "line_count": block["line_count"],
                    "has_execution_risk": block.get("has_execution_risk", False)
                }
                for block in skill_data.get("code_blocks", [])
            ]
        )
        
        return safe_metadata
    
    def generate_execution_package(
        self,
        skill_data: dict,
        session_id: str
    ) -> ExecutionPackage:
        """
        生成执行包，供 Agent Sandbox 使用。
        
        注意：此包仅传递给 Agent，不在 GraphSkill 内执行。
        """
        return ExecutionPackage(
            skill_id=skill_data["skill_id"],
            session_id=session_id,
            code_blocks=skill_data.get("code_blocks", []),
            parameters={},  # 由 Agent 填充
            execution_context={
                "sandbox_type": "docker",
                "timeout_seconds": 60,
                "resource_limits": {
                    "cpu": "1",
                    "memory": "512Mi"
                }
            }
        )
    
    def validate_execution_request(
        self,
        request: ExecutionRequest
    ) -> bool:
        """
        验证执行请求来自 Agent Sandbox，而非 GraphSkill 内部。
        """
        # 检查请求来源
        if request.source == "graphskill_internal":
            raise SecurityViolationError(
                "Execution request from GraphSkill internal is forbidden"
            )
        
        # 检查请求是否包含有效的 Sandbox 标识
        if not request.sandbox_id:
            raise SecurityViolationError(
                "Execution request must include valid sandbox_id"
            )
        
        return True
```

### 7.4 Sandbox 配置规范

```yaml
# config/sandbox.yaml
sandbox:
  type: "docker"  # docker | gvisor | firecracker
  
  # Docker 配置
  docker:
    image: "graphskill/sandbox:latest"
    network: "none"  # 默认无网络
    security_opt:
      - "no-new-privileges"
    cap_drop:
      - "ALL"
    read_only: true
    tmpfs:
      - "/tmp:size=100M"
    
  # 资源限制
  resource_limits:
    cpu: "1"
    memory: "512Mi"
    timeout_seconds: 60
    
  # 网络策略
  network:
    default: "none"
    allowed_domains:
      - "api.github.com"
      - "api.openai.com"
    dns_servers:
      - "8.8.8.8"
```

---

## 8. 容灾恢复流程

### 8.1 容灾架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Disaster Recovery Architecture                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Region A (Active)                                │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ Routing     │  │ Neo4j       │  │ Milvus      │  │ Redis       │ │   │
│  │  │ Gateway     │  │ (Primary)   │  │ (Primary)   │  │ (Cluster)   │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              │ Async Replication                            │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Region B (Standby)                               │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ Routing     │  │ Neo4j       │  │ Milvus      │  │ Redis       │ │   │
│  │  │ Gateway     │  │ (Replica)   │  │ (Replica)   │  │ (Replica)   │ │   │
│  │  │ (Standby)   │  │             │  │             │  │             │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 容灾恢复指标

| 指标 | 目标值 | 描述 |
|------|--------|------|
| RTO (Recovery Time Objective) | < 5 分钟 | 从故障到恢复的时间 |
| RPO (Recovery Point Objective) | < 5 分钟 | 数据丢失的时间窗口 |
| 数据同步延迟 | < 1 分钟 | 主备数据同步延迟 |

### 8.3 容灾恢复流程

```python
class DisasterRecoveryManager:
    """
    容灾恢复管理器。
    """
    
    def __init__(self, config: DRConfig):
        self.config = config
        self.active_region = config.primary_region
        self.standby_region = config.standby_region
        self.failover_state = "normal"
    
    async def check_region_health(self, region: str) -> RegionHealthStatus:
        """
        检查区域健康状态。
        """
        checks = await asyncio.gather(
            self._check_graph_db(region),
            self._check_vector_db(region),
            self._check_redis(region),
            self._check_routing_gateway(region)
        )
        
        all_healthy = all(c.is_healthy for c in checks)
        
        return RegionHealthStatus(
            region=region,
            is_healthy=all_healthy,
            components=checks,
            last_check=datetime.utcnow()
        )
    
    async def execute_failover(self) -> FailoverResult:
        """
        执行故障转移。
        """
        # 1. 确认 Active Region 故障
        active_health = await self.check_region_health(self.active_region)
        
        if active_health.is_healthy:
            return FailoverResult(
                success=False,
                reason="Active region is healthy, no need for failover"
            )
        
        # 2. 检查 Standby Region 状态
        standby_health = await self.check_region_health(self.standby_region)
        
        if not standby_health.is_healthy:
            return FailoverResult(
                success=False,
                reason="Standby region is not ready for failover"
            )
        
        # 3. 检查数据同步状态
        sync_status = await self._check_data_sync()
        
        if sync_status.lag_seconds > self.config.max_sync_lag:
            logger.warning(
                f"Data sync lag {sync_status.lag_seconds}s exceeds threshold"
            )
        
        # 4. 执行故障转移
        self.failover_state = "failover_in_progress"
        
        # 4.1 提升 Standby 为 Active
        await self._promote_standby()
        
        # 4.2 更新 DNS/负载均衡器
        await self._update_load_balancer()
        
        # 4.3 通知所有服务节点
        await self._notify_service_nodes()
        
        # 5. 更新状态
        self.active_region = self.standby_region
        self.standby_region = self.active_region
        self.failover_state = "failover_completed"
        
        return FailoverResult(
            success=True,
            new_active_region=self.active_region,
            rto_seconds=self._calculate_rto(),
            rpo_seconds=sync_status.lag_seconds
        )
    
    async def _promote_standby(self) -> None:
        """
        提升 Standby 为 Active。
        """
        # 提升图数据库
        await self.graph_db_client.promote_replica(self.standby_region)
        
        # 提升向量数据库
        await self.vector_db_client.promote_replica(self.standby_region)
        
        # 提升 Redis
        await self.redis_client.promote_replica(self.standby_region)
    
    async def _update_load_balancer(self) -> None:
        """
        更新负载均衡器配置。
        """
        # 更新 DNS 记录
        await self.dns_client.update_record(
            domain="api.graphskill.io",
            target=self.standby_region_endpoint
        )
        
        # 更新负载均衡器后端
        await self.lb_client.update_backends(
            pool="routing_gateway",
            backends=self._get_standby_backends()
        )
    
    async def _notify_service_nodes(self) -> None:
        """
        通知所有服务节点。
        """
        notification = {
            "event_type": "REGION_FAILOVER",
            "new_active_region": self.active_region,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.kafka_producer.send(
            topic="graphskill_control",
            key="failover",
            value=json.dumps(notification)
        )
```

### 8.4 容灾恢复配置

```yaml
# config/disaster_recovery.yaml
disaster_recovery:
  enabled: true
  
  regions:
    primary: "cn-east-1"
    standby: "cn-north-1"
  
  # 故障检测
  health_check:
    interval_seconds: 10
    timeout_seconds: 5
    failure_threshold: 3
  
  # 数据同步
  replication:
    mode: "async"
    sync_interval_seconds: 10
    max_lag_seconds: 60
  
  # 故障转移
  failover:
    auto_failover: true
    manual_confirmation: false
    rto_target_seconds: 300
    rpo_target_seconds: 300
  
  # 恢复流程
  recovery:
    auto_recovery: false  # 需人工确认
    data_validation: true
    consistency_check: true
```

---

## 9. 混沌工程与故障演练

### 9.1 混沌工程原则

系统 SHOULD 定期执行混沌工程演练，验证高可用能力：

| 原则 | 描述 |
|------|------|
| **建立稳态行为假设** | 定义系统正常运行的指标基线 |
| **模拟真实世界事件** | 注入真实的故障场景 |
| **在生产环境中运行** | 在真实环境中验证 |
| **自动化持续运行** | 定期自动执行演练 |
| **最小化爆炸半径** | 控制故障影响范围 |

### 9.2 故障注入场景

| 场景 | 描述 | 预期行为 | 验证指标 |
|------|------|----------|----------|
| **图数据库宕机** | Neo4j 进程终止 | 自动降级为纯向量检索 | 降级率 < 5% |
| **向量数据库超时** | Milvus 响应延迟 > 500ms | 触发熔断，降级响应 | 熔断触发时间 < 10s |
| **Redis 连接耗尽** | 连接池满 | 快速失败，返回 429 | 错误率 < 1% |
| **网络分区** | 跨区域网络中断 | 自动故障转移 | RTO < 5min |
| **高负载压力** | QPS 超过阈值 2 倍 | 限流保护 | 限流生效时间 < 1s |
| **节点故障** | 单服务节点宕机 | 负载均衡器自动摘除 | 恢复时间 < 30s |

### 9.3 混沌工程框架

```python
class ChaosEngineeringFramework:
    """
    混沌工程框架，执行故障演练。
    """
    
    def __init__(self, config: ChaosConfig):
        self.config = config
        self.experiments = {}
    
    def register_experiment(
        self,
        name: str,
        fault_injector: Callable,
        verification: Callable,
        rollback: Callable
    ) -> None:
        """
        注册混沌实验。
        """
        self.experiments[name] = ChaosExperiment(
            name=name,
            fault_injector=fault_injector,
            verification=verification,
            rollback=rollback
        )
    
    async def run_experiment(
        self,
        name: str,
        duration_seconds: int = 60
    ) -> ExperimentResult:
        """
        执行混沌实验。
        """
        experiment = self.experiments.get(name)
        
        if not experiment:
            raise ExperimentNotFoundError(f"Experiment '{name}' not found")
        
        # 1. 记录稳态基线
        baseline = await self._capture_baseline()
        
        # 2. 注入故障
        await experiment.fault_injector()
        
        # 3. 观察系统行为
        observations = await self._observe(duration_seconds)
        
        # 4. 验证预期行为
        verification_result = await experiment.verification(observations)
        
        # 5. 回滚故障
        await experiment.rollback()
        
        # 6. 验证恢复
        recovery_result = await self._verify_recovery()
        
        return ExperimentResult(
            experiment_name=name,
            baseline=baseline,
            observations=observations,
            verification_result=verification_result,
            recovery_result=recovery_result,
            passed=verification_result.passed and recovery_result.passed
        )
    
    async def _capture_baseline(self) -> BaselineMetrics:
        """
        记录稳态基线。
        """
        return BaselineMetrics(
            routing_latency_p99=await self._get_metric("routing_latency_p99"),
            error_rate=await self._get_metric("error_rate"),
            qps=await self._get_metric("qps"),
            cache_hit_rate=await self._get_metric("cache_hit_rate")
        )
    
    async def _observe(self, duration_seconds: int) -> List[Observation]:
        """
        观察系统行为。
        """
        observations = []
        
        for _ in range(duration_seconds):
            observation = Observation(
                timestamp=datetime.utcnow(),
                routing_latency=await self._get_metric("routing_latency"),
                error_rate=await self._get_metric("error_rate"),
                fallback_rate=await self._get_metric("fallback_rate"),
                circuit_breaker_state=await self._get_circuit_breaker_state()
            )
            observations.append(observation)
            
            await asyncio.sleep(1)
        
        return observations
    
    async def _verify_recovery(self) -> RecoveryResult:
        """
        验证系统恢复。
        """
        # 等待恢复
        await asyncio.sleep(30)
        
        # 检查指标是否恢复到基线
        current_metrics = await self._capture_baseline()
        
        return RecoveryResult(
            passed=current_metrics.error_rate < 0.01,
            recovery_time_seconds=30,
            current_metrics=current_metrics
        )


# 预定义故障注入器
class FaultInjectors:
    """
    预定义故障注入器集合。
    """
    
    @staticmethod
    async def inject_graph_db_failure():
        """
        注入图数据库故障。
        """
        # 终止 Neo4j 进程
        await execute_command("docker stop neo4j-primary")
    
    @staticmethod
    async def inject_vector_db_latency():
        """
        注入向量数据库延迟。
        """
        # 添加网络延迟
        await execute_command(
            "tc qdisc add dev eth0 root netem delay 500ms"
        )
    
    @staticmethod
    async def inject_connection_pool_exhaustion():
        """
        注入连接池耗尽。
        """
        # 占用所有连接
        for _ in range(100):
            await redis_client.acquire()
    
    @staticmethod
    async def rollback_graph_db_failure():
        """
        回滚图数据库故障。
        """
        await execute_command("docker start neo4j-primary")
    
    @staticmethod
    async def rollback_vector_db_latency():
        """
        回滚向量数据库延迟。
        """
        await execute_command("tc qdisc del dev eth0 root")
```

### 9.4 混沌工程配置

```yaml
# config/chaos.yaml
chaos_engineering:
  enabled: true
  
  # 演练计划
  schedule:
    frequency: "weekly"
    day: "sunday"
    time: "02:00"
    
  # 实验配置
  experiments:
    graph_db_failure:
      enabled: true
      duration_seconds: 60
      blast_radius: "single_node"
      
    vector_db_latency:
      enabled: true
      duration_seconds: 120
      latency_ms: 500
      
    high_load:
      enabled: true
      duration_seconds: 300
      target_qps: 2000
      
  # 安全边界
  safety:
    max_concurrent_experiments: 1
    require_approval: true
    auto_rollback: true
    rollback_timeout_seconds: 30
    
  # 告警
  alerts:
    notify_on_start: true
    notify_on_completion: true
    notify_on_failure: true
```

---

## 10. 版本历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|----------|------|
| 1.0.0 | 2026-04-12 | 初始版本发布 | GraphSkill Architecture Team |
| 1.1.0 | 2026-04-17 | VR-First 架构适配：降级机制从 ZS→VR baseline；缓存策略适配 VR-first pipeline | GraphSkill Architecture Team |

---

**文档结束**

*本文档定义了 GraphSkill 系统的性能安全与高可用规范。相关部署与运维规范详见 [RFC-09: 部署与运维规范](RFC-09-deployment-operations.md)，测试与质量保障规范详见 [RFC-10: 测试与质量保障规范](RFC-10-testing-quality-assurance.md)。*