# RFC-05: 遥测监控与自我进化反馈循环

**文档编号:** RFC-05  
**版本:** 1.0.0  
**状态:** 正式发布  
**最后更新:** 2026-04-12  
**作者:** GraphSkill Architecture Team  
**分类:** 架构规范 - 运行时反馈  
**依赖:** RFC-00, RFC-01, RFC-03

---

## 目录

1. [概述](#1-概述)
2. [遥测架构总览](#2-遥测架构总览)
3. [埋点规范与追踪器设计](#3-埋点规范与追踪器设计)
4. [遥测数据格式与 Kafka Topic 设计](#4-遥测数据格式与-kafka-topic-设计)
5. [节点可靠性衰减算法](#5-节点可靠性衰减算法)
6. [隐性边发现与边权强化机制](#6-隐性边发现与边权强化机制)
7. [冲突边自发现算法](#7-冲突边自发现算法)
8. [后台作业调度策略](#8-后台作业调度策略)
9. [监控告警体系](#9-监控告警体系)
10. [版本历史](#10-版本历史)

---

## 1. 概述

### 1.1 文档目的

本文档定义 GraphSkill 系统的遥测监控与自我进化反馈循环（Telemetry & Self-Evolution Feedback Loop），涵盖埋点规范、追踪器设计、遥测数据格式、Kafka Topic 设计、节点可靠性衰减算法、隐性边发现与边权强化机制、冲突边自发现算法、后台作业调度策略以及监控告警体系。

### 1.2 适用范围

本文档适用于：
- 后端开发工程师：实现遥测数据收集与处理
- 数据工程师：设计反馈循环算法
- DevOps 工程师：配置监控告警
- 系统架构师：理解自我进化机制

### 1.3 设计原则

| 原则 | 描述 |
|------|------|
| **非侵入式埋点** | 埋点逻辑 MUST 不影响主流程性能 |
| **异步处理** | 遥测数据处理 MUST 采用异步批处理 |
| **数据驱动进化** | 图谱权重调整 MUST 基于真实执行数据 |
| **可回滚性** | 自动进化操作 MUST 支持人工回滚 |

### 1.3 自我进化核心理念

GraphSkill 系统的图谱不能是静态的，MUST 具备自愈与自我进化能力：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Self-Evolution Feedback Loop                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐                                                            │
│  │  Agent      │  执行技能，产生遥测数据                                      │
│  │  Execution  │                                                            │
│  └──────┬──────┘                                                            │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                    │
│  │  Tracer     │────▶│  Kafka      │────▶│  Consumer   │                    │
│  │  (埋点)     │     │  Topic      │     │  Worker     │                    │
│  └─────────────┘     └─────────────┘     └──────┬──────┘                    │
│                                                 │                           │
│                                                 ▼                           │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                    │
│  │  Graph      │◀────│  Evolution  │◀────│  Analytics  │                    │
│  │  Update     │     │  Engine     │     │  Engine     │                    │
│  │             │     │             │     │             │                    │
│  └─────────────┘     └─────────────┘     └─────────────┘                    │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────┐                                                            │
│  │  Routing    │  使用更新后的权重进行路由                                    │
│  │  Gateway    │                                                            │
│  └─────────────┘                                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 遥测架构总览

### 2.1 架构组件图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Telemetry Architecture                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Data Collection Layer                            │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ Execution   │  │ Routing     │  │ Permission  │  │ Performance │ │   │
│  │  │ Tracer      │  │ Tracer      │  │ Tracer      │  │ Tracer      │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Data Transport Layer                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ Kafka       │  │ Buffer      │  │ Batch       │  │ Schema      │ │   │
│  │  │ Producer    │  │ Manager     │  │ Aggregator  │  │ Validator   │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Data Processing Layer                            │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ Kafka       │  │ Stream      │  │ Analytics   │  │ Evolution   │ │   │
│  │  │ Consumer    │  │ Processor   │  │ Engine      │  │ Engine      │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Action Layer                                     │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ Weight      │  │ Edge        │  │ Node        │  │ Alert       │ │   │
│  │  │ Adjuster    │  │ Creator     │  │ Updater     │  │ Manager     │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Storage Layer                                    │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ Graph DB    │  │ TimeSeries  │  │ Audit Log   │  │ Metrics DB  │ │   │
│  │  │ (Neo4j)     │  │ (Prometheus)│  │ (Elastic)   │  │ (PostgreSQL)│ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 模块职责定义

| 模块 | 职责 | 输入 | 输出 |
|------|------|------|------|
| **Execution Tracer** | 记录技能执行状态 | 执行事件 | 遥测记录 |
| **Routing Tracer** | 记录路由决策过程 | 路由请求/响应 | 路由日志 |
| **Permission Tracer** | 记录权限校验结果 | 权限校验事件 | 权限日志 |
| **Performance Tracer** | 记录性能指标 | 性能数据 | 性能日志 |
| **Kafka Producer** | 发送遥测数据到 Kafka | 遥测记录 | Kafka Message |
| **Stream Processor** | 实时处理遥测流 | Kafka Stream | 处理结果 |
| **Analytics Engine** | 分析遥测数据，生成洞察 | 历史遥测数据 | 分析报告 |
| **Evolution Engine** | 执行图谱进化操作 | 分析报告 | 进化指令 |
| **Weight Adjuster** | 调整节点/边权重 | 进化指令 | 权重更新 |
| **Edge Creator** | 创建新边关系 | 进化指令 | 新边数据 |

---

## 3. 埋点规范与追踪器设计

### 3.1 埋点事件类型定义

系统 MUST 在以下关键节点进行埋点：

| 事件类型 | 事件码 | 触发时机 | 关键字段 |
|----------|--------|----------|----------|
| `SKILL_CALLED` | `E001` | Agent 调用技能时 | skill_id, session_id, parameters |
| `SKILL_SUCCESS` | `E002` | 技能执行成功时 | skill_id, session_id, duration_ms |
| `SKILL_FAILED` | `E003` | 技能执行失败时 | skill_id, session_id, error_type |
| `ROUTING_STARTED` | `E004` | 路由请求开始时 | query_hash, session_id |
| `ROUTING_COMPLETED` | `E005` | 路由请求完成时 | query_hash, skill_count, latency_ms |
| `ROUTING_FALLBACK` | `E006` | 路由降级时 | query_hash, fallback_reason |
| `PERMISSION_CHECK` | `E007` | 权限校验时 | skill_id, action, result |
| `PERMISSION_DENIED` | `E008` | 权限拒绝时 | skill_id, action, reason |
| `CONTEXT_OVERFLOW` | `E009` | Token 超限时 | session_id, token_count |
| `CONFLICT_DETECTED` | `E010` | 检测到冲突时 | skill_ids, conflict_type |

### 3.2 追踪器接口定义

```python
class TracerInterface:
    """
    追踪器接口，定义统一的埋点方法。
    """
    
    def trace_event(
        self,
        event_type: str,
        event_data: dict,
        context: TraceContext
    ) -> None:
        """
        记录埋点事件。
        
        Args:
            event_type: 事件类型
            event_data: 事件数据
            context: 追踪上下文
        """
        pass
    
    def flush(self) -> None:
        """
        刷新缓冲区，发送累积的事件。
        """
        pass


class TraceContext:
    """
    追踪上下文，包含请求级别的元数据。
    """
    
    trace_id: str           # 全局追踪 ID
    session_id: str         # Session ID
    agent_id: str           # Agent ID
    timestamp: str          # 时间戳
    span_id: str            # 当前 Span ID
    parent_span_id: str     # 父 Span ID（可选）
```

### 3.3 Execution Tracer 实现

```python
class ExecutionTracer(TracerInterface):
    """
    技能执行追踪器，记录技能调用状态。
    """
    
    def __init__(self, kafka_producer, config: TracerConfig):
        self.kafka_producer = kafka_producer
        self.config = config
        self.buffer = []
        self.buffer_size = config.buffer_size
        self.flush_interval = config.flush_interval
    
    def trace_skill_call(
        self,
        skill_id: str,
        session_id: str,
        parameters: dict,
        context: TraceContext
    ) -> None:
        """
        记录技能调用开始。
        """
        event = TelemetryEvent(
            event_type="SKILL_CALLED",
            event_code="E001",
            trace_id=context.trace_id,
            session_id=session_id,
            skill_id=skill_id,
            timestamp=datetime.utcnow().isoformat(),
            data={
                "parameters": parameters,
                "span_id": context.span_id
            }
        )
        
        self._add_to_buffer(event)
    
    def trace_skill_success(
        self,
        skill_id: str,
        session_id: str,
        duration_ms: float,
        result: dict,
        context: TraceContext
    ) -> None:
        """
        记录技能执行成功。
        """
        event = TelemetryEvent(
            event_type="SKILL_SUCCESS",
            event_code="E002",
            trace_id=context.trace_id,
            session_id=session_id,
            skill_id=skill_id,
            timestamp=datetime.utcnow().isoformat(),
            data={
                "duration_ms": duration_ms,
                "result_summary": self._summarize_result(result),
                "span_id": context.span_id
            }
        )
        
        self._add_to_buffer(event)
    
    def trace_skill_failure(
        self,
        skill_id: str,
        session_id: str,
        error_type: str,
        error_message: str,
        context: TraceContext
    ) -> None:
        """
        记录技能执行失败。
        """
        event = TelemetryEvent(
            event_type="SKILL_FAILED",
            event_code="E003",
            trace_id=context.trace_id,
            session_id=session_id,
            skill_id=skill_id,
            timestamp=datetime.utcnow().isoformat(),
            data={
                "error_type": error_type,
                "error_message": error_message,
                "span_id": context.span_id
            }
        )
        
        self._add_to_buffer(event)
    
    def _add_to_buffer(self, event: TelemetryEvent) -> None:
        """
        添加事件到缓冲区。
        """
        self.buffer.append(event)
        
        # 达到缓冲区大小或时间间隔时刷新
        if len(self.buffer) >= self.buffer_size:
            self.flush()
    
    def flush(self) -> None:
        """
        刷新缓冲区，发送到 Kafka。
        """
        if not self.buffer:
            return
        
        # 批量发送
        for event in self.buffer:
            self.kafka_producer.send(
                topic="graphskill_telemetry",
                key=event.trace_id,
                value=event.to_json()
            )
        
        self.buffer.clear()
    
    def _summarize_result(self, result: dict) -> str:
        """
        汇总执行结果，避免记录敏感数据。
        """
        # 仅记录结果类型，不记录具体内容
        if result.get("success"):
            return "success"
        elif result.get("error"):
            return f"error: {result['error'].get('type', 'unknown')}"
        else:
            return "unknown"
```

### 3.4 Routing Tracer 实现

```python
class RoutingTracer(TracerInterface):
    """
    路由追踪器，记录路由决策过程。
    """
    
    def trace_routing_start(
        self,
        query: str,
        query_hash: str,
        session_id: str,
        max_tokens: int,
        context: TraceContext
    ) -> None:
        """
        记录路由请求开始。
        """
        event = TelemetryEvent(
            event_type="ROUTING_STARTED",
            event_code="E004",
            trace_id=context.trace_id,
            session_id=session_id,
            timestamp=datetime.utcnow().isoformat(),
            data={
                "query_hash": query_hash,
                "query_length": len(query),
                "max_tokens": max_tokens,
                "span_id": context.span_id
            }
        )
        
        self._add_to_buffer(event)
    
    def trace_routing_complete(
        self,
        query_hash: str,
        session_id: str,
        skill_ids: List[str],
        latency_ms: float,
        routing_mode: str,
        context: TraceContext
    ) -> None:
        """
        记录路由请求完成。
        """
        event = TelemetryEvent(
            event_type="ROUTING_COMPLETED",
            event_code="E005",
            trace_id=context.trace_id,
            session_id=session_id,
            timestamp=datetime.utcnow().isoformat(),
            data={
                "query_hash": query_hash,
                "skill_count": len(skill_ids),
                "skill_ids": skill_ids,
                "latency_ms": latency_ms,
                "routing_mode": routing_mode,
                "span_id": context.span_id
            }
        )
        
        self._add_to_buffer(event)
    
    def trace_routing_fallback(
        self,
        query_hash: str,
        session_id: str,
        fallback_reason: str,
        context: TraceContext
    ) -> None:
        """
        记录路由降级。
        """
        event = TelemetryEvent(
            event_type="ROUTING_FALLBACK",
            event_code="E006",
            trace_id=context.trace_id,
            session_id=session_id,
            timestamp=datetime.utcnow().isoformat(),
            data={
                "query_hash": query_hash,
                "fallback_reason": fallback_reason,
                "span_id": context.span_id
            }
        )
        
        self._add_to_buffer(event)
```

### 3.5 埋点配置规范

```yaml
# config/tracer.yaml
tracer:
  # 缓冲区配置
  buffer_size: 100
  flush_interval_ms: 1000
  
  # Kafka 配置
  kafka:
    topic: "graphskill_telemetry"
    partition_key: "trace_id"
    compression: "snappy"
    batch_size: 1000
    
  # 采样率配置
  sampling:
    default_rate: 1.0      # 默认全量采样
    success_rate: 0.1      # 成功事件采样率（降低存储压力）
    failure_rate: 1.0      # 失败事件全量采样
    fallback_rate: 1.0     # 降级事件全量采样
    
  # 敏感数据过滤
  sensitive_fields:
    - "password"
    - "token"
    - "secret"
    - "api_key"
    - "credential"
```

---

## 4. 遥测数据格式与 Kafka Topic 设计

### 4.1 遥测事件数据结构

```python
class TelemetryEvent:
    """
    遥测事件数据结构。
    """
    
    # 必填字段
    event_type: str        # 事件类型
    event_code: str        # 事件码
    trace_id: str          # 全局追踪 ID
    timestamp: str         # 时间戳 (ISO 8601)
    
    # 可选字段
    session_id: str        # Session ID
    skill_id: str          # 技能 ID
    agent_id: str          # Agent ID
    
    # 事件数据
    data: dict             # 事件详细数据
    
    # 元数据
    metadata: dict         # 系统元数据
    
    def to_json(self) -> str:
        """
        序列化为 JSON。
        """
        return json.dumps({
            "event_type": self.event_type,
            "event_code": self.event_code,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "skill_id": self.skill_id,
            "agent_id": self.agent_id,
            "data": self.data,
            "metadata": self.metadata
        })
```

### 4.2 完整事件示例

```json
{
  "event_type": "SKILL_SUCCESS",
  "event_code": "E002",
  "trace_id": "trace_abc123def456",
  "timestamp": "2026-04-12T10:00:00.123Z",
  "session_id": "sess_abc123",
  "skill_id": "git:commit_changes",
  "agent_id": "agent_001",
  "data": {
    "duration_ms": 1523.5,
    "result_summary": "success",
    "span_id": "span_001",
    "parent_span_id": "span_root"
  },
  "metadata": {
    "version": "1.0.0",
    "environment": "production",
    "region": "cn-east-1",
    "hostname": "graphskill-node-01"
  }
}
```

### 4.3 Kafka Topic 设计

系统 MUST 使用以下 Kafka Topic 结构：

| Topic 名称 | 分区数 | 用途 | 消费者组 |
|------------|--------|------|----------|
| `graphskill_telemetry` | 12 | 主遥测数据流 | analytics-consumer |
| `graphskill_evolution` | 6 | 进化指令流 | evolution-consumer |
| `graphskill_compensation` | 3 | 补偿删除流 | compensation-consumer |
| `graphskill_alerts` | 3 | 告警事件流 | alert-consumer |

### 4.4 Topic Schema 定义

```yaml
# Kafka Topic Schema
graphskill_telemetry:
  partitions: 12
  replication_factor: 3
  retention_ms: 604800000  # 7 天
  compression: snappy
  
  key_schema:
    type: string
    description: trace_id
  
  value_schema:
    type: json
    schema: |
      {
        "type": "object",
        "required": ["event_type", "event_code", "trace_id", "timestamp"],
        "properties": {
          "event_type": {"type": "string"},
          "event_code": {"type": "string"},
          "trace_id": {"type": "string"},
          "timestamp": {"type": "string", "format": "date-time"},
          "session_id": {"type": "string"},
          "skill_id": {"type": "string"},
          "data": {"type": "object"}
        }
      }

graphskill_evolution:
  partitions: 6
  replication_factor: 3
  retention_ms: 2592000000  # 30 天
  
  key_schema:
    type: string
    description: evolution_id
  
  value_schema:
    type: json
    schema: |
      {
        "type": "object",
        "required": ["evolution_type", "target", "action"],
        "properties": {
          "evolution_id": {"type": "string"},
          "evolution_type": {"type": "string"},
          "target": {"type": "string"},
          "action": {"type": "object"},
          "confidence": {"type": "number"},
          "verified": {"type": "boolean"}
        }
      }
```

### 4.5 Kafka Consumer 实现

```python
class TelemetryConsumer:
    """
    遥测数据消费者，处理 Kafka 消息。
    """
    
    def __init__(self, kafka_client, analytics_engine):
        self.kafka_client = kafka_client
        self.analytics_engine = analytics_engine
    
    async def consume(self) -> None:
        """
        消费遥测数据流。
        """
        consumer = self.kafka_client.get_consumer(
            group_id="analytics-consumer",
            topics=["graphskill_telemetry"]
        )
        
        async for message in consumer:
            try:
                event = TelemetryEvent.from_json(message.value)
                
                # 根据事件类型分发处理
                await self._dispatch_event(event)
                
            except Exception as e:
                logger.error(f"Failed to process telemetry event: {e}")
    
    async def _dispatch_event(self, event: TelemetryEvent) -> None:
        """
        分发事件到对应处理器。
        """
        handlers = {
            "SKILL_SUCCESS": self._handle_skill_success,
            "SKILL_FAILED": self._handle_skill_failure,
            "ROUTING_COMPLETED": self._handle_routing_complete,
            "ROUTING_FALLBACK": self._handle_routing_fallback,
            "CONFLICT_DETECTED": self._handle_conflict_detected
        }
        
        handler = handlers.get(event.event_type)
        if handler:
            await handler(event)
    
    async def _handle_skill_success(self, event: TelemetryEvent) -> None:
        """
        处理技能成功事件。
        """
        # 更新成功率统计
        await self.analytics_engine.record_success(
            skill_id=event.skill_id,
            session_id=event.session_id,
            duration_ms=event.data.get("duration_ms")
        )
    
    async def _handle_skill_failure(self, event: TelemetryEvent) -> None:
        """
        处理技能失败事件。
        """
        # 更新失败率统计
        await self.analytics_engine.record_failure(
            skill_id=event.skill_id,
            session_id=event.session_id,
            error_type=event.data.get("error_type")
        )
```

---

## 5. 节点可靠性衰减算法

### 5.1 算法概述

节点可靠性（`execution_success_rate`）反映技能的历史执行成功率。系统 MUST 根据执行结果动态调整该值，实现可靠性衰减与恢复机制。

### 5.2 衰减公式

可靠性衰减采用指数加权移动平均（EWMA）算法：

$$R_{new} = \alpha \cdot R_{current} + (1 - \alpha) \cdot S_{latest}$$

其中：
- $R_{new}$：更新后的可靠性
- $R_{current}$：当前可靠性
- $S_{latest}$：最新执行结果（1 = 成功，0 = 失败）
- $\alpha$：衰减因子（默认 0.95）

### 5.3 衰减算法实现

```python
class ReliabilityDecayEngine:
    """
    节点可靠性衰减引擎。
    """
    
    def __init__(self, graph_store, config: DecayConfig):
        self.graph_store = graph_store
        self.config = config
        self.alpha = config.decay_factor  # 默认 0.95
        self.min_reliability = config.min_reliability  # 默认 0.1
        self.deprecation_threshold = config.deprecation_threshold  # 默认 0.3
    
    async def update_reliability(
        self,
        skill_id: str,
        success: bool
    ) -> float:
        """
        更新技能节点可靠性。
        
        Args:
            skill_id: 技能 ID
            success: 执行是否成功
            
        Returns:
            float: 更新后的可靠性值
        """
        # 获取当前可靠性
        current_reliability = await self._get_current_reliability(skill_id)
        
        # 计算新可靠性
        latest_result = 1.0 if success else 0.0
        new_reliability = (
            self.alpha * current_reliability +
            (1 - self.alpha) * latest_result
        )
        
        # 应用下限约束
        new_reliability = max(new_reliability, self.min_reliability)
        
        # 更新图数据库
        await self._update_node_reliability(skill_id, new_reliability)
        
        # 检查是否需要降级
        if new_reliability < self.deprecation_threshold:
            await self._check_deprecation(skill_id, new_reliability)
        
        return new_reliability
    
    async def _get_current_reliability(self, skill_id: str) -> float:
        """
        获取当前可靠性值。
        """
        query = """
        MATCH (s:SkillNode {uid: $skill_id})
        RETURN s.execution_success_rate as rate, s.execution_count as count
        """
        result = await self.graph_store.execute_query(query, {"skill_id": skill_id})
        
        if result:
            return result[0].get("rate", 1.0)
        
        return 1.0  # 新技能默认可靠性为 1.0
    
    async def _update_node_reliability(
        self,
        skill_id: str,
        new_reliability: float
    ) -> None:
        """
        更新节点可靠性属性。
        """
        query = """
        MATCH (s:SkillNode {uid: $skill_id})
        SET s.execution_success_rate = $rate,
            s.execution_count = s.execution_count + 1,
            s.last_execution_time = datetime()
        """
        await self.graph_store.execute_query(
            query,
            {"skill_id": skill_id, "rate": new_reliability}
        )
    
    async def _check_deprecation(
        self,
        skill_id: str,
        reliability: float
    ) -> None:
        """
        检查是否需要降级技能。
        """
        # 获取连续失败次数
        consecutive_failures = await self._get_consecutive_failures(skill_id)
        
        # 连续失败超过阈值时触发降级
        if consecutive_failures >= self.config.consecutive_failure_threshold:
            await self._deprecate_skill(skill_id, reliability)
    
    async def _get_consecutive_failures(self, skill_id: str) -> int:
        """
        获取连续失败次数。
        """
        # 从遥测数据库查询最近执行记录
        query = """
        SELECT consecutive_failures
        FROM skill_execution_stats
        WHERE skill_id = $skill_id
        """
        result = await self.metrics_db.execute_query(query, {"skill_id": skill_id})
        
        return result[0].get("consecutive_failures", 0) if result else 0
    
    async def _deprecate_skill(
        self,
        skill_id: str,
        reliability: float
    ) -> None:
        """
        降级技能（软删除）。
        """
        query = """
        MATCH (s:SkillNode {uid: $skill_id})
        SET s.is_deprecated = true,
            s.deprecation_reason = "low_reliability",
            s.deprecation_reliability = $rate,
            s.deprecated_at = datetime()
        """
        await self.graph_store.execute_query(
            query,
            {"skill_id": skill_id, "rate": reliability}
        )
        
        # 发送告警
        await self._send_deprecation_alert(skill_id, reliability)
    
    async def _send_deprecation_alert(
        self,
        skill_id: str,
        reliability: float
    ) -> None:
        """
        发送技能降级告警。
        """
        alert = {
            "alert_type": "SKILL_DEPRECATION",
            "skill_id": skill_id,
            "reliability": reliability,
            "timestamp": datetime.utcnow().isoformat(),
            "message": f"Skill '{skill_id}' deprecated due to low reliability ({reliability:.2f})"
        }
        
        await self.kafka_producer.send(
            topic="graphskill_alerts",
            key=skill_id,
            value=json.dumps(alert)
        )
```

### 5.4 衰减配置规范

```yaml
# config/decay.yaml
decay:
  # 衰减因子
  decay_factor: 0.95
  
  # 可靠性边界
  min_reliability: 0.1
  max_reliability: 1.0
  
  # 降级阈值
  deprecation_threshold: 0.3
  consecutive_failure_threshold: 5
  
  # 恢复机制
  recovery:
    enabled: true
    recovery_rate: 0.05  # 每次成功增加的恢复量
    full_recovery_threshold: 0.8  # 恢复到此值后取消降级标记
  
  # 更新频率
  update_interval_seconds: 60
```

---

## 6. 隐性边发现与边权强化机制

### 6.1 隐性边发现原理

系统 SHOULD 自动发现技能之间的隐性依赖关系。当大量成功任务中，技能 A 和技能 B 总是被先后调用（即使它们之间没有人工声明的 `REQUIRES` 边），系统应自动构建一条弱相关边。

### 6.2 共现分析算法

```python
class ImplicitEdgeDiscoveryEngine:
    """
    隐性边发现引擎，基于共现分析发现隐性依赖。
    """
    
    def __init__(self, graph_store, metrics_db, config: DiscoveryConfig):
        self.graph_store = graph_store
        self.metrics_db = metrics_db
        self.config = config
        self.co_occurrence_threshold = config.co_occurrence_threshold  # 默认 50
        self.confidence_threshold = config.confidence_threshold  # 默认 0.7
    
    async def discover_implicit_edges(self) -> List[ImplicitEdge]:
        """
        发现隐性边关系。
        
        Returns:
            List[ImplicitEdge]: 发现的隐性边列表
        """
        # 获取技能共现统计
        co_occurrence_stats = await self._get_co_occurrence_stats()
        
        # 分析共现模式
        implicit_edges = []
        
        for stat in co_occurrence_stats:
            skill_a = stat["skill_a"]
            skill_b = stat["skill_b"]
            co_occurrence_count = stat["count"]
            success_rate = stat["success_rate"]
            
            # 检查是否满足阈值
            if co_occurrence_count >= self.co_occurrence_threshold:
                # 计算置信度
                confidence = self._calculate_confidence(
                    co_occurrence_count,
                    success_rate
                )
                
                if confidence >= self.confidence_threshold:
                    # 判断边类型
                    edge_type = self._determine_edge_type(stat)
                    
                    implicit_edges.append(ImplicitEdge(
                        source=skill_a,
                        target=skill_b,
                        edge_type=edge_type,
                        confidence=confidence,
                        co_occurrence_count=co_occurrence_count
                    ))
        
        return implicit_edges
    
    async def _get_co_occurrence_stats(self) -> List[dict]:
        """
        获取技能共现统计。
        """
        # 从遥测数据库查询共现数据
        query = """
        SELECT 
            skill_a,
            skill_b,
            COUNT(*) as count,
            AVG(CASE WHEN success THEN 1 ELSE 0 END) as success_rate,
            AVG(time_diff_ms) as avg_time_diff
        FROM skill_co_occurrence
        WHERE time_window = '7d'
        GROUP BY skill_a, skill_b
        HAVING COUNT(*) >= $threshold
        ORDER BY count DESC
        """
        
        result = await self.metrics_db.execute_query(
            query,
            {"threshold": self.co_occurrence_threshold}
        )
        
        return result
    
    def _calculate_confidence(
        self,
        co_occurrence_count: int,
        success_rate: float
    ) -> float:
        """
        计算置信度。
        
        置信度 = 共现频率权重 × 成功率权重
        """
        # 共现频率权重（归一化）
        frequency_weight = min(co_occurrence_count / 100, 1.0)
        
        # 成功率权重
        success_weight = success_rate
        
        return frequency_weight * success_weight
    
    def _determine_edge_type(self, stat: dict) -> str:
        """
        判断边类型。
        
        规则：
        - 平均时间差 < 5s 且 skill_a 先于 skill_b → REQUIRES
        - 平均时间差 > 5s 且成功率 > 0.9 → ENHANCES
        """
        avg_time_diff = stat.get("avg_time_diff", 0)
        success_rate = stat.get("success_rate", 0)
        
        if avg_time_diff < 5000 and success_rate > 0.8:
            return "REQUIRES"
        elif success_rate > 0.9:
            return "ENHANCES"
        else:
            return "ENHANCES"  # 默认为增强边
    
    async def create_implicit_edge(
        self,
        edge: ImplicitEdge
    ) -> None:
        """
        创建隐性边。
        """
        # 检查是否已存在相同边
        exists = await self._check_edge_exists(edge.source, edge.target, edge.edge_type)
        
        if exists:
            # 更新现有边权重
            await self._update_edge_weight(edge)
        else:
            # 创建新边
            await self._create_new_edge(edge)
    
    async def _create_new_edge(self, edge: ImplicitEdge) -> None:
        """
        创建新边。
        """
        query = f"""
        MATCH (a:SkillNode {{uid: $source}})
        MATCH (b:SkillNode {{uid: $target}})
        CREATE (a)-[:{edge.edge_type} {{
            weight: $weight,
            confidence: $confidence,
            auto_discovered: true,
            verified_by_human: false,
            co_occurrence_count: $count,
            created_at: datetime()
        }}]->(b)
        """
        
        await self.graph_store.execute_query(
            query,
            {
                "source": edge.source,
                "target": edge.target,
                "weight": edge.confidence,
                "confidence": edge.confidence,
                "count": edge.co_occurrence_count
            }
        )
    
    async def _update_edge_weight(self, edge: ImplicitEdge) -> None:
        """
        更新现有边权重。
        """
        query = f"""
        MATCH (a:SkillNode {{uid: $source}})-[r:{edge.edge_type}]->(b:SkillNode {{uid: $target}})
        SET r.weight = r.weight + $increment,
            r.co_occurrence_count = r.co_occurrence_count + $count,
            r.confidence = $confidence
        """
        
        await self.graph_store.execute_query(
            query,
            {
                "source": edge.source,
                "target": edge.target,
                "increment": 0.1,  # 每次增加 0.1
                "count": edge.co_occurrence_count,
                "confidence": edge.confidence
            }
        )
```

### 6.3 边权强化机制

```python
class EdgeWeightReinforcementEngine:
    """
    边权强化引擎，根据执行反馈强化边权重。
    """
    
    def __init__(self, graph_store, config: ReinforcementConfig):
        self.graph_store = graph_store
        self.config = config
        self.max_weight = config.max_weight  # 默认 1.0
        self.min_weight = config.min_weight  # 默认 0.1
        self.reinforcement_rate = config.reinforcement_rate  # 默认 0.05
    
    async def reinforce_edge(
        self,
        source: str,
        target: str,
        edge_type: str,
        success: bool
    ) -> float:
        """
        强化边权重。
        
        Args:
            source: 源技能 ID
            target: 目标技能 ID
            edge_type: 边类型
            success: 执行是否成功
            
        Returns:
            float: 更新后的权重
        """
        # 获取当前权重
        current_weight = await self._get_edge_weight(source, target, edge_type)
        
        # 计算新权重
        if success:
            # 成功时增加权重
            new_weight = current_weight + self.reinforcement_rate
        else:
            # 失败时减少权重
            new_weight = current_weight - self.reinforcement_rate
        
        # 应用边界约束
        new_weight = max(self.min_weight, min(self.max_weight, new_weight))
        
        # 更新图数据库
        await self._update_edge_weight(source, target, edge_type, new_weight)
        
        return new_weight
    
    async def _get_edge_weight(
        self,
        source: str,
        target: str,
        edge_type: str
    ) -> float:
        """
        获取当前边权重。
        """
        query = f"""
        MATCH (a:SkillNode {{uid: $source}})-[r:{edge_type}]->(b:SkillNode {{uid: $target}})
        RETURN r.weight as weight
        """
        
        result = await self.graph_store.execute_query(
            query,
            {"source": source, "target": target}
        )
        
        return result[0].get("weight", 0.5) if result else 0.5
    
    async def _update_edge_weight(
        self,
        source: str,
        target: str,
        edge_type: str,
        new_weight: float
    ) -> None:
        """
        更新边权重。
        """
        query = f"""
        MATCH (a:SkillNode {{uid: $source}})-[r:{edge_type}]->(b:SkillNode {{uid: $target}})
        SET r.weight = $weight,
            r.last_reinforcement = datetime()
        """
        
        await self.graph_store.execute_query(
            query,
            {"source": source, "target": target, "weight": new_weight}
        )
```

### 6.4 边权转化为正式依赖

当隐性边的权重跨越阈值时，系统 SHOULD 将其转化为正式的 `REQUIRES` 边：

```python
async def promote_to_requires(self, edge: ImplicitEdge) -> None:
    """
    将高权重隐性边转化为正式 REQUIRES 边。
    """
    promotion_threshold = 0.85
    
    if edge.confidence >= promotion_threshold:
        # 删除原有的 ENHANCES 边
        await self._delete_edge(edge.source, edge.target, "ENHANCES")
        
        # 创建新的 REQUIRES 边
        await self._create_requires_edge(edge)
        
        # 发送通知
        await self._send_promotion_notification(edge)


async def _create_requires_edge(self, edge: ImplicitEdge) -> None:
    """
    创建正式 REQUIRES 边。
    """
    query = """
    MATCH (a:SkillNode {uid: $source})
    MATCH (b:SkillNode {uid: $target})
    CREATE (a)-[:REQUIRES {
        weight: 1.0,
        is_hard: false,
        auto_discovered: true,
        verified_by_human: false,
        promoted_from: "ENHANCES",
        created_at: datetime()
    }]->(b)
    """
    
    await self.graph_store.execute_query(
        query,
        {"source": edge.source, "target": edge.target}
    )
```

---

## 7. 冲突边自发现算法

### 7.1 冲突发现原理

系统 SHOULD 监控 Agent 的死锁行为。当日志显示引入技能 A 和 B 后，Agent 陷入循环重试或状态机崩溃，系统自动提取 A 和 B，利用 LLM 进行死锁原因分析。若确认逻辑互斥，自动向图数据库写入 `CONFLICTS_WITH` 边。

### 7.2 死锁检测算法

```python
class DeadlockDetectionEngine:
    """
    死锁检测引擎，识别 Agent 执行中的死锁模式。
    """
    
    def __init__(self, metrics_db, config: DeadlockConfig):
        self.metrics_db = metrics_db
        self.config = config
        self.max_retry_threshold = config.max_retry_threshold  # 默认 5
        self.loop_pattern_threshold = config.loop_pattern_threshold  # 默认 3
    
    async def detect_deadlock_patterns(self) -> List[DeadlockPattern]:
        """
        检测死锁模式。
        
        Returns:
            List[DeadlockPattern]: 检测到的死锁模式列表
        """
        # 查询异常执行记录
        query = """
        SELECT 
            session_id,
            skill_ids,
            retry_count,
            loop_pattern,
            error_type,
            timestamp
        FROM execution_anomalies
        WHERE anomaly_type = 'potential_deadlock'
        AND timestamp > NOW() - INTERVAL '7 days'
        """
        
        anomalies = await self.metrics_db.execute_query(query)
        
        deadlock_patterns = []
        
        for anomaly in anomalies:
            skill_ids = anomaly["skill_ids"]
            
            # 分析技能组合
            if len(skill_ids) >= 2:
                # 检查是否满足死锁条件
                if anomaly["retry_count"] >= self.max_retry_threshold:
                    deadlock_patterns.append(DeadlockPattern(
                        skill_ids=skill_ids,
                        session_id=anomaly["session_id"],
                        retry_count=anomaly["retry_count"],
                        loop_pattern=anomaly["loop_pattern"],
                        timestamp=anomaly["timestamp"]
                    ))
        
        return deadlock_patterns
    
    async def analyze_deadlock_cause(
        self,
        pattern: DeadlockPattern
    ) -> ConflictAnalysisResult:
        """
        分析死锁原因，判断是否为技能冲突。
        
        Args:
            pattern: 死锁模式
            
        Returns:
            ConflictAnalysisResult: 分析结果
        """
        # 获取技能描述
        skill_descriptions = await self._get_skill_descriptions(pattern.skill_ids)
        
        # 构建 LLM 分析 Prompt
        prompt = self._build_analysis_prompt(skill_descriptions, pattern)
        
        # 调用 LLM 分析
        response = await self.llm_client.generate(
            prompt=prompt,
            model="gpt-4o",
            temperature=0.3
        )
        
        # 解析分析结果
        result = self._parse_analysis_response(response)
        
        return result
    
    def _build_analysis_prompt(
        self,
        skill_descriptions: List[dict],
        pattern: DeadlockPattern
    ) -> str:
        """
        构建死锁分析 Prompt。
        """
        return f"""
分析以下技能组合是否存在逻辑冲突导致死锁：

技能列表：
{self._format_skill_descriptions(skill_descriptions)}

执行异常信息：
- 重试次数: {pattern.retry_count}
- 循环模式: {pattern.loop_pattern}

请分析：
1. 这些技能是否存在逻辑互斥？
2. 如果存在冲突，请说明冲突原因
3. 冲突严重程度（1-5）

输出 JSON 格式：
{
  "has_conflict": true/false,
  "conflict_reason": "...",
  "severity": 1-5,
  "confidence": 0.0-1.0
}
"""
    
    async def create_conflict_edge(
        self,
        analysis_result: ConflictAnalysisResult,
        skill_ids: List[str]
    ) -> None:
        """
        创建冲突边。
        """
        if analysis_result.has_conflict and analysis_result.confidence >= 0.8:
            # 创建 CONFLICTS_WITH 边
            for i, skill_a in enumerate(skill_ids):
                for skill_b in skill_ids[i+1:]:
                    await self._create_conflict_edge(
                        skill_a,
                        skill_b,
                        analysis_result.severity,
                        analysis_result.conflict_reason
                    )
    
    async def _create_conflict_edge(
        self,
        skill_a: str,
        skill_b: str,
        severity: int,
        reason: str
    ) -> None:
        """
        创建单条冲突边。
        """
        query = """
        MATCH (a:SkillNode {uid: $skill_a})
        MATCH (b:SkillNode {uid: $skill_b})
        CREATE (a)-[:CONFLICTS_WITH {
            severity: $severity,
            reason: $reason,
            auto_discovered: true,
            verified_by_human: false,
            created_at: datetime()
        }]->(b)
        """
        
        await self.graph_store.execute_query(
            query,
            {
                "skill_a": skill_a,
                "skill_b": skill_b,
                "severity": severity,
                "reason": reason
            }
        )
```

### 7.3 冲突边数据结构

```python
class DeadlockPattern:
    """
    死锁模式数据结构。
    """
    
    skill_ids: List[str]       # 涉及的技能 ID
    session_id: str            # Session ID
    retry_count: int           # 重试次数
    loop_pattern: str          # 循环模式描述
    timestamp: str             # 时间戳


class ConflictAnalysisResult:
    """
    冲突分析结果。
    """
    
    has_conflict: bool         # 是否存在冲突
    conflict_reason: str       # 冲突原因
    severity: int              # 严重程度 (1-5)
    confidence: float          # 分析置信度
```

---

## 8. 后台作业调度策略

### 8.1 作业类型定义

系统 MUST 定期执行以下后台作业：

| 作业名称 | 执行频率 | 描述 | 优先级 |
|----------|----------|------|--------|
| `reliability_update` | 每分钟 | 更新节点可靠性 | 高 |
| `implicit_edge_discovery` | 每小时 | 发现隐性边 | 中 |
| `edge_weight_reinforcement` | 每 5 分钟 | 强化边权重 | 高 |
| `deadlock_detection` | 每 15 分钟 | 检测死锁模式 | 高 |
| `graph_consistency_check` | 每天 | 检查图一致性 | 低 |
| `data_retention_cleanup` | 每天 | 清理过期数据 | 低 |

### 8.2 作业调度器实现

```python
class BackgroundJobScheduler:
    """
    后台作业调度器。
    """
    
    def __init__(self, config: SchedulerConfig):
        self.config = config
        self.jobs = {}
        self.running = False
    
    def register_job(
        self,
        job_name: str,
        job_func: Callable,
        interval_seconds: int,
        priority: int = 0
    ) -> None:
        """
        注册后台作业。
        """
        self.jobs[job_name] = BackgroundJob(
            name=job_name,
            func=job_func,
            interval_seconds=interval_seconds,
            priority=priority,
            last_run=None,
            next_run=datetime.utcnow()
        )
    
    async def start(self) -> None:
        """
        启动调度器。
        """
        self.running = True
        
        while self.running:
            # 获取当前时间
            now = datetime.utcnow()
            
            # 检查每个作业
            for job_name, job in sorted(
                self.jobs.items(),
                key=lambda x: x[1].priority,
                reverse=True
            ):
                if job.next_run <= now:
                    # 执行作业
                    try:
                        await job.func()
                        job.last_run = now
                        job.next_run = now + timedelta(seconds=job.interval_seconds)
                        
                        logger.info(f"Job '{job_name}' completed successfully")
                        
                    except Exception as e:
                        logger.error(f"Job '{job_name}' failed: {e}")
                        
                        # 失败后延迟重试
                        job.next_run = now + timedelta(seconds=job.interval_seconds * 2)
            
            # 等待下一次检查
            await asyncio.sleep(1)
    
    async def stop(self) -> None:
        """
        停止调度器。
        """
        self.running = False


class BackgroundJob:
    """
    后台作业数据结构。
    """
    
    name: str
    func: Callable
    interval_seconds: int
    priority: int
    last_run: datetime
    next_run: datetime
```

### 8.3 作业配置规范

```yaml
# config/scheduler.yaml
scheduler:
  enabled: true
  
  jobs:
    reliability_update:
      interval_seconds: 60
      priority: 10
      enabled: true
    
    implicit_edge_discovery:
      interval_seconds: 3600
      priority: 5
      enabled: true
    
    edge_weight_reinforcement:
      interval_seconds: 300
      priority: 8
      enabled: true
    
    deadlock_detection:
      interval_seconds: 900
      priority: 9
      enabled: true
    
    graph_consistency_check:
      interval_seconds: 86400
      priority: 1
      enabled: true
    
    data_retention_cleanup:
      interval_seconds: 86400
      priority: 0
      enabled: true
  
  # 并发控制
  max_concurrent_jobs: 3
  
  # 失败处理
  retry_policy:
    max_retries: 3
    retry_delay_seconds: 60
    exponential_backoff: true
```

---

## 9. 监控告警体系

### 9.1 监控指标定义

系统 MUST 收集以下监控指标：

| 指标类别 | 指标名称 | 描述 | 告警阈值 |
|----------|----------|------|----------|
| **路由性能** | `routing_latency_p99` | 路由延迟 P99 | > 500ms |
| **路由性能** | `routing_fallback_rate` | 降级率 | > 5% |
| **路由性能** | `routing_cache_hit_rate` | 缓存命中率 | < 30% |
| **技能执行** | `skill_success_rate_avg` | 平均成功率 | < 80% |
| **技能执行** | `skill_failure_rate_spike` | 失败率突增 | > 20% |
| **技能执行** | `skill_deprecation_count` | 降级技能数 | > 10 |
| **图谱进化** | `implicit_edge_created_count` | 隐性边创建数 | - |
| **图谱进化** | `conflict_edge_created_count` | 冲突边创建数 | - |
| **系统健康** | `graph_db_latency` | 图数据库延迟 | > 200ms |
| **系统健康** | `vector_db_latency` | 向量数据库延迟 | > 100ms |
| **系统健康** | `kafka_lag` | Kafka 消费延迟 | > 1000 |

### 9.2 Prometheus 指标定义

```python
from prometheus_client import Counter, Gauge, Histogram

# 路由指标
ROUTING_LATENCY = Histogram(
    'graphskill_routing_latency_seconds',
    'Routing request latency',
    buckets=[0.1, 0.2, 0.3, 0.5, 1.0, 2.0]
)

ROUTING_REQUEST_COUNT = Counter(
    'graphskill_routing_requests_total',
    'Total routing requests',
    ['routing_mode', 'status']
)

ROUTING_FALLBACK_COUNT = Counter(
    'graphskill_routing_fallbacks_total',
    'Total routing fallbacks',
    ['reason']
)

# 技能执行指标
SKILL_CALL_COUNT = Counter(
    'graphskill_skill_calls_total',
    'Total skill calls',
    ['skill_id', 'status']
)

SKILL_SUCCESS_RATE = Gauge(
    'graphskill_skill_success_rate',
    'Skill success rate',
    ['skill_id']
)

# 图谱进化指标
IMPLICIT_EDGE_CREATED = Counter(
    'graphskill_implicit_edges_created_total',
    'Total implicit edges created',
    ['edge_type']
)

CONFLICT_EDGE_CREATED = Counter(
    'graphskill_conflict_edges_created_total',
    'Total conflict edges created',
    ['severity']
)

# 系统健康指标
GRAPH_DB_LATENCY = Histogram(
    'graphskill_graph_db_latency_seconds',
    'Graph database query latency',
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0]
)

KAFKA_LAG = Gauge(
    'graphskill_kafka_consumer_lag',
    'Kafka consumer lag',
    ['topic', 'consumer_group']
)
```

### 9.3 告警规则定义

```yaml
# config/alerts.yaml
alerts:
  rules:
    # 路由性能告警
    - name: routing_latency_high
      expr: histogram_quantile(0.99, graphskill_routing_latency_seconds) > 0.5
      severity: warning
      message: "Routing latency P99 exceeds 500ms"
      for: 5m
      
    - name: routing_fallback_rate_high
      expr: |
        sum(rate(graphskill_routing_fallbacks_total[5m])) 
        / sum(rate(graphskill_routing_requests_total[5m])) > 0.05
      severity: warning
      message: "Routing fallback rate exceeds 5%"
      for: 5m
    
    # 技能执行告警
    - name: skill_success_rate_low
      expr: avg(graphskill_skill_success_rate) < 0.8
      severity: warning
      message: "Average skill success rate below 80%"
      for: 10m
      
    - name: skill_failure_spike
      expr: |
        sum(rate(graphskill_skill_calls_total{status="failed"}[5m]))
        / sum(rate(graphskill_skill_calls_total[5m])) > 0.2
      severity: critical
      message: "Skill failure rate spike detected"
      for: 2m
    
    # 系统健康告警
    - name: graph_db_latency_high
      expr: histogram_quantile(0.95, graphskill_graph_db_latency_seconds) > 0.2
      severity: warning
      message: "Graph database latency P95 exceeds 200ms"
      for: 5m
      
    - name: kafka_lag_high
      expr: graphskill_kafka_consumer_lag > 1000
      severity: warning
      message: "Kafka consumer lag exceeds 1000 messages"
      for: 10m
  
  # 告警通知配置
  notifications:
    email:
      enabled: true
      recipients: ["admin@example.com"]
    
    slack:
      enabled: true
      channel: "#graphskill-alerts"
    
    pagerduty:
      enabled: true
      service_key: "xxx"
      severity_threshold: "critical"
```

### 9.4 Grafana Dashboard 配置

```json
{
  "dashboard": {
    "title": "GraphSkill Telemetry Dashboard",
    "panels": [
      {
        "title": "Routing Performance",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.99, rate(graphskill_routing_latency_seconds_bucket[5m]))",
            "legendFormat": "P99 Latency"
          },
          {
            "expr": "histogram_quantile(0.50, rate(graphskill_routing_latency_seconds_bucket[5m]))",
            "legendFormat": "P50 Latency"
          }
        ]
      },
      {
        "title": "Skill Success Rate",
        "type": "gauge",
        "targets": [
          {
            "expr": "avg(graphskill_skill_success_rate)",
            "legendFormat": "Average"
          }
        ],
        "thresholds": [
          {"value": 0.8, "color": "green"},
          {"value": 0.6, "color": "yellow"},
          {"value": 0.4, "color": "red"}
        ]
      },
      {
        "title": "Graph Evolution Activity",
        "type": "counter",
        "targets": [
          {
            "expr": "sum(rate(graphskill_implicit_edges_created_total[1h]))",
            "legendFormat": "Implicit Edges/hr"
          },
          {
            "expr": "sum(rate(graphskill_conflict_edges_created_total[1h]))",
            "legendFormat": "Conflict Edges/hr"
          }
        ]
      }
    ]
  }
}
```

---

## 10. 版本历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|----------|------|
| 1.0.0 | 2026-04-12 | 初始版本发布 | GraphSkill Architecture Team |
| 1.1.0 | 2026-04-17 | VR-First 架构适配：遥测数据新增 EnhancementResult 和 FallbackMetadata 采集 | GraphSkill Architecture Team |

---

**文档结束**

*本文档定义了 GraphSkill 系统的遥测监控与自我进化反馈循环。相关数据结构定义详见 [RFC-08: 数据结构与 Schema 定义](RFC-08-data-structures-schema.md)，性能与高可用规范详见 [RFC-06: 性能安全与高可用规范](RFC-06-performance-security-high-availability.md)。*