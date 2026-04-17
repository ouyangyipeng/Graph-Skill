# RFC-03: 在线动态路由引擎

**文档编号:** RFC-03  
**版本:** 2.0.0
**状态:** 正式发布
**最后更新:** 2026-04-17
**作者:** GraphSkill Architecture Team  
**分类:** 架构规范 - 核心算法  
**依赖:** RFC-00, RFC-01, RFC-08

---

## 目录

1. [概述](#1-概述)
2. [路由引擎架构总览](#2-路由引擎架构总览)
3. [输入标准化与意图向量化](#3-输入标准化与意图向量化)
4. [拓扑感知混合召回算法](#4-拓扑感知混合召回算法)
5. [动态打分与节点权重计算](#5-动态打分与节点权重计算)
6. [最大权重独立集冲突剪枝算法](#6-最大权重独立集冲突剪枝算法)
7. [上下文拼装与 Token 截断](#7-上下文拼装与-token-截断)
8. [缓存策略与降级机制](#8-缓存策略与降级机制)
9. [性能基准与优化策略](#9-性能基准与优化策略)
10. [版本历史](#10-版本历史)

---

## 1. 概述

### 1.1 文档目的

本文档定义 GraphSkill 系统的核心技术资产——在线动态路由引擎（Routing Gateway）。涵盖输入标准化、意图向量化、拓扑感知混合召回算法、动态打分函数、最大权重独立集（MWIS）冲突剪枝算法、上下文拼装与 Token 截断策略、缓存策略以及性能基准。

### 1.2 适用范围

本文档适用于：
- 核心算法工程师：实现路由算法与剪枝策略
- 后端开发工程师：实现 Routing Gateway 服务
- 性能优化工程师：优化路由延迟与吞吐量
- 系统架构师：理解路由引擎的设计决策

### 1.3 设计原则

| 原则 | 描述 |
|------|------|
| **GS ≥ VR 保证** | GraphSkill 结果 MUST 不劣于 Vector-RAG baseline——最差情况 fallback 到 VR 结果而非 Zero-shot |
| **毫秒级响应** | 路由请求 MUST 在 500ms 内完成（P99） |
| **零冲突输出** | 输出技能子集 MUST NOT 包含任何互斥或替代关系 |
| **最小必要上下文** | 输出 MUST 是支撑当前任务的最小技能集合 |
| **VR Seed 不可丢弃** | VR baseline 检索的种子技能 MUST 享有保护优先级——MWIS pruning 不可移除 VR seed |
| **可降级性** | 图增强无效时 MUST 降级为 VR baseline（而非 Zero-shot）；图数据库故障时降级为纯向量检索 |

### 1.4 核心算法流程概览（VR-First Architecture）

> **范式转变**：旧架构（Graph-First）采用 ANN→BFS 2-hop→Scoring→MWIS→threshold→ZS fallback，导致 GS ≈ ZS 或 GS < VR。新架构（VR-First）保证 GS ≥ VR。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                  Routing Gateway Algorithm Flow - VR-First                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STEP 1: VR Baseline Retrieval — 与 Vector-RAG baseline 等价               │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                    │
│  │  Query      │────▶│  Noise      │────▶│  ANN Top-5  │                    │
│  │  Receiver   │     │  Reduction  │     │  S_VR       │                    │
│  └─────────────┘     └─────────────┘     └──────┬──────┘                    │
│                                                 │                           │
│                 S_VR MUST 永远保留 — 图增强层不可丢弃 VR seed              │
│                                                 ▼                           │
│  STEP 2: Graph Enhancement Layer — 在 VR seed 上增量优化                   │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────────────┐            │
│  │  1-hop      │────▶│  Scoring    │────▶│  MWIS + VR Protect  │            │
│  │  Expansion  │     │  α=0.8      │     │  VR seeds不可被prune│            │
│  │  depth=1    │     │  β=0.1,γ=0.1│     │                     │            │
│  └─────────────┘     └─────────────┘     └──────┬──────────────┘            │
│                                                 │                           │
│                 enhancement_score > 0 ?                                      │
│                 ┌───────┼───────┐                                             │
│                 │ YES           │ NO                                          │
│                 ▼               ▼                                             │
│  STEP 3a: Enhanced      STEP 3b: Fallback Guarantee                        │
│  ┌─────────────┐        ┌─────────────┐                                     │
│  │  Context    │        │  VR Only    │                                     │
│  │  Assembly   │        │  GS = VR    │                                     │
│  │  VR+enhanced│        │  保证 ≥ VR  │                                     │
│  └─────────────┘        └─────────────┘                                     │
│                 │               │                                             │
│                 └───────┬───────┘                                             │
│                         ▼                                                    │
│  STEP 4: RoutingResponse — GS ≥ VR ✅                                      │
│  ┌─────────────┐                                                            │
│  │  Response   │                                                            │
│  │  Builder    │                                                            │
│  └─────────────┘                                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**4-Phase Pipeline 设计不变量**：
- **STEP 1**: S_VR = ANN-TopK(q, K=5)，与 Vector-RAG baseline 完全等价
- **STEP 2**: 图增强层只能在 S_VR 基础上增删，不能丢弃 VR seed
- **STEP 3**: Fallback 目标 MUST 是 VR baseline（不是 Zero-shot）
- **STEP 4**: 最终输出 MUST 保证 GS ≥ VR

---

## 2. 路由引擎架构总览

### 2.1 模块架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Routing Gateway Architecture                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        API Layer                                     │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐  │   │
│  │  │ REST API    │  │ gRPC API    │  │ WebSocket Stream (optional) │  │   │
│  │  │ (FastAPI)   │  │ (Go Gin)    │  │                             │  │   │
│  │  └───────┬─────┘  └───────┬─────┘  └─────────────┬───────────────┘  │   │
│  │          │                │                      │                  │   │
│  └──────────┼────────────────┼──────────────────────┼──────────────────┘   │
│             │                │                      │                       │
│             ▼                ▼                      ▼                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Request Handler Layer                            │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ Rate        │  │ Request     │  │ Auth        │  │ Context     │ │   │
│  │  │ Limiter     │  │ Validator   │  │ Checker     │  │ Extractor   │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Core Routing Engine                              │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ Query       │  │ Hybrid      │  │ Conflict    │  │ Context     │ │   │
│  │  │ Processor   │──▶│ Retriever   │──▶│ Pruner      │──▶│ Assembler   │ │   │
│  │  │             │  │             │  │             │  │             │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  │         │                │                │                │        │   │
│  │         ▼                ▼                ▼                ▼        │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ Embedding   │  │ Graph       │  │ Scoring     │  │ Tokenizer   │ │   │
│  │  │ Service     │  │ Traverser   │  │ Engine      │  │ (tiktoken)  │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Data Access Layer                                │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │ Vector DB   │  │ Graph DB    │  │ Redis Cache │  │ Kafka MQ    │ │   │
│  │  │ Client      │  │ Client      │  │ Client      │  │ Producer    │ │   │
│  │  │ (Milvus)    │  │ (Neo4j)     │  │             │  │             │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 模块职责定义

| 模块 | 职责 | 输入 | 输出 | 性能要求 |
|------|------|------|------|----------|
| **Query Processor** | 标准化输入、降噪处理 | Raw Query | Processed Query | < 10ms |
| **Embedding Service** | 生成 Query 向量 | Processed Query | Query Vector | < 50ms |
| **Hybrid Retriever** | 执行混合召回 | Query Vector | Candidate Nodes | < 200ms |
| **Conflict Pruner** | 执行冲突剪枝 | Candidate Nodes | Final Skill Set | < 50ms |
| **Context Assembler** | 拼装上下文 | Final Skill Set | Structured Context | < 100ms |

### 2.3 性能基准指标

| 指标 | 目标值 (P99) | 测量方法 | 降级阈值 |
|------|--------------|----------|----------|
| 总路由延迟 | < 500ms | 端到端计时 | > 1000ms 触发降级 |
| 向量检索延迟 | < 100ms | ANN 搜索计时 | > 200ms 触发降级 |
| 图扩展延迟 | < 200ms | 图遍历计时 | > 500ms 触发降级 |
| 冲突剪枝延迟 | < 50ms | MWIS 算法计时 | - |
| Token 截断延迟 | < 10ms | Token 计算计时 | - |

---

## 3. 输入标准化与意图向量化

### 3.1 API 签名定义

路由请求 MUST 通过以下 API 端点提交：

```yaml
# API 端点定义
endpoint: /v1/route_skills
method: POST
content_type: application/json

# 请求 Schema
request_schema:
  type: object
  required:
    - query
  properties:
    query:
      type: string
      description: 用户查询文本
      min_length: 10
      max_length: 2000
    context_state:
      type: object
      description: 当前 Agent 上下文状态
      properties:
        session_id:
          type: string
        previous_skills:
          type: array
          items:
            type: string
        environment:
          type: object
        agent_capabilities:
          type: array
          items:
            type: string
    max_tokens:
      type: integer
      description: Token 预算上限
      default: 4000
      minimum: 500
      maximum: 32000
    routing_options:
      type: object
      description: 路由选项配置
      properties:
        include_enhances:
          type: boolean
          default: true
        expansion_depth:
          type: integer
          default: 2
          minimum: 1
          maximum: 3
        seed_count:
          type: integer
          default: 5
          minimum: 3
          maximum: 20

# 响应 Schema
response_schema:
  type: object
  required:
    - skills
    - routing_mode
    - token_count
  properties:
    skills:
      type: array
      items:
        type: object
        properties:
          skill_id:
            type: string
          priority:
            type: integer
          description:
            type: string
          instructions:
            type: string
          requires:
            type: array
            items:
              type: string
    routing_mode:
      type: string
      enum:
        - normal
        - fallback
        - cached
    token_count:
      type: integer
    latency_ms:
      type: integer
    warnings:
      type: array
      items:
        type: string
```

### 3.2 请求示例

```json
{
  "query": "我需要提交当前的代码变更到 Git 仓库，并推送到远程分支",
  "context_state": {
    "session_id": "sess_abc123",
    "previous_skills": ["git:configure", "git:stage_files"],
    "environment": {
      "git_repo": true,
      "git_configured": true
    },
    "agent_capabilities": ["fs:read", "fs:write", "exec:git"]
  },
  "max_tokens": 4000,
  "routing_options": {
    "include_enhances": true,
    "expansion_depth": 2,
    "seed_count": 5
  }
}
```

### 3.3 Query 降噪处理

系统 MUST 对原始 Query 执行降噪处理，提升向量检索质量：

```python
class QueryProcessor:
    """
    Query 处理器，执行标准化与降噪处理。
    """
    
    def process(self, raw_query: str, context_state: dict) -> ProcessedQuery:
        """
        处理原始 Query。
        
        Args:
            raw_query: 原始用户查询
            context_state: 当前上下文状态
            
        Returns:
            ProcessedQuery: 处理后的查询对象
        """
        # Step 1: 文本清洗
        cleaned_query = self._clean_text(raw_query)
        
        # Step 2: 上下文融合
        enriched_query = self._enrich_with_context(cleaned_query, context_state)
        
        # Step 3: 意图提取
        intent_keywords = self._extract_intent_keywords(enriched_query)
        
        # Step 4: 历史技能过滤
        filtered_query = self._filter_previous_skills(enriched_query, context_state)
        
        return ProcessedQuery(
            original=raw_query,
            cleaned=cleaned_query,
            enriched=enriched_query,
            intent_keywords=intent_keywords,
            previous_skills=context_state.get("previous_skills", []),
            environment=context_state.get("environment", {})
        )
    
    def _clean_text(self, text: str) -> str:
        """
        文本清洗：移除噪声、标准化格式。
        """
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text.strip())
        
        # 移除特殊字符（保留中文、英文、数字）
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', '', text)
        
        # 统一大小写（英文部分）
        text = text.lower()
        
        return text
    
    def _enrich_with_context(self, query: str, context: dict) -> str:
        """
        融合上下文信息，增强 Query 语义。
        """
        environment = context.get("environment", {})
        
        # 添加环境状态关键词
        env_keywords = []
        if environment.get("git_repo"):
            env_keywords.append("git repository")
        if environment.get("database_connected"):
            env_keywords.append("database")
        
        if env_keywords:
            query = f"{query} context: {', '.join(env_keywords)}"
        
        return query
    
    def _extract_intent_keywords(self, query: str) -> list:
        """
        提取意图关键词，用于辅助检索。
        """
        # 定义意图关键词映射
        intent_patterns = {
            "git": ["git", "commit", "push", "pull", "branch", "merge"],
            "database": ["database", "query", "sql", "table", "insert", "update"],
            "file": ["file", "read", "write", "delete", "copy", "move"],
            "network": ["http", "api", "request", "fetch", "download"]
        }
        
        keywords = []
        for category, patterns in intent_patterns.items():
            for pattern in patterns:
                if pattern in query.lower():
                    keywords.append(category)
                    break
        
        return keywords
```

### 3.4 Embedding 生成规范

系统 MUST 使用与技能向量相同的 Embedding 模型生成 Query 向量：

```python
class EmbeddingService:
    """
    Embedding 生成服务。
    """
    
    def __init__(self, model_name: str = "text-embedding-3-small"):
        self.model_name = model_name
        self.client = OpenAIEmbeddingClient()
        self.dimension = 1536  # 与技能向量维度一致
    
    async def generate(self, text: str) -> np.ndarray:
        """
        生成文本向量嵌入。
        
        Args:
            text: 输入文本
            
        Returns:
            np.ndarray: 向量数组
            
        Raises:
            EmbeddingGenerationError: 生成失败时抛出
        """
        try:
            response = await self.client.embeddings.create(
                model=self.model_name,
                input=text,
                encoding_format="float"
            )
            
            vector = np.array(response.data[0].embedding, dtype=np.float32)
            
            # 验证向量维度
            if vector.shape[0] != self.dimension:
                raise EmbeddingDimensionMismatchError(
                    expected=self.dimension,
                    actual=vector.shape[0]
                )
            
            return vector
            
        except Exception as e:
            raise EmbeddingGenerationError(f"Embedding generation failed: {e}")
    
    def compute_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        计算余弦相似度。
        """
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
```

---

## 4. 拓扑感知混合召回算法

### 4.1 算法概述

混合召回算法分为两个阶段：
1. **Phase 1: Semantic Seed Recall（语义种子召回）** - 基于 ANN 检索召回 Top-K 种子节点
2. **Phase 2: Graph Expansion（图谱多跳扩展）** - 从种子节点出发执行受限深度图遍历

### 4.2 Phase 1: 语义种子召回

#### 4.2.1 ANN 检索规范

> **VR-First 变更**：默认 `top_k` 从 10 → 5，与 VR baseline 一致。ANN 检索结果 S_VR MUST 永远保留，图增强层不可丢弃。

```python
class SemanticSeedRecaller:
    """
    语义种子召回器，执行 ANN 检索。
    VR-First: top_k=5, 结果 S_VR MUST 永远保留。
    """
    
    def __init__(self, vector_store, config: RetrievalConfig):
        self.vector_store = vector_store
        self.config = config
    
    async def recall(
        self,
        query_vector: np.ndarray,
        top_k: int = 5  # VR-First: 从 10 → 5
    ) -> List[SeedNode]:
        """
        执行语义种子召回。
        
        Args:
            query_vector: Query 向量
            top_k: 返回种子数量
            
        Returns:
            List[SeedNode]: 种子节点列表
        """
        # 执行 ANN 检索
        search_params = {
            "metric_type": "COSINE",
            "params": {"ef": self.config.search_ef}
        }
        
        results = await self.vector_store.search(
            collection_name="skill_vectors",
            query_vector=query_vector,
            top_k=top_k * 2,  # 多召回一些，用于过滤
            search_params=search_params
        )
        
        # 过滤废弃节点
        filtered_results = []
        for result in results:
            skill_node = await self._get_skill_node(result["skill_id"])
            if skill_node and not skill_node.get("is_deprecated"):
                filtered_results.append(SeedNode(
                    skill_id=result["skill_id"],
                    vector_id=result["id"],
                    similarity=result["distance"],
                    node_properties=skill_node
                ))
        
        # 返回 Top-K
        return filtered_results[:top_k]
    
    async def _get_skill_node(self, skill_id: str) -> dict:
        """
        从图数据库获取技能节点属性。
        """
        query = """
        MATCH (s:SkillNode {uid: $skill_id})
        RETURN s.uid, s.embedding_id, s.execution_success_rate, 
               s.is_deprecated, s.permissions, s.intent_description
        """
        result = await self.graph_store.execute_query(query, {"skill_id": skill_id})
        return result[0] if result else None
```

#### 4.2.2 种子节点数据结构

```python
class SeedNode:
    """
    种子节点数据结构。
    """
    
    skill_id: str           # 技能 ID
    vector_id: str          # 向量 ID
    similarity: float       # 与 Query 的相似度
    node_properties: dict   # 节点属性
    expansion_path: list    # 扩展路径（后续填充）
```

### 4.3 Phase 2: 图谱多跳扩展

#### 4.3.1 扩展规则规范

图扩展 MUST 遵循以下规则：

| 规则 | 描述 | 参数 |
|------|------|------|
| **深度限制** | 最大扩展深度 MUST 限制为 **1 跳**（VR-First: 2-hop 引入过多噪声） | `max_depth: 1` |
| **边类型过滤** | 仅沿着 REQUIRES（出边）和 ENHANCES（出边）扩展 | `edge_types: ["REQUIRES", "ENHANCES"]` |
| **节点过滤** | 跳过 `is_deprecated: true` 的节点 | `filter_deprecated: true` |
| **重复检测** | 避免重复访问同一节点 | `track_visited: true` |

#### 4.3.2 图扩展算法实现

```python
class GraphExpander:
    """
    图谱多跳扩展器。
    """
    
    def __init__(self, graph_store, config: ExpansionConfig):
        self.graph_store = graph_store
        self.config = config
    
    async def expand(
        self,
        seed_nodes: List[SeedNode],
        max_depth: int = 1  # VR-First: 从 2 → 1，避免噪声扩张
    ) -> CandidatePool:
        """
        执行图谱多跳扩展。
        
        Args:
            seed_nodes: 种子节点列表
            max_depth: 最大扩展深度
            
        Returns:
            CandidatePool: 候选节点池
        """
        candidate_pool = CandidatePool()
        visited = set()
        
        # 初始化：将种子节点加入候选池
        for seed in seed_nodes:
            candidate_pool.add_node(
                CandidateNode(
                    skill_id=seed.skill_id,
                    similarity=seed.similarity,
                    depth=0,
                    is_seed=True,
                    expansion_path=[seed.skill_id]
                )
            )
            visited.add(seed.skill_id)
        
        # BFS 扩展
        for depth in range(1, max_depth + 1):
            current_frontier = candidate_pool.get_nodes_at_depth(depth - 1)
            
            for node in current_frontier:
                # 获取出边邻居
                neighbors = await self._get_out_neighbors(node.skill_id)
                
                for neighbor in neighbors:
                    if neighbor["skill_id"] not in visited:
                        visited.add(neighbor["skill_id"])
                        
                        candidate_pool.add_node(
                            CandidateNode(
                                skill_id=neighbor["skill_id"],
                                similarity=0.0,  # 非种子节点，相似度待计算
                                depth=depth,
                                is_seed=False,
                                expansion_path=node.expansion_path + [neighbor["skill_id"]],
                                edge_type=neighbor["edge_type"],
                                edge_weight=neighbor["weight"]
                            )
                        )
        
        return candidate_pool
    
    async def _get_out_neighbors(self, skill_id: str) -> List[dict]:
        """
        获取节点的出边邻居（REQUIRES 和 ENHANCES）。
        """
        query = """
        MATCH (source:SkillNode {uid: $skill_id})
        MATCH (source)-[r:REQUIRES|ENHANCES]->(target:SkillNode)
        WHERE NOT target.is_deprecated
        RETURN target.uid as skill_id, 
               type(r) as edge_type, 
               r.weight as weight,
               r.is_hard as is_hard
        """
        
        results = await self.graph_store.execute_query(query, {"skill_id": skill_id})
        
        neighbors = []
        for result in results:
            neighbors.append({
                "skill_id": result["skill_id"],
                "edge_type": result["edge_type"],
                "weight": result.get("weight", 1.0),
                "is_hard": result.get("is_hard", True)
            })
        
        return neighbors
```

#### 4.3.3 候选节点池数据结构

```python
class CandidatePool:
    """
    候选节点池，存储扩展过程中的所有候选节点。
    """
    
    def __init__(self):
        self.nodes: Dict[str, CandidateNode] = {}
        self.depth_groups: Dict[int, List[str]] = defaultdict(list)
    
    def add_node(self, node: CandidateNode):
        """
        添加候选节点。
        """
        self.nodes[node.skill_id] = node
        self.depth_groups[node.depth].append(node.skill_id)
    
    def get_nodes_at_depth(self, depth: int) -> List[CandidateNode]:
        """
        获取指定深度的所有节点。
        """
        skill_ids = self.depth_groups.get(depth, [])
        return [self.nodes[sid] for sid in skill_ids]
    
    def get_all_nodes(self) -> List[CandidateNode]:
        """
        获取所有候选节点。
        """
        return list(self.nodes.values())
    
    def get_seed_nodes(self) -> List[CandidateNode]:
        """
        获取所有种子节点。
        """
        return [n for n in self.nodes.values() if n.is_seed]
    
    def to_dict(self) -> dict:
        """
        序列化为字典。
        """
        return {
            "total_nodes": len(self.nodes),
            "seed_count": len(self.get_seed_nodes()),
            "depth_distribution": {
                str(d): len(self.depth_groups[d])
                for d in self.depth_groups
            },
            "nodes": [n.to_dict() for n in self.nodes.values()]
        }


class CandidateNode:
    """
    候选节点数据结构。
    """
    
    skill_id: str           # 技能 ID
    similarity: float       # 与 Query 的相似度（种子节点有值）
    depth: int              # 扩展深度（0 = 种子）
    is_seed: bool           # 是否为种子节点
    expansion_path: list    # 扩展路径
    edge_type: str          # 入边类型（非种子节点）
    edge_weight: float      # 入边权重
    score: float            # 综合得分（后续计算）
    
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

---

## 5. 动态打分与节点权重计算

### 5.1 打分函数定义

为每个候选节点 $n$ 计算综合权重得分：

$$Score(n) = \alpha \cdot CosineSim(V_q, V_n) + \beta \cdot PageRank_{local}(n) + \gamma \cdot Reliability(n)$$

> **VR-First 变更**：默认权重从 α=0.5, β=0.3, γ=0.2 → **α=0.8, β=0.1, γ=0.1**。原因：在 SWE-bench 场景中，similarity 是唯一有区分度的维度；PageRank 在小 subgraph 中几乎无区分度；reliability 全是初始值。category_weights 全部设为 1.0（移除人为放大）。

其中：
- $\alpha, \beta, \gamma$ 为可调超参数（**默认 $\alpha=0.8, \beta=0.1, \gamma=0.1$**）
- $CosineSim$ 为节点与 Query 的余弦相似度
- $PageRank_{local}$ 为候选子图内的局部中心度
- $Reliability$ 为技能历史执行成功率

### 5.2 打分引擎实现

```python
class ScoringEngine:
    """
    动态打分引擎，计算候选节点的综合权重。
    """
    
    def __init__(self, config: ScoringConfig):
        self.config = config
        self.alpha = config.alpha  # VR-First: 默认 0.8
        self.beta = config.beta    # VR-First: 默认 0.1
        self.gamma = config.gamma  # VR-First: 默认 0.1
    
    async def score_all(
        self,
        candidate_pool: CandidatePool,
        query_vector: np.ndarray
    ) -> CandidatePool:
        """
        为所有候选节点计算综合得分。
        
        Args:
            candidate_pool: 候选节点池
            query_vector: Query 向量
            
        Returns:
            CandidatePool: 更新得分后的候选池
        """
        nodes = candidate_pool.get_all_nodes()
        
        # 计算各维度得分
        similarity_scores = await self._compute_similarity_scores(nodes, query_vector)
        pagerank_scores = await self._compute_local_pagerank(nodes)
        reliability_scores = await self._compute_reliability_scores(nodes)
        
        # 综合打分
        for node in nodes:
            node.score = (
                self.alpha * similarity_scores.get(node.skill_id, 0.0) +
                self.beta * pagerank_scores.get(node.skill_id, 0.0) +
                self.gamma * reliability_scores.get(node.skill_id, 0.0)
            )
        
        return candidate_pool
    
    async def _compute_similarity_scores(
        self,
        nodes: List[CandidateNode],
        query_vector: np.ndarray
    ) -> Dict[str, float]:
        """
        计算相似度得分。
        """
        scores = {}
        
        for node in nodes:
            if node.is_seed:
                # 种子节点已有相似度
                scores[node.skill_id] = node.similarity
            else:
                # 非种子节点需要计算
                node_vector = await self._get_node_vector(node.skill_id)
                if node_vector:
                    similarity = self._cosine_similarity(query_vector, node_vector)
                    scores[node.skill_id] = similarity
                else:
                    scores[node.skill_id] = 0.0
        
        return scores
    
    async def _compute_local_pagerank(
        self,
        nodes: List[CandidateNode]
    ) -> Dict[str, float]:
        """
        计算候选子图内的局部 PageRank。
        """
        import networkx as nx
        
        # 构建局部子图
        graph = nx.DiGraph()
        skill_ids = [n.skill_id for n in nodes]
        
        # 获取子图内的 REQUIRES 边
        query = """
        MATCH (a:SkillNode)-[r:REQUIRES]->(b:SkillNode)
        WHERE a.uid IN $skill_ids AND b.uid IN $skill_ids
        RETURN a.uid as source, b.uid as target, r.weight as weight
        """
        edges = await self.graph_store.execute_query(query, {"skill_ids": skill_ids})
        
        for edge in edges:
            graph.add_edge(edge["source"], edge["target"], weight=edge.get("weight", 1.0))
        
        # 添加孤立节点
        for skill_id in skill_ids:
            if skill_id not in graph.nodes:
                graph.add_node(skill_id)
        
        # 计算 PageRank
        pagerank_scores = nx.pagerank(graph, weight="weight")
        
        # 归一化到 [0, 1]
        max_score = max(pagerank_scores.values()) if pagerank_scores else 1.0
        normalized_scores = {
            k: v / max_score for k, v in pagerank_scores.items()
        }
        
        return normalized_scores
    
    async def _compute_reliability_scores(
        self,
        nodes: List[CandidateNode]
    ) -> Dict[str, float]:
        """
        计算可靠性得分（历史执行成功率）。
        """
        scores = {}
        
        for node in nodes:
            node_props = await self._get_node_properties(node.skill_id)
            success_rate = node_props.get("execution_success_rate", 1.0)
            scores[node.skill_id] = success_rate
        
        return scores
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        计算余弦相似度。
        """
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
```

### 5.3 超参数配置

```yaml
# config/scoring.yaml
scoring:
  alpha: 0.5      # 相似度权重
  beta: 0.3       # PageRank 权重
  gamma: 0.2      # 可靠性权重
  
  # 动态调整策略
  dynamic_adjustment:
    enabled: true
    adjust_interval: 3600  # 每小时调整一次
    min_alpha: 0.3
    max_alpha: 0.7
    
  # 特殊场景权重调整
  scenario_weights:
    high_reliability_priority:
      alpha: 0.4
      beta: 0.2
      gamma: 0.4
    exploration_mode:
      alpha: 0.6
      beta: 0.3
      gamma: 0.1
```

---

## 6. 最大权重独立集冲突剪枝算法

### 6.1 算法概述

候选池中通常包含冗余和互相排斥的节点。系统 MUST 通过 MWIS（Maximum Weight Independent Set）算法进行剪枝，确保输出技能子集内零冲突。

> **VR-First 变更**：MWIS pruning MUST 增加 VR Seed Protection 机制。VR baseline 检索的种子技能享有保护优先级——当 VR seed 与扩展技能冲突时，MUST 移除扩展技能而非 VR seed。两个 VR seed 互相冲突时，保留 score 更高的。这保证 S_VR 的核心结果不被图增强层丢弃，从而维持 GS ≥ VR 不变量。

### 6.2 冲突图构建

```python
class ConflictGraphBuilder:
    """
    冲突图构建器，提取候选池中的冲突关系。
    """
    
    def __init__(self, graph_store):
        self.graph_store = graph_store
    
    async def build(
        self,
        candidate_pool: CandidatePool
    ) -> ConflictGraph:
        """
        构建冲突图。
        
        Args:
            candidate_pool: 候选节点池
            
        Returns:
            ConflictGraph: 冲突图对象
        """
        skill_ids = [n.skill_id for n in candidate_pool.get_all_nodes()]
        
        # 获取 CONFLICTS_WITH 边
        conflicts_query = """
        MATCH (a:SkillNode)-[r:CONFLICTS_WITH]-(b:SkillNode)
        WHERE a.uid IN $skill_ids AND b.uid IN $skill_ids
        RETURN a.uid as node_a, b.uid as node_b, r.severity as severity
        """
        conflicts = await self.graph_store.execute_query(
            conflicts_query, {"skill_ids": skill_ids}
        )
        
        # 获取 SUBSTITUTES 边
        substitutes_query = """
        MATCH (a:SkillNode)-[r:SUBSTITUTES]-(b:SkillNode)
        WHERE a.uid IN $skill_ids AND b.uid IN $skill_ids
        RETURN a.uid as node_a, b.uid as node_b, r.similarity as similarity
        """
        substitutes = await self.graph_store.execute_query(
            substitutes_query, {"skill_ids": skill_ids}
        )
        
        # 构建冲突图
        conflict_graph = ConflictGraph()
        
        # 添加节点
        for node in candidate_pool.get_all_nodes():
            conflict_graph.add_node(node.skill_id, node.score)
        
        # 添加冲突边
        for edge in conflicts:
            conflict_graph.add_conflict_edge(
                edge["node_a"],
                edge["node_b"],
                severity=edge.get("severity", 3)
            )
        
        # 添加替代边
        for edge in substitutes:
            conflict_graph.add_substitute_edge(
                edge["node_a"],
                edge["node_b"],
                similarity=edge.get("similarity", 0.8)
            )
        
        return conflict_graph


class ConflictGraph:
    """
    冲突图数据结构。
    """
    
    def __init__(self):
        self.nodes: Dict[str, float] = {}  # skill_id -> score
        self.conflict_edges: List[tuple] = []  # (node_a, node_b, severity)
        self.substitute_edges: List[tuple] = []  # (node_a, node_b, similarity)
        self.adjacency: Dict[str, Set[str]] = defaultdict(set)
    
    def add_node(self, skill_id: str, score: float):
        """
        添加节点。
        """
        self.nodes[skill_id] = score
    
    def add_conflict_edge(self, node_a: str, node_b: str, severity: int):
        """
        添加冲突边。
        """
        self.conflict_edges.append((node_a, node_b, severity))
        self.adjacency[node_a].add(node_b)
        self.adjacency[node_b].add(node_a)
    
    def add_substitute_edge(self, node_a: str, node_b: str, similarity: float):
        """
        添加替代边。
        """
        self.substitute_edges.append((node_a, node_b, similarity))
        self.adjacency[node_a].add(node_b)
        self.adjacency[node_b].add(node_a)
    
    def has_conflict(self, node_a: str, node_b: str) -> bool:
        """
        检查两个节点是否存在冲突。
        """
        return node_b in self.adjacency.get(node_a, set())
    
    def get_neighbors(self, skill_id: str) -> Set[str]:
        """
        获取节点的所有冲突邻居。
        """
        return self.adjacency.get(skill_id, set())
```

### 6.3 贪心 MWIS 算法实现

```python
class MWISPruner:
    """
    最大权重独立集剪枝器，使用贪心算法求解。
    VR-First: 增加 prune_with_protection() 方法，VR seed 不可被移除。
    """
    
    def prune(
        self,
        conflict_graph: ConflictGraph
    ) -> List[str]:
        """
        执行 MWIS 剪枝，返回零冲突的技能子集。
        
        Args:
            conflict_graph: 冲突图
            
        Returns:
            List[str]: 最终技能 ID 列表
        """
        # 按得分降序排列节点
        sorted_nodes = sorted(
            conflict_graph.nodes.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 贪心选择
        final_set: Set[str] = set()
        
        for skill_id, score in sorted_nodes:
            # 检查是否与已选节点冲突
            has_conflict = False
            for selected in final_set:
                if conflict_graph.has_conflict(skill_id, selected):
                    has_conflict = True
                    break
            
            if not has_conflict:
                final_set.add(skill_id)
        
        # 验证结果
        self._validate_no_conflicts(final_set, conflict_graph)
        
        return list(final_set)
    
    def _validate_no_conflicts(
        self,
        final_set: Set[str],
        conflict_graph: ConflictGraph
    ):
        """
        验证最终集合内无冲突。
        """
        for node_a in final_set:
            for node_b in final_set:
                if node_a != node_b:
                    if conflict_graph.has_conflict(node_a, node_b):
                        raise ConflictPruningError(
                            f"Conflict detected in final set: {node_a} <-> {node_b}"
                        )
```

### 6.4 算法伪代码

```
Algorithm: Greedy MWIS for Conflict Pruning

Input: 
  - CandidatePool P (nodes with scores)
  - ConflictGraph G (conflict edges)

Output:
  - FinalSkillSet S (zero-conflict subset)

Procedure:
1. Sort all nodes in P by score descending: N = sort(P.nodes)
2. Initialize empty set: S = {}
3. For each node n in N:
   a. Check if n conflicts with any node in S
   b. If no conflict: add n to S
   c. If conflict: skip n
4. Validate S has no internal conflicts
5. Return S

Time Complexity: O(|P| × |S|) where |S| ≤ |P|
Space Complexity: O(|G|) for conflict graph storage
```

### 6.5 安全底线原则

系统 MUST 确保输出的技能子集内**绝对不存在**任何逻辑互斥或功能平替的技能：

```python
class ConflictPruningError(Exception):
    """
    冲突剪枝错误，当最终集合内检测到冲突时抛出。
    """
    
    def __init__(self, message: str, conflict_pair: tuple):
        self.message = message
        self.conflict_pair = conflict_pair
        super().__init__(message)
    
    def to_dict(self) -> dict:
        return {
            "error_type": "ConflictPruningError",
            "message": self.message,
            "conflict_pair": self.conflict_pair
        }
```

---

## 7. 上下文拼装与 Token 截断

### 7.1 拓扑排序

系统 MUST 对最终技能子集进行拓扑排序，确保被依赖的底层核心技能排在前面：

```python
class TopologicalSorter:
    """
    拓扑排序器，基于 REQUIRES 关系排序技能。
    """
    
    def __init__(self, graph_store):
        self.graph_store = graph_store
    
    async def sort(
        self,
        skill_ids: List[str]
    ) -> List[str]:
        """
        执行拓扑排序。
        
        Args:
            skill_ids: 技能 ID 列表
            
        Returns:
            List[str]: 排序后的技能 ID 列表
        """
        import networkx as nx
        
        # 获取子图内的 REQUIRES 边
        query = """
        MATCH (a:SkillNode)-[r:REQUIRES]->(b:SkillNode)
        WHERE a.uid IN $skill_ids AND b.uid IN $skill_ids
        RETURN a.uid as source, b.uid as target
        """
        edges = await self.graph_store.execute_query(
            query, {"skill_ids": skill_ids}
        )
        
        # 构建依赖图
        graph = nx.DiGraph()
        
        for skill_id in skill_ids:
            graph.add_node(skill_id)
        
        for edge in edges:
            graph.add_edge(edge["source"], edge["target"])
        
        # 拓扑排序
        try:
            sorted_ids = list(nx.topological_sort(graph))
            return sorted_ids
        except nx.NetworkXUnfeasible:
            # 存在环路（理论上不应发生，因为 DAG 校验已通过）
            logger.warning(f"Cycle detected in skill dependencies: {skill_ids}")
            return skill_ids  # 返回原始顺序
```

### 7.2 Token 预算控制

系统 MUST 遵守 Token 预算限制，使用与下游 LLM 一致的 Tokenizer：

```python
class TokenBudgetController:
    """
    Token 预算控制器，确保上下文不超出限制。
    """
    
    def __init__(self, tokenizer_name: str = "cl100k_base"):
        import tiktoken
        self.tokenizer = tiktoken.get_encoding(tokenizer_name)
    
    def count_tokens(self, text: str) -> int:
        """
        计算文本 Token 数量。
        """
        return len(self.tokenizer.encode(text))
    
    def assemble_with_budget(
        self,
        sorted_skills: List[str],
        skill_contents: Dict[str, str],
        max_tokens: int,
        reserved_tokens: int = 500  # 为系统提示预留
    ) -> AssembledContext:
        """
        在 Token 预算内拼装上下文。
        
        Args:
            sorted_skills: 排序后的技能 ID 列表
            skill_contents: 技能内容字典
            max_tokens: 最大 Token 数
            reserved_tokens: 预留 Token 数
            
        Returns:
            AssembledContext: 拼装结果
        """
        available_tokens = max_tokens - reserved_tokens
        assembled_skills = []
        total_tokens = 0
        skipped_skills = []
        
        for skill_id in sorted_skills:
            content = skill_contents.get(skill_id, "")
            skill_tokens = self.count_tokens(content)
            
            # 检查是否超出预算
            if total_tokens + skill_tokens <= available_tokens:
                assembled_skills.append(skill_id)
                total_tokens += skill_tokens
            else:
                skipped_skills.append(skill_id)
        
        # 拼装文本
        assembled_text = self._assemble_text(assembled_skills, skill_contents)
        
        return AssembledContext(
            skills=assembled_skills,
            skipped_skills=skipped_skills,
            total_tokens=total_tokens + reserved_tokens,
            assembled_text=assembled_text,
            budget_exceeded=len(skipped_skills) > 0
        )
    
    def _assemble_text(
        self,
        skill_ids: List[str],
        skill_contents: Dict[str, str]
    ) -> str:
        """
        拼装技能文本。
        """
        parts = []
        for skill_id in skill_ids:
            content = skill_contents.get(skill_id, "")
            parts.append(f"<Skill id=\"{skill_id}\">\n{content}\n</Skill>")
        
        return "\n\n".join(parts)
```

### 7.3 截断防崩溃策略

当 Token 预算耗尽时，系统 MUST 执行以下策略：

| 策略 | 描述 | 优先级 |
|------|------|--------|
| **优先保留强依赖** | REQUIRES 关系标记为 `is_hard: true` 的技能 MUST 优先保留 | 最高 |
| **优先保留种子节点** | 语义召回的种子节点 SHOULD 优先保留 | 高 |
| **优先抛弃 ENHANCES** | ENHANCES 关系的节点 SHOULD 优先抛弃 | 低 |
| **记录告警** | Token 超出 MUST 记录 `ContextOverflowWarning` | 必须 |

```python
class TruncationStrategy:
    """
    Token 截断策略，决定哪些技能优先保留/抛弃。
    """
    
    async def prioritize_skills(
        self,
        skill_ids: List[str],
        candidate_pool: CandidatePool
    ) -> List[str]:
        """
        根据优先级重新排序技能。
        
        优先级规则：
        1. 强依赖节点（REQUIRES is_hard=true）
        2. 种子节点
        3. 高得分节点
        """
        priorities = {}
        
        for skill_id in skill_ids:
            node = candidate_pool.nodes.get(skill_id)
            if node:
                # 计算优先级分数
                priority_score = 0
                
                # 强依赖加分
                if await self._is_hard_dependency(skill_id):
                    priority_score += 100
                
                # 种子节点加分
                if node.is_seed:
                    priority_score += 50
                
                # 综合得分加分
                priority_score += node.score * 10
                
                priorities[skill_id] = priority_score
        
        # 按优先级排序
        sorted_ids = sorted(
            skill_ids,
            key=lambda x: priorities.get(x, 0),
            reverse=True
        )
        
        return sorted_ids
    
    async def _is_hard_dependency(self, skill_id: str) -> bool:
        """
        检查技能是否被其他技能强依赖。
        """
        query = """
        MATCH (a:SkillNode)-[r:REQUIRES]->(b:SkillNode {uid: $skill_id})
        WHERE r.is_hard = true
        RETURN count(a) as dependents
        """
        result = await self.graph_store.execute_query(query, {"skill_id": skill_id})
        return result[0]["dependents"] > 0 if result else False
```

### 7.4 输出格式规范

系统 MUST 以结构化格式返回拼装结果：

```xml
<SystemSkills token_count="2850" routing_mode="normal">
  <Skill id="git:configure" priority="1" type="required">
    <Description>配置 Git 用户信息，设置 name 和 email</Description>
    <Instructions>
      执行以下命令配置 Git：
      git config --global user.name "$NAME"
      git config --global user.email "$EMAIL"
    </Instructions>
    <Permissions>
      <Permission>exec:git</Permission>
      <Permission>env:write</Permission>
    </Permissions>
  </Skill>
  
  <Skill id="git:commit_changes" priority="2" type="seed" requires="git:configure">
    <Description>执行 Git 提交操作，将当前工作区的变更提交到本地仓库</Description>
    <Instructions>
      1. 检查是否有未暂存的文件
      2. 使用 git add 暂存变更
      3. 执行 git commit -m "$MESSAGE"
    </Instructions>
    <Permissions>
      <Permission>fs:read</Permission>
      <Permission>exec:git</Permission>
    </Permissions>
  </Skill>
  
  <Skill id="git:push_remote" priority="3" type="enhances" enhances="git:commit_changes">
    <Description>推送本地提交到远程仓库</Description>
    <Instructions>
      执行 git push origin $BRANCH
    </Instructions>
  </Skill>
</SystemSkills>
```

---

## 8. 缓存策略与降级机制

### 8.1 Graph Cache 设计

系统 MUST 在 Redis 中维护热门 Query 到技能子图的映射关系：

```python
class GraphCache:
    """
    图缓存管理器，缓存高频查询的路由结果。
    """
    
    def __init__(self, redis_client, config: CacheConfig):
        self.redis = redis_client
        self.config = config
        self.ttl = config.cache_ttl  # 默认 1 小时
    
    async def get_cached_result(
        self,
        query_hash: str
    ) -> Optional[CachedRoutingResult]:
        """
        获取缓存的路由结果。
        
        Args:
            query_hash: Query 哈希值
            
        Returns:
            Optional[CachedRoutingResult]: 缓存结果或 None
        """
        cache_key = f"routing:{query_hash}"
        cached_data = await self.redis.get(cache_key)
        
        if cached_data:
            result = json.loads(cached_data)
            return CachedRoutingResult(
                query_hash=query_hash,
                skills=result["skills"],
                token_count=result["token_count"],
                cached_at=result["cached_at"],
                hit_count=result.get("hit_count", 0) + 1
            )
        
        return None
    
    async def cache_result(
        self,
        query_hash: str,
        routing_result: RoutingResult
    ):
        """
        缓存路由结果。
        """
        cache_key = f"routing:{query_hash}"
        
        cache_data = {
            "skills": routing_result.skills,
            "token_count": routing_result.token_count,
            "cached_at": datetime.utcnow().isoformat(),
            "hit_count": 0
        }
        
        await self.redis.setex(
            cache_key,
            self.ttl,
            json.dumps(cache_data)
        )
    
    def compute_query_hash(
        self,
        query: str,
        context_state: dict,
        max_tokens: int
    ) -> str:
        """
        计算 Query 哈希值，用于缓存键。
        """
        import hashlib
        
        # 提取关键信息
        hash_input = {
            "query": query,
            "previous_skills": context_state.get("previous_skills", []),
            "max_tokens": max_tokens
        }
        
        hash_str = json.dumps(hash_input, sort_keys=True)
        return hashlib.sha256(hash_str.encode()).hexdigest()[:16]
```

### 8.2 缓存配置

```yaml
# config/cache.yaml
cache:
  enabled: true
  ttl_seconds: 3600  # 1 小时
  
  # 缓存策略
  strategy:
    type: "query_hash"  # query_hash | semantic_similarity
    similarity_threshold: 0.95  # 语义相似缓存阈值
    
  # 缓存淘汰
  eviction:
    max_entries: 10000
    policy: "lru"  # lru | lfu | ttl
    
  # 缓存预热
  warmup:
    enabled: true
    top_queries: 100  # 预热 Top 100 高频查询
```

### 8.3 降级响应机制

> **VR-First 变更**：降级目标从 "纯向量检索" → "VR baseline"。旧架构在低分数时降级到 Zero-shot（threshold < 0.4 → ZS），这是 GS < VR 的直接原因。新架构 MUST 保证：图增强无效时降级到 VR baseline，图数据库故障时降级到纯向量检索（ANN top-5）。两种降级 MUST NOT 降级到 Zero-shot。

当图增强层未产生有效增量（enhancement_score ≤ 0）或图数据库宕机/响应超时时，系统 MUST 无缝降级：

| 降级场景 | 降级目标 | 触发条件 | 保证 |
|----------|----------|----------|------|
| **图增强无效** | VR baseline (ANN top-5) | enhancement_score ≤ 0 | GS = VR ≥ ZS |
| **图数据库故障** | VR baseline (ANN top-5) | graph_health.is_healthy = false | GS = VR ≥ ZS |
| **向量数据库故障** | Zero-shot（仅此场景） | vector_store unavailable | 无法检索 |

> ⚠️ **关键变更**：旧架构的 `SKILL_RELEVANCE_THRESHOLD=0.4` → Zero-shot fallback MUST NOT 在新架构中使用。新架构的 fallback MUST 始终指向 VR baseline。

```python
class FallbackHandler:
    """
    降级处理器，处理图数据库故障场景。
    """
    
    def __init__(self, config: FallbackConfig):
        self.config = config
        self.graph_timeout_threshold = config.graph_timeout_ms  # 默认 500ms
    
    async def handle_routing(
        self,
        query_vector: np.ndarray,
        graph_health: GraphHealthStatus
    ) -> RoutingResult:
        """
        处理路由请求，根据图数据库健康状态决定是否降级。
        
        Args:
            query_vector: Query 向量
            graph_health: 图数据库健康状态
            
        Returns:
            RoutingResult: 路由结果
        """
        if graph_health.is_healthy:
            # 正常模式：完整路由流程
            return await self._normal_routing(query_vector)
        else:
            # 降级模式：纯向量检索
            return await self._fallback_routing(query_vector)
    
    async def _normal_routing(
        self,
        query_vector: np.ndarray
    ) -> RoutingResult:
        """
        正常路由流程。
        """
        # ... 完整的混合召回 + 冲突剪枝流程
        result = await self.full_routing_pipeline(query_vector)
        result.routing_mode = "normal"
        return result
    
    async def _fallback_routing(
        self,
        query_vector: np.ndarray
    ) -> RoutingResult:
        """
        降级路由流程：纯向量检索，放弃冲突消解。
        """
        # 仅执行向量检索（VR-First: top_k=5, 与 VR baseline 一致）
        seed_nodes = await self.vector_recaller.recall(query_vector, top_k=5)
        
        # 直接返回种子节点（无冲突消解）
        skills = [n.skill_id for n in seed_nodes]
        
        result = RoutingResult(
            skills=skills,
            routing_mode="fallback",
            token_count=self._estimate_tokens(skills),
            warnings=["Graph database unavailable, conflict resolution skipped"]
        )
        
        return result
    
    def check_graph_health(self) -> GraphHealthStatus:
        """
        检查图数据库健康状态。
        """
        try:
            # 执行简单查询测试
            start_time = time.time()
            result = self.graph_store.execute_query("RETURN 1")
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
```

### 8.4 降级响应标记

降级响应 MUST 在响应 Header 中标记路由模式：

```python
# 响应 Header 规范
response_headers = {
    "x-routing-mode": "normal|fallback|cached",
    "x-routing-latency-ms": "285",
    "x-graph-health": "healthy|degraded|unavailable"
}
```

---

## 9. 性能基准与优化策略

### 9.1 性能基准测试

系统 MUST 定期执行性能基准测试，确保满足 SLA：

```python
class PerformanceBenchmark:
    """
    性能基准测试套件。
    """
    
    async def run_benchmark(self) -> BenchmarkResult:
        """
        执行完整性能基准测试。
        """
        test_cases = self._generate_test_cases()
        results = []
        
        for case in test_cases:
            start_time = time.time()
            result = await self.routing_gateway.route(case)
            latency = (time.time() - start_time) * 1000
            
            results.append({
                "query_type": case["type"],
                "latency_ms": latency,
                "skill_count": len(result["skills"]),
                "token_count": result["token_count"],
                "routing_mode": result["routing_mode"]
            })
        
        return BenchmarkResult(
            total_cases=len(results),
            p50_latency=self._percentile(results, "latency_ms", 50),
            p99_latency=self._percentile(results, "latency_ms", 99),
            max_latency=max(r["latency_ms"] for r in results),
            avg_skill_count=sum(r["skill_count"] for r in results) / len(results)
        )
```

### 9.2 性能优化策略

| 优化策略 | 描述 | 预期收益 |
|----------|------|----------|
| **向量检索并行化** | 多线程执行 ANN 检索 | 延迟降低 30% |
| **图遍历批量化** | 批量获取邻居节点 | 延迟降低 40% |
| **缓存预热** | 预加载高频查询结果 | 缓存命中率提升 50% |
| **连接池优化** | 增加图数据库连接池大小 | 吞吐量提升 20% |
| **异步处理** | 非关键步骤异步执行 | 延迟降低 15% |

### 9.3 性能监控指标

系统 MUST 收集以下性能指标：

| 指标 | 描述 | 告警阈值 |
|------|------|----------|
| `routing_latency_p99` | 路由延迟 P99 | > 500ms |
| `vector_search_latency` | 向量检索延迟 | > 100ms |
| `graph_expansion_latency` | 图扩展延迟 | > 200ms |
| `cache_hit_rate` | 缓存命中率 | < 30% |
| `fallback_rate` | 降级率 | > 5% |
| `conflict_detected_count` | 检测到的冲突数 | - |

---

## 10. 版本历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|----------|------|
| 1.0.0 | 2026-04-12 | 初始版本发布 | GraphSkill Architecture Team |
| 2.0.0 | 2026-04-17 | **VR-First Architecture 范式转变**：算法流程从 Graph-First → VR-First 4-Phase Pipeline；ANN top_k 10→5；expansion depth 2→1；scoring α=0.5→0.8,β=0.3→0.1,γ=0.2→0.1；新增 VR Seed Protection；fallback 目标从 ZS→VR baseline | GraphSkill Architecture Team |

---

**文档结束**

*本文档定义了 GraphSkill 系统的核心路由引擎算法。相关数据结构定义详见 [RFC-08: 数据结构与 Schema 定义](RFC-08-data-structures-schema.md)，API 接口规范详见 [RFC-07: API 接口规范](RFC-07-api-interface-specification.md)。*