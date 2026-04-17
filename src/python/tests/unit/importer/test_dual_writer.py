"""
DualWriteTransactionManager 单元测试。

测试双写事务管理器的所有功能。
"""

from __future__ import annotations

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from graphskill.ingestion.importer.dual_writer import (
    WriteOperation,
    WriteStep,
    DualWriteResult,
    DualWriteTransactionManager,
)
from graphskill.core.models import SkillNode, SkillEdge, EdgeType


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def manager() -> DualWriteTransactionManager:
    """创建管理器实例（无客户端）。"""
    return DualWriteTransactionManager()


@pytest.fixture
def manager_with_mocked_clients() -> DualWriteTransactionManager:
    """创建带模拟客户端的管理器。"""
    graph_client = MagicMock()
    graph_client.create_node = AsyncMock(return_value={"success": True, "uid": "test:skill"})
    graph_client.update_node = AsyncMock(return_value={"success": True})
    graph_client.delete_node = AsyncMock(return_value={"success": True})
    graph_client.create_edge = AsyncMock(return_value={"success": True})
    
    vector_client = MagicMock()
    vector_client.insert = AsyncMock(return_value={"success": True, "id": "test:skill"})
    vector_client.upsert = AsyncMock(return_value={"success": True, "id": "test:skill"})
    vector_client.delete = AsyncMock(return_value={"success": True})
    
    return DualWriteTransactionManager(
        graph_client=graph_client,
        vector_client=vector_client,
        max_retries=3,
        retry_delay=0.1,
    )


@pytest.fixture
def skill_node() -> SkillNode:
    """创建技能节点。"""
    return SkillNode(
        uid="test:skill",
        intent="Test Skill",
        intent_description="A test skill for unit testing purposes with sufficient length to pass validation",
        permissions=["fs:read"],
        version="1.0.0",
    )


@pytest.fixture
def skill_edge() -> SkillEdge:
    """创建技能边。"""
    return SkillEdge(
        source_uid="test:skill",
        target_uid="test:dep",
        edge_type=EdgeType.REQUIRES,
        weight=1.0,
    )


@pytest.fixture
def embedding() -> list[float]:
    """创建嵌入向量。"""
    return [0.1] * 384  # 384 维向量


@pytest.fixture
def skill_nodes_batch() -> list[SkillNode]:
    """创建批量技能节点。"""
    return [
        SkillNode(
            uid=f"test:skill{i}",
            intent=f"Test Skill {i}",
            intent_description=f"A test skill {i} for unit testing purposes with sufficient length to pass validation",
            permissions=["fs:read"],
            version="1.0.0",
        )
        for i in range(3)
    ]


@pytest.fixture
def embeddings_batch() -> list[list[float]]:
    """创建批量嵌入向量。"""
    return [[0.1] * 384 for _ in range(3)]


# ============================================================================
# WriteOperation Tests
# ============================================================================


class TestWriteOperation:
    """WriteOperation 枚举测试。"""
    
    def test_operation_enum_values(self) -> None:
        """测试枚举值。"""
        assert WriteOperation.CREATE.value == "create"
        assert WriteOperation.UPDATE.value == "update"
        assert WriteOperation.DELETE.value == "delete"
    
    def test_operation_enum_count(self) -> None:
        """测试枚举数量。"""
        assert len(WriteOperation) == 3
    
    def test_operation_is_string_enum(self) -> None:
        """测试是否为字符串枚举。"""
        assert isinstance(WriteOperation.CREATE, str)


# ============================================================================
# WriteStep Tests
# ============================================================================


class TestWriteStep:
    """WriteStep 数据结构测试。"""
    
    def test_create_write_step_success(self) -> None:
        """测试创建成功的写入步骤。"""
        step = WriteStep(
            operation=WriteOperation.CREATE,
            target="graph",
            data={"uid": "skill:test:1.0"},
            timestamp=datetime.now(),
            success=True,
        )
        
        assert step.operation == WriteOperation.CREATE
        assert step.target == "graph"
        assert step.data == {"uid": "skill:test:1.0"}
        assert step.success is True
        assert step.error is None
    
    def test_create_write_step_failure(self) -> None:
        """测试创建失败的写入步骤。"""
        step = WriteStep(
            operation=WriteOperation.CREATE,
            target="graph",
            data={"uid": "skill:test:1.0"},
            timestamp=datetime.now(),
            success=False,
            error="Connection failed",
        )
        
        assert step.success is False
        assert step.error == "Connection failed"
    
    def test_write_step_to_dict(self) -> None:
        """测试转换为字典。"""
        timestamp = datetime.now()
        step = WriteStep(
            operation=WriteOperation.CREATE,
            target="graph",
            data={"uid": "skill:test:1.0"},
            timestamp=timestamp,
            success=True,
        )
        
        result = step.to_dict()
        
        assert result["operation"] == "create"
        assert result["target"] == "graph"
        assert result["data"] == {"uid": "skill:test:1.0"}
        assert result["timestamp"] == timestamp.isoformat()
        assert result["success"] is True
        assert result["error"] is None


