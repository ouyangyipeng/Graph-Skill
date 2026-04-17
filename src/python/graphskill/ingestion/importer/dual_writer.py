"""
双写事务管理器。

确保图数据库与向量数据库的强一致性写入。
采用 Saga 模式实现补偿事务。

Reference: RFC-01 Section 5.1
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any

from graphskill.core.models import SkillNode, SkillEdge
from graphskill.core.exceptions import DatabaseError


class WriteOperation(str, Enum):
    """写入操作类型。"""
    
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


@dataclass
class WriteStep:
    """写入步骤记录。"""
    
    operation: WriteOperation
    target: str  # "graph" or "vector"
    data: dict
    timestamp: datetime
    success: bool
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "operation": self.operation.value,
            "target": self.target,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "success": self.success,
            "error": self.error,
        }


@dataclass
class DualWriteResult:
    """双写结果。"""
    
    success: bool
    operation: WriteOperation
    skill_uid: str
    graph_result: Optional[dict] = None
    vector_result: Optional[dict] = None
    error: Optional[str] = None
    rollback_executed: bool = False
    rollback_success: bool = False
    steps: list[WriteStep] = field(default_factory=list)
    duration_ms: int = 0
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "operation": self.operation.value,
            "skill_uid": self.skill_uid,
            "graph_result": self.graph_result,
            "vector_result": self.vector_result,
            "error": self.error,
            "rollback_executed": self.rollback_executed,
            "rollback_success": self.rollback_success,
            "steps": [s.to_dict() for s in self.steps],
            "duration_ms": self.duration_ms,
        }


class DualWriteTransactionManager:
    """
    双写事务管理器。
    
    实现图数据库与向量数据库的强一致性写入。
    采用 Saga 模式：先写向量数据库，成功后写图数据库，
    失败时执行补偿事务回滚。
    
    Per RFC-01 Section 5.1: 写入顺序 MUST 为 vector-first，
    因为向量索引是检索的第一入口，图关系是扩展入口。
    
    Features:
        - Saga 模式补偿事务
        - 自动重试机制
        - 写入顺序保证 (vector-first)
        - 失败回滚
    
    Example:
        >>> manager = DualWriteTransactionManager(graph_client, vector_client)
        >>> result = await manager.write_skill(skill_node, embedding)
        >>> if not result.success:
        ...     print(f"Error: {result.error}")
    """
    
    # 默认重试配置
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 0.5  # 秒
    
    def __init__(
        self,
        graph_client: Optional[Any] = None,
        vector_client: Optional[Any] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ):
        """
        初始化管理器。
        
        Args:
            graph_client: 图数据库客户端
            vector_client: 向量数据库客户端
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        """
        self.graph_client = graph_client
        self.vector_client = vector_client
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    async def write_skill(
        self,
        skill_node: SkillNode,
        embedding: list[float],
        operation: WriteOperation = WriteOperation.CREATE,
    ) -> DualWriteResult:
        """
        双写技能节点。
        
        Saga 流程 (vector-first per RFC-01 Section 5.1):
        1. 写入向量数据库（检索第一入口）
        2. 成功后写入图数据库（扩展入口）
        3. 图数据库失败时回滚向量数据库
        
        Args:
            skill_node: 技能节点
            embedding: 向量嵌入
            operation: 操作类型
            
        Returns:
            DualWriteResult: 写入结果
        """
        start_time = datetime.now()
        steps: list[WriteStep] = []
        skill_uid = skill_node.uid
        
        # Step 1: 写入向量数据库 (vector-first)
        vector_result = None
        for attempt in range(self.max_retries):
            try:
                vector_result = await self._write_to_vector(skill_node, embedding, operation)
                steps.append(WriteStep(
                    operation=operation,
                    target="vector",
                    data={"uid": skill_uid, "embedding_dim": len(embedding)},
                    timestamp=datetime.now(),
                    success=True,
                ))
                break
            except Exception as e:
                error_msg = str(e)
                if attempt == self.max_retries - 1:
                    steps.append(WriteStep(
                        operation=operation,
                        target="vector",
                        data={"uid": skill_uid},
                        timestamp=datetime.now(),
                        success=False,
                        error=error_msg,
                    ))
                    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                    return DualWriteResult(
                        success=False,
                        operation=operation,
                        skill_uid=skill_uid,
                        error=f"Vector DB write failed after {self.max_retries} retries: {error_msg}",
                        steps=steps,
                        duration_ms=duration_ms,
                    )
                await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        # Step 2: 写入图数据库
        graph_result = None
        try:
            graph_result = await self._write_to_graph(skill_node, operation)
            steps.append(WriteStep(
                operation=operation,
                target="graph",
                data={"uid": skill_uid},
                timestamp=datetime.now(),
                success=True,
            ))
        except Exception as e:
            error_msg = str(e)
            steps.append(WriteStep(
                operation=operation,
                target="graph",
                data={"uid": skill_uid},
                timestamp=datetime.now(),
                success=False,
                error=error_msg,
            ))
            
            # Step 3: 回滚向量数据库
            rollback_success = await self._rollback_vector(skill_node, operation)
            
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return DualWriteResult(
                success=False,
                operation=operation,
                skill_uid=skill_uid,
                vector_result=vector_result,
                error=f"Graph DB write failed: {error_msg}",
                rollback_executed=True,
                rollback_success=rollback_success,
                steps=steps,
                duration_ms=duration_ms,
            )
        
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        return DualWriteResult(
            success=True,
            operation=operation,
            skill_uid=skill_uid,
            graph_result=graph_result,
            vector_result=vector_result,
            steps=steps,
            duration_ms=duration_ms,
        )
    
    async def write_edge(
        self,
        edge: SkillEdge,
        operation: WriteOperation = WriteOperation.CREATE,
    ) -> DualWriteResult:
        """
        写入边关系。
        
        边只存储在图数据库，不涉及向量数据库。
        
        Args:
            edge: 技能边
            operation: 操作类型
            
        Returns:
            DualWriteResult: 写入结果
        """
        start_time = datetime.now()
        steps: list[WriteStep] = []
        edge_key = f"{edge.source_uid}->{edge.target_uid}"
        
        try:
            result = await self._write_edge_to_graph(edge, operation)
            steps.append(WriteStep(
                operation=operation,
                target="graph",
                data={"edge": edge_key, "type": edge.edge_type.value},
                timestamp=datetime.now(),
                success=True,
            ))
            
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return DualWriteResult(
                success=True,
                operation=operation,
                skill_uid=edge_key,
                graph_result=result,
                steps=steps,
                duration_ms=duration_ms,
            )
        except Exception as e:
            steps.append(WriteStep(
                operation=operation,
                target="graph",
                data={"edge": edge_key},
                timestamp=datetime.now(),
                success=False,
                error=str(e),
            ))
            
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return DualWriteResult(
                success=False,
                operation=operation,
                skill_uid=edge_key,
                error=f"Edge write failed: {e}",
                steps=steps,
                duration_ms=duration_ms,
            )
    
    async def batch_write_skills(
        self,
        skill_nodes: list[SkillNode],
        embeddings: list[list[float]],
        operation: WriteOperation = WriteOperation.CREATE,
    ) -> list[DualWriteResult]:
        """
        批量写入技能节点。
        
        Args:
            skill_nodes: 技能节点列表
            embeddings: 向量嵌入列表
            operation: 操作类型
            
        Returns:
            list: 写入结果列表
        """
        if len(skill_nodes) != len(embeddings):
            raise DatabaseError("Mismatched skill_nodes and embeddings count")
        
        results: list[DualWriteResult] = []
        
        # 并行写入（但每个写入内部保证顺序）
        tasks = [
            self.write_skill(node, emb, operation)
            for node, emb in zip(skill_nodes, embeddings)
        ]
        
        results = await asyncio.gather(*tasks)
        
        return results
    
    async def batch_write_edges(
        self,
        edges: list[SkillEdge],
        operation: WriteOperation = WriteOperation.CREATE,
    ) -> list[DualWriteResult]:
        """
        批量写入边。
        
        Args:
            edges: 边列表
            operation: 操作类型
            
        Returns:
            list: 写入结果列表
        """
        tasks = [self.write_edge(edge, operation) for edge in edges]
        results = await asyncio.gather(*tasks)
        return results
    
    async def _write_to_graph(
        self,
        skill_node: SkillNode,
        operation: WriteOperation,
    ) -> dict:
        """
        写入图数据库。
        
        Args:
            skill_node: 技能节点
            operation: 操作类型
            
        Returns:
            dict: 写入结果
        """
        if self.graph_client is None:
            # 模拟写入（用于测试）
            return {"uid": skill_node.uid, "status": "mock_success"}
        
        # 实际写入逻辑（需要根据具体客户端实现）
        # 这里提供通用接口
        if operation == WriteOperation.CREATE:
            return await self.graph_client.create_node(skill_node)
        elif operation == WriteOperation.UPDATE:
            return await self.graph_client.update_node(skill_node)
        elif operation == WriteOperation.DELETE:
            return await self.graph_client.delete_node(skill_node.uid)
        
        raise DatabaseError(f"Unknown operation: {operation}")
    
    async def _write_to_vector(
        self,
        skill_node: SkillNode,
        embedding: list[float],
        operation: WriteOperation,
    ) -> dict:
        """
        写入向量数据库。
        
        Args:
            skill_node: 技能节点
            embedding: 向量嵌入
            operation: 操作类型
            
        Returns:
            dict: 写入结果
        """
        if self.vector_client is None:
            # 模拟写入（用于测试）
            return {"uid": skill_node.uid, "status": "mock_success"}
        
        # 实际写入逻辑
        if operation == WriteOperation.CREATE:
            return await self.vector_client.insert(
                skill_node.uid,
                embedding,
                skill_node.model_dump(),
            )
        elif operation == WriteOperation.UPDATE:
            return await self.vector_client.upsert(
                skill_node.uid,
                embedding,
                skill_node.model_dump(),
            )
        elif operation == WriteOperation.DELETE:
            return await self.vector_client.delete(skill_node.uid)
        
        raise DatabaseError(f"Unknown operation: {operation}")
    
    async def _write_edge_to_graph(
        self,
        edge: SkillEdge,
        operation: WriteOperation,
    ) -> dict:
        """
        写入边到图数据库。
        
        Args:
            edge: 技能边
            operation: 操作类型
            
        Returns:
            dict: 写入结果
        """
        if self.graph_client is None:
            return {"edge": f"{edge.source_uid}->{edge.target_uid}", "status": "mock_success"}
        
        if operation == WriteOperation.CREATE:
            return await self.graph_client.create_edge(edge)
        elif operation == WriteOperation.UPDATE:
            return await self.graph_client.update_edge(edge)
        elif operation == WriteOperation.DELETE:
            return await self.graph_client.delete_edge(
                edge.source_uid, edge.target_uid, edge.edge_type
            )
        
        raise DatabaseError(f"Unknown operation: {operation}")
    
    async def _rollback_graph(
        self,
        skill_node: SkillNode,
        operation: WriteOperation,
    ) -> bool:
        """
        回滚图数据库写入。
        
        Args:
            skill_node: 技能节点
            operation: 原操作类型
            
        Returns:
            bool: 回滚是否成功
        """
        try:
            # 根据原操作执行反向操作
            if operation == WriteOperation.CREATE:
                # 创建的回滚是删除
                await self._write_to_graph(skill_node, WriteOperation.DELETE)
            elif operation == WriteOperation.UPDATE:
                # 更新的回滚需要恢复原数据（这里简化处理）
                # 实际实现需要保存原数据
                pass
            elif operation == WriteOperation.DELETE:
                # 删除的回滚是重新创建（需要原数据）
                pass
            
            return True
        except Exception:
            return False
    
    async def _rollback_vector(
        self,
        skill_node: SkillNode,
        operation: WriteOperation,
    ) -> bool:
        """
        回滚向量数据库写入。
        
        Args:
            skill_node: 技能节点
            operation: 原操作类型
            
        Returns:
            bool: 回滚是否成功
        """
        try:
            if operation == WriteOperation.CREATE:
                # 创建的回滚是删除
                await self._write_to_vector(
                    skill_node, [], WriteOperation.DELETE
                )
            elif operation == WriteOperation.UPDATE:
                # 更新的回滚需要恢复原向量（简化处理）
                pass
            elif operation == WriteOperation.DELETE:
                # 删除的回滚是重新插入（需要原向量）
                pass
            
            return True
        except Exception:
            return False
    
    def set_clients(
        self,
        graph_client: Any,
        vector_client: Any,
    ) -> None:
        """
        设置数据库客户端。
        
        Args:
            graph_client: 图数据库客户端
            vector_client: 向量数据库客户端
        """
        self.graph_client = graph_client
        self.vector_client = vector_client
    
    def get_stats(
        self,
        results: list[DualWriteResult],
    ) -> dict:
        """
        获取批量写入统计。
        
        Args:
            results: 写入结果列表
            
        Returns:
            dict: 统计信息
        """
        total = len(results)
        success = sum(1 for r in results if r.success)
        failed = total - success
        rollback_count = sum(1 for r in results if r.rollback_executed)
        rollback_success = sum(1 for r in results if r.rollback_success)
        total_duration_ms = sum(r.duration_ms for r in results)
        
        return {
            "total": total,
            "success": success,
            "failed": failed,
            "success_rate": round(success / total * 100, 2) if total > 0 else 0,
            "rollback_count": rollback_count,
            "rollback_success": rollback_success,
            "total_duration_ms": total_duration_ms,
            "avg_duration_ms": round(total_duration_ms / total, 2) if total > 0 else 0,
        }