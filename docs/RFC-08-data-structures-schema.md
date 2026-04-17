# RFC-08: 数据结构与 Schema 定义

**文档编号:** RFC-08  
**版本:** 2.0.0
**状态:** 正式发布
**最后更新:** 2026-04-17
**作者:** GraphSkill Architecture Team  
**分类:** 架构规范 - 数据契约  
**依赖:** RFC-00, RFC-01

---

## 目录

1. [概述](#1-概述)
2. [核心数据结构定义](#2-核心数据结构定义)
3. [图数据库数据模型](#3-图数据库数据模型)
4. [向量数据库 Schema](#4-向量数据库-schema)
5. [遥测数据结构](#5-遥测数据结构)
6. [路由数据结构](#6-路由数据结构)
7. [Session 数据结构](#7-session-数据结构)
8. [错误数据结构](#8-错误数据结构)
9. [Protocol Buffers 定义](#9-protocol-buffers-定义)
10. [序列化规范](#10-序列化规范)
11. [版本历史](#11-版本历史)

---

## 1. 概述

### 1.1 文档目的

本文档作为 GraphSkill 系统的**数据契约单一真相来源（Single Source of Truth）**，汇总所有核心数据结构定义。所有其他 RFC 文档 MUST 引用本文档的数据结构定义，MUST NOT 在其他文档中重复定义。

### 1.2 适用范围

本文档适用于：
- 所有 RFC 文档：引用数据结构定义
- 后端开发工程师：实现数据结构类
- 数据工程师：设计数据库 Schema
- API 开发者：定义请求/响应格式

### 1.3 数据结构分类

| 类别 | 描述 | 存储位置 |
|------|------|----------|
| **图数据模型** | 技能节点与边关系 | Neo4j/Memgraph |
| **向量数据模型** | 技能向量嵌入 | Milvus/Qdrant |
| **遥测数据结构** | 执行追踪与监控数据 | Kafka/PostgreSQL |
| **路由数据结构** | 路由请求与响应 | 内存/API |
| **Session 数据结构** | Agent 会话状态 | Redis |
| **错误数据结构** | 错误响应与异常 | API |

### 1.4 Schema 版本管理

所有 Schema MUST 包含版本标识：

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://graphskill.io/schemas/{schema_name}-v{version}.json",
  "version": "1.0.0"
}
```

---

## 2. 核心数据结构定义

### 2.1 SkillNode（技能节点）

技能节点是图数据库的核心实体，表示单个技能。

#### 2.1.1 JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://graphskill.io/schemas/skill-node-v1.json",
  "title": "SkillNode",
  "description": "技能节点数据结构",
  "type": "object",
  "required": [
    "uid",
    "version",
    "intent_description",
    "permissions",
    "execution_success_rate",
    "is_deprecated",
    "created_at",
    "updated_at"
  ],
  "properties": {
    "uid": {
      "type": "string",
      "pattern": "^[a-z0-9_-]+:[a-z0-9_-]+$",
      "description": "全局唯一技能标识符",
      "examples": ["git:commit_changes", "db:query_postgres"]
    },
    "embedding_id": {
      "type": "string",
      "description": "关联的向量数据库主键"
    },
    "version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+\\.\\d+(-[a-zA-Z0-9]+)?$",
      "description": "语义化版本号 (SemVer 2.0.0)",
      "examples": ["1.0.0", "2.1.3-beta"]
    },
    "intent_description": {
      "type": "string",
      "minLength": 50,
      "maxLength": 500,
      "description": "面向 LLM 的意图描述"
    },
    "permissions": {
      "type": "array",
      "items": {
        "type": "string",
        "pattern": "^[a-z]+:[a-z]+(:[a-zA-Z0-9_/-]+)?$"
      },
      "minItems": 1,
      "description": "权限声明列表"
    },
    "trigger_conditions": {
      "type": "object",
      "description": "触发前置条件",
      "properties": {
        "env_vars": {
          "type": "object",
          "additionalProperties": {"type": "string"}
        },
        "file_exists": {
          "type": "array",
          "items": {"type": "string"}
        },
        "service_available": {
          "type": "array",
          "items": {"type": "string"}
        }
      }
    },
    "execution_success_rate": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "default": 1.0,
      "description": "历史执行成功率"
    },
    "execution_count": {
      "type": "integer",
      "minimum": 0,
      "default": 0,
      "description": "累计执行次数"
    },
    "last_execution_time": {
      "type": "string",
      "format": "date-time",
      "description": "最后执行时间"
    },
    "is_deprecated": {
      "type": "boolean",
      "default": false,
      "description": "软删除标记"
    },
    "deprecated_reason": {
      "type": "string",
      "description": "废弃原因"
    },
    "deprecated_at": {
      "type": "string",
      "format": "date-time",
      "description": "废弃时间"
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "description": "创建时间"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time",
      "description": "更新时间"
    },
    "author": {
      "type": "string",
      "description": "作者标识"
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"},
      "description": "分类标签"
    },
    "verified_by_human": {
      "type": "boolean",
      "default": false,
      "description": "人工审核标记"
    }
  },
  "additionalProperties": false
}
```

#### 2.1.2 Python 类定义

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional

@dataclass
class SkillNode:
    """
    技能节点数据结构。
    
    Attributes:
        uid: 全局唯一技能标识符
        embedding_id: 关联的向量数据库主键
        version: 语义化版本号
        intent_description: 面向 LLM 的意图描述
        permissions: 权限声明列表
        trigger_conditions: 触发前置条件
        execution_success_rate: 历史执行成功率
        execution_count: 累计执行次数
        last_execution_time: 最后执行时间
        is_deprecated: 软删除标记
        created_at: 创建时间
        updated_at: 更新时间
    """
    
    uid: str
    version: str
    intent_description: str
    permissions: List[str]
    
    embedding_id: Optional[str] = None
    trigger_conditions: Optional[Dict] = None
    
    execution_success_rate: float = 1.0
    execution_count: int = 0
    last_execution_time: Optional[datetime] = None
    
    is_deprecated: bool = False
    deprecated_reason: Optional[str] = None
    deprecated_at: Optional[datetime] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    verified_by_human: bool = False
    
    def to_dict(self) -> dict:
        """
        序列化为字典。
        """
        return {
            "uid": self.uid,
            "embedding_id": self.embedding_id,
            "version": self.version,
            "intent_description": self.intent_description,
            "permissions": self.permissions,
            "trigger_conditions": self.trigger_conditions,
            "execution_success_rate": self.execution_success_rate,
            "execution_count": self.execution_count,
            "last_execution_time": self.last_execution_time.isoformat() if self.last_execution_time else None,
            "is_deprecated": self.is_deprecated,
            "deprecated_reason": self.deprecated_reason,
            "deprecated_at": self.deprecated_at.isoformat() if self.deprecated_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "author": self.author,
            "tags": self.tags,
            "verified_by_human": self.verified_by_human
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SkillNode':
        """
        从字典反序列化。
        """
        return cls(
            uid=data["uid"],
            version=data["version"],
            intent_description=data["intent_description"],
            permissions=data["permissions"],
            embedding_id=data.get("embedding_id"),
            trigger_conditions=data.get("trigger_conditions"),
            execution_success_rate=data.get("execution_success_rate", 1.0),
            execution_count=data.get("execution_count", 0),
            last_execution_time=datetime.fromisoformat(data["last_execution_time"]) if data.get("last_execution_time") else None,
            is_deprecated=data.get("is_deprecated", False),
            deprecated_reason=data.get("deprecated_reason"),
            deprecated_at=datetime.fromisoformat(data["deprecated_at"]) if data.get("deprecated_at") else None,
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            author=data.get("author"),
            tags=data.get("tags", []),
            verified_by_human=data.get("verified_by_human", False)
        )
```

### 2.2 SkillEdge（技能边）

技能边表示技能节点之间的拓扑关系。

#### 2.2.1 JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://graphskill.io/schemas/skill-edge-v1.json",
  "title": "SkillEdge",
  "description": "技能边数据结构",
  "type": "object",
  "required": ["source", "target", "edge_type", "created_at"],
  "properties": {
    "source": {
      "type": "string",
      "pattern": "^[a-z0-9_-]+:[a-z0-9_-]+$",
      "description": "源技能 ID"
    },
    "target": {
      "type": "string",
      "pattern": "^[a-z0-9_-]+:[a-z0-9_-]+$",
      "description": "目标技能 ID"
    },
    "edge_type": {
      "type": "string",
      "enum": ["REQUIRES", "CONFLICTS_WITH", "ENHANCES", "SUBSTITUTES"],
      "description": "边类型"
    },
    "properties": {
      "type": "object",
      "description": "边属性",
      "properties": {
        "weight": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 1.0,
          "default": 1.0,
          "description": "权重"
        },
        "is_hard": {
          "type": "boolean",
          "default": true,
          "description": "是否为硬依赖（仅 REQUIRES）"
        },
        "severity": {
          "type": "integer",
          "minimum": 1,
          "maximum": 5,
          "default": 3,
          "description": "冲突严重程度（仅 CONFLICTS_WITH）"
        },
        "similarity": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 1.0,
          "description": "功能相似度（仅 SUBSTITUTES）"
        },
        "success_rate_boost": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 0.5,
          "description": "成功率提升幅度（仅 ENHANCES）"
        },
        "confidence": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 1.0,
          "description": "LLM 推演置信度"
        },
        "reason": {
          "type": "string",
          "maxLength": 200,
          "description": "关系原因描述"
        },
        "verified_by_human": {
          "type": "boolean",
          "default": false,
          "description": "人工审核标记"
        },
        "auto_discovered": {
          "type": "boolean",
          "default": false,
          "description": "自动发现标记"
        },
        "co_occurrence_count": {
          "type": "integer",
          "minimum": 0,
          "description": "共现次数（仅 ENHANCES）"
        }
      }
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "description": "创建时间"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time",
      "description": "更新时间"
    }
  }
}
```

#### 2.2.2 Python 类定义

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum

class EdgeType(Enum):
    """
    边类型枚举。
    """
    REQUIRES = "REQUIRES"
    CONFLICTS_WITH = "CONFLICTS_WITH"
    ENHANCES = "ENHANCES"
    SUBSTITUTES = "SUBSTITUTES"


@dataclass
class EdgeProperties:
    """
    边属性数据结构。
    """
    
    weight: float = 1.0
    is_hard: bool = True
    severity: int = 3
    similarity: Optional[float] = None
    success_rate_boost: Optional[float] = None
    confidence: Optional[float] = None
    reason: Optional[str] = None
    verified_by_human: bool = False
    auto_discovered: bool = False
    co_occurrence_count: int = 0
    
    def to_dict(self) -> dict:
        return {
            "weight": self.weight,
            "is_hard": self.is_hard,
            "severity": self.severity,
            "similarity": self.similarity,
            "success_rate_boost": self.success_rate_boost,
            "confidence": self.confidence,
            "reason": self.reason,
            "verified_by_human": self.verified_by_human,
            "auto_discovered": self.auto_discovered,
            "co_occurrence_count": self.co_occurrence_count
        }


@dataclass
class SkillEdge:
    """
    技能边数据结构。
    """
    
    source: str
    target: str
    edge_type: EdgeType
    properties: EdgeProperties = field(default_factory=EdgeProperties)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "edge_type": self.edge_type.value,
            "properties": self.properties.to_dict(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SkillEdge':
        return cls(
            source=data["source"],
            target=data["target"],
            edge_type=EdgeType(data["edge_type"]),
            properties=EdgeProperties(**data.get("properties", {})),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data.get("updated_at", data["created_at"]))
        )
```

### 2.3 Permission（权限声明）

#### 2.3.1 JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://graphskill.io/schemas/permission-v1.json",
  "title": "Permission",
  "description": "权限声明数据结构",
  "type": "object",
  "required": ["resource_type", "action"],
  "properties": {
    "resource_type": {
      "type": "string",
      "enum": ["fs", "net", "db", "exec", "env", "api"],
      "description": "资源类型"
    },
    "action": {
      "type": "string",
      "description": "动作类型",
      "examples": ["read", "write", "delete", "run", "query"]
    },
    "target": {
      "type": "string",
      "default": "*",
      "description": "目标路径/域名/命令"
    }
  }
}
```

#### 2.3.2 Python 类定义

```python
from dataclasses import dataclass
from enum import Enum

class ResourceType(Enum):
    """
    资源类型枚举。
    """
    FS = "fs"       # 文件系统
    NET = "net"     # 网络
    DB = "db"       # 数据库
    EXEC = "exec"   # 命令执行
    ENV = "env"     # 环境变量
    API = "api"     # API 调用


@dataclass
class Permission:
    """
    权限声明数据结构。
    """
    
    resource_type: ResourceType
    action: str
    target: str = "*"
    
    def __str__(self) -> str:
        """
        转换为权限字符串格式。
        """
        return f"{self.resource_type.value}:{self.action}:{self.target}"
    
    @classmethod
    def from_string(cls, perm_str: str) -> 'Permission':
        """
        从权限字符串解析。
        """
        parts = perm_str.split(":")
        return cls(
            resource_type=ResourceType(parts[0]),
            action=parts[1],
            target=parts[2] if len(parts) > 2 else "*"
        )
    
    def to_dict(self) -> dict:
        return {
            "resource_type": self.resource_type.value,
            "action": self.action,
            "target": self.target
        }
```

---

## 3. 图数据库数据模型

### 3.1 Neo4j Cypher Schema

```cypher
// ============================================
// GraphSkill Neo4j Schema Definition
// ============================================

// 节点约束
CREATE CONSTRAINT skill_node_uid_unique IF NOT EXISTS
FOR (s:SkillNode) REQUIRE s.uid IS UNIQUE;

CREATE CONSTRAINT skill_node_embedding_id IF NOT EXISTS
FOR (s:SkillNode) ON (s.embedding_id);

CREATE INDEX skill_node_is_deprecated IF NOT EXISTS
FOR (s:SkillNode) ON (s.is_deprecated);

CREATE INDEX skill_node_execution_success_rate IF NOT EXISTS
FOR (s:SkillNode) ON (s.execution_success_rate);

CREATE INDEX skill_node_routing_composite IF NOT EXISTS
FOR (s:SkillNode) ON (s.is_deprecated, s.execution_success_rate);

// 边索引（用于快速查询）
CREATE INDEX skill_edge_requires IF NOT EXISTS
FOR ()-[r:REQUIRES]-() ON (r.is_hard);

CREATE INDEX skill_edge_conflicts_severity IF NOT EXISTS
FOR ()-[r:CONFLICTS_WITH]-() ON (r.severity);

// ============================================
// Node Properties Definition
// ============================================

// SkillNode 属性完整定义
// uid: String (PRIMARY KEY)
// embedding_id: String
// version: String
// intent_description: String
// permissions: List<String>
// trigger_conditions: Map
// execution_success_rate: Float (0.0-1.0)
// execution_count: Integer
// last_execution_time: DateTime
// is_deprecated: Boolean
// deprecated_reason: String
// deprecated_at: DateTime
// created_at: DateTime
// updated_at: DateTime
// author: String
// tags: List<String>
// verified_by_human: Boolean

// ============================================
// Edge Properties Definition
// ============================================

// REQUIRES 边属性
// weight: Float (0.0-1.0)
// is_hard: Boolean
// confidence: Float
// reason: String
// verified_by_human: Boolean
// auto_discovered: Boolean
// created_at: DateTime

// CONFLICTS_WITH 边属性
// severity: Integer (1-5)
// reason: String
// verified_by_human: Boolean
// auto_discovered: Boolean
// created_at: DateTime

// ENHANCES 边属性
// weight: Float (0.0-1.0)
// success_rate_boost: Float (0.0-0.5)
// confidence: Float
// verified_by_human: Boolean
// auto_discovered: Boolean
// co_occurrence_count: Integer
// created_at: DateTime

// SUBSTITUTES 边属性
// similarity: Float (0.0-1.0)
// preferred: String
// verified_by_human: Boolean
// created_at: DateTime
```

### 3.2 Memgraph Schema（备选）

```cypher
// Memgraph Schema Definition (与 Neo4j 兼容)

CREATE CONSTRAINT ON (s:SkillNode) ASSERT s.uid IS UNIQUE;

CREATE INDEX ON :SkillNode(embedding_id);
CREATE INDEX ON :SkillNode(is_deprecated);
CREATE INDEX ON :SkillNode(execution_success_rate);
```

---

## 4. 向量数据库 Schema

### 4.1 Milvus Collection Schema

```python
# Milvus Collection Schema Definition

from pymilvus import Collection, CollectionSchema, FieldSchema, DataType

# 技能向量 Collection
SKILL_VECTOR_SCHEMA = CollectionSchema(
    fields=[
        FieldSchema(
            name="id",
            dtype=DataType.VARCHAR,
            max_length=64,
            is_primary=True,
            description="向量唯一标识符"
        ),
        FieldSchema(
            name="skill_id",
            dtype=DataType.VARCHAR,
            max_length=128,
            description="关联的技能 ID"
        ),
        FieldSchema(
            name="vector",
            dtype=DataType.FLOAT_VECTOR,
            dim=1536,  # text-embedding-3-small 维度
            description="技能描述向量嵌入"
        ),
        FieldSchema(
            name="intent_description",
            dtype=DataType.VARCHAR,
            max_length=512,
            description="原始意图描述文本"
        ),
        FieldSchema(
            name="version",
            dtype=DataType.VARCHAR,
            max_length=32,
            description="技能版本号"
        ),
        FieldSchema(
            name="created_at",
            dtype=DataType.INT64,
            description="创建时间（Unix timestamp）"
        ),
        FieldSchema(
            name="updated_at",
            dtype=DataType.INT64,
            description="更新时间（Unix timestamp）"
        )
    ],
    description="GraphSkill 技能向量存储",
    enable_dynamic_field=False
)

# 索引定义
VECTOR_INDEX_PARAMS = {
    "metric_type": "COSINE",
    "index_type": "HNSW",
    "params": {
        "M": 16,
        "efConstruction": 200
    }
}

SKILL_ID_INDEX_PARAMS = {
    "index_type": "Trie"
}
```

### 4.2 Qdrant Collection Schema（备选）

```python
# Qdrant Collection Schema Definition

from qdrant_client import QdrantClient
from qdrant_client.http import models

# 技能向量 Collection
SKILL_VECTOR_COLLECTION = models.CollectionParams(
    vectors_config=models.VectorParams(
        size=1536,
        distance=models.Distance.COSINE,
        hnsw_config=models.HnswConfigDiff(
            m=16,
            ef_construct=200
        )
    )
)

# Payload Schema（存储元数据）
SKILL_PAYLOAD_SCHEMA = {
    "skill_id": models.PayloadSchemaParams(
        type=models.PayloadSchemaType.KEYWORD
    ),
    "version": models.PayloadSchemaParams(
        type=models.PayloadSchemaType.KEYWORD
    ),
    "intent_description": models.PayloadSchemaParams(
        type=models.PayloadSchemaType.TEXT
    ),
    "created_at": models.PayloadSchemaParams(
        type=models.PayloadSchemaType.INTEGER
    )
}
```

---

## 5. 遥测数据结构

### 5.1 TelemetryEvent（遥测事件）

#### 5.1.1 JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://graphskill.io/schemas/telemetry-event-v1.json",
  "title": "TelemetryEvent",
  "description": "遥测事件数据结构",
  "type": "object",
  "required": ["event_type", "event_code", "trace_id", "timestamp"],
  "properties": {
    "event_type": {
      "type": "string",
      "enum": [
        "SKILL_CALLED",
        "SKILL_SUCCESS",
        "SKILL_FAILED",
        "ROUTING_STARTED",
        "ROUTING_COMPLETED",
        "ROUTING_FALLBACK",
        "PERMISSION_CHECK",
        "PERMISSION_DENIED",
        "CONTEXT_OVERFLOW",
        "CONFLICT_DETECTED"
      ],
      "description": "事件类型"
    },
    "event_code": {
      "type": "string",
      "pattern": "^E\\d{3}$",
      "description": "事件码"
    },
    "trace_id": {
      "type": "string",
      "description": "全局追踪 ID"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "时间戳"
    },
    "session_id": {
      "type": "string",
      "description": "Session ID"
    },
    "skill_id": {
      "type": "string",
      "description": "技能 ID"
    },
    "agent_id": {
      "type": "string",
      "description": "Agent ID"
    },
    "data": {
      "type": "object",
      "description": "事件详细数据"
    },
    "metadata": {
      "type": "object",
      "description": "系统元数据",
      "properties": {
        "version": {"type": "string"},
        "environment": {"type": "string"},
        "region": {"type": "string"},
        "hostname": {"type": "string"}
      }
    }
  }
}
```

#### 5.1.2 Python 类定义

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict
from enum import Enum

class EventType(Enum):
    """
    遥测事件类型枚举。
    """
    SKILL_CALLED = "SKILL_CALLED"
    SKILL_SUCCESS = "SKILL_SUCCESS"
    SKILL_FAILED = "SKILL_FAILED"
    ROUTING_STARTED = "ROUTING_STARTED"
    ROUTING_COMPLETED = "ROUTING_COMPLETED"
    ROUTING_FALLBACK = "ROUTING_FALLBACK"
    PERMISSION_CHECK = "PERMISSION_CHECK"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    CONTEXT_OVERFLOW = "CONTEXT_OVERFLOW"
    CONFLICT_DETECTED = "CONFLICT_DETECTED"


@dataclass
class TelemetryEvent:
    """
    遥测事件数据结构。
    """
    
    event_type: EventType
    event_code: str
    trace_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    session_id: Optional[str] = None
    skill_id: Optional[str] = None
    agent_id: Optional[str] = None
    
    data: Dict = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)
    
    def to_json(self) -> str:
        """
        序列化为 JSON。
        """
        import json
        return json.dumps({
            "event_type": self.event_type.value,
            "event_code": self.event_code,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "skill_id": self.skill_id,
            "agent_id": self.agent_id,
            "data": self.data,
            "metadata": self.metadata
        })
    
    @classmethod
    def from_json(cls, json_str: str) -> 'TelemetryEvent':
        """
        从 JSON 反序列化。
        """
        import json
        data = json.loads(json_str)
        return cls(
            event_type=EventType(data["event_type"]),
            event_code=data["event_code"],
            trace_id=data["trace_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            session_id=data.get("session_id"),
            skill_id=data.get("skill_id"),
            agent_id=data.get("agent_id"),
            data=data.get("data", {}),
            metadata=data.get("metadata", {})
        )
```

### 5.2 SkillExecutionRecord（技能执行记录）

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://graphskill.io/schemas/skill-execution-record-v1.json",
  "title": "SkillExecutionRecord",
  "description": "技能执行记录数据结构",
  "type": "object",
  "required": ["skill_id", "session_id", "status", "timestamp"],
  "properties": {
    "record_id": {
      "type": "string",
      "description": "记录唯一 ID"
    },
    "skill_id": {
      "type": "string",
      "description": "技能 ID"
    },
    "session_id": {
      "type": "string",
      "description": "Session ID"
    },
    "status": {
      "type": "string",
      "enum": ["SUCCESS", "FAILED", "TIMEOUT"],
      "description": "执行状态"
    },
    "duration_ms": {
      "type": "number",
      "description": "执行时长（毫秒）"
    },
    "error_type": {
      "type": "string",
      "description": "错误类型"
    },
    "error_message": {
      "type": "string",
      "description": "错误消息"
    },
    "parameters": {
      "type": "object",
      "description": "执行参数"
    },
    "result_summary": {
      "type": "string",
      "description": "结果摘要"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "执行时间"
    }
  }
}
```

---

## 6. 路由数据结构

### 6.1 RoutingRequest（路由请求）

#### 6.1.1 JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://graphskill.io/schemas/routing-request-v1.json",
  "title": "RoutingRequest",
  "description": "路由请求数据结构",
  "type": "object",
  "required": ["query"],
  "properties": {
    "query": {
      "type": "string",
      "minLength": 10,
      "maxLength": 2000,
      "description": "用户查询文本"
    },
    "context_state": {
      "type": "object",
      "description": "当前上下文状态",
      "properties": {
        "session_id": {"type": "string"},
        "previous_skills": {
          "type": "array",
          "items": {"type": "string"}
        },
        "environment": {
          "type": "object",
          "additionalProperties": {"type": "string"}
        },
        "agent_capabilities": {
          "type": "array",
          "items": {"type": "string"}
        }
      }
    },
    "max_tokens": {
      "type": "integer",
      "default": 4000,
      "minimum": 500,
      "maximum": 32000,
      "description": "Token 预算上限"
    },
    "routing_options": {
      "type": "object",
      "description": "路由选项",
      "properties": {
        "include_enhances": {"type": "boolean", "default": true},
        "expansion_depth": {"type": "integer", "default": 2, "minimum": 1, "maximum": 3},
        "seed_count": {"type": "integer", "default": 5, "minimum": 3, "maximum": 20},
        "output_format": {"type": "string", "enum": ["xml", "json", "markdown"], "default": "xml"}
      }
    }
  }
}
```

#### 6.1.2 Python 类定义

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class ContextState:
    """
    上下文状态数据结构。
    """
    
    session_id: Optional[str] = None
    previous_skills: List[str] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    agent_capabilities: List[str] = field(default_factory=list)


@dataclass
class RoutingOptions:
    """
    路由选项数据结构。
    """
    
    include_enhances: bool = True
    expansion_depth: int = 2
    seed_count: int = 5
    output_format: str = "xml"


@dataclass
class RoutingRequest:
    """
    路由请求数据结构。
    """
    
    query: str
    context_state: ContextState = field(default_factory=ContextState)
    max_tokens: int = 4000
    routing_options: RoutingOptions = field(default_factory=RoutingOptions)
    
    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "context_state": {
                "session_id": self.context_state.session_id,
                "previous_skills": self.context_state.previous_skills,
                "environment": self.context_state.environment,
                "agent_capabilities": self.context_state.agent_capabilities
            },
            "max_tokens": self.max_tokens,
            "routing_options": {
                "include_enhances": self.routing_options.include_enhances,
                "expansion_depth": self.routing_options.expansion_depth,
                "seed_count": self.routing_options.seed_count,
                "output_format": self.routing_options.output_format
            }
        }
```

### 6.2 RoutingResult（路由结果）

#### 6.2.1 JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://graphskill.io/schemas/routing-result-v1.json",
  "title": "RoutingResult",
  "description": "路由结果数据结构",
  "type": "object",
  "required": ["skills", "routing_mode", "token_count"],
  "properties": {
    "skills": {
      "type": "array",
      "items": {
        "$ref": "#/definitions/SkillData"
      },
      "description": "技能列表"
    },
    "routing_mode": {
      "type": "string",
      "enum": ["normal", "fallback", "cached"],
      "description": "路由模式"
    },
    "token_count": {
      "type": "integer",
      "description": "实际 Token 数"
    },
    "latency_ms": {
      "type": "integer",
      "description": "路由延迟（毫秒）"
    },
    "warnings": {
      "type": "array",
      "items": {"type": "string"},
      "description": "警告信息"
    },
    "fallback_info": {
      "type": "object",
      "description": "降级信息（仅 fallback 模式）",
      "properties": {
        "reason": {"type": "string"},
        "fallback_duration_seconds": {"type": "integer"},
        "estimated_recovery_time": {"type": "string", "format": "date-time"}
      }
    }
  },
  "definitions": {
    "SkillData": {
      "type": "object",
      "required": ["skill_id", "priority", "type", "description"],
      "properties": {
        "skill_id": {"type": "string"},
        "priority": {"type": "integer"},
        "type": {"type": "string", "enum": ["seed", "required", "enhances"]},
        "description": {"type": "string"},
        "instructions": {"type": "string"},
        "permissions": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "resource": {"type": "string"},
              "action": {"type": "string"},
              "target": {"type": "string"}
            }
          }
        },
        "tool_call_schema": {"type": "object"},
        "requires": {
          "type": "array",
          "items": {"type": "string"}
        }
      }
    }
  }
}
```

#### 6.2.2 Python 类定义

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

class SkillType(Enum):
    """
    技能类型枚举。
    """
    SEED = "seed"       # 语义召回的种子节点
    REQUIRED = "required"  # 强依赖节点
    ENHANCES = "enhances"  # 增强节点


class RoutingMode(Enum):
    """
    路由模式枚举。
    """
    NORMAL = "normal"
    FALLBACK = "fallback"
    CACHED = "cached"


@dataclass
class SkillData:
    """
    技能数据结构（路由结果中的技能）。
    """
    
    skill_id: str
    priority: int
    type: SkillType
    description: str
    instructions: str = ""
    permissions: List[Dict] = field(default_factory=list)
    tool_call_schema: Optional[Dict] = None
    requires: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "priority": self.priority,
            "type": self.type.value,
            "description": self.description,
            "instructions": self.instructions,
            "permissions": self.permissions,
            "tool_call_schema": self.tool_call_schema,
            "requires": self.requires
        }


@dataclass
class FallbackInfo:
    """
    降级信息数据结构。
    """
    
    reason: str
    fallback_duration_seconds: int = 0
    estimated_recovery_time: Optional[str] = None


@dataclass
class RoutingResult:
    """
    路由结果数据结构。
    """
    
    skills: List[SkillData]
    routing_mode: RoutingMode
    token_count: int
    latency_ms: int = 0
    warnings: List[str] = field(default_factory=list)
    fallback_info: Optional[FallbackInfo] = None
    
    def to_dict(self) -> dict:
        result = {
            "skills": [s.to_dict() for s in self.skills],
            "routing_mode": self.routing_mode.value,
            "token_count": self.token_count,
            "latency_ms": self.latency_ms,
            "warnings": self.warnings
        }
        
        if self.fallback_info:
            result["fallback_info"] = {
                "reason": self.fallback_info.reason,
                "fallback_duration_seconds": self.fallback_info.fallback_duration_seconds,
                "estimated_recovery_time": self.fallback_info.estimated_recovery_time
            }
        
        return result
```

### 6.3 CandidateNode（候选节点）

```python
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class CandidateNode:
    """
    候选节点数据结构（路由过程中的中间状态）。
    """
    
    skill_id: str
    similarity: float = 0.0
    depth: int = 0
    is_seed: bool = False
    expansion_path: List[str] = field(default_factory=list)
    edge_type: Optional[str] = None
    edge_weight: float = 1.0
    score: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "similarity": self.similarity,
            "depth": self.depth,
            "is_seed": self.is_seed,
            "expansion_path": self.expansion_path,
            "edge_type": self.edge_type,
            "edge_weight": self.edge_weight,
            "score": self.score
        }
```

### 6.4 ConflictGraph（冲突图）

```python
from dataclasses import dataclass, field
from typing import Dict, Set, List, Tuple

@dataclass
class ConflictGraph:
    """
    冲突图数据结构（用于 MWIS 算法）。
    """
    
    nodes: Dict[str, float] = field(default_factory=dict)  # skill_id -> score
    conflict_edges: List[Tuple[str, str, int]] = field(default_factory=list)  # (a, b, severity)
    substitute_edges: List[Tuple[str, str, float]] = field(default_factory=list)  # (a, b, similarity)
    adjacency: Dict[str, Set[str]] = field(default_factory=lambda: {})
    
    def add_node(self, skill_id: str, score: float) -> None:
        self.nodes[skill_id] = score
    
    def add_conflict_edge(self, node_a: str, node_b: str, severity: int) -> None:
        self.conflict_edges.append((node_a, node_b, severity))
        self.adjacency[node_a] = self.adjacency.get(node_a, set())
        self.adjacency[node_a].add(node_b)
        self.adjacency[node_b] = self.adjacency.get(node_b, set())
        self.adjacency[node_b].add(node_a)
    
    def add_substitute_edge(self, node_a: str, node_b: str, similarity: float) -> None:
        self.substitute_edges.append((node_a, node_b, similarity))
        self.adjacency[node_a] = self.adjacency.get(node_a, set())
        self.adjacency[node_a].add(node_b)
        self.adjacency[node_b] = self.adjacency.get(node_b, set())
        self.adjacency[node_b].add(node_a)
    
    def has_conflict(self, node_a: str, node_b: str) -> bool:
        return node_b in self.adjacency.get(node_a, set())
    
    def get_neighbors(self, skill_id: str) -> Set[str]:
        return self.adjacency.get(skill_id, set())
```

### 6.5 EnhancementResult（图增强层结果）

> **VR-First 新增数据契约**：记录 VR baseline → Graph enhancement 的增量变化，是 GS ≥ VR 保证的核心数据载体。

#### 6.5.1 JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://graphskill.io/schemas/enhancement-result-v1.json",
  "title": "EnhancementResult",
  "description": "VR-First 图增强层结果，记录 VR baseline 到最终输出的增量变化",
  "type": "object",
  "required": ["vr_seed_ids", "expanded_ids", "pruned_ids", "final_ids", "improved", "enhancement_score"],
  "properties": {
    "vr_seed_ids": {
      "type": "array",
      "items": {"type": "string"},
      "description": "VR baseline 的 skill IDs (ANN top-5)"
    },
    "expanded_ids": {
      "type": "array",
      "items": {"type": "string"},
      "description": "1-hop expansion 新增的 skill IDs"
    },
    "pruned_ids": {
      "type": "array",
      "items": {"type": "string"},
      "description": "MWIS+VR protection pruning 移除的 skill IDs"
    },
    "final_ids": {
      "type": "array",
      "items": {"type": "string"},
      "description": "最终入选的 skill IDs"
    },
    "improved": {
      "type": "boolean",
      "description": "图增强是否产生了有价值的变化。若 false，final_ids 必须等于 vr_seed_ids"
    },
    "enhancement_score": {
      "type": "number",
      "minimum": 0,
      "description": "增量价值评分 = avg_score(final_ids) - avg_score(vr_seed_ids)"
    }
  }
}
```

#### 6.5.2 Python 类定义

```python
from pydantic import BaseModel, Field, model_validator


class EnhancementResult(BaseModel):
    """VR-First 图增强层结果，记录 VR→Graph 的增量变化。

    关键不变量：如果 improved=False，final_ids MUST 等于 vr_seed_ids，
    保证 GS ≥ VR（fallback 到 VR baseline）。
    """

    vr_seed_ids: list[str] = Field(
        ...,
        description="VR baseline 的 skill IDs (ANN top-5)",
    )
    expanded_ids: list[str] = Field(
        default_factory=list,
        description="1-hop expansion 新增的 skill IDs",
    )
    pruned_ids: list[str] = Field(
        default_factory=list,
        description="MWIS+VR protection pruning 移除的 skill IDs",
    )
    final_ids: list[str] = Field(
        ...,
        description="最终入选的 skill IDs",
    )
    improved: bool = Field(
        ...,
        description="图增强是否产生了有价值的变化",
    )
    enhancement_score: float = Field(
        default=0.0,
        ge=0.0,
        description="增量价值评分",
    )

    @model_validator(mode="after")
    def validate_fallback_guarantee(self) -> "EnhancementResult":
        """GS ≥ VR 保证：如果图增强无效，final_ids 必须等于 vr_seed_ids。"""
        if not self.improved:
            assert set(self.final_ids) == set(self.vr_seed_ids), (
                f"Fallback guarantee violated: improved=False but "
                f"final_ids={self.final_ids} != vr_seed_ids={self.vr_seed_ids}"
            )
        return self
```

### 6.6 VRSeedProtectionConfig（VR Seed 保护配置）

```python
class VRSeedProtectionConfig(BaseModel):
    """VR Seed 保护配置，控制 MWIS pruning 中 VR seed 的保护策略。"""

    enabled: bool = Field(default=True, description="是否启用 VR seed 保护")
    allow_vr_seed_replacement: bool = Field(
        default=False,
        description="是否允许更高分的 VR seed 替代低分的 VR seed（两个 VR seed 冲突时）",
    )
    fallback_to_vr_baseline: bool = Field(
        default=True,
        description="图增强无效时是否 fallback 到 VR baseline（而非 Zero-shot）",
    )
```

### 6.7 FallbackMetadata（降级元数据）

```python
class FallbackMetadata(BaseModel):
    """降级路由元数据，记录 fallback 触发原因和目标。"""

    fallback_target: str = Field(
        ...,
        description="降级目标：vr_baseline | zero_shot | cached",
    )
    fallback_reason: str = Field(
        ...,
        description="降级原因：enhancement_score_le_zero | graph_db_unavailable | vector_db_unavailable | pipeline_error",
    )
    vr_baseline_skills: list[str] = Field(
        default_factory=list,
        description="VR baseline 的 skill IDs（fallback 后使用这些技能）",
    )
    original_pipeline_skills: list[str] = Field(
        default_factory=list,
        description="原始管线尝试选出的 skill IDs（被丢弃）",
    )
```

---

## 7. Session 数据结构

### 7.1 AgentSession（Agent 会话）

#### 7.1.1 JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://graphskill.io/schemas/agent-session-v1.json",
  "title": "AgentSession",
  "description": "Agent Session 数据结构",
  "type": "object",
  "required": ["session_id", "agent_id", "created_at", "expires_at"],
  "properties": {
    "session_id": {
      "type": "string",
      "description": "Session 唯一 ID"
    },
    "agent_id": {
      "type": "string",
      "description": "Agent 实例 ID"
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "description": "创建时间"
    },
    "expires_at": {
      "type": "string",
      "format": "date-time",
      "description": "过期时间"
    },
    "current_context": {
      "type": "object",
      "description": "当前技能上下文",
      "properties": {
        "skills": {"type": "array", "items": {"type": "string"}},
        "routing_mode": {"type": "string"},
        "last_routing_time": {"type": "string", "format": "date-time"},
        "token_count": {"type": "integer"},
        "query_hash": {"type": "string"}
      }
    },
    "context_history": {
      "type": "array",
      "items": {"type": "object"},
      "description": "上下文变更历史"
    },
    "authorization": {
      "type": "object",
      "description": "Session 授权范围",
      "properties": {
        "authorized_permissions": {"type": "array"},
        "authorized_skills": {"type": "array", "items": {"type": "string"}},
        "expires_at": {"type": "string", "format": "date-time"}
      }
    },
    "execution_state": {
      "type": "object",
      "description": "执行状态",
      "properties": {
        "status": {"type": "string", "enum": ["idle", "executing", "waiting", "error"]},
        "current_skill": {"type": "string"},
        "pending_actions": {"type": "array"},
        "error_history": {"type": "array"}
      }
    },
    "skill_call_history": {
      "type": "array",
      "items": {"type": "object"},
      "description": "技能调用历史"
    },
    "metadata": {
      "type": "object",
      "description": "Session 元数据"
    }
  }
}
```

#### 7.1.2 Python 类定义

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum

class ExecutionStatus(Enum):
    """
    执行状态枚举。
    """
    IDLE = "idle"
    EXECUTING = "executing"
    WAITING = "waiting"
    ERROR = "error"


@dataclass
class SessionContext:
    """
    Session 技能上下文。
    """
    
    skills: List[str] = field(default_factory=list)
    routing_mode: str = "none"
    last_routing_time: Optional[datetime] = None
    token_count: int = 0
    query_hash: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "skills": self.skills,
            "routing_mode": self.routing_mode,
            "last_routing_time": self.last_routing_time.isoformat() if self.last_routing_time else None,
            "token_count": self.token_count,
            "query_hash": self.query_hash
        }


@dataclass
class SessionAuthorization:
    """
    Session 授权范围。
    """
    
    session_id: str
    authorized_permissions: List[Dict] = field(default_factory=list)
    authorized_skills: List[str] = field(default_factory=list)
    expires_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "authorized_permissions": self.authorized_permissions,
            "authorized_skills": self.authorized_skills,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }


@dataclass
class ExecutionState:
    """
    执行状态。
    """
    
    status: ExecutionStatus = ExecutionStatus.IDLE
    current_skill: Optional[str] = None
    pending_actions: List[Dict] = field(default_factory=list)
    error_history: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "current_skill": self.current_skill,
            "pending_actions": self.pending_actions,
            "error_history": self.error_history
        }


@dataclass
class AgentSession:
    """
    Agent Session 数据结构。
    """
    
    session_id: str
    agent_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow())
    
    current_context: SessionContext = field(default_factory=SessionContext)
    context_history: List[Dict] = field(default_factory=list)
    authorization: SessionAuthorization = field(default_factory=lambda: SessionAuthorization(session_id=""))
    execution_state: ExecutionState = field(default_factory=ExecutionState)
    skill_call_history: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    
    def to_json(self) -> str:
        import json
        return json.dumps({
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "current_context": self.current_context.to_dict(),
            "context_history": self.context_history,
            "authorization": self.authorization.to_dict(),
            "execution_state": self.execution_state.to_dict(),
            "skill_call_history": self.skill_call_history,
            "metadata": self.metadata
        })
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AgentSession':
        import json
        data = json.loads(json_str)
        return cls(
            session_id=data["session_id"],
            agent_id=data["agent_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            current_context=SessionContext(**data.get("current_context", {})),
            context_history=data.get("context_history", []),
            authorization=SessionAuthorization(**data.get("authorization", {})),
            execution_state=ExecutionState(**data.get("execution_state", {})),
            skill_call_history=data.get("skill_call_history", []),
            metadata=data.get("metadata", {})
        )
```

---

## 8. 错误数据结构

### 8.1 ErrorResponse（错误响应）

#### 8.1.1 JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://graphskill.io/schemas/error-response-v1.json",
  "title": "ErrorResponse",
  "description": "API 错误响应数据结构",
  "type": "object",
  "required": ["error", "meta"],
  "properties": {
    "error": {
      "type": "object",
      "required": ["type", "code", "message"],
      "properties": {
        "type": {
          "type": "string",
          "description": "错误类型名称"
        },
        "code": {
          "type": "string",
          "pattern": "^\\d{4}$",
          "description": "错误码"
        },
        "message": {
          "type": "string",
          "description": "错误消息"
        },
        "details": {
          "type": "object",
          "description": "错误详情"
        },
        "suggestion": {
          "type": "string",
          "description": "修复建议"
        }
      }
    },
    "meta": {
      "type": "object",
      "required": ["request_id", "timestamp", "version"],
      "properties": {
        "request_id": {"type": "string"},
        "timestamp": {"type": "string", "format": "date-time"},
        "version": {"type": "string"}
      }
    }
  }
}
```

#### 8.1.2 Python 类定义

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

@dataclass
class ErrorDetail:
    """
    错误详情数据结构。
    """
    
    type: str
    code: str
    message: str
    details: Dict = field(default_factory=dict)
    suggestion: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "suggestion": self.suggestion
        }


@dataclass
class ResponseMeta:
    """
    响应元数据。
    """
    
    request_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    version: str = "v1"
    
    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version
        }


@dataclass
class ErrorResponse:
    """
    API 错误响应数据结构。
    """
    
    error: ErrorDetail
    meta: ResponseMeta
    
    def to_dict(self) -> dict:
        return {
            "error": self.error.to_dict(),
            "meta": self.meta.to_dict()
        }
    
    def to_agent_format(self) -> str:
        """
        转换为 Agent 可理解的格式。
        """
        return f"""
[ERROR] {self.error.type}
Code: {self.error.code}
Message: {self.error.message}
Details: {self.error.details}
Suggestion: {self.error.suggestion or 'No suggestion available'}

Please adjust your plan based on this error.
"""
```

### 8.2 错误码定义表

```python
from enum import Enum

class ErrorCode(Enum):
    """
    错误码枚举。
    """
    
    # 客户端错误 (1000-1999)
    INVALID_REQUEST = "1001"
    MISSING_REQUIRED_FIELD = "1002"
    INVALID_SKILL_ID_FORMAT = "1003"
    INVALID_VERSION_FORMAT = "1004"
    INVALID_PERMISSION_FORMAT = "1005"
    
    AUTHENTICATION_FAILED = "1010"
    TOKEN_EXPIRED = "1011"
    INVALID_TOKEN = "1012"
    
    PERMISSION_DENIED = "1020"
    SKILL_NOT_IN_CONTEXT = "1021"
    SESSION_NOT_AUTHORIZED = "1022"
    
    RATE_LIMIT_EXCEEDED = "1030"
    
    RESOURCE_NOT_FOUND = "1040"
    SKILL_NOT_FOUND = "1041"
    SESSION_NOT_FOUND = "1042"
    
    RESOURCE_ALREADY_EXISTS = "1050"
    SKILL_ID_EXISTS = "1051"
    EDGE_EXISTS = "1052"
    
    # 服务端错误 (2000-2999)
    INTERNAL_ERROR = "2001"
    ROUTING_ERROR = "2002"
    DATABASE_ERROR = "2003"
    
    SERVICE_UNAVAILABLE = "2010"
    SERVICE_DEGRADED = "2011"
    
    # 业务错误 (3000-3999)
    TOPOLOGY_CYCLE_ERROR = "3001"
    SCHEMA_VALIDATION_ERROR = "3002"
    DAG_VALIDATION_ERROR = "3003"
    CONFLICT_PRUNING_ERROR = "3004"
    TOKEN_BUDGET_EXCEEDED = "3005"
    
    # 外部依赖错误 (4000-4999)
    GRAPH_DB_ERROR = "4001"
    VECTOR_DB_ERROR = "4002"
    REDIS_ERROR = "4003"
    KAFKA_ERROR = "4004"
    LLM_API_ERROR = "4005"


# 错误码与 HTTP 状态码映射
ERROR_CODE_HTTP_STATUS = {
    # 客户端错误
    "1001": 400, "1002": 400, "1003": 400, "1004": 400, "1005": 400,
    "1010": 401, "1011": 401, "1012": 401,
    "1020": 403, "1021": 403, "1022": 403,
    "1030": 429,
    "1040": 404, "1041": 404, "1042": 404,
    "1050": 409, "1051": 409, "1052": 409,
    
    # 服务端错误
    "2001": 500, "2002": 500, "2003": 500,
    "2010": 503, "2011": 503,
    
    # 业务错误
    "3001": 422, "3002": 400, "3003": 422, "3004": 500, "3005": 400,
    
    # 外部依赖错误
    "4001": 503, "4002": 503, "4003": 503, "4004": 503, "4005": 503,
}
```

---

## 9. Protocol Buffers 定义

### 9.1 完整 Proto 文件

参见 [RFC-07: API 接口规范](RFC-07-api-interface-specification.md) 第 4.1 节的完整 Proto 定义。

### 9.2 Proto 编译规范

```bash
# Python 编译
protoc --python_out=./src/graphskill/v1 graphskill.proto

# Go 编译
protoc --go_out=./pkg/api/v1 graphskill.proto

# Java 编译
protoc --java_out=./src/main/java/io/graphskill/api/v1 graphskill.proto
```

---

## 10. 序列化规范

### 10.1 JSON 序列化规范

| 规则 | 描述 |
|------|------|
| **日期格式** | MUST 使用 ISO 8601 格式 (`2026-04-12T10:00:00Z`) |
| **枚举值** | MUST 序列化为字符串值（而非数字） |
| **空值处理** | SHOULD 使用 `null` 表示空值，而非省略字段 |
| **数字精度** | Float MUST 保留 6 位有效数字 |
| **数组空值** | 空数组 MUST 序列化为 `[]`，而非 `null` |

### 10.2 Protobuf 序列化规范

| 规则 | 描述 |
|------|------|
| **字段编号** | MUST 从 1 开始，保留 1-15 给高频字段 |
| **枚举定义** | MUST 包含 `UNKNOWN = 0` 作为默认值 |
| **日期处理** | MUST 使用 `int64` 存储 Unix timestamp |
| **可选字段** | SHOULD 使用 `optional` 关键字标记可选字段 |

### 10.3 序列化性能要求

| 格式 | 序列化延迟 | 反序列化延迟 | 数据大小 |
|------|------------|--------------|----------|
| **JSON** | < 5ms | < 5ms | 较大 |
| **Protobuf** | < 1ms | < 1ms | 较小 |
| **MsgPack** | < 2ms | < 2ms | 中等 |

---

## 11. 版本历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|----------|------|
| 1.0.0 | 2026-04-12 | 初始版本发布 | GraphSkill Architecture Team |
| 2.0.0 | 2026-04-17 | **VR-First Architecture 新增数据契约**：新增 EnhancementResult、VRSeedProtectionConfig、FallbackMetadata；记录 VR→Graph 增量变化；GS ≥ VR fallback 保证验证 | GraphSkill Architecture Team |

---

**文档结束**

*本文档是 GraphSkill 系统的数据契约单一真相来源。所有其他 RFC 文档 MUST 引用本文档的数据结构定义。*