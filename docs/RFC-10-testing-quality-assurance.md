# RFC-10: 测试与质量保障规范

**文档编号:** RFC-10  
**版本:** 2.0.0
**状态:** 正式发布
**最后更新:** 2026-04-17
**作者:** GraphSkill Architecture Team  
**分类:** 架构规范 - 测试质量  
**依赖:** RFC-00, RFC-03, RFC-06

---

## 目录

1. [概述](#1-概述)
2. [测试策略总览](#2-测试策略总览)
3. [单元测试规范](#3-单元测试规范)
4. [集成测试规范](#4-集成测试规范)
5. [端到端测试规范](#5-端到端测试规范)
6. [性能测试规范](#6-性能测试规范)
7. [混沌工程测试规范](#7-混沌工程测试规范)
8. [测试覆盖率要求](#8-测试覆盖率要求)
9. [Mock 策略](#9-mock-策略)
10. [测试数据管理](#10-测试数据管理)
11. [CI/CD 流水线集成](#11-cicd-流水线集成)
12. [质量门禁与发布准则](#12-质量门禁与发布准则)
13. [版本历史](#13-版本历史)

---

## 1. 概述

### 1.1 文档目的

本文档定义 GraphSkill 系统的测试与质量保障规范，涵盖测试策略总览、单元测试规范、集成测试规范、端到端测试规范、性能测试规范、混沌工程测试规范、测试覆盖率要求、Mock 策略、测试数据管理、CI/CD 流水线集成以及质量门禁与发布准则。

### 1.2 适用范围

本文档适用于：
- 测试工程师：编写测试用例与测试框架
- 开发工程师：编写单元测试与集成测试
- QA 工程师：执行端到端测试与验收测试
- DevOps 工程师：配置 CI/CD 流水线

### 1.3 测试金字塔

系统 MUST 遵循测试金字塔原则，确保测试层次合理分布：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Testing Pyramid                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                              ┌─────────────┐                                │
│                              │   E2E Tests │  数量: 少 (< 50)               │
│                              │   (UI/API)  │  速度: 慢 (分钟级)             │
│                              └─────────────┘  成本: 高                      │
│                                                                             │
│                        ┌─────────────────────┐                              │
│                        │  Integration Tests  │  数量: 中 (100-200)          │
│                        │  (Service/DB)       │  速度: 中 (秒级)             │
│                        └─────────────────────┘  成本: 中                    │
│                                                                             │
│              ┌─────────────────────────────────────┐                        │
│              │          Unit Tests                  │  数量: 多 (> 500)      │
│              │          (Function/Class)           │  速度: 快 (毫秒级)     │
│              └─────────────────────────────────────┘  成本: 低              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.4 测试类型定义

| 测试类型 | 描述 | 执行频率 | 负责角色 |
|----------|------|----------|----------|
| **单元测试** | 测试单个函数/方法 | 每次提交 | 开发工程师 |
| **集成测试** | 测试模块间交互 | 每次合并 | 开发工程师 |
| **端到端测试** | 测试完整业务流程 | 每日/发布前 | QA 工程师 |
| **性能测试** | 测试系统性能指标 | 每周/发布前 | 测试工程师 |
| **混沌工程** | 测试系统容错能力 | 每周 | SRE 工程师 |
| **安全测试** | 测试安全漏洞 | 每月 | 安全工程师 |

---

## 2. 测试策略总览

### 2.1 测试策略矩阵

| 测试维度 | 单元测试 | 集成测试 | E2E 测试 | 性能测试 |
|----------|----------|----------|----------|----------|
| **Routing Gateway** | ✅ 必须 | ✅ 必须 | ✅ 必须 | ✅ 必须 |
| **Ingestion Engine** | ✅ 必须 | ✅ 必须 | ✅ 必须 | ⚠️ 推荐 |
| **Telemetry Consumer** | ✅ 必须 | ✅ 必须 | ⚠️ 推荐 | ⚠️ 推荐 |
| **Graph-Vector Store** | ⚠️ 推荐 | ✅ 必须 | ✅ 必须 | ✅ 必须 |
| **Permission Interceptor** | ✅ 必须 | ✅ 必须 | ✅ 必须 | ⚠️ 推荐 |

### 2.2 测试环境定义

| 环境 | 用途 | 数据 | 配置 |
|------|------|------|------|
| **Local** | 开发调试 | Mock 数据 | 最小配置 |
| **CI** | 自动化测试 | 测试数据集 | 标准配置 |
| **Staging** | 预发布验证 | 生产镜像数据 | 生产配置 |
| **Performance** | 性能基准 | 压测数据 | 高配资源 |

### 2.3 测试数据策略

| 数据类型 | 来源 | 管理 |
|----------|------|------|
| **Mock 数据** | 程序生成 | 内存/临时文件 |
| **测试数据集** | 预定义 | Git 仓库 |
| **生产镜像** | 生产环境脱敏 | 定期同步 |
| **压测数据** | 自动生成 | 批量脚本 |

---

## 3. 单元测试规范

### 3.1 单元测试原则

| 原则 | 描述 |
|------|------|
| **FIRST 原则** | Fast（快速）、Independent（独立）、Repeatable（可重复）、Self-validating（自验证）、Timely（及时） |
| **单一职责** | 每个测试只验证一个功能点 |
| **边界覆盖** | 必须覆盖边界条件和异常场景 |
| **命名规范** | 测试方法名清晰描述测试场景 |

### 3.2 单元测试命名规范

```python
# Python 单元测试命名规范
# 格式: test_{method_name}_{scenario}_{expected_result}

class TestRoutingGateway:
    
    # 正常场景
    def test_route_with_valid_query_returns_skills(self):
        pass
    
    # 边界场景
    def test_route_with_empty_query_raises_validation_error(self):
        pass
    
    def test_route_with_max_tokens_limit_truncates_context(self):
        pass
    
    # 异常场景
    def test_route_when_graph_db_down_returns_fallback_response(self):
        pass
    
    def test_route_when_vector_search_fails_raises_error(self):
        pass
```

```go
// Go 单元测试命名规范
// 格式: Test{MethodName}_{Scenario}_{ExpectedResult}

func TestRoute_WithValidQuery_ReturnsSkills(t *testing.T) {}

func TestRoute_WithEmptyQuery_RaisesValidationError(t *testing.T) {}

func TestRoute_WhenGraphDBDown_ReturnsFallbackResponse(t *testing.T) {}
```

### 3.3 Python 单元测试示例

```python
import pytest
from unittest.mock import Mock, patch, MagicMock
from graphskill.routing.gateway import RoutingGateway
from graphskill.routing.retriever import HybridRetriever
from graphskill.routing.pruner import ConflictPruner

class TestRoutingGateway:
    """
    Routing Gateway 单元测试。
    """
    
    @pytest.fixture
    def mock_graph_store(self):
        """Mock 图数据库客户端。"""
        return Mock()
    
    @pytest.fixture
    def mock_vector_store(self):
        """Mock 向量数据库客户端。"""
        return Mock()
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis 客户端。"""
        return Mock()
    
    @pytest.fixture
    def gateway(self, mock_graph_store, mock_vector_store, mock_redis):
        """创建 Routing Gateway 实例。"""
        return RoutingGateway(
            graph_store=mock_graph_store,
            vector_store=mock_vector_store,
            redis=mock_redis,
            config=RoutingConfig()
        )
    
    def test_route_with_valid_query_returns_skills(
        self,
        gateway,
        mock_vector_store,
        mock_graph_store
    ):
        """
        测试正常路由请求返回技能列表。
        """
        # Setup: Mock 向量检索返回种子节点
        mock_vector_store.search.return_value = [
            {"skill_id": "git:commit", "distance": 0.85},
            {"skill_id": "git:push", "distance": 0.80}
        ]
        
        # Setup: Mock 图扩展返回依赖节点
        mock_graph_store.execute_query.return_value = [
            {"uid": "git:configure", "properties": {}}
        ]
        
        # Execute
        result = gateway.route(
            query="提交代码变更",
            context_state={},
            max_tokens=4000
        )
        
        # Verify
        assert result is not None
        assert len(result.skills) >= 2
        assert result.routing_mode == "normal"
        assert result.token_count > 0
        
        # Verify 调用链
        mock_vector_store.search.assert_called_once()
        mock_graph_store.execute_query.assert_called()
    
    def test_route_with_empty_query_raises_validation_error(self, gateway):
        """
        测试空 Query 触发校验错误。
        """
        with pytest.raises(ValidationError) as exc_info:
            gateway.route(
                query="",  # 空 Query
                context_state={},
                max_tokens=4000
            )
        
        assert exc_info.value.error_code == "1002"
        assert "query" in str(exc_info.value.message)
    
    def test_route_with_invalid_max_tokens_raises_validation_error(self, gateway):
        """
        测试无效 max_tokens 触发校验错误。
        """
        with pytest.raises(ValidationError):
            gateway.route(
                query="测试查询",
                context_state={},
                max_tokens=100  # 低于最小值 500
            )
    
    @patch('graphskill.routing.gateway.time.time')
    def test_route_when_graph_db_timeout_returns_fallback_response(
        self,
        mock_time,
        gateway,
        mock_graph_store,
        mock_vector_store
    ):
        """
        测试图数据库超时时返回降级响应。
        """
        # Setup: Mock 图数据库超时
        mock_graph_store.execute_query.side_effect = TimeoutError("Graph DB timeout")
        
        # Setup: Mock 向量检索正常
        mock_vector_store.search.return_value = [
            {"skill_id": "git:commit", "distance": 0.85}
        ]
        
        # Execute
        result = gateway.route(
            query="提交代码变更",
            context_state={},
            max_tokens=4000
        )
        
        # Verify: 返回降级响应
        assert result.routing_mode == "fallback"
        assert "Graph database unavailable" in result.warnings
        assert len(result.skills) > 0
    
    def test_route_with_cached_result_returns_cached_response(
        self,
        gateway,
        mock_redis,
        mock_vector_store
    ):
        """
        测试缓存命中时返回缓存响应。
        """
        # Setup: Mock Redis 缓存命中
        cached_result = {
            "skills": [{"skill_id": "git:commit"}],
            "routing_mode": "cached",
            "token_count": 1000
        }
        mock_redis.get.return_value = json.dumps(cached_result)
        
        # Execute
        result = gateway.route(
            query="提交代码变更",
            context_state={},
            max_tokens=4000
        )
        
        # Verify: 返回缓存结果，不调用向量检索
        assert result.routing_mode == "cached"
        mock_vector_store.search.assert_not_called()


class TestConflictPruner:
    """
    冲突剪枝器单元测试。
    """
    
    @pytest.fixture
    def pruner(self):
        return ConflictPruner()
    
    def test_prune_with_no_conflicts_returns_all_nodes(self, pruner):
        """
        测试无冲突时返回所有节点。
        """
        nodes = [
            CandidateNode(skill_id="a", score=0.9),
            CandidateNode(skill_id="b", score=0.8),
            CandidateNode(skill_id="c", score=0.7)
        ]
        
        conflict_graph = ConflictGraph()
        for node in nodes:
            conflict_graph.add_node(node.skill_id, node.score)
        
        result = pruner.prune(conflict_graph)
        
        assert len(result) == 3
    
    def test_prune_with_conflicts_returns_max_independent_set(self, pruner):
        """
        测试有冲突时返回最大独立集。
        """
        conflict_graph = ConflictGraph()
        conflict_graph.add_node("a", 0.9)
        conflict_graph.add_node("b", 0.8)
        conflict_graph.add_node("c", 0.7)
        
        # 添加冲突边
        conflict_graph.add_conflict_edge("a", "b", severity=5)
        
        result = pruner.prune(conflict_graph)
        
        # 应返回 a（得分最高）和 c（无冲突）
        assert "a" in result
        assert "c" in result
        assert "b" not in result  # b 与 a 冲突
    
    def test_prune_with_all_conflicts_returns_single_node(self, pruner):
        """
        测试所有节点冲突时返回单个最高得分节点。
        """
        conflict_graph = ConflictGraph()
        conflict_graph.add_node("a", 0.9)
        conflict_graph.add_node("b", 0.8)
        conflict_graph.add_node("c", 0.7)
        
        # 所有节点互相冲突
        conflict_graph.add_conflict_edge("a", "b", severity=5)
        conflict_graph.add_conflict_edge("a", "c", severity=5)
        conflict_graph.add_conflict_edge("b", "c", severity=5)
        
        result = pruner.prune(conflict_graph)
        
        assert len(result) == 1
        assert "a" in result  # 最高得分
    
    def test_prune_with_substitutes_keeps_only_one(self, pruner):
        """
        测试替代关系时只保留一个节点。
        """
        conflict_graph = ConflictGraph()
        conflict_graph.add_node("git:commit", 0.9)
        conflict_graph.add_node("git:commit_amend", 0.8)
        
        # 添加替代边
        conflict_graph.add_substitute_edge("git:commit", "git:commit_amend", similarity=0.85)
        
        result = pruner.prune(conflict_graph)
        
        assert len(result) == 1
        assert "git:commit" in result  # 保留得分更高的
```

### 3.4 Go 单元测试示例

```go
package routing

import (
    "testing"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/mock"
)

// MockGraphStore 是图数据库的 Mock
type MockGraphStore struct {
    mock.Mock
}

func (m *MockGraphStore) ExecuteQuery(query string, params map[string]interface{}) ([]map[string]interface{}, error) {
    args := m.Called(query, params)
    return args.Get(0).([]map[string]interface{}), args.Error(1)
}

// TestRoute_WithValidQuery_ReturnsSkills 测试正常路由
func TestRoute_WithValidQuery_ReturnsSkills(t *testing.T) {
    // Setup
    mockGraph := new(MockGraphStore)
    mockVector := new(MockVectorStore)
    
    mockVector.On("Search", mock.Anything, 5).Return([]SearchResult{
        {SkillID: "git:commit", Distance: 0.85},
    }, nil)
    
    mockGraph.On("ExecuteQuery", mock.Anything, mock.Anything).Return([]map[string]interface{}{
        {"uid": "git:configure"},
    }, nil)
    
    gateway := NewRoutingGateway(mockGraph, mockVector, nil, DefaultConfig())
    
    // Execute
    result, err := gateway.Route("提交代码变更", ContextState{}, 4000)
    
    // Verify
    assert.NoError(t, err)
    assert.NotNil(t, result)
    assert.GreaterOrEqual(t, len(result.Skills), 1)
    assert.Equal(t, "normal", result.RoutingMode)
    
    mockVector.AssertExpectations(t)
    mockGraph.AssertExpectations(t)
}

// TestRoute_WithEmptyQuery_RaisesValidationError 测试空 Query
func TestRoute_WithEmptyQuery_RaisesValidationError(t *testing.T) {
    gateway := NewRoutingGateway(nil, nil, nil, DefaultConfig())
    
    result, err := gateway.Route("", ContextState{}, 4000)
    
    assert.Nil(t, result)
    assert.Error(t, err)
    assert.Equal(t, "1002", err.(*ValidationError).Code)
}

// TestRoute_WhenGraphDBDown_ReturnsFallbackResponse 测试降级
func TestRoute_WhenGraphDBDown_ReturnsFallbackResponse(t *testing.T) {
    mockGraph := new(MockGraphStore)
    mockVector := new(MockVectorStore)
    
    mockVector.On("Search", mock.Anything, 10).Return([]SearchResult{
        {SkillID: "git:commit", Distance: 0.85},
    }, nil)
    
    mockGraph.On("ExecuteQuery", mock.Anything, mock.Anything).Return(nil, errors.New("connection refused"))
    
    gateway := NewRoutingGateway(mockGraph, mockVector, nil, DefaultConfig())
    
    result, err := gateway.Route("提交代码变更", ContextState{}, 4000)
    
    assert.NoError(t, err)
    assert.Equal(t, "fallback", result.RoutingMode)
    assert.Contains(t, result.Warnings, "Graph database unavailable")
}
```

### 3.5 单元测试覆盖率要求

| 模块 | 行覆盖率要求 | 分支覆盖率要求 |
|------|--------------|----------------|
| **Routing Gateway** | ≥ 80% | ≥ 70% |
| **Ingestion Engine** | ≥ 75% | ≥ 65% |
| **Conflict Pruner** | ≥ 90% | ≥ 85% |
| **Permission Interceptor** | ≥ 85% | ≥ 75% |
| **Telemetry Consumer** | ≥ 70% | ≥ 60% |

---

## 4. 集成测试规范

### 4.1 集成测试范围

集成测试 MUST 覆盖以下模块间交互：

| 测试场景 | 模块交互 | 测试重点 |
|----------|----------|----------|
| **路由完整流程** | Gateway → Vector DB → Graph DB → Pruner | 数据流转正确性 |
| **导入完整流程** | Ingestion → Parser → Validator → DB | 数据一致性 |
| **权限校验流程** | Interceptor → Session → Permission | 权限判断正确性 |
| **遥测反馈流程** | Consumer → Kafka → Analytics → DB | 数据处理正确性 |

### 4.2 集成测试环境配置

```yaml
# docker-compose.test.yaml
version: '3.8'

services:
  # 测试服务
  routing-gateway-test:
    build:
      context: ./services/routing-gateway
      dockerfile: Dockerfile.test
    environment:
      - ENVIRONMENT=test
      - NEO4J_URI=bolt://neo4j-test:7687
      - MILVUS_HOST=milvus-test
      - REDIS_HOST=redis-test
    depends_on:
      - neo4j-test
      - milvus-test
      - redis-test
  
  # 测试数据库
  neo4j-test:
    image: neo4j:5.12-community
    environment:
      - NEO4J_AUTH=neo4j/testpassword
    ports:
      - "7687:7687"
  
  milvus-test:
    image: milvusdb/milvus:v2.3.3
    ports:
      - "19530:19530"
  
  redis-test:
    image: redis:7.2-alpine
    ports:
      - "6379:6379"
```

### 4.3 Python 集成测试示例

```python
import pytest
import asyncio
from graphskill.routing.gateway import RoutingGateway
from graphskill.ingestion.engine import IngestionEngine
from graphskill.storage.graph_store import Neo4jClient
from graphskill.storage.vector_store import MilvusClient

@pytest.mark.integration
class TestRoutingIntegration:
    """
    路由集成测试（使用真实数据库连接）。
    """
    
    @pytest.fixture(scope="class")
    async def graph_client(self):
        """创建真实图数据库连接。"""
        client = Neo4jClient(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="testpassword"
        )
        await client.connect()
        yield client
        await client.close()
    
    @pytest.fixture(scope="class")
    async def vector_client(self):
        """创建真实向量数据库连接。"""
        client = MilvusClient(
            host="localhost",
            port=19530
        )
        await client.connect()
        yield client
        await client.close()
    
    @pytest.fixture(scope="class")
    async def gateway(self, graph_client, vector_client):
        """创建 Routing Gateway 实例。"""
        return RoutingGateway(
            graph_store=graph_client,
            vector_store=vector_client,
            redis=None,  # 测试环境不使用缓存
            config=RoutingConfig()
        )
    
    async def test_route_returns_correct_skill_dependencies(
        self,
        gateway,
        graph_client
    ):
        """
        测试路由返回正确的技能依赖关系。
        """
        # Setup: 插入测试数据
        await graph_client.execute_query("""
        CREATE (a:SkillNode {uid: 'test:skill_a'})
        CREATE (b:SkillNode {uid: 'test:skill_b'})
        CREATE (a)-[:REQUIRES {is_hard: true}]->(b)
        """)
        
        # Execute
        result = await gateway.route(
            query="执行测试技能 A",
            context_state={},
            max_tokens=4000
        )
        
        # Verify: skill_b 应作为依赖被召回
        skill_ids = [s.skill_id for s in result.skills]
        assert "test:skill_b" in skill_ids
        
        # Cleanup
        await graph_client.execute_query("""
        MATCH (n:SkillNode) WHERE n.uid STARTS WITH 'test:' DETACH DELETE n
        """)
    
    async def test_route_handles_conflict_correctly(
        self,
        gateway,
        graph_client
    ):
        """
        测试路由正确处理冲突关系。
        """
        # Setup: 插入冲突技能
        await graph_client.execute_query("""
        CREATE (a:SkillNode {uid: 'test:skill_a'})
        CREATE (b:SkillNode {uid: 'test:skill_b'})
        CREATE (a)-[:CONFLICTS_WITH {severity: 5}]->(b)
        """)
        
        # Execute
        result = await gateway.route(
            query="执行测试技能",
            context_state={},
            max_tokens=4000
        )
        
        # Verify: 结果中不应同时包含 a 和 b
        skill_ids = [s.skill_id for s in result.skills]
        if "test:skill_a" in skill_ids:
            assert "test:skill_b" not in skill_ids
        elif "test:skill_b" in skill_ids:
            assert "test:skill_a" not in skill_ids
        
        # Cleanup
        await graph_client.execute_query("""
        MATCH (n:SkillNode) WHERE n.uid STARTS WITH 'test:' DETACH DELETE n
        """)
    
    async def test_vector_search_and_graph_expansion_combined(
        self,
        gateway,
        vector_client,
        graph_client
    ):
        """
        测试向量检索与图扩展的组合流程。
        """
        # Setup: 插入向量数据
        test_embedding = [0.1] * 1536  # 测试向量
        await vector_client.insert({
            "id": "test_vector_1",
            "skill_id": "test:skill_a",
            "vector": test_embedding
        })
        
        # Setup: 插入图数据
        await graph_client.execute_query("""
        CREATE (a:SkillNode {uid: 'test:skill_a', embedding_id: 'test_vector_1'})
        CREATE (b:SkillNode {uid: 'test:skill_b'})
        CREATE (a)-[:REQUIRES]->(b)
        """)
        
        # Execute
        result = await gateway.route(
            query="测试查询",
            context_state={},
            max_tokens=4000
        )
        
        # Verify: 应召回 skill_a（向量匹配）和 skill_b（图扩展）
        skill_ids = [s.skill_id for s in result.skills]
        assert "test:skill_a" in skill_ids
        assert "test:skill_b" in skill_ids
        
        # Cleanup
        await vector_client.delete("test_vector_1")
        await graph_client.execute_query("""
        MATCH (n:SkillNode) WHERE n.uid STARTS WITH 'test:' DETACH DELETE n
        """)


@pytest.mark.integration
class TestIngestionIntegration:
    """
    导入集成测试。
    """
    
    async def test_ingest_skill_creates_graph_and_vector_entries(
        self,
        graph_client,
        vector_client
    ):
        """
        测试导入技能后图数据库和向量数据库都有记录。
        """
        engine = IngestionEngine(
            graph_store=graph_client,
            vector_store=vector_client
        )
        
        # Execute: 导入测试技能
        skill_data = {
            "skill_id": "test:ingested_skill",
            "version": "1.0.0",
            "intent_description": "测试导入的技能描述，长度满足50字符要求",
            "permissions": ["fs:read:/tmp"]
        }
        
        result = await engine.ingest(skill_data)
        
        # Verify: 图数据库有节点
        graph_result = await graph_client.execute_query("""
        MATCH (s:SkillNode {uid: 'test:ingested_skill'}) RETURN s
        """)
        assert len(graph_result) > 0
        
        # Verify: 向量数据库有向量
        vector_result = await vector_client.get_by_skill_id("test:ingested_skill")
        assert vector_result is not None
        
        # Cleanup
        await graph_client.execute_query("""
        MATCH (n:SkillNode {uid: 'test:ingested_skill'}) DETACH DELETE n
        """)
        await vector_client.delete_by_skill_id("test:ingested_skill")
```

### 4.4 集成测试标记规范

```python
# pytest.ini
[pytest]
markers =
    unit: 单元测试（快速，无外部依赖）
    integration: 集成测试（需要外部服务）
    e2e: 端到端测试（完整业务流程）
    performance: 性能测试
    slow: 慢速测试（执行时间 > 1s）

# 执行特定标记的测试
pytest -m unit          # 仅执行单元测试
pytest -m integration   # 仅执行集成测试
pytest -m "not slow"    # 排除慢速测试
```

---

## 5. 端到端测试规范

### 5.1 E2E 测试场景定义

| 场景 ID | 场景描述 | 测试步骤 | 预期结果 |
|---------|----------|----------|----------|
| **E2E-001** | 完整路由流程 | Query → Route → Skills → Assemble | 返回正确技能上下文 |
| **E2E-002** | 技能导入流程 | File → Ingest → Validate → Store | 技能成功入库 |
| **E2E-003** | 权限校验流程 | Action → Validate → Allow/Deny | 正确判断权限 |
| **E2E-004** | 降级恢复流程 | Graph DB Down → Fallback → Recovery | 正确降级与恢复 |
| **E2E-005** | 遥测反馈流程 | Execute → Report → Update | 可靠性正确更新 |

### 5.2 E2E 测试实现

```python
import pytest
import requests
import time

@pytest.mark.e2e
class TestRoutingE2E:
    """
    路由端到端测试。
    """
    
    BASE_URL = "http://localhost:8080/v1"
    
    def test_complete_routing_flow_returns_valid_context(self):
        """
        E2E-001: 完整路由流程测试。
        """
        # Step 1: 创建 Session
        session_response = requests.post(
            f"{self.BASE_URL}/sessions",
            json={"agent_id": "test_agent"}
        )
        assert session_response.status_code == 201
        session_id = session_response.json()["data"]["session_id"]
        
        # Step 2: 执行路由请求
        route_response = requests.post(
            f"{self.BASE_URL}/route",
            headers={"X-Session-ID": session_id},
            json={
                "query": "我需要提交代码变更到 Git 仓库",
                "max_tokens": 4000
            }
        )
        
        # Verify: 路由成功
        assert route_response.status_code == 200
        data = route_response.json()["data"]
        
        # Verify: 返回技能列表
        assert len(data["skills"]) > 0
        
        # Verify: 技能包含必要字段
        for skill in data["skills"]:
            assert "skill_id" in skill
            assert "description" in skill
            assert "instructions" in skill
        
        # Verify: routing_mode 为 normal
        assert data["routing_mode"] == "normal"
        
        # Step 3: 验证技能依赖关系正确
        skill_ids = [s["skill_id"] for s in data["skills"]]
        
        # 如果包含 git:commit，应包含 git:configure
        if any("commit" in sid for sid in skill_ids):
            assert any("configure" in sid for sid in skill_ids)
    
    def test_skill_import_flow_creates_valid_entries(self):
        """
        E2E-002: 技能导入流程测试。
        """
        # Step 1: 创建测试技能文件
        skill_content = """
---
skill_id: e2e:test_skill
version: 1.0.0
intent_description: |
  E2E 测试技能，用于验证导入流程的正确性。
  此描述满足最小长度要求。
permissions:
  - fs:read:/tmp
---
# Test Skill
这是一个测试技能。
"""
        
        # Step 2: 执行导入
        ingest_response = requests.post(
            f"{self.BASE_URL}/ingest",
            json={
                "source": {
                    "type": "file",
                    "path": "/tmp/e2e_test_skill.md"
                },
                "options": {
                    "validation_mode": "strict"
                }
            }
        )
        
        # Verify: 导入成功
        assert ingest_response.status_code == 202
        
        # Step 3: 等待导入完成
        import_id = ingest_response.json()["data"]["import_id"]
        time.sleep(5)  # 等待异步处理
        
        # Step 4: 验证技能已入库
        skill_response = requests.get(
            f"{self.BASE_URL}/skills/e2e:test_skill"
        )
        assert skill_response.status_code == 200
    
    def test_permission_validation_flow_correctly_deny(self):
        """
        E2E-003: 权限校验流程测试。
        """
        # Step 1: 创建 Session（无 fs:write 权限）
        session_response = requests.post(
            f"{self.BASE_URL}/sessions",
            json={
                "agent_id": "test_agent",
                "authorization": {
                    "permissions": ["fs:read:/tmp"]  # 仅读权限
                }
            }
        )
        session_id = session_response.json()["data"]["session_id"]
        
        # Step 2: 尝试调用需要写权限的技能
        validate_response = requests.post(
            f"{self.BASE_URL}/validate_permission",
            headers={"X-Session-ID": session_id},
            json={
                "skill_id": "fs:write_file",
                "action": {
                    "tool_name": "write_file",
                    "parameters": {"path": "/tmp/test.txt"}
                }
            }
        )
        
        # Verify: 权限被拒绝
        data = validate_response.json()["data"]
        assert data["allowed"] is False
        assert "PERMISSION_DENIED" in data["error_code"]
    
    def test_fallback_and_recovery_flow(self):
        """
        E2E-004: 降级恢复流程测试。
        """
        # Step 1: 模拟图数据库故障（通过配置）
        # 此步骤需要手动触发或使用混沌工程工具
        
        # Step 2: 执行路由请求
        route_response = requests.post(
            f"{self.BASE_URL}/route",
            json={
                "query": "测试降级场景",
                "max_tokens": 4000
            }
        )
        
        # Verify: 返回降级响应
        if route_response.status_code == 503:
            data = route_response.json()["data"]
            assert data["routing_mode"] == "fallback"
            assert len(data["warnings"]) > 0
        
        # Step 3: 等待恢复
        time.sleep(30)
        
        # Step 4: 验证恢复正常
        health_response = requests.get(f"{self.BASE_URL}/health")
        assert health_response.json()["data"]["status"] == "healthy"
```

### 5.3 E2E 测试数据管理

```python
# test_data/skills/e2e_skill_1.md
---
skill_id: e2e:skill_1
version: 1.0.0
intent_description: |
  E2E 测试技能 1，用于验证基本路由功能。
  此技能模拟 Git 提交操作。
permissions:
  - exec:git
  - fs:read:/tmp
topology_hints:
  requires:
    - e2e:skill_2
---

# E2E Skill 1

执行 Git 提交操作。

```bash
git commit -m "$MESSAGE"
```
```

```python
# test_data/skills/e2e_skill_2.md
---
skill_id: e2e:skill_2
version: 1.0.0
intent_description: |
  E2E 测试技能 2，用于验证依赖关系。
  此技能模拟 Git 配置操作。
permissions:
  - exec:git
---

# E2E Skill 2

配置 Git 用户信息。

```bash
git config --global user.name "$NAME"
git config --global user.email "$EMAIL"
```
```

---

## 6. 性能测试规范

### 6.1 性能测试指标

| 指标 | 目标值 | 测试方法 | 告警阈值 |
|------|--------|----------|----------|
| **路由延迟 P50** | < 200ms | 压测工具 | > 300ms |
| **路由延迟 P99** | < 500ms | 压测工具 | > 800ms |
| **吞吐量 QPS** | > 1000 | 压测工具 | < 800 |
| **错误率** | < 0.1% | 压测工具 | > 0.5% |
| **CPU 使用率** | < 70% | 监控 | > 80% |
| **内存使用率** | < 80% | 监控 | > 90% |

### 6.2 性能测试工具配置

```yaml
# locustfile.py
from locust import HttpUser, task, between

class RoutingUser(HttpUser):
    """
    路由性能测试用户。
    """
    
    wait_time = between(0.1, 0.5)
    
    def on_start(self):
        """创建 Session。"""
        response = self.client.post("/v1/sessions", json={"agent_id": "perf_test"})
        self.session_id = response.json()["data"]["session_id"]
    
    @task(10)
    def route_normal_query(self):
        """正常路由请求。"""
        self.client.post(
            "/v1/route",
            headers={"X-Session-ID": self.session_id},
            json={
                "query": "提交代码变更到 Git 仓库",
                "max_tokens": 4000
            },
            name="/route/normal"
        )
    
    @task(3)
    def route_complex_query(self):
        """复杂路由请求。"""
        self.client.post(
            "/v1/route",
            headers={"X-Session-ID": self.session_id},
            json={
                "query": "执行完整的 CI/CD 流程，包括代码提交、构建、测试和部署",
                "max_tokens": 8000
            },
            name="/route/complex"
        )
    
    @task(1)
    def route_short_query(self):
        """短 Query 路由请求。"""
        self.client.post(
            "/v1/route",
            headers={"X-Session-ID": self.session_id},
            json={
                "query": "查看文件",
                "max_tokens": 2000
            },
            name="/route/short"
        )
```

### 6.3 性能测试执行脚本

```bash
# 执行性能测试
locust -f locustfile.py \
    --host http://localhost:8080 \
    --users 100 \
    --spawn-rate 10 \
    --run-time 5m \
    --headless \
    --html results.html

# 执行压力测试（极限场景）
locust -f locustfile.py \
    --host http://localhost:8080 \
    --users 500 \
    --spawn-rate 50 \
    --run-time 10m \
    --headless
```

### 6.4 性能基准测试代码

```python
import pytest
import time
import statistics

@pytest.mark.performance
class TestRoutingPerformance:
    """
    路由性能基准测试。
    """
    
    def test_routing_latency_p99_under_500ms(self, gateway):
        """
        测试路由延迟 P99 < 500ms。
        """
        latencies = []
        
        for _ in range(1000):
            start = time.time()
            gateway.route("测试查询", {}, 4000)
            latency = (time.time() - start) * 1000
            latencies.append(latency)
        
        p99 = statistics.quantiles(latencies, n=100)[98]  # 99th percentile
        
        assert p99 < 500, f"P99 latency {p99}ms exceeds 500ms threshold"
    
    def test_routing_throughput_over_1000_qps(self, gateway):
        """
        测试吞吐量 > 1000 QPS。
        """
        import asyncio
        
        async def single_route():
            return gateway.route("测试查询", {}, 4000)
        
        # 并发执行 1000 请求
        start = time.time()
        results = asyncio.gather(*[single_route() for _ in range(1000)])
        duration = time.time() - start
        
        qps = 1000 / duration
        
        assert qps > 1000, f"QPS {qps} below 1000 threshold"
    
    def test_routing_under_high_load_maintains_error_rate(self, gateway):
        """
        测试高负载下错误率 < 0.1%。
        """
        errors = 0
        total = 10000
        
        for _ in range(total):
            try:
                gateway.route("测试查询", {}, 4000)
            except Exception:
                errors += 1
        
        error_rate = errors / total
        
        assert error_rate < 0.001, f"Error rate {error_rate} exceeds 0.1%"
```

---

## 7. 混沌工程测试规范

### 7.1 混沌测试场景

| 场景 | 故障注入 | 预期行为 | 验证指标 |
|------|----------|----------|----------|
| **CHAOS-001** | Neo4j 进程终止 | 自动降级 | fallback_rate < 5% |
| **CHAOS-002** | Milvus 响应延迟 500ms | 熔断触发 | 熔断时间 < 10s |
| **CHAOS-003** | Redis 连接耗尽 | 快速失败 | 错误率 < 1% |
| **CHAOS-004** | 网络分区 | 自动故障转移 | RTO < 5min |
| **CHAOS-005** | Pod 随机终止 | 自动恢复 | 恢复时间 < 30s |

### 7.2 混沌测试实现

```python
import pytest
import subprocess
import time

@pytest.mark.chaos
class TestChaosEngineering:
    """
    混沌工程测试。
    """
    
    def test_neo4j_failure_triggers_fallback(self):
        """
        CHAOS-001: Neo4j 故障触发降级。
        """
        # Step 1: 记录初始状态
        initial_health = requests.get("http://localhost:8080/v1/health").json()
        assert initial_health["data"]["components"]["graph_db"]["status"] == "healthy"
        
        # Step 2: 注入故障 - 终止 Neo4j
        subprocess.run(["docker", "stop", "neo4j-test"], check=True)
        time.sleep(5)  # 等待故障生效
        
        # Step 3: 执行路由请求
        response = requests.post(
            "http://localhost:8080/v1/route",
            json={"query": "测试混沌场景", "max_tokens": 4000}
        )
        
        # Verify: 返回降级响应
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["routing_mode"] == "fallback"
        
        # Step 4: 恢复 Neo4j
        subprocess.run(["docker", "start", "neo4j-test"], check=True)
        time.sleep(30)  # 等待恢复
        
        # Step 5: 验证恢复正常
        health = requests.get("http://localhost:8080/v1/health").json()
        assert health["data"]["components"]["graph_db"]["status"] == "healthy"
    
    def test_milvus_latency_triggers_circuit_breaker(self):
        """
        CHAOS-002: Milvus 延迟触发熔断。
        """
        # Step 1: 注入网络延迟
        subprocess.run([
            "docker", "exec", "routing-gateway-test",
            "tc", "qdisc", "add", "dev", "eth0",
            "root", "netem", "delay", "500ms"
        ], check=True)
        
        # Step 2: 执行多次路由请求
        responses = []
        for _ in range(10):
            response = requests.post(
                "http://localhost:8080/v1/route",
                json={"query": "测试熔断", "max_tokens": 4000}
            )
            responses.append(response)
        
        # Verify: 熔断触发（部分请求返回降级响应）
        fallback_count = sum(
            1 for r in responses
            if r.json()["data"]["routing_mode"] == "fallback"
        )
        assert fallback_count > 0
        
        # Step 3: 移除延迟
        subprocess.run([
            "docker", "exec", "routing-gateway-test",
            "tc", "qdisc", "del", "dev", "eth0", "root"
        ], check=True)
    
    def test_pod_failure_auto_recovery(self):
        """
        CHAOS-005: Pod 故障自动恢复。
        """
        # Step 1: 获取当前 Pod 数量
        initial_pods = subprocess.run(
            ["kubectl", "get", "pods", "-n", "graphskill", "-l", "app=routing-gateway"],
            capture_output=True, text=True
        )
        initial_count = len(initial_pods.stdout.strip().split('\n')) - 1
        
        # Step 2: 随机终止一个 Pod
        pod_name = initial_pods.stdout.strip().split('\n')[1].split()[0]
        subprocess.run(["kubectl", "delete", "pod", pod_name, "-n", "graphskill"], check=True)
        
        # Step 3: 等待自动恢复
        time.sleep(30)
        
        # Step 4: 验证 Pod 数量恢复
        recovered_pods = subprocess.run(
            ["kubectl", "get", "pods", "-n", "graphskill", "-l", "app=routing-gateway"],
            capture_output=True, text=True
        )
        recovered_count = len(recovered_pods.stdout.strip().split('\n')) - 1
        
        assert recovered_count == initial_count
```

---

## 8. 测试覆盖率要求

### 8.1 覆盖率目标

| 覆盖率类型 | 目标值 | 最低值 |
|------------|--------|--------|
| **行覆盖率** | 80% | 70% |
| **分支覆盖率** | 70% | 60% |
| **函数覆盖率** | 90% | 80% |
| **模块覆盖率** | 100% | 95% |

### 8.2 覆盖率测量工具

```bash
# Python 覆盖率测量
pytest --cov=graphskill --cov-report=html --cov-report=xml

# Go 覆盖率测量
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out -o coverage.html
```

### 8.3 覆盖率报告配置

```yaml
# .coveragerc
[run]
source = graphskill
branch = True
omit =
    graphskill/tests/*
    graphskill/__init__.py

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise NotImplementedError
    if TYPE_CHECKING:
    @abstractmethod

[html]
directory = htmlcov

[xml]
output = coverage.xml
```

---

## 9. Mock 策略

### 9.1 Mock 使用原则

| 原则 | 描述 |
|------|------|
| **外部依赖必须 Mock** | 数据库、网络服务、文件系统等外部依赖 MUST 使用 Mock |
| **内部逻辑不 Mock** | 业务逻辑 SHOULD NOT Mock，应使用真实实现 |
| **Mock 行为可验证** | Mock 对象 MUST 可验证调用次数和参数 |
| **Mock 数据真实** | Mock 数据 SHOULD 模拟真实数据格式 |

### 9.2 Mock 实现示例

```python
from unittest.mock import Mock, MagicMock, patch

# Mock 图数据库
def create_mock_graph_store():
    mock = Mock()
    
    # 配置默认返回值
    mock.execute_query.return_value = [
        {"uid": "test:skill", "properties": {"execution_success_rate": 1.0}}
    ]
    
    # 配置异常场景
    mock.execute_query.side_effect = TimeoutError("Connection timeout")
    
    return mock

# Mock 向量数据库
def create_mock_vector_store():
    mock = Mock()
    
    mock.search.return_value = [
        {"skill_id": "test:skill", "distance": 0.85, "id": "vec_001"}
    ]
    
    mock.insert.return_value = "vec_001"
    
    return mock

# Mock Redis
def create_mock_redis():
    mock = MagicMock()
    
    # 配置缓存命中
    mock.get.return_value = json.dumps({
        "skills": [{"skill_id": "cached:skill"}],
        "routing_mode": "cached"
    })
    
    # 配置缓存未命中
    mock.get.return_value = None
    
    return mock

# 使用 patch 进行临时 Mock
@patch('graphskill.routing.gateway.Neo4jClient')
@patch('graphskill.routing.gateway.MilvusClient')
def test_with_patched_dependencies(mock_neo4j, mock_milvus):
    """使用 patch 临时替换依赖。"""
    # 配置 Mock 行为
    mock_neo4j.return_value.execute_query.return_value = []
    
    # 执行测试
    gateway = RoutingGateway(...)
    result = gateway.route(...)
```

### 9.3 Mock 数据生成器

```python
class MockDataGenerator:
    """
    Mock 数据生成器。
    """
    
    @staticmethod
    def generate_skill_node(skill_id: str = None) -> dict:
        """生成 Mock 技能节点。"""
        return {
            "uid": skill_id or f"mock:skill_{uuid.uuid4().hex[:8]}",
            "version": "1.0.0",
            "intent_description": f"Mock 技能描述 {uuid.uuid4().hex[:8]}",
            "permissions": ["fs:read:/tmp"],
            "execution_success_rate": 0.95,
            "is_deprecated": False,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def generate_skill_edge(source: str, target: str, edge_type: str) -> dict:
        """生成 Mock 技能边。"""
        return {
            "source": source,
            "target": target,
            "edge_type": edge_type,
            "properties": {
                "weight": 1.0,
                "verified_by_human": False
            },
            "created_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def generate_routing_result(skill_count: int = 5) -> dict:
        """生成 Mock 路由结果。"""
        skills = []
        for i in range(skill_count):
            skills.append({
                "skill_id": f"mock:skill_{i}",
                "priority": i + 1,
                "type": "seed" if i < 2 else "required",
                "description": f"Mock 技能 {i}",
                "instructions": f"执行 Mock 操作 {i}"
            })
        
        return {
            "skills": skills,
            "routing_mode": "normal",
            "token_count": 1000 * skill_count,
            "latency_ms": 200 + skill_count * 10,
            "warnings": []
        }
```

---

## 10. 测试数据管理

### 10.1 测试数据目录结构

```
test_data/
├── skills/
│   ├── basic/
│   │   ├── skill_1.md
│   │   ├── skill_2.md
│   │   └── skill_3.md
│   ├── conflicts/
│   │   ├── conflict_a.md
│   │   └── conflict_b.md
│   ├── dependencies/
│   │   ├── parent_skill.md
│   │   └── child_skill.md
│   └── invalid/
│   │   ├── missing_field.md
│   │   ├── invalid_format.md
│   │   └── cycle_a.md
│   └── cycle_b.md
├── vectors/
│   ├── test_vectors.json
│   └── benchmark_vectors.json
├── sessions/
│   ├── test_session_1.json
│   └── test_session_2.json
├── queries/
│   ├── normal_queries.json
│   ├── edge_case_queries.json
│   └── performance_queries.json
└── expected_results/
    ├── routing_results.json
    └── validation_results.json
```

### 10.2 测试数据加载器

```python
import json
import os

class TestDataLoader:
    """
    测试数据加载器。
    """
    
    DATA_DIR = "test_data"
    
    @classmethod
    def load_skills(cls, category: str) -> list:
        """加载技能测试数据。"""
        skills_dir = os.path.join(cls.DATA_DIR, "skills", category)
        skills = []
        
        for filename in os.listdir(skills_dir):
            if filename.endswith(".md"):
                filepath = os.path.join(skills_dir, filename)
                with open(filepath, 'r') as f:
                    skills.append({
                        "filename": filename,
                        "content": f.read()
                    })
        
        return skills
    
    @classmethod
    def load_vectors(cls, name: str = "test_vectors") -> list:
        """加载向量测试数据。"""
        filepath = os.path.join(cls.DATA_DIR, "vectors", f"{name}.json")
        with open(filepath, 'r') as f:
            return json.load(f)
    
    @classmethod
    def load_queries(cls, category: str) -> list:
        """加载查询测试数据。"""
        filepath = os.path.join(cls.DATA_DIR, "queries", f"{category}_queries.json")
        with open(filepath, 'r') as f:
            return json.load(f)
    
    @classmethod
    def load_expected_results(cls) -> dict:
        """加载预期结果。"""
        filepath = os.path.join(cls.DATA_DIR, "expected_results", "routing_results.json")
        with open(filepath, 'r') as f:
            return json.load(f)
```

### 10.3 测试数据清理策略

```python
class TestDataCleaner:
    """
    测试数据清理器。
    """
    
    @staticmethod
    async def cleanup_test_skills(graph_client, prefix: str = "test:"):
        """清理测试技能节点。"""
        await graph_client.execute_query(f"""
        MATCH (n:SkillNode) WHERE n.uid STARTS WITH '{prefix}' DETACH DELETE n
        """)
    
    @staticmethod
    async def cleanup_test_vectors(vector_client, prefix: str = "test_"):
        """清理测试向量。"""
        await vector_client.delete_by_prefix(prefix)
    
    @staticmethod
    async def cleanup_test_sessions(redis_client, prefix: str = "test_sess_"):
        """清理测试 Session。"""
        keys = await redis_client.keys(f"{prefix}*")
        for key in keys:
            await redis_client.delete(key)
```

---

## 11. CI/CD 流水线集成

### 11.1 GitHub Actions 配置

```yaml
# .github/workflows/test.yml
name: Test Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      
      - name: Run unit tests
        run: pytest -m unit --cov=graphskill --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: coverage.xml

  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    
    services:
      neo4j:
        image: neo4j:5.12-community
        env:
          NEO4J_AUTH: neo4j/testpassword
        ports:
          - 7687:7687
      
      redis:
        image: redis:7.2-alpine
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest
      
      - name: Run integration tests
        run: pytest -m integration
        env:
          NEO4J_URI: bolt://localhost:7687
          NEO4J_PASSWORD: testpassword
          REDIS_HOST: localhost

  e2e-tests:
    name: E2E Tests
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest requests
      
      - name: Deploy test environment
        run: |
          docker-compose -f docker-compose.test.yaml up -d
          sleep 30
      
      - name: Run E2E tests
        run: pytest -m e2e
      
      - name: Cleanup
        run: docker-compose -f docker-compose.test.yaml down

  performance-tests:
    name: Performance Tests
    runs-on: ubuntu-latest
    needs: [e2e-tests]
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install locust
      
      - name: Deploy test environment
        run: |
          docker-compose -f docker-compose.test.yaml up -d
          sleep 30
      
      - name: Run performance tests
        run: |
          locust -f locustfile.py \
            --host http://localhost:8080 \
            --users 100 \
            --spawn-rate 10 \
            --run-time 5m \
            --headless \
            --html results.html
      
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: performance-results
          path: results.html

  quality-gate:
    name: Quality Gate
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests, e2e-tests]
    
    steps:
      - name: Check coverage threshold
        run: |
          coverage=$(cat coverage.xml | grep 'line-rate' | head -1 | sed 's/.*line-rate="\([0-9.]*\)".*/\1/')
          if [ $(echo "$coverage < 0.7" | bc) -eq 1 ]; then
            echo "Coverage $coverage below threshold 70%"
            exit 1
          fi
      
      - name: All tests passed
        run: echo "All quality gates passed"
```

### 11.2 测试执行流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Code Push  │────▶│  Unit Tests │────▶│ Integration │────▶│  E2E Tests  │
│             │     │             │     │   Tests     │     │             │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  [触发 CI]           [快速反馈]          [服务验证]          [业务验证]
       │                   │                   │                   │
       │                   │                   │                   │
       │                   ▼                   ▼                   ▼
       │             ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
       │             │  Coverage   │     │  DB Tests   │     │  Full Flow  │
       │             │  Check      │     │             │     │             │
       │             └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Quality     │◀────│  Coverage   │◀────│  All Tests  │◀────│  Results    │
│ Gate        │     │  Report     │     │  Passed     │     │  Upload     │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

---

## 12. 质量门禁与发布准则

### 12.1 质量门禁定义

| 门禁项 | 要求 | 检查时机 |
|--------|------|----------|
| **单元测试通过** | 100% 通过 | 每次提交 |
| **集成测试通过** | 100% 通过 | 每次合并 |
| **E2E 测试通过** | 100% 通过 | 发布前 |
| **覆盖率达标** | ≥ 70% | 每次提交 |
| **无安全漏洞** | 0 高危漏洞 | 发布前 |
| **性能达标** | P99 < 500ms | 发布前 |
| **代码审查通过** | 至少 1 人 Approve | 每次合并 |

### 12.2 发布准则

```yaml
# 发布检查清单
release_checklist:
  pre_release:
    - all_unit_tests_passed: true
    - all_integration_tests_passed: true
    - all_e2e_tests_passed: true
    - coverage_threshold_met: true
    - security_scan_passed: true
    - performance_benchmark_passed: true
    - code_review_approved: true
    - documentation_updated: true
  
  release:
    - version_tag_created: true
    - changelog_updated: true
    - release_notes_published: true
  
  post_release:
    - deployment_successful: true
    - smoke_tests_passed: true
    - monitoring_alerts_normal: true
```

### 12.3 质量门禁脚本

```bash
#!/bin/bash
# quality_gate.sh

echo "Running Quality Gate Checks..."

# 1. 单元测试
pytest -m unit --tb=short
if [ $? -ne 0 ]; then
    echo "❌ Unit tests failed"
    exit 1
fi
echo "✅ Unit tests passed"

# 2. 覆盖率检查
coverage=$(pytest --cov=graphskill --cov-report=term | grep TOTAL | awk '{print $4}' | sed 's/%//')
if [ $(echo "$coverage < 70" | bc) -eq 1 ]; then
    echo "❌ Coverage $coverage% below threshold 70%"
    exit 1
fi
echo "✅ Coverage $coverage% meets threshold"

# 3. 安全扫描
safety check
if [ $? -ne 0 ]; then
    echo "❌ Security vulnerabilities found"
    exit 1
fi
echo "✅ Security scan passed"

# 4. Lint 检查
ruff check graphskill
if [ $? -ne 0 ]; then
    echo "❌ Lint check failed"
    exit 1
fi
echo "✅ Lint check passed"

echo "🎉 All quality gates passed!"
```

---

## 13. 版本历史

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|----------|------|
| 1.0.0 | 2026-04-12 | 初始版本发布 | GraphSkill Architecture Team |
| 2.0.0 | 2026-04-17 | **VR-First 架构适配**：新增 VR-first 集成测试定义（GS ≥ VR 保证验证、VR Seed Protection 测试、消融实验测试）；新增 EnhancementResult 数据契约测试 | GraphSkill Architecture Team |

---

**文档结束**

*本文档定义了 GraphSkill 系统的测试与质量保障规范。相关部署与运维规范详见 [RFC-09: 部署与运维规范](RFC-09-deployment-operations.md)，性能与高可用规范详见 [RFC-06: 性能安全与高可用规范](RFC-06-performance-security-high-availability.md)。*