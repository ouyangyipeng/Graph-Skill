# RFC-01: 数据规范与存储层设计

**文档编号:** RFC-01  
**版本:** 1.0.0  
**状态:** 正式发布  
**最后更新:** 2026-04-12  
**作者:** GraphSkill Architecture Team  
**分类:** 架构规范 - 数据层  
**依赖:** RFC-00, RFC-08

---

## 目录

1. [概述](#1-概述)
2. [技能清单 Schema 规范](#2-技能清单-schema-规范)
3. [图数据库数据模型](#3-图数据库数据模型)
4. [向量数据库 Schema](#4-向量数据库-schema)
5. [图-向量双写一致性保障](#5-图-向量双写一致性保障)
6. [数据生命周期管理](#6-数据生命周期管理)
7. [索引设计规范](#7-索引设计规范)
8. [数据迁移策略](#8-数据迁移策略)
9. [版本历史](#9-版本历史)

---

## 1. 概述

### 1.1 文档目的

本文档定义 GraphSkill 系统的数据规范与存储层设计，涵盖技能清单 Schema、图数据库数据模型、向量数据库 Schema、双写一致性保障机制、数据生命周期管理、索引设计以及数据迁移策略。

### 1.2 适用范围

本文档适用于：
- 数据架构师：设计数据模型与存储策略
- 后端开发工程师：实现数据访问层
- 数据库管理员：配置与维护数据库实例
- DevOps 工程师：规划数据迁移与备份策略

### 1.3 设计原则

| 原则 | 描述 |
|------|------|
| **Schema 严格性** | 所有数据 MUST 遵循本文档定义的 Schema，系统 MUST 拒收不合规数据 |
| **双写一致性** | 图数据库与向量数据库 MUST 保持强一致性，不允许数据漂移 |
| **可追溯性** | 所有数据变更 MUST 记录审计日志，支持历史追溯 |
| **可恢复性** | 数据 MUST 支持从备份恢复，RPO < 5分钟 |

---

## 2. 技能清单 Schema 规范

### 2.1 YAML Frontmatter 规范

每个 `SKILL.md` 文件的 YAML Frontmatter MUST 包含以下字段。系统 MUST 拒收不符合规范的文件。

#### 2.1.1 必填字段

| 字段名 | 类型 | 约束 | 描述 |
|--------|------|------|------|
| `skill_id` | String | 正则: `^[a-z0-9_-]+:[a-z0-9_-]+$` | 全局唯一标识符，格式为 `namespace:action` |
| `version` | String | SemVer 2.0.0 | 语义化版本号，格式为 `MAJOR.MINOR.PATCH` |
| `intent_description` | String | 长度: 50-500 字符 | 面向 LLM 的自然语言意图描述，用于生成向量 Embedding |
| `permissions` | List[String] | 非空 | 细粒度权限声明列表 |

#### 2.1.2 可选字段

| 字段名 | 类型 | 约束 | 描述 |
|--------|------|------|------|
| `trigger_conditions` | Dict | - | 触发前置环境状态断言 |
| `topology_hints` | Dict | - | 人工声明的拓扑提示 |
| `author` | String | - | 技能作者标识 |
| `created_at` | String | ISO 8601 | 技能创建时间 |
| `updated_at` | String | ISO 8601 | 技能最后更新时间 |
| `deprecated` | Boolean | 默认 false | 软删除标记 |
| `tags` | List[String] | - | 技能分类标签 |

#### 2.1.3 topology_hints 子字段

| 字段名 | 类型 | 描述 |
|--------|------|------|
| `requires` | List[String] | 强依赖技能 ID 列表 |
| `conflicts_with` | List[String] | 互斥技能 ID 列表 |
| `substitutes` | List[String] | 替代技能 ID 列表 |
| `enhances` | List[String] | 增强技能 ID 列表 |

### 2.2 完整 Schema 定义 (JSON Schema)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://graphskill.io/schemas/skill-manifest-v1.json",
  "title": "Skill Manifest Schema",
  "description": "GraphSkill 技能清单元数据规范",
  "type": "object",
  "required": ["skill_id", "version", "intent_description", "permissions"],
  "additionalProperties": false,
  "properties": {
    "skill_id": {
      "type": "string",
      "pattern": "^[a-z0-9_-]+:[a-z0-9_-]+$",
      "description": "全局唯一技能标识符，格式: namespace:action",
      "examples": ["git:commit_changes", "db:query_postgres", "fs:read_file"]
    },
    "version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+\\.\\d+(-[a-zA-Z0-9]+)?$",
      "description": "语义化版本号 (SemVer 2.0.0)",
      "examples": ["1.0.0", "2.1.3-beta", "0.5.0-alpha.1"]
    },
    "intent_description": {
      "type": "string",
      "minLength": 50,
      "maxLength": 500,
      "description": "面向 LLM 的意图描述，用于向量生成",
      "examples": ["执行 Git 提交操作，将当前工作区的变更提交到本地仓库。需要先配置 Git 用户信息，支持添加提交消息。"]
    },
    "permissions": {
      "type": "array",
      "items": {
        "type": "string",
        "pattern": "^[a-z]+:[a-z]+(:[a-zA-Z0-9_/-]+)?$"
      },
      "minItems": 1,
      "description": "细粒度权限声明列表",
      "examples": [
        ["fs:read:/tmp", "fs:write:/tmp", "net:github.com"],
        ["db:query:postgres", "db:execute:mysql"]
      ]
    },
    "trigger_conditions": {
      "type": "object",
      "description": "触发前置环境状态断言",
      "additionalProperties": {
        "type": ["string", "boolean", "number", "object"]
      },
      "properties": {
        "env_vars": {
          "type": "object",
          "description": "必需的环境变量",
          "additionalProperties": {"type": "string"}
        },
        "file_exists": {
          "type": "array",
          "items": {"type": "string"},
          "description": "必需存在的文件路径"
        },
        "service_available": {
          "type": "array",
          "items": {"type": "string"},
          "description": "必需可用的服务"
        }
      }
    },
    "topology_hints": {
      "type": "object",
      "description": "人工声明的拓扑关系提示",
      "properties": {
        "requires": {
          "type": "array",
          "items": {
            "type": "string",
            "pattern": "^[a-z0-9_-]+:[a-z0-9_-]+$"
          },
          "description": "强依赖技能 ID 列表"
        },
        "conflicts_with": {
          "type": "array",
          "items": {
            "type": "string",
            "pattern": "^[a-z0-9_-]+:[a-z0-9_-]+$"
          },
          "description": "互斥技能 ID 列表"
        },
        "substitutes": {
          "type": "array",
          "items": {
            "type": "string",
            "pattern": "^[a-z0-9_-]+:[a-z0-9_-]+$"
          },
          "description": "替代技能 ID 列表"
        },
        "enhances": {
          "type": "array",
          "items": {
            "type": "string",
            "pattern": "^[a-z0-9_-]+:[a-z0-9_-]+$"
          },
          "description": "增强技能 ID 列表"
        }
      }
    },
    "author": {
      "type": "string",
      "description": "技能作者标识"
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "description": "技能创建时间 (ISO 8601)"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time",
      "description": "技能最后更新时间 (ISO 8601)"
    },
    "deprecated": {
      "type": "boolean",
      "default": false,
      "description": "软删除标记"
    },
    "tags": {
      "type": "array",
      "items": {"type": "string"},
      "description": "技能分类标签"
    }
  }
}
```

### 2.3 示例 Frontmatter

```yaml
---
skill_id: git:commit_changes
version: 1.2.0
intent_description: |
  执行 Git 提交操作，将当前工作区的变更提交到本地仓库。
  此技能需要先配置 Git 用户信息（name 和 email）。
  支持自定义提交消息，默认消息为 "Update changes"。
  执行前会检查是否有未暂存的文件，并提示用户确认。
permissions:
  - fs:read:/tmp
  - fs:write:/tmp
  - net:github.com
  - exec:git
trigger_conditions:
  env_vars:
    GIT_AUTHOR_NAME: "required"
    GIT_AUTHOR_EMAIL: "required"
  file_exists:
    - ".git"
topology_hints:
  requires:
    - git:configure
    - git:stage_files
  conflicts_with:
    - git:reset_hard
    - env:clean_workspace
  enhances:
    - git:push_remote
  substitutes:
    - git:commit_amend
author: graphskill-team
created_at: 2026-01-15T10:00:00Z
updated_at: 2026-04-10T14:30:00Z
tags:
  - git
  - version-control
  - commit
---
```

### 2.4 权限声明规范

权限声明 MUST 遵循以下格式：

```
<resource_type>:<action>:<resource_path>
```

| 资源类型 | 可用动作 | 资源路径示例 |
|----------|----------|--------------|
| `fs` | `read`, `write`, `delete`, `execute` | `/tmp`, `/home/user/project` |
| `net` | `connect`, `listen` | `github.com`, `api.example.com:443` |
| `db` | `query`, `execute`, `admin` | `postgres`, `mysql://localhost` |
| `exec` | `run` | `git`, `python`, `bash` |
| `env` | `read`, `write`, `delete` | `PATH`, `HOME`, `API_KEY` |

**权限校验逻辑：**
- Agent Session MUST 持有技能声明的所有权限才能执行
- 权限路径支持通配符：`fs:read:/tmp/*` 表示 `/tmp` 下所有文件
- 权限 MUST NOT 超越 Agent Session 的授权范围

---

## 3. 图数据库数据模型

### 3.1 节点定义 (SkillNode)

图数据库中的核心节点类型为 `SkillNode`，表示单个技能实体。

#### 3.1.1 节点属性 Schema

| 属性名 | 类型 | 约束 | 描述 |
|--------|------|------|------|
| `uid` | String | PRIMARY KEY, UNIQUE | 映射 `skill_id`，全局唯一 |
| `embedding_id` | String | FOREIGN KEY | 映射至向量数据库的主键 |
| `version` | String | NOT NULL | 技能版本号 |
| `intent_description` | String | NOT NULL | 意图描述文本 |
| `permissions` | List[String] | NOT NULL | 权限声明列表 |
| `trigger_conditions` | Dict | OPTIONAL | 触发条件 |
| `execution_success_rate` | Float | DEFAULT 1.0, RANGE [0.0, 1.0] | 运行时成功率统计 |
| `execution_count` | Integer | DEFAULT 0 | 累计执行次数 |
| `last_execution_time` | DateTime | OPTIONAL | 最后执行时间 |
| `is_deprecated` | Boolean | DEFAULT false | 软删除标记 |
| `created_at` | DateTime | NOT NULL | 创建时间 |
| `updated_at` | DateTime | NOT NULL | 更新时间 |
| `author` | String | OPTIONAL | 作者标识 |
| `tags` | List[String] | OPTIONAL | 分类标签 |
| `verified_by_human` | Boolean | DEFAULT false | 人工审核标记 |

#### 3.1.2 Cypher 创建语句示例

```cypher
CREATE (s:SkillNode {
  uid: "git:commit_changes",
  embedding_id: "vec_abc123",
  version: "1.2.0",
  intent_description: "执行 Git 提交操作...",
  permissions: ["fs:read:/tmp", "fs:write:/tmp", "net:github.com", "exec:git"],
  trigger_conditions: {
    env_vars: {GIT_AUTHOR_NAME: "required", GIT_AUTHOR_EMAIL: "required"},
    file_exists: [".git"]
  },
  execution_success_rate: 1.0,
  execution_count: 0,
  is_deprecated: false,
  created_at: datetime("2026-01-15T10:00:00Z"),
  updated_at: datetime("2026-04-10T14:30:00Z"),
  author: "graphskill-team",
  tags: ["git", "version-control", "commit"],
  verified_by_human: true
})
```

### 3.2 边定义规范

图模型定义四类核心边类型，每类边具有特定的语义和属性。

#### 3.2.1 REQUIRES 边（依赖边）

**语义：** 有向边，表示源节点依赖目标节点。若调度源节点，MUST 同时载入目标节点。

| 属性名 | 类型 | 约束 | 描述 |
|--------|------|------|------|
| `weight` | Float | DEFAULT 1.0, RANGE [0.0, 1.0] | 依赖强度权重 |
| `is_hard` | Boolean | DEFAULT true | 是否为硬依赖（强制载入） |
| `verified_by_human` | Boolean | DEFAULT false | 是否经人工审核 |
| `confidence` | Float | OPTIONAL, RANGE [0.0, 1.0] | LLM 推演置信度 |
| `created_at` | DateTime | NOT NULL | 边创建时间 |

**Cypher 创建语句示例：**

```cypher
// 硬依赖：git:commit_changes 强依赖 git:configure
MATCH (a:SkillNode {uid: "git:commit_changes"})
MATCH (b:SkillNode {uid: "git:configure"})
CREATE (a)-[:REQUIRES {
  weight: 1.0,
  is_hard: true,
  verified_by_human: true,
  created_at: datetime()
}]->(b)

// 软依赖：git:commit_changes 软依赖 git:stage_files
MATCH (a:SkillNode {uid: "git:commit_changes"})
MATCH (b:SkillNode {uid: "git:stage_files"})
CREATE (a)-[:REQUIRES {
  weight: 0.7,
  is_hard: false,
  verified_by_human: true,
  created_at: datetime()
}]->(b)
```

**约束规则：**
- REQUIRES 边构成的子图 MUST 是有向无环图（DAG）
- 系统 MUST 在每次写入前执行环路检测
- 若检测到环路，系统 MUST 抛出 `TopologyCycleException` 并拒绝写入

#### 3.2.2 CONFLICTS_WITH 边（互斥边）

**语义：** 无向边，表示两个技能逻辑互斥，MUST NOT 同时出现在同一上下文中。

| 属性名 | 类型 | 约束 | 描述 |
|--------|------|------|------|
| `severity` | Integer | RANGE [1, 5] | 冲突严重级别（1=警告, 5=致命死锁） |
| `reason` | String | OPTIONAL | 冲突原因描述 |
| `verified_by_human` | Boolean | DEFAULT false | 是否经人工审核 |
| `auto_discovered` | Boolean | DEFAULT false | 是否由系统自动发现 |
| `created_at` | DateTime | NOT NULL | 边创建时间 |

**严重级别定义：**

| 级别 | 名称 | 描述 | 处理策略 |
|------|------|------|----------|
| 1 | WARNING | 轻微冲突，可能导致性能下降 | SHOULD 避免同时加载 |
| 2 | MODERATE | 中等冲突，可能导致执行失败 | SHOULD NOT 同时加载 |
| 3 | SIGNIFICANT | 显著冲突，可能导致数据损坏 | MUST NOT 同时加载 |
| 4 | CRITICAL | 严重冲突，可能导致系统崩溃 | MUST NOT 同时加载 |
| 5 | FATAL | 致命冲突，必然导致死锁 | MUST NOT 同时加载，系统 MUST 拒绝 |

**Cypher 创建语句示例：**

```cypher
// 致命互斥：git:commit_changes 与 git:reset_hard
MATCH (a:SkillNode {uid: "git:commit_changes"})
MATCH (b:SkillNode {uid: "git:reset_hard"})
CREATE (a)-[:CONFLICTS_WITH {
  severity: 5,
  reason: "提交操作与硬重置操作逻辑互斥，同时执行将导致数据丢失",
  verified_by_human: true,
  auto_discovered: false,
  created_at: datetime()
}]->(b)
```

#### 3.2.3 SUBSTITUTES 边（替代边）

**语义：** 无向边，表示两个技能功能相似，同一子图中 SHOULD 只保留其一。

| 属性名 | 类型 | 约束 | 描述 |
|--------|------|------|------|
| `similarity` | Float | RANGE [0.0, 1.0] | 功能相似度 |
| `preferred` | String | OPTIONAL | 推荐优先使用的技能 ID |
| `verified_by_human` | Boolean | DEFAULT false | 是否经人工审核 |
| `created_at` | DateTime | NOT NULL | 边创建时间 |

**Cypher 创建语句示例：**

```cypher
// 替代关系：git:commit_changes 与 git:commit_amend
MATCH (a:SkillNode {uid: "git:commit_changes"})
MATCH (b:SkillNode {uid: "git:commit_amend"})
CREATE (a)-[:SUBSTITUTES {
  similarity: 0.85,
  preferred: "git:commit_changes",
  verified_by_human: true,
  created_at: datetime()
}]->(b)
```

#### 3.2.4 ENHANCES 边（增强边）

**语义：** 有向边，表示目标节点能提升源节点的执行成功率，属于软依赖。

| 属性名 | 类型 | 约束 | 描述 |
|--------|------|------|------|
| `weight` | Float | DEFAULT 0.5, RANGE [0.0, 1.0] | 增强效果权重 |
| `success_rate_boost` | Float | OPTIONAL, RANGE [0.0, 0.5] | 预期成功率提升幅度 |
| `verified_by_human` | Boolean | DEFAULT false | 是否经人工审核 |
| `auto_discovered` | Boolean | DEFAULT false | 是否由系统自动发现 |
| `co_occurrence_count` | Integer | DEFAULT 0 | 共现次数统计 |
| `created_at` | DateTime | NOT NULL | 边创建时间 |

**Cypher 创建语句示例：**

```cypher
// 增强关系：git:push_remote 增强 git:commit_changes
MATCH (a:SkillNode {uid: "git:commit_changes"})
MATCH (b:SkillNode {uid: "git:push_remote"})
CREATE (a)-[:ENHANCES {
  weight: 0.3,
  success_rate_boost: 0.1,
  verified_by_human: false,
  auto_discovered: true,
  co_occurrence_count: 150,
  created_at: datetime()
}]->(b)
```

### 3.3 图结构约束

#### 3.3.1 DAG 约束（REQUIRES 子图）

REQUIRES 边构成的子图 MUST 是有向无环图（DAG）。系统 MUST 在以下时机执行环路检测：

1. 新建 REQUIRES 边时
2. 更新 REQUIRES 边的 `is_hard` 属性为 `true` 时
3. 批量导入技能数据时
4. 定期后台巡检（RECOMMENDED 每小时）

**环路检测算法：** 采用 Tarjan 算法或 DFS 变体，时间复杂度 O(V+E)。

**检测到环路时的处理：**
```python
class TopologyCycleException(Exception):
    """拓扑环路异常，REQUIRES 子图检测到环路"""
    def __init__(self, cycle_path: List[str]):
        self.cycle_path = cycle_path
        super().__init__(
            f"REQUIRES subgraph contains cycle: {cycle_path}. "
            f"Operation rejected to prevent deadlock."
        )
```

#### 3.3.2 节点唯一性约束

系统 MUST 保证 `uid` 属性的全局唯一性：

```cypher
// Neo4j 唯一性约束
CREATE CONSTRAINT skill_node_uid_unique IF NOT EXISTS
FOR (s:SkillNode) REQUIRE s.uid IS UNIQUE;
```

#### 3.3.3 边完整性约束

系统 SHOULD 保证边的引用完整性：
- 创建边时，源节点和目标节点 MUST 已存在
- 删除节点时，系统 MUST 同时删除所有关联边

---

## 4. 向量数据库 Schema

### 4.1 Collection 定义

向量数据库 MUST 创建专用的 Collection 用于存储技能向量。

#### 4.1.1 Collection Schema

| 字段名 | 类型 | 约束 | 描述 |
|--------|------|------|------|
| `id` | String | PRIMARY KEY | 向量唯一标识符，与图数据库 `embedding_id` 关联 |
| `skill_id` | String | NOT NULL, INDEXED | 技能 ID，用于关联查询 |
| `vector` | Float Array | DIMENSION: 1536 (或配置值) | 技能描述向量嵌入 |
| `intent_description` | String | NOT NULL | 原始意图描述文本（用于调试） |
| `version` | String | NOT NULL | 技能版本号 |
| `created_at` | DateTime | NOT NULL | 创建时间 |
| `updated_at` | DateTime | NOT NULL | 更新时间 |

#### 4.1.2 Milvus Collection 创建示例

```python
from pymilvus import Collection, CollectionSchema, FieldSchema, DataType

fields = [
    FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
    FieldSchema(name="skill_id", dtype=DataType.VARCHAR, max_length=128),
    FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=1536),
    FieldSchema(name="intent_description", dtype=DataType.VARCHAR, max_length=512),
    FieldSchema(name="version", dtype=DataType.VARCHAR, max_length=32),
    FieldSchema(name="created_at", dtype=DataType.INT64),  # Unix timestamp
    FieldSchema(name="updated_at", dtype=DataType.INT64),
]

schema = CollectionSchema(
    fields=fields,
    description="GraphSkill 技能向量存储",
    enable_dynamic_field=False
)

collection = Collection(name="skill_vectors", schema=schema)

# 创建 HNSW 索引
index_params = {
    "metric_type": "COSINE",
    "index_type": "HNSW",
    "params": {
        "M": 16,           # 每层最大连接数
        "efConstruction": 200  # 构建时搜索范围
    }
}
collection.create_index(field_name="vector", index_params=index_params)

# 创建 skill_id 索引（用于关联查询）
collection.create_index(
    field_name="skill_id",
    index_params={"index_type": "Trie"}
)
```

### 4.2 向量维度规范

向量维度 MUST 与 Embedding 模型输出维度一致：

| Embedding 模型 | 向量维度 | 推荐场景 |
|----------------|----------|----------|
| `text-embedding-3-small` | 1536 | 默认推荐，性价比最优 |
| `text-embedding-3-large` | 3072 | 高精度场景 |
| `text-embedding-ada-002` | 1536 | 兼容旧版 |
| 自定义模型 | 可配置 | 特殊需求 |

**配置规范：** 向量维度 MUST 在系统初始化时配置，运行时 MUST NOT 动态变更。

### 4.3 索引参数规范

HNSW 索引 MUST 配置以下参数：

| 参数 | 推荐值 | 范围 | 描述 |
|------|--------|------|------|
| `M` | 16 | [4, 64] | 每层最大连接数，影响召回精度与内存占用 |
| `efConstruction` | 200 | [100, 500] | 构建时搜索范围，影响构建质量与时间 |
| `ef` (查询时) | 64 | [efConstruction/2, efConstruction] | 查询时搜索范围，影响查询精度与延迟 |

**性能权衡：**
- `M` 增大 → 召召精度提升，内存占用增加
- `efConstruction` 增大 → 构建质量提升，构建时间增加
- `ef` 增大 → 查询精度提升，查询延迟增加

---

## 5. 图-向量双写一致性保障

### 5.1 双写事务流程

所有涉及图数据库与向量数据库的写入操作 MUST 遵循以下事务流程：

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Dual-Write Transaction Flow                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Step 1: Generate Embedding                                         │
│  ┌─────────────┐                                                    │
│  │ LLM API     │──▶ vector = embed(intent_description)              │
│  └─────────────┘                                                    │
│         │                                                           │
│         ▼                                                           │
│  Step 2: Begin Transaction                                          │
│  ┌─────────────┐                                                    │
│  │ Transaction │──▶ tx = begin_distributed_transaction()            │
│  │ Manager     │                                                    │
│  └─────────────┘                                                    │
│         │                                                           │
│         ▼                                                           │
│  Step 3: Write Vector DB                                            │
│  ┌─────────────┐                                                    │
│  │ Vector DB   │──▶ vector_id = insert_vector(vector, metadata)     │
│  └─────────────┘                                                    │
│         │                                                           │
│         ▼                                                           │
│  Step 4: Write Graph DB                                             │
│  ┌─────────────┐                                                    │
│  │ Graph DB    │──▶ create_node(skill_id, vector_id, ...)           │
│  └─────────────┘                                                    │
│         │                                                           │
│         ▼                                                           │
│  Step 5: Commit Transaction                                         │
│  ┌─────────────┐                                                    │
│  │ Transaction │──▶ commit(tx) OR rollback(tx)                      │
│  │ Manager     │                                                    │
│  └─────────────┘                                                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 写入顺序规范

写入操作 MUST 遵循以下顺序：

1. **生成 Embedding 向量**：调用 LLM API 生成技能描述向量
2. **开启分布式事务**：获取事务 ID
3. **写入向量数据库**：插入向量记录，获取返回的 `vector_id`
4. **写入图数据库**：创建节点并关联 `vector_id`
5. **提交事务**：若第 4 步失败，执行回滚并触发补偿删除

### 5.3 失败补偿机制

当双写事务部分失败时，系统 MUST 执行补偿操作：

| 失败场景 | 补偿策略 |
|----------|----------|
| Step 3 失败（向量写入失败） | 直接回滚事务，无需补偿 |
| Step 4 失败（图写入失败） | 通过 MQ 触发向量数据库的异步补偿删除 |
| Step 5 失败（提交失败） | 回滚两边数据库，通过 MQ 触发补偿清理 |

**补偿删除 MQ 消息格式：**

```json
{
  "message_type": "compensation_delete",
  "target": "vector_db",
  "vector_id": "vec_abc123",
  "skill_id": "git:commit_changes",
  "reason": "graph_db_write_failed",
  "timestamp": "2026-04-12T10:00:00Z",
  "retry_count": 0,
  "max_retries": 3
}
```

### 5.4 最终一致性保障

对于无法实现强一致性的场景（如跨数据中心），系统 MUST 实现最终一致性：

1. **定期对账作业**：每小时执行一次图-向量数据对账
2. **差异检测**：比对两边的 `skill_id` 列表，识别不一致记录
3. **自动修复**：根据图数据库为准原则，修复向量数据库的漂移数据

**对账 SQL 示例（Neo4j + Milvus）：**

```cypher
// Neo4j: 获取所有 skill_id
MATCH (s:SkillNode) WHERE NOT s.is_deprecated
RETURN s.uid as skill_id, s.embedding_id as vector_id

// Milvus: 获取所有 skill_id
query_result = collection.query(
    expr="skill_id != ''",
    output_fields=["skill_id", "id"]
)

// 差异比对
graph_skill_ids = set([r["skill_id"] for r in neo4j_result])
vector_skill_ids = set([r["skill_id"] for r in milvus_result])

missing_in_vector = graph_skill_ids - vector_skill_ids  # 需补充
extra_in_vector = vector_skill_ids - graph_skill_ids    # 需删除
```

---

## 6. 数据生命周期管理

### 6.1 数据状态流转

技能数据 MUST 遵循以下状态流转模型：

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   PENDING   │────▶│   ACTIVE    │────▶│  DEPRECATED │────▶│   ARCHIVED  │
│  (待审核)   │     │  (活跃)     │     │  (已废弃)   │     │  (已归档)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  [人工审核]          [正常使用]          [软删除标记]         [物理删除]
  或自动审核          或更新版本          或替换升级          或永久保留
```

### 6.2 状态定义

| 状态 | 描述 | 可执行操作 |
|------|------|------------|
| `PENDING` | 新导入技能，待审核 | 仅可查询，不可路由 |
| `ACTIVE` | 审核通过，正常使用 | 可查询、可路由、可更新 |
| `DEPRECATED` | 已废弃，软删除标记 | 可查询，不可路由，可恢复 |
| `ARCHIVED` | 已归档，物理删除预备 | 仅可查询历史，不可恢复 |

### 6.3 数据保留策略

| 数据类型 | 保留周期 | 删除策略 |
|----------|----------|----------|
| ACTIVE 技能节点 | 永久保留 | 仅通过 DEPRECATED 流程删除 |
| DEPRECATED 技能节点 | 90 天 | 自动归档 |
| ARCHIVED 技能节点 | 30 天 | 物理删除 |
| 遥测日志 | 365 天 | 按时间自动清理 |
| 审计日志 | 永久保留 | 仅可手动清理 |

### 6.4 版本管理策略

技能版本 MUST 遵循 SemVer 2.0.0 规范：

| 版本变更类型 | 规则 | 示例 |
|--------------|------|------|
| MAJOR | 不兼容的 API 变更 | `1.0.0` → `2.0.0` |
| MINOR | 向后兼容的功能新增 | `1.0.0` → `1.1.0` |
| PATCH | 向后兼容的问题修复 | `1.0.0` → `1.0.1` |

**多版本共存策略：**
- 系统 MAY 同时存储同一技能的多个版本
- 路由时 SHOULD 默认使用最新 ACTIVE 版本
- 用户 MAY 指定特定版本进行路由

---

## 7. 索引设计规范

### 7.1 图数据库索引

#### 7.1.1 必需索引

| 索引名 | 类型 | 字段 | 用途 |
|--------|------|------|------|
| `skill_node_uid_unique` | UNIQUE | `uid` | 保证节点唯一性 |
| `skill_node_embedding_id` | BTREE | `embedding_id` | 关联向量查询 |
| `skill_node_is_deprecated` | BTREE | `is_deprecated` | 过滤废弃节点 |
| `skill_node_execution_success_rate` | BTREE | `execution_success_rate` | 按成功率排序 |

#### 7.1.2 Cypher 索引创建语句

```cypher
// 唯一性约束（同时创建索引）
CREATE CONSTRAINT skill_node_uid_unique IF NOT EXISTS
FOR (s:SkillNode) REQUIRE s.uid IS UNIQUE;

// 普通索引
CREATE INDEX skill_node_embedding_id IF NOT EXISTS
FOR (s:SkillNode) ON (s.embedding_id);

CREATE INDEX skill_node_is_deprecated IF NOT EXISTS
FOR (s:SkillNode) ON (s.is_deprecated);

CREATE INDEX skill_node_execution_success_rate IF NOT EXISTS
FOR (s:SkillNode) ON (s.execution_success_rate);

// 复合索引（用于路由查询）
CREATE INDEX skill_node_routing_composite IF NOT EXISTS
FOR (s:SkillNode) ON (s.is_deprecated, s.execution_success_rate);
```

### 7.2 向量数据库索引

#### 7.2.1 HNSW 索引参数

| 参数 | 生产环境推荐值 | 开发环境推荐值 |
|------|----------------|----------------|
| `M` | 16 | 8 |
| `efConstruction` | 200 | 100 |
| `metric_type` | COSINE | COSINE |

#### 7.2.2 辅助索引

| 索引名 | 类型 | 字段 | 用途 |
|--------|------|------|------|
| `skill_id_index` | Trie | `skill_id` | 关联查询 |
| `version_index` | Trie | `version` | 版本过滤 |

---

## 8. 数据迁移策略

### 8.1 迁移场景

| 场景 | 描述 | 迁移策略 |
|------|------|----------|
| 版本升级 | GraphSkill 版本升级导致 Schema 变更 | 滚动迁移，保持兼容性 |
| 数据中心迁移 | 跨数据中心数据迁移 | 全量导出 + 导入，验证一致性 |
| 数据库切换 | 从 Neo4j 切换到 Memgraph | Schema 转换 + 数据迁移 |
| 技能库导入 | 批量导入外部技能库 | 批量导入 + DAG 校验 |

### 8.2 迁移流程规范

数据迁移 MUST 遵循以下流程：

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  1. 准备    │────▶│  2. 导出    │────▶│  3. 导入    │────▶│  4. 验证    │
│  (备份)     │     │  (全量)     │     │  (增量)     │     │  (一致性)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  [停止写入]          [导出数据]          [导入数据]          [对账验证]
  [创建备份]          [记录位置]          [DAG校验]           [切换流量]
```

### 8.3 迁移工具规范

系统 MUST 提供以下迁移工具：

| 工具 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `graphskill-export` | 全量数据导出 | 数据库连接 | JSON/CSV 文件 |
| `graphskill-import` | 数据导入 | JSON/CSV 文件 | 数据库连接 |
| `graphskill-validate` | 数据一致性验证 | 两数据库连接 | 验证报告 |
| `graphskill-migrate` | 一站式迁移 | 配置文件 | 迁移日志 |

### 8.4 迁移数据格式

导出数据 MUST 使用以下 JSON 格式：

```json
{
  "export_version": "1.0",
  "export_time": "2026-04-12T10:00:00Z",
  "source_db": {
    "type": "neo4j",
    "version": "5.12.0",
    "node_count": 150,
    "edge_count": 320
  },
  "nodes": [
    {
      "uid": "git:commit_changes",
      "embedding_id": "vec_abc123",
      "version": "1.2.0",
      "intent_description": "...",
      "permissions": ["fs:read:/tmp", "..."],
      "execution_success_rate": 0.95,
      "is_deprecated": false,
      "created_at": "2026-01-15T10:00:00Z",
      "updated_at": "2026-04-10T14:30:00Z"
    }
  ],
  "edges": [
    {
      "source": "git:commit_changes",
      "target": "git:configure",
      "type": "REQUIRES",
      "properties": {
        "weight": 1.0,
        "is_hard": true,
        "verified_by_human": true
      }
    }
  ],
  "vectors": [
    {
      "id": "vec_abc123",
      "skill_id": "git:commit_changes",
      "vector": [0.123, 0.456, "..."],  // 1536 维
      "dimension": 1536
    }
  ]
}
```

---

## 9. 版本历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|----------|------|
| 1.0.0 | 2026-04-12 | 初始版本发布 | GraphSkill Architecture Team |
| 1.1.0 | 2026-04-17 | VR-First 架构适配：引用 RFC-00 v2.0 VR-First 范式转变；存储层接口适配 VR baseline 检索优先 | GraphSkill Architecture Team |

---

**文档结束**

*本文档定义了 GraphSkill 系统的数据规范与存储层设计。相关数据结构定义详见 [RFC-08: 数据结构与 Schema 定义](RFC-08-data-structures-schema.md)。*