"""
Milvus 向量数据库客户端。

提供技能向量嵌入的存储和检索功能。

Reference: RFC-01 Section 4
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Any

from graphskill.core.exceptions import DatabaseError
from graphskill.core.constants import (
    MILVUS_COLLECTION_NAME,
    MILVUS_VECTOR_DIMENSION,
    MILVUS_INDEX_TYPE,
    MILVUS_METRIC_TYPE,
)


class VectorDBError(DatabaseError):
    """向量数据库错误。
    
    Error Code: GS-4002
    """
    
    def __init__(self, message: str, collection: Optional[str] = None):
        details = {}
        if collection:
            details["collection"] = collection
        # DatabaseError 使用 database 和 operation 参数
        super().__init__(message, database="milvus", operation="vector", details=details)
        self.collection = collection
        # 覆盖错误码
        self.code = "GS-4002"
    
    def to_dict(self) -> dict:
        result = super().to_dict()
        if self.collection:
            result["collection"] = self.collection
        return result


@dataclass
class SearchResult:
    """向量搜索结果。"""
    
    results: list[dict] = field(default_factory=list)
    total_count: int = 0
    query_time_ms: int = 0
    
    def to_dict(self) -> dict:
        return {
            "results": self.results,
            "total_count": self.total_count,
            "query_time_ms": self.query_time_ms,
        }


@dataclass
class VectorInfo:
    """向量信息。"""
    
    uid: str
    embedding: list[float]
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "uid": self.uid,
            "embedding_dim": len(self.embedding),
            "metadata": self.metadata,
        }


class MilvusClient:
    """
    Milvus 向量数据库客户端。
    
    提供技能向量嵌入的存储和检索功能。
    
    Features:
        - 向量插入/更新/删除
        - ANN 搜索
        - 批量操作
        - Collection 管理
    
    Example:
        >>> client = MilvusClient(host="localhost", port=19530)
        >>> await client.connect()
        >>> results = await client.search(query_vector, top_k=10)
        >>> await client.close()
    """
    
    # 默认配置
    DEFAULT_HOST = "localhost"
    DEFAULT_PORT = 19530
    DEFAULT_COLLECTION = MILVUS_COLLECTION_NAME
    DEFAULT_VECTOR_DIM = MILVUS_VECTOR_DIMENSION
    
    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        collection_name: str = DEFAULT_COLLECTION,
        vector_dimension: int = DEFAULT_VECTOR_DIM,
        index_type: str = MILVUS_INDEX_TYPE,
        metric_type: str = MILVUS_METRIC_TYPE,
    ):
        """
        初始化客户端。
        
        Args:
            host: Milvus 服务地址
            port: Milvus 服务端口
            collection_name: Collection 名称
            vector_dimension: 向量维度
            index_type: 索引类型
            metric_type: 距离度量类型
        """
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.vector_dimension = vector_dimension
        self.index_type = index_type
        self.metric_type = metric_type
        
        self._client: Optional[Any] = None
        self._connected = False
        self._mock_mode = False  # True when pymilvus is unavailable
    
    async def connect(self) -> None:
        """
        连接数据库。
        
        Raises:
            VectorDBError: 连接失败
        """
        try:
            from pymilvus import MilvusClient as PyMilvusClient
            
            self._client = PyMilvusClient(
                uri=f"http://{self.host}:{self.port}"
            )
            
            # 确保 Collection 存在
            await self._ensure_collection()
            
            self._connected = True
        
        except ImportError:
            # pymilvus 库未安装，进入 mock 模式
            import logging
            logging.getLogger(__name__).warning(
                "pymilvus not installed — operating in MOCK mode. "
                "All vector DB operations will return empty/mock results. "
                "Install with: pip install pymilvus"
            )
            self._mock_mode = True
            self._connected = False  # NOT actually connected
        except Exception as e:
            raise VectorDBError(f"Connection failed: {e}", self.collection_name)
    
    def connect_sync(self) -> None:
        """
        同步连接数据库。
        """
        try:
            from pymilvus import MilvusClient as PyMilvusClient
            
            self._client = PyMilvusClient(
                uri=f"http://{self.host}:{self.port}"
            )
            
            # 确保 Collection 存在
            self._ensure_collection_sync()
            
            self._connected = True
        
        except ImportError:
            self._mock_mode = True
            self._connected = False
        except Exception as e:
            raise VectorDBError(f"Connection failed: {e}", self.collection_name)
    
    async def close(self) -> None:
        """
        关闭连接。
        """
        if self._client:
            self._client.close()
            self._client = None
        self._connected = False
    
    async def _ensure_collection(self) -> None:
        """
        确保 Collection 存在。
        
        使用 VARCHAR 类型作为主键，以支持字符串类型的技能 UID。
        """
        if self._client is None:
            return
        
        try:
            if not self._client.has_collection(self.collection_name):
                # 使用自定义 schema，主键为 VARCHAR 类型
                from pymilvus import DataType
                
                schema = self._client.create_schema(
                    auto_id=False,
                    enable_dynamic_field=True,
                    description="Skill embeddings collection"
                )
                
                # 主键使用 VARCHAR 类型，支持字符串 UID
                schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=256)
                # 向量字段
                schema.add_field("vector", DataType.FLOAT_VECTOR, dim=self.vector_dimension)
                
                # 准备索引参数
                index_params = self._client.prepare_index_params()
                index_params.add_index(
                    field_name="vector",
                    index_type=self.index_type,
                    metric_type=self.metric_type,
                    params={"M": 16, "efConstruction": 200},
                )
                
                self._client.create_collection(
                    collection_name=self.collection_name,
                    schema=schema,
                    index_params=index_params,
                )
                
                # 加载 collection 到内存以支持搜索
                self._client.load_collection(self.collection_name)
        except Exception as e:
            raise VectorDBError(f"Collection creation failed: {e}", self.collection_name)
    
    def _ensure_collection_sync(self) -> None:
        """
        同步确保 Collection 存在。
        
        使用 VARCHAR 类型作为主键，以支持字符串类型的技能 UID。
        """
        if self._client is None:
            return
        
        try:
            if not self._client.has_collection(self.collection_name):
                # 使用自定义 schema，主键为 VARCHAR 类型
                from pymilvus import DataType
                
                schema = self._client.create_schema(
                    auto_id=False,
                    enable_dynamic_field=True,
                    description="Skill embeddings collection"
                )
                
                # 主键使用 VARCHAR 类型，支持字符串 UID
                schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=256)
                # 向量字段
                schema.add_field("vector", DataType.FLOAT_VECTOR, dim=self.vector_dimension)
                
                # 准备索引参数
                index_params = self._client.prepare_index_params()
                index_params.add_index(
                    field_name="vector",
                    index_type=self.index_type,
                    metric_type=self.metric_type,
                    params={"M": 16, "efConstruction": 200},
                )
                
                self._client.create_collection(
                    collection_name=self.collection_name,
                    schema=schema,
                    index_params=index_params,
                )
                
                # 加载 collection 到内存以支持搜索
                self._client.load_collection(self.collection_name)
        except Exception as e:
            raise VectorDBError(f"Collection creation failed: {e}", self.collection_name)
    
    async def insert(
        self,
        uid: str,
        embedding: list[float],
        metadata: dict,
    ) -> dict:
        """
        插入向量。
        
        Args:
            uid: 技能 UID
            embedding: 向量嵌入
            metadata: 元数据
            
        Returns:
            dict: 插入结果
        """
        if self._client is None:
            return {"uid": uid, "status": "mock_inserted"}
        
        try:
            # 准备数据
            data = [
                {
                    "id": uid,
                    "vector": embedding,
                    **metadata,
                }
            ]
            
            result = self._client.insert(
                collection_name=self.collection_name,
                data=data,
            )
            
            return {"uid": uid, "status": "inserted", "insert_count": result.get("insert_count", 1)}
        
        except Exception as e:
            raise VectorDBError(f"Insert failed: {e}", self.collection_name)
    
    async def upsert(
        self,
        uid: str,
        embedding: list[float],
        metadata: dict,
    ) -> dict:
        """
        更新或插入向量。
        
        Args:
            uid: 技能 UID
            embedding: 向量嵌入
            metadata: 元数据
            
        Returns:
            dict: 操作结果
        """
        if self._client is None:
            return {"uid": uid, "status": "mock_upserted"}
        
        try:
            data = [
                {
                    "id": uid,
                    "vector": embedding,
                    **metadata,
                }
            ]
            
            result = self._client.upsert(
                collection_name=self.collection_name,
                data=data,
            )
            
            return {"uid": uid, "status": "upserted"}
        
        except Exception as e:
            raise VectorDBError(f"Upsert failed: {e}", self.collection_name)
    
    async def delete(
        self,
        uid: str,
    ) -> dict:
        """
        删除向量。
        
        Args:
            uid: 技能 UID
            
        Returns:
            dict: 删除结果
        """
        if self._client is None:
            return {"uid": uid, "status": "mock_deleted"}
        
        try:
            self._client.delete(
                collection_name=self.collection_name,
                ids=[uid],
            )
            
            return {"uid": uid, "status": "deleted"}
        
        except Exception as e:
            raise VectorDBError(f"Delete failed: {e}", self.collection_name)
    
    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filter_expr: Optional[str] = None,
        output_fields: Optional[list[str]] = None,
    ) -> SearchResult:
        """
        向量搜索。
        
        Args:
            query_vector: 查询向量
            top_k: 返回数量
            filter_expr: 过滤表达式
            output_fields: 输出字段
            
        Returns:
            SearchResult: 搜索结果
        """
        if self._client is None:
            return SearchResult(
                results=[{"id": "mock", "distance": 0.0, "entity": {}}],
                total_count=1,
            )
        
        try:
            # 默认只输出 id 字段，动态字段会自动包含
            default_output_fields = ["id"]
            
            search_params = {
                "collection_name": self.collection_name,
                "data": [query_vector],
                "limit": top_k,
                "output_fields": output_fields or default_output_fields,
            }
            
            if filter_expr:
                search_params["filter"] = filter_expr
            
            results = self._client.search(**search_params)
            
            # 处理结果
            processed_results: list[dict] = []
            for hit in results[0]:
                processed_results.append({
                    "id": hit.get("id"),
                    "distance": hit.get("distance"),
                    "entity": hit.get("entity", {}),
                })
            
            return SearchResult(
                results=processed_results,
                total_count=len(processed_results),
            )
        
        except Exception as e:
            raise VectorDBError(f"Search failed: {e}", self.collection_name)
    
    async def batch_insert(
        self,
        vectors: list[VectorInfo],
    ) -> dict:
        """
        批量插入向量。
        
        Args:
            vectors: 向量信息列表
            
        Returns:
            dict: 批量插入结果
        """
        if self._client is None:
            return {"insert_count": len(vectors), "status": "mock_batch_inserted"}
        
        try:
            data = [
                {
                    "id": v.uid,
                    "vector": v.embedding,
                    **v.metadata,
                }
                for v in vectors
            ]
            
            result = self._client.insert(
                collection_name=self.collection_name,
                data=data,
            )
            
            return {
                "insert_count": result.get("insert_count", len(vectors)),
                "status": "batch_inserted",
            }
        
        except Exception as e:
            raise VectorDBError(f"Batch insert failed: {e}", self.collection_name)
    
    async def get(
        self,
        uid: str,
        output_fields: Optional[list[str]] = None,
    ) -> Optional[dict]:
        """
        获取向量数据。
        
        Args:
            uid: 技能 UID
            output_fields: 输出字段
            
        Returns:
            Optional[dict]: 向量数据
        """
        if self._client is None:
            return {"id": uid, "vector": [], "entity": {}}
        
        try:
            default_fields = ["uid", "intent_description", "tags", "permissions"]
            
            result = self._client.get(
                collection_name=self.collection_name,
                ids=[uid],
                output_fields=output_fields or default_fields,
            )
            
            if result:
                return result[0]
            
            return None
        
        except Exception as e:
            raise VectorDBError(f"Get failed: {e}", self.collection_name)
    
    async def query(
        self,
        filter_expr: str,
        output_fields: Optional[list[str]] = None,
        limit: int = 100,
    ) -> SearchResult:
        """
        条件查询。
        
        Args:
            filter_expr: 过滤表达式
            output_fields: 输出字段
            limit: 返回数量限制
            
        Returns:
            SearchResult: 查询结果
        """
        if self._client is None:
            return SearchResult(results=[], total_count=0)
        
        try:
            default_fields = ["uid", "intent_description", "tags", "permissions"]
            
            results = self._client.query(
                collection_name=self.collection_name,
                filter=filter_expr,
                output_fields=output_fields or default_fields,
                limit=limit,
            )
            
            return SearchResult(
                results=results,
                total_count=len(results),
            )
        
        except Exception as e:
            raise VectorDBError(f"Query failed: {e}", self.collection_name)
    
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
                # 尝试获取 Collection 信息
                has_collection = self._client.has_collection(self.collection_name)
            
            return {
                "status": "healthy",
                "connected": self._connected,
                "host": self.host,
                "port": self.port,
                "collection": self.collection_name,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "connected": False,
            }
    
    def get_collection_stats(self) -> dict:
        """
        获取 Collection 统计信息。
        
        Returns:
            dict: 统计信息
        """
        if self._client is None:
            return {
                "collection_name": self.collection_name,
                "row_count": 0,
                "status": "mock",
            }
        
        try:
            stats = self._client.get_collection_stats(self.collection_name)
            return stats
        except Exception as e:
            return {
                "collection_name": self.collection_name,
                "error": str(e),
            }