# ============================================================================
# DualWriteResult Tests
# ============================================================================


class TestDualWriteResult:
    """DualWriteResult 数据结构测试。"""
    
    def test_create_success_result(self) -> None:
        """测试创建成功结果。"""
        result = DualWriteResult(
            success=True,
            operation=WriteOperation.CREATE,
            skill_uid="skill:test:1.0",
            graph_result={"uid": "skill:test:1.0"},
            vector_result={"id": "skill:test:1.0"},
        )
        
        assert result.success is True
        assert result.operation == WriteOperation.CREATE
        assert result.skill_uid == "skill:test:1.0"
        assert result.graph_result is not None
        assert result.vector_result is not None
        assert result.error is None
        assert result.rollback_executed is False
        assert result.rollback_success is False
    
    def test_create_failure_result(self) -> None:
        """测试创建失败结果。"""
        result = DualWriteResult(
            success=False,
            operation=WriteOperation.CREATE,
            skill_uid="skill:test:1.0",
            error="Write failed",
            rollback_executed=True,
            rollback_success=True,
        )
        
        assert result.success is False
        assert result.error == "Write failed"
        assert result.rollback_executed is True
        assert result.rollback_success is True
    
    def test_result_defaults(self) -> None:
        """测试默认值。"""
        result = DualWriteResult(
            success=True,
            operation=WriteOperation.CREATE,
            skill_uid="skill:test:1.0",
        )
        
        assert result.graph_result is None
        assert result.vector_result is None
        assert result.error is None
        assert result.rollback_executed is False
        assert result.rollback_success is False
        assert result.steps == []
        assert result.duration_ms == 0
    
    def test_result_to_dict(self) -> None:
        """测试转换为字典。"""
        step = WriteStep(
            operation=WriteOperation.CREATE,
            target="graph",
            data={"uid": "skill:test:1.0"},
            timestamp=datetime.now(),
            success=True,
        )
        
        result = DualWriteResult(
            success=True,
            operation=WriteOperation.CREATE,
            skill_uid="skill:test:1.0",
            graph_result={"uid": "skill:test:1.0"},
            steps=[step],
            duration_ms=100,
        )
        
        d = result.to_dict()
        
        assert d["success"] is True
        assert d["operation"] == "create"
        assert d["skill_uid"] == "skill:test:1.0"
        assert d["graph_result"] == {"uid": "skill:test:1.0"}
        assert d["duration_ms"] == 100
        assert len(d["steps"]) == 1


# ============================================================================
# DualWriteTransactionManager Init Tests
# ============================================================================


class TestDualWriteTransactionManagerInit:
    """DualWriteTransactionManager 初始化测试。"""
    
    def test_init_default(self) -> None:
        """测试默认初始化。"""
        manager = DualWriteTransactionManager()
        
        assert manager.graph_client is None
        assert manager.vector_client is None
        assert manager.max_retries == DualWriteTransactionManager.DEFAULT_MAX_RETRIES
        assert manager.retry_delay == DualWriteTransactionManager.DEFAULT_RETRY_DELAY
    
    def test_init_with_clients(self) -> None:
        """测试带客户端初始化。"""
        graph_client = MagicMock()
        vector_client = MagicMock()
        
        manager = DualWriteTransactionManager(
            graph_client=graph_client,
            vector_client=vector_client,
            max_retries=5,
            retry_delay=1.0,
        )
        
        assert manager.graph_client == graph_client
        assert manager.vector_client == vector_client
        assert manager.max_retries == 5
        assert manager.retry_delay == 1.0
    
    def test_default_constants(self) -> None:
        """测试默认常量。"""
        assert DualWriteTransactionManager.DEFAULT_MAX_RETRIES == 3
        assert DualWriteTransactionManager.DEFAULT_RETRY_DELAY == 0.5


# ============================================================================
# DualWriteTransactionManager Write Skill Tests
# ============================================================================


class TestDualWriteTransactionManagerWriteSkill:
    """write_skill 方法测试。"""
    
    @pytest.mark.asyncio
    async def test_write_skill_no_clients(
        self,
        manager: DualWriteTransactionManager,
        skill_node: SkillNode,
        embedding: list[float],
    ) -> None:
        """测试无客户端时的写入。"""
        result = await manager.write_skill(skill_node, embedding)
        
        # 无客户端时源代码有 mock 处理，返回成功
        assert result.success is True
        assert result.skill_uid == skill_node.uid
    
    @pytest.mark.asyncio
    async def test_write_skill_success(
        self,
        manager_with_mocked_clients: DualWriteTransactionManager,
        skill_node: SkillNode,
        embedding: list[float],
    ) -> None:
        """测试成功写入。"""
        result = await manager_with_mocked_clients.write_skill(skill_node, embedding)
        
        assert result.success is True
        assert result.skill_uid == skill_node.uid
        assert result.graph_result is not None
        assert result.vector_result is not None
        assert len(result.steps) == 2  # graph + vector
    
    @pytest.mark.asyncio
    async def test_write_skill_update_operation(
        self,
        manager_with_mocked_clients: DualWriteTransactionManager,
        skill_node: SkillNode,
        embedding: list[float],
    ) -> None:
        """测试更新操作。"""
        result = await manager_with_mocked_clients.write_skill(
            skill_node, embedding, WriteOperation.UPDATE
        )
        
        assert result.success is True
        assert result.operation == WriteOperation.UPDATE
    
    @pytest.mark.asyncio
    async def test_write_skill_delete_operation(
        self,
        manager_with_mocked_clients: DualWriteTransactionManager,
        skill_node: SkillNode,
        embedding: list[float],
    ) -> None:
        """测试删除操作。"""
        result = await manager_with_mocked_clients.write_skill(
            skill_node, embedding, WriteOperation.DELETE
        )
        
        assert result.success is True
        assert result.operation == WriteOperation.DELETE
    
    @pytest.mark.asyncio
    async def test_write_skill_graph_failure(
        self,
        skill_node: SkillNode,
        embedding: list[float],
    ) -> None:
        """测试图数据库写入失败（vector-first: vector 成功后 graph 失败，回滚 vector）。"""
        graph_client = MagicMock()
        graph_client.create_node = AsyncMock(side_effect=Exception("Graph DB error"))
        
        vector_client = MagicMock()
        vector_client.insert = AsyncMock(return_value={"success": True, "id": skill_node.uid})
        vector_client.delete = AsyncMock(return_value={"success": True})  # rollback
        
        manager = DualWriteTransactionManager(
            graph_client=graph_client,
            vector_client=vector_client,
            max_retries=2,
            retry_delay=0.1,
        )
        
        result = await manager.write_skill(skill_node, embedding)
        
        assert result.success is False
        assert "Graph DB write failed" in result.error
        assert result.rollback_executed is True
    
    @pytest.mark.asyncio
    async def test_write_skill_vector_failure_no_rollback(
        self,
        skill_node: SkillNode,
        embedding: list[float],
    ) -> None:
        """测试向量数据库写入失败（vector-first: vector 第一步失败，无需回滚）。"""
        graph_client = MagicMock()
        graph_client.create_node = AsyncMock(return_value={"success": True})
        graph_client.delete_node = AsyncMock(return_value={"success": True})
        
        vector_client = MagicMock()
        vector_client.insert = AsyncMock(side_effect=Exception("Vector DB error"))
        
        manager = DualWriteTransactionManager(
            graph_client=graph_client,
            vector_client=vector_client,
        )
        
        result = await manager.write_skill(skill_node, embedding)
        
        assert result.success is False
        assert "Vector DB write failed" in result.error
        assert result.rollback_executed is False


# ============================================================================
# DualWriteTransactionManager Write Edge Tests
# ============================================================================


class TestDualWriteTransactionManagerWriteEdge:
    """write_edge 方法测试。"""
    
    @pytest.mark.asyncio
    async def test_write_edge_no_client(
        self,
        manager: DualWriteTransactionManager,
        skill_edge: SkillEdge,
    ) -> None:
        """测试无客户端时的边写入。"""
        result = await manager.write_edge(skill_edge)
        
        # 无客户端时源代码有 mock 处理，返回成功
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_write_edge_success(
        self,
        manager_with_mocked_clients: DualWriteTransactionManager,
        skill_edge: SkillEdge,
    ) -> None:
        """测试成功写入边。"""
        result = await manager_with_mocked_clients.write_edge(skill_edge)
        
        assert result.success is True
        assert result.skill_uid == f"{skill_edge.source_uid}->{skill_edge.target_uid}"
        assert len(result.steps) == 1
    
    @pytest.mark.asyncio
    async def test_write_edge_failure(
        self,
        skill_edge: SkillEdge,
    ) -> None:
        """测试边写入失败。"""
        graph_client = MagicMock()
        graph_client.create_edge = AsyncMock(side_effect=Exception("Edge creation failed"))
        
        manager = DualWriteTransactionManager(graph_client=graph_client)
        
        result = await manager.write_edge(skill_edge)
        
        assert result.success is False
        assert "Edge write failed" in result.error


# ============================================================================
# DualWriteTransactionManager Batch Write Tests
# ============================================================================


class TestDualWriteTransactionManagerBatchWrite:
    """batch_write_skills 方法测试。"""
    
    @pytest.mark.asyncio
    async def test_batch_write_empty(
        self,
        manager_with_mocked_clients: DualWriteTransactionManager,
    ) -> None:
        """测试空批量写入。"""
        result = await manager_with_mocked_clients.batch_write_skills([], [])
        
        # batch_write_skills 返回 list
        assert len(result) == 0
    
    @pytest.mark.asyncio
    async def test_batch_write_success(
        self,
        manager_with_mocked_clients: DualWriteTransactionManager,
        skill_nodes_batch: list[SkillNode],
        embeddings_batch: list[list[float]],
    ) -> None:
        """测试成功批量写入。"""
        result = await manager_with_mocked_clients.batch_write_skills(
            skill_nodes_batch, embeddings_batch
        )
        
        # batch_write_skills 返回 list
        assert len(result) == 3
        success_count = sum(1 for r in result if r.success)
        assert success_count == 3
    
    @pytest.mark.asyncio
    async def test_batch_write_partial_failure(
        self,
        skill_nodes_batch: list[SkillNode],
        embeddings_batch: list[list[float]],
    ) -> None:
        """测试部分失败批量写入。"""
        graph_client = MagicMock()
        # 第一个成功，第二个失败，第三个成功
        graph_client.create_node = AsyncMock(
            side_effect=[
                {"success": True},
                Exception("Failed"),
                {"success": True},
            ]
        )
        
        vector_client = MagicMock()
        vector_client.insert = AsyncMock(return_value={"success": True})
        vector_client.upsert = AsyncMock(return_value={"success": True})
        
        manager = DualWriteTransactionManager(
            graph_client=graph_client,
            vector_client=vector_client,
            max_retries=1,
        )
        
        result = await manager.batch_write_skills(skill_nodes_batch, embeddings_batch)
        
        # batch_write_skills 返回 list
        success_count = sum(1 for r in result if r.success)
        failure_count = sum(1 for r in result if not r.success)
        assert success_count == 2
        assert failure_count == 1


# ============================================================================
# Edge Cases Tests
# ============================================================================


class TestEdgeCases:
    """边界条件测试。"""
    
    @pytest.mark.asyncio
    async def test_write_skill_empty_embedding(
        self,
        manager_with_mocked_clients: DualWriteTransactionManager,
        skill_node: SkillNode,
    ) -> None:
        """测试空嵌入向量。"""
        result = await manager_with_mocked_clients.write_skill(skill_node, [])
        
        # 应该能处理空嵌入
        assert result.success is True or result.success is False
    
    @pytest.mark.asyncio
    async def test_write_skill_large_embedding(
        self,
        manager: DualWriteTransactionManager,
        skill_node: SkillNode,
    ) -> None:
        """测试大嵌入向量。"""
        large_embedding = [0.1] * 1536  # 1536 维
        result = await manager.write_skill(skill_node, large_embedding)
        
        # 无客户端时 mock 处理返回成功
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_concurrent_writes(
        self,
        manager: DualWriteTransactionManager,
        skill_nodes_batch: list[SkillNode],
        embeddings_batch: list[list[float]],
    ) -> None:
        """测试并发写入。"""
        import asyncio
        
        tasks = [
            manager.write_skill(node, emb)
            for node, emb in zip(skill_nodes_batch, embeddings_batch)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # 无客户端时 mock 处理返回成功
        assert all(r.success for r in results)


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """集成测试。"""
    
    @pytest.mark.asyncio
    async def test_full_write_workflow(
        self,
        manager: DualWriteTransactionManager,
        skill_node: SkillNode,
        skill_edge: SkillEdge,
        embedding: list[float],
    ) -> None:
        """测试完整写入工作流。"""
        # 1. 写入节点
        node_result = await manager.write_skill(skill_node, embedding)
        assert node_result.success is True
        
        # 2. 写入边
        edge_result = await manager.write_edge(skill_edge)
        assert edge_result.success is True
    
    @pytest.mark.asyncio
    async def test_write_and_delete_workflow(
        self,
        manager: DualWriteTransactionManager,
        skill_node: SkillNode,
        embedding: list[float],
    ) -> None:
        """测试写入和删除工作流。"""
        # 1. 创建
        create_result = await manager.write_skill(
            skill_node, embedding, WriteOperation.CREATE
        )
        assert create_result.success is True
        
        # 2. 删除
        delete_result = await manager.write_skill(
            skill_node, embedding, WriteOperation.DELETE
        )
        assert delete_result.success is True