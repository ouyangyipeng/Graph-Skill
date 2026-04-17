"""
Neo4j 图数据库客户端。

提供技能图谱的存储和查询功能。

Reference: RFC-01 Section 3
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional, Any

from graphskill.core.models import SkillNode, SkillEdge, EdgeType
from graphskill.core.exceptions import DatabaseError


class GraphDBError(DatabaseError):
    """图数据库错误。
    
    Error Code: GS-4001
    """
    
    def __init__(self, message: str, query: Optional[str] = None):
        details = {}
        if query:
            details["query"] = query[:200]  # 截断
        # DatabaseError 使用 database 和 operation 参数
        super().__init__(message, database="neo4j", operation="query", details=details)
        self.query = query
        # 覆盖错误码
        self.code = "GS-4001"
    
    def to_dict(self) -> dict:
        result = super().to_dict()
        if self.query:
            result["query"] = self.query[:200]  # 截断
        return result


@dataclass
class NodeQueryResult:
    """节点查询结果。"""
    
    nodes: list[dict] = field(default_factory=list)
    total_count: int = 0
    query_time_ms: int = 0
    
    def to_dict(self) -> dict:
        return {
            "nodes": self.nodes,
            "total_count": self.total_count,
            "query_time_ms": self.query_time_ms,
        }


@dataclass
class EdgeQueryResult:
    """边查询结果。"""
    
    edges: list[dict] = field(default_factory=list)
    total_count: int = 0
    query_time_ms: int = 0
    
    def to_dict(self) -> dict:
        return {
            "edges": self.edges,
            "total_count": self.total_count,
            "query_time_ms": self.query_time_ms,
        }


class Neo4jClient:
    """
    Neo4j 图数据库客户端。
    
    提供技能图谱的存储和查询功能。
    
    Features:
        - 节点 CRUD 操作
        - 边 CRUD 操作
        - 图遍历查询
        - 拓扑关系查询
        - 连接池管理
    
    Example:
        >>> client = Neo4jClient(uri="bolt://localhost:7687", user="neo4j", password="password")
        >>> await client.connect()
        >>> node = await client.get_node("git:commit")
        >>> await client.close()
    """
    
    # 默认配置
    DEFAULT_URI = "bolt://localhost:7687"
    DEFAULT_USER = "neo4j"
    DEFAULT_DATABASE = "neo4j"
    
    def __init__(
        self,
        uri: str = DEFAULT_URI,
        user: str = DEFAULT_USER,
        password: str = "",
        database: str = DEFAULT_DATABASE,
        max_connection_pool_size: int = 50,
        connection_timeout: int = 30,
    ):
        """
        初始化客户端。
        
        Args:
            uri: Neo4j 连接 URI
            user: 用户名
            password: 密码
            database: 数据库名
            max_connection_pool_size: 最大连接池大小
            connection_timeout: 连接超时（秒）
        """
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.max_connection_pool_size = max_connection_pool_size
        self.connection_timeout = connection_timeout
        
        self._driver: Optional[Any] = None
        self._connected = False
        self._mock_mode = False  # True when neo4j driver is unavailable
    
    async def connect(self) -> None:
        """
        连接数据库。
        
        Raises:
            GraphDBError: 连接失败
        """
        try:
            from neo4j import AsyncGraphDatabase
            
            self._driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                max_connection_pool_size=self.max_connection_pool_size,
                connection_timeout=self.connection_timeout,
            )
            
            # 验证连接
            await self._driver.verify_connectivity()
            self._connected = True
        
        except ImportError:
            # neo4j 库未安装，进入 mock 模式
            import logging
            logging.getLogger(__name__).warning(
                "neo4j driver not installed — operating in MOCK mode. "
                "All graph DB operations will return empty/mock results. "
                "Install with: pip install neo4j"
            )
            self._mock_mode = True
            self._connected = False  # NOT actually connected
        except Exception as e:
            raise GraphDBError(f"Connection failed: {e}")
    
    async def close(self) -> None:
        """
        关闭连接。
        """
        if self._driver:
            await self._driver.close()
            self._driver = None
        self._connected = False
    
    async def create_node(
        self,
        skill_node: SkillNode,
    ) -> dict:
        """
        创建技能节点。
        
        Args:
            skill_node: 技能节点
            
        Returns:
            dict: 创建结果
            
        Raises:
            GraphDBError: 创建失败
        """
        query = """
        MERGE (n:SkillNode {uid: $uid})
        SET n.version = $version,
            n.intent_description = $intent_description,
            n.permissions = $permissions,
            n.tags = $tags,
            n.execution_success_rate = $execution_success_rate,
            n.execution_count = $execution_count,
            n.deprecated = $deprecated,
            n.created_at = datetime(),
            n.updated_at = datetime()
        RETURN n.uid as uid, n.version as version
        """
        
        params = {
            "uid": skill_node.uid,
            "version": skill_node.version,
            "intent_description": skill_node.intent_description,
            "permissions": skill_node.permissions,
            "tags": skill_node.tags or [],
            "execution_success_rate": skill_node.execution_success_rate,
            "execution_count": skill_node.execution_count,
            "deprecated": skill_node.is_deprecated,
        }
        
        result = await self._execute_query(query, params)
        
        if result:
            return {"uid": skill_node.uid, "status": "created"}
        
        raise GraphDBError(f"Failed to create node: {skill_node.uid}", query)
    
    async def update_node(
        self,
        skill_node: SkillNode,
    ) -> dict:
        """
        更新技能节点。
        
        Args:
            skill_node: 技能节点
            
        Returns:
            dict: 更新结果
        """
        query = """
        MATCH (n:SkillNode {uid: $uid})
        SET n.version = $version,
            n.intent_description = $intent_description,
            n.permissions = $permissions,
            n.tags = $tags,
            n.execution_success_rate = $execution_success_rate,
            n.execution_count = $execution_count,
            n.deprecated = $deprecated,
            n.updated_at = datetime()
        RETURN n.uid as uid
        """
        
        params = {
            "uid": skill_node.uid,
            "version": skill_node.version,
            "intent_description": skill_node.intent_description,
            "permissions": skill_node.permissions,
            "tags": skill_node.tags or [],
            "execution_success_rate": skill_node.execution_success_rate,
            "execution_count": skill_node.execution_count,
            "deprecated": skill_node.is_deprecated,
        }
        
        result = await self._execute_query(query, params)
        
        if result:
            return {"uid": skill_node.uid, "status": "updated"}
        
        raise GraphDBError(f"Failed to update node: {skill_node.uid}", query)
    
    async def delete_node(
        self,
        uid: str,
    ) -> dict:
        """
        删除技能节点。
        
        Args:
            uid: 技能 UID
            
        Returns:
            dict: 删除结果
        """
        query = """
        MATCH (n:SkillNode {uid: $uid})
        DETACH DELETE n
        RETURN count(n) as deleted_count
        """
        
        params = {"uid": uid}
        
        result = await self._execute_query(query, params)
        
        return {"uid": uid, "status": "deleted"}
    
    async def get_node(
        self,
        uid: str,
    ) -> Optional[dict]:
        """
        获取技能节点。
        
        Args:
            uid: 技能 UID
            
        Returns:
            Optional[dict]: 节点数据
        """
        query = """
        MATCH (n:SkillNode {uid: $uid})
        RETURN n.uid as uid,
               n.version as version,
               n.intent_description as intent_description,
               n.permissions as permissions,
               n.tags as tags,
               n.execution_success_rate as execution_success_rate,
               n.avg_execution_latency_ms as avg_execution_latency_ms,
               n.deprecated as deprecated,
               n.deprecation_message as deprecation_message
        """
        
        params = {"uid": uid}
        
        result = await self._execute_query(query, params)
        
        if result:
            return result[0]
        
        return None
    
    async def get_all_nodes(
        self,
        limit: int = 100,
        skip: int = 0,
    ) -> NodeQueryResult:
        """
        获取所有节点。
        
        Args:
            limit: 返回数量限制
            skip: 跳过数量
            
        Returns:
            NodeQueryResult: 查询结果
        """
        query = """
        MATCH (n:SkillNode)
        RETURN n.uid as uid,
               n.version as version,
               n.intent_description as intent_description,
               n.permissions as permissions,
               n.tags as tags
        ORDER BY n.uid
        SKIP $skip
        LIMIT $limit
        """
        
        count_query = """
        MATCH (n:SkillNode)
        RETURN count(n) as total_count
        """
        
        params = {"limit": limit, "skip": skip}
        
        nodes = await self._execute_query(query, params)
        count_result = await self._execute_query(count_query, {})
        
        total_count = count_result[0]["total_count"] if count_result else 0
        
        return NodeQueryResult(
            nodes=nodes,
            total_count=total_count,
        )
    
    async def create_edge(
        self,
        edge: SkillEdge,
    ) -> dict:
        """
        创建边关系。
        
        Args:
            edge: 技能边
            
        Returns:
            dict: 创建结果
        """
        edge_type = edge.edge_type.value.upper()
        
        query = f"""
        MATCH (source:SkillNode {{uid: $source_uid}})
        MATCH (target:SkillNode {{uid: $target_uid}})
        MERGE (source)-[r:{edge_type}]->(target)
        SET r.weight = $weight,
            r.created_at = datetime()
        RETURN source.uid as source_uid, target.uid as target_uid, type(r) as edge_type
        """
        
        params = {
            "source_uid": edge.source_uid,
            "target_uid": edge.target_uid,
            "weight": edge.weight,
        }
        
        result = await self._execute_query(query, params)
        
        if result:
            return {
                "source_uid": edge.source_uid,
                "target_uid": edge.target_uid,
                "edge_type": edge.edge_type.value,
                "status": "created",
            }
        
        raise GraphDBError(
            f"Failed to create edge: {edge.source_uid} -> {edge.target_uid}",
            query
        )
    
    async def delete_edge(
        self,
        source_uid: str,
        target_uid: str,
        edge_type: EdgeType,
    ) -> dict:
        """
        删除边关系。
        
        Args:
            source_uid: 源节点 UID
            target_uid: 目标节点 UID
            edge_type: 边类型
            
        Returns:
            dict: 删除结果
        """
        edge_type_str = edge_type.value.upper()
        
        query = f"""
        MATCH (source:SkillNode {{uid: $source_uid}})-[r:{edge_type_str}]->(target:SkillNode {{uid: $target_uid}})
        DELETE r
        RETURN count(r) as deleted_count
        """
        
        params = {
            "source_uid": source_uid,
            "target_uid": target_uid,
        }
        
        result = await self._execute_query(query, params)
        
        return {
            "source_uid": source_uid,
            "target_uid": target_uid,
            "edge_type": edge_type.value,
            "status": "deleted",
        }
    
    async def get_neighbors(
        self,
        uid: str,
        edge_types: Optional[list[EdgeType]] = None,
        depth: int = 1,
    ) -> NodeQueryResult:
        """
        获取邻居节点。
        
        Args:
            uid: 节点 UID
            edge_types: 边类型过滤
            depth: 遍历深度
            
        Returns:
            NodeQueryResult: 邻居节点
        """
        if edge_types:
            edge_type_filter = "|".join([et.value.upper() for et in edge_types])
            query = f"""
            MATCH (n:SkillNode {{uid: $uid}})-[r:{edge_type_filter}*1..{depth}]-(neighbor:SkillNode)
            RETURN DISTINCT neighbor.uid as uid,
                   neighbor.version as version,
                   neighbor.intent_description as intent_description,
                   neighbor.permissions as permissions,
                   neighbor.tags as tags,
                   type(r) as edge_type
            """
        else:
            query = f"""
            MATCH (n:SkillNode {{uid: $uid}})-[r*1..{depth}]-(neighbor:SkillNode)
            RETURN DISTINCT neighbor.uid as uid,
                   neighbor.version as version,
                   neighbor.intent_description as intent_description,
                   neighbor.permissions as permissions,
                   neighbor.tags as tags,
                   type(r) as edge_type
            """
        
        params = {"uid": uid}
        
        nodes = await self._execute_query(query, params)
        
        return NodeQueryResult(
            nodes=nodes,
            total_count=len(nodes),
        )
    
    async def get_dependencies(
        self,
        uid: str,
        recursive: bool = False,
    ) -> NodeQueryResult:
        """
        获取依赖节点。
        
        Args:
            uid: 节点 UID
            recursive: 是否递归
            
        Returns:
            NodeQueryResult: 依赖节点
        """
        if recursive:
            query = """
            MATCH (n:SkillNode {uid: $uid})-[r:REQUIRES*]->(dep:SkillNode)
            RETURN DISTINCT dep.uid as uid,
                   dep.version as version,
                   dep.intent_description as intent_description,
                   dep.permissions as permissions,
                   dep.tags as tags
            """
        else:
            query = """
            MATCH (n:SkillNode {uid: $uid})-[r:REQUIRES]->(dep:SkillNode)
            RETURN dep.uid as uid,
                   dep.version as version,
                   dep.intent_description as intent_description,
                   dep.permissions as permissions,
                   dep.tags as tags
            """
        
        params = {"uid": uid}
        
        nodes = await self._execute_query(query, params)
        
        return NodeQueryResult(
            nodes=nodes,
            total_count=len(nodes),
        )
    
    async def get_conflicts(
        self,
        uid: str,
    ) -> NodeQueryResult:
        """
        获取冲突节点。
        
        Args:
            uid: 节点 UID
            
        Returns:
            NodeQueryResult: 冲突节点
        """
        query = """
        MATCH (n:SkillNode {uid: $uid})-[r:CONFLICTS_WITH]-(conflict:SkillNode)
        RETURN conflict.uid as uid,
               conflict.version as version,
               conflict.intent_description as intent_description,
               conflict.permissions as permissions,
               conflict.tags as tags
        """
        
        params = {"uid": uid}
        
        nodes = await self._execute_query(query, params)
        
        return NodeQueryResult(
            nodes=nodes,
            total_count=len(nodes),
        )
    
    async def _execute_query(
        self,
        query: str,
        params: dict,
    ) -> list[dict]:
        """
        执行查询。
        
        Args:
            query: Cypher 查询
            params: 参数
            
        Returns:
            list: 结果列表
        """
        if self._driver is None:
            # 模拟模式
            return self._mock_execute(query, params)
        
        try:
            async with self._driver.session(database=self.database) as session:
                result = await session.run(query, params)
                records = await result.data()
                return records
        except Exception as e:
            raise GraphDBError(f"Query execution failed: {e}", query)
    
    def _mock_execute(
        self,
        query: str,
        params: dict,
    ) -> list[dict]:
        """
        模拟执行（用于测试）。
        
        Args:
            query: Cypher 查询
            params: 参数
            
        Returns:
            list: 模拟结果
        """
        # 简单模拟
        if "MERGE" in query and "SkillNode" in query:
            return [{"uid": params.get("uid", ""), "version": params.get("version", "")}]
        elif "MATCH" in query and "RETURN" in query:
            if "count" in query:
                return [{"total_count": 0}]
            return []
        
        return []
    
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
            if self._driver:
                await self._driver.verify_connectivity()
            
            return {
                "status": "healthy",
                "connected": self._connected,
                "uri": self.uri,
                "database": self.database,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "connected": False,
            }