"""
增量导入器。

支持增量更新技能图谱数据。

Reference: RFC-02 Section 3.5
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Any

from graphskill.core.models import SkillNode, SkillEdge
from graphskill.core.exceptions import IngestionError
from graphskill.ingestion.importer.dual_writer import (
    DualWriteTransactionManager,
    DualWriteResult,
    WriteOperation,
)


class ChangeType(str, Enum):
    """变更类型。"""
    
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    UNCHANGED = "unchanged"


@dataclass
class FileChange:
    """文件变更信息。"""
    
    file_path: Path
    change_type: ChangeType
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "file_path": str(self.file_path),
            "change_type": self.change_type.value,
            "old_hash": self.old_hash,
            "new_hash": self.new_hash,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class IncrementalImportResult:
    """增量导入结果。"""
    
    success: bool
    changes_processed: int = 0
    nodes_created: int = 0
    nodes_updated: int = 0
    nodes_deleted: int = 0
    edges_created: int = 0
    edges_updated: int = 0
    edges_deleted: int = 0
    errors: list[str] = field(default_factory=list)
    duration_ms: int = 0
    change_details: list[FileChange] = field(default_factory=list)
    
    @property
    def total_changes(self) -> int:
        return self.changes_processed
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "changes_processed": self.changes_processed,
            "nodes_created": self.nodes_created,
            "nodes_updated": self.nodes_updated,
            "nodes_deleted": self.nodes_deleted,
            "edges_created": self.edges_created,
            "edges_updated": self.edges_updated,
            "edges_deleted": self.edges_deleted,
            "errors": self.errors,
            "duration_ms": self.duration_ms,
            "change_details": [c.to_dict() for c in self.change_details],
        }


class IncrementalImporter:
    """
    增量导入器。
    
    支持增量更新技能图谱数据。
    
    Features:
        - 文件变更检测
        - 增量更新
        - 版本管理
        - 回滚支持
    
    Example:
        >>> importer = IncrementalImporter(dual_writer, embedder)
        >>> result = await importer.process_changes(changes)
        >>> print(f"Updated {result.nodes_updated} nodes")
    """
    
    def __init__(
        self,
        dual_writer: Optional[DualWriteTransactionManager] = None,
        embedder: Optional[Any] = None,
        hash_store: Optional[dict[str, str]] = None,
    ):
        """
        初始化导入器。
        
        Args:
            dual_writer: 双写事务管理器
            embedder: 向量嵌入生成器
            hash_store: 文件哈希存储（用于变更检测）
        """
        self.dual_writer = dual_writer or DualWriteTransactionManager()
        self.embedder = embedder
        self.hash_store = hash_store or {}
    
    async def process_changes(
        self,
        changes: list[FileChange],
    ) -> IncrementalImportResult:
        """
        处理文件变更。
        
        Args:
            changes: 文件变更列表
            
        Returns:
            IncrementalImportResult: 处理结果
        """
        start_time = datetime.now()
        result = IncrementalImportResult(change_details=changes)
        
        for change in changes:
            try:
                if change.change_type == ChangeType.CREATED:
                    await self._process_create(change, result)
                elif change.change_type == ChangeType.MODIFIED:
                    await self._process_modify(change, result)
                elif change.change_type == ChangeType.DELETED:
                    await self._process_delete(change, result)
                
                result.changes_processed += 1
            
            except Exception as e:
                result.errors.append(f"Error processing {change.file_path}: {e}")
        
        result.success = len(result.errors) == 0
        result.duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return result
    
    async def _process_create(
        self,
        change: FileChange,
        result: IncrementalImportResult,
    ) -> None:
        """
        处理新建文件。
        
        Args:
            change: 文件变更
            result: 结果对象
        """
        from graphskill.ingestion.parser.markdown_parser import MarkdownParser
        from graphskill.ingestion.validator.schema_validator import SchemaValidator
        
        parser = MarkdownParser(strict_mode=False)
        validator = SchemaValidator(strict_mode=False)
        
        parsed = parser.parse(change.file_path)
        validation = validator.validate(parsed.frontmatter, change.file_path)
        
        if not validation.is_valid:
            result.errors.append(f"Validation failed for {change.file_path}")
            return
        
        # 构建 SkillNode
        node = self._build_skill_node(parsed.frontmatter)
        
        # 生成嵌入
        embedding = await self._generate_embedding(node)
        
        # 写入
        write_result = await self.dual_writer.write_skill(
            node, embedding, WriteOperation.CREATE
        )
        
        if write_result.success:
            result.nodes_created += 1
            # 更新哈希存储
            self.hash_store[str(change.file_path)] = change.new_hash or ""
        else:
            result.errors.append(write_result.error or "Create failed")
        
        # 处理边
        edges = self._extract_edges(parsed.frontmatter)
        for edge in edges:
            edge_result = await self.dual_writer.write_edge(edge, WriteOperation.CREATE)
            if edge_result.success:
                result.edges_created += 1
            else:
                result.errors.append(f"Edge create failed: {edge.source_uid}->{edge.target_uid}")
    
    async def _process_modify(
        self,
        change: FileChange,
        result: IncrementalImportResult,
    ) -> None:
        """
        处理修改文件。
        
        Args:
            change: 文件变更
            result: 结果对象
        """
        from graphskill.ingestion.parser.markdown_parser import MarkdownParser
        from graphskill.ingestion.validator.schema_validator import SchemaValidator
        
        parser = MarkdownParser(strict_mode=False)
        validator = SchemaValidator(strict_mode=False)
        
        parsed = parser.parse(change.file_path)
        validation = validator.validate(parsed.frontmatter, change.file_path)
        
        if not validation.is_valid:
            result.errors.append(f"Validation failed for {change.file_path}")
            return
        
        # 构建 SkillNode
        node = self._build_skill_node(parsed.frontmatter)
        
        # 生成嵌入
        embedding = await self._generate_embedding(node)
        
        # 更新
        write_result = await self.dual_writer.write_skill(
            node, embedding, WriteOperation.UPDATE
        )
        
        if write_result.success:
            result.nodes_updated += 1
            # 更新哈希存储
            self.hash_store[str(change.file_path)] = change.new_hash or ""
        else:
            result.errors.append(write_result.error or "Update failed")
        
        # 处理边（先删除旧边，再创建新边）
        # 这里简化处理，实际需要比较新旧边
        edges = self._extract_edges(parsed.frontmatter)
        for edge in edges:
            edge_result = await self.dual_writer.write_edge(edge, WriteOperation.UPDATE)
            if edge_result.success:
                result.edges_updated += 1
    
    async def _process_delete(
        self,
        change: FileChange,
        result: IncrementalImportResult,
    ) -> None:
        """
        处理删除文件。
        
        Args:
            change: 文件变更
            result: 结果对象
        """
        # 从文件路径推断 skill_id
        skill_id = self._infer_skill_id(change.file_path)
        
        if not skill_id:
            result.errors.append(f"Cannot infer skill_id from {change.file_path}")
            return
        
        # 删除节点
        dummy_node = SkillNode(
            uid=skill_id,
            version="0.0.0",
            intent_description="deleted",
            permissions=["fs:read"],
        )
        
        write_result = await self.dual_writer.write_skill(
            dummy_node, [], WriteOperation.DELETE
        )
        
        if write_result.success:
            result.nodes_deleted += 1
            # 清理哈希存储
            if str(change.file_path) in self.hash_store:
                del self.hash_store[str(change.file_path)]
        else:
            result.errors.append(write_result.error or "Delete failed")
    
    def detect_changes(
        self,
        skill_dir: Path,
        recursive: bool = True,
    ) -> list[FileChange]:
        """
        检测文件变更。
        
        Args:
            skill_dir: 技能目录
            recursive: 是否递归
            
        Returns:
            list: 变更列表
        """
        import hashlib
        
        changes: list[FileChange] = []
        
        # 扫描当前文件
        current_files: dict[str, Path] = {}
        
        if recursive:
            for file_path in skill_dir.rglob("SKILL.md"):
                current_files[str(file_path)] = file_path
        else:
            for file_path in skill_dir.glob("SKILL.md"):
                current_files[str(file_path)] = file_path
        
        # 检查新增和修改
        for file_key, file_path in current_files.items():
            new_hash = self._compute_file_hash(file_path)
            
            if file_key not in self.hash_store:
                # 新文件
                changes.append(FileChange(
                    file_path=file_path,
                    change_type=ChangeType.CREATED,
                    new_hash=new_hash,
                ))
            elif self.hash_store[file_key] != new_hash:
                # 修改文件
                changes.append(FileChange(
                    file_path=file_path,
                    change_type=ChangeType.MODIFIED,
                    old_hash=self.hash_store[file_key],
                    new_hash=new_hash,
                ))
        
        # 检查删除
        for file_key in self.hash_store:
            if file_key not in current_files:
                # 删除文件
                changes.append(FileChange(
                    file_path=Path(file_key),
                    change_type=ChangeType.DELETED,
                    old_hash=self.hash_store[file_key],
                ))
        
        return changes
    
    def _compute_file_hash(
        self,
        file_path: Path,
    ) -> str:
        """
        计算文件哈希。
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: MD5 哈希值
        """
        import hashlib
        
        content = file_path.read_text(encoding="utf-8")
        return hashlib.md5(content.encode()).hexdigest()
    
    def _build_skill_node(
        self,
        frontmatter: dict,
    ) -> SkillNode:
        """
        构建 SkillNode。
        
        Args:
            frontmatter: YAML Frontmatter
            
        Returns:
            SkillNode: 技能节点
        """
        return SkillNode(
            uid=frontmatter.get("skill_id", ""),
            version=frontmatter.get("version", "1.0.0"),
            intent_description=frontmatter.get("intent_description", ""),
            permissions=frontmatter.get("permissions", []),
            tags=frontmatter.get("tags", []),
            topology_hints=frontmatter.get("topology_hints", {}),
            execution_success_rate=frontmatter.get("success_rate", 1.0),
            avg_execution_latency_ms=frontmatter.get("avg_latency_ms", 0),
            deprecated=frontmatter.get("deprecated", False),
            deprecation_message=frontmatter.get("deprecation_message"),
        )
    
    def _extract_edges(
        self,
        frontmatter: dict,
    ) -> list[SkillEdge]:
        """
        从 topology_hints 提取边。
        
        Args:
            frontmatter: YAML Frontmatter
            
        Returns:
            list: 边列表
        """
        from graphskill.core.models import EdgeType
        
        edges: list[SkillEdge] = []
        source_uid = frontmatter.get("skill_id", "")
        topology_hints = frontmatter.get("topology_hints", {})
        
        for target_uid in topology_hints.get("requires", []):
            edges.append(SkillEdge(
                source_uid=source_uid,
                target_uid=target_uid,
                edge_type=EdgeType.REQUIRES,
                weight=1.0,
            ))
        
        for target_uid in topology_hints.get("conflicts_with", []):
            edges.append(SkillEdge(
                source_uid=source_uid,
                target_uid=target_uid,
                edge_type=EdgeType.CONFLICTS_WITH,
                weight=1.0,
            ))
        
        for target_uid in topology_hints.get("enhances", []):
            edges.append(SkillEdge(
                source_uid=source_uid,
                target_uid=target_uid,
                edge_type=EdgeType.ENHANCES,
                weight=0.8,
            ))
        
        for target_uid in topology_hints.get("substitutes", []):
            edges.append(SkillEdge(
                source_uid=source_uid,
                target_uid=target_uid,
                edge_type=EdgeType.SUBSTITUTES,
                weight=0.9,
            ))
        
        return edges
    
    def _infer_skill_id(
        self,
        file_path: Path,
    ) -> Optional[str]:
        """
        从文件路径推断 skill_id。
        
        Args:
            file_path: 文件路径
            
        Returns:
            Optional[str]: skill_id
        """
        # 假设路径格式为 .../namespace/skill_name/SKILL.md
        parts = file_path.parts
        
        if len(parts) >= 2:
            # 尝试从父目录名推断
            parent_dir = file_path.parent.name
            grandparent_dir = file_path.parent.parent.name if file_path.parent.parent else ""
            
            if grandparent_dir:
                return f"{grandparent_dir}:{parent_dir}"
            else:
                return parent_dir
        
        return None
    
    async def _generate_embedding(
        self,
        node: SkillNode,
    ) -> list[float]:
        """
        生成向量嵌入。
        
        Args:
            node: 技能节点
            
        Returns:
            list: 嵌入向量
        """
        if self.embedder is None:
            return []
        
        text = node.intent_description
        
        if hasattr(self.embedder, 'embed'):
            return await self.embedder.embed(text)
        elif hasattr(self.embedder, 'aembed'):
            return await self.embedder.aembed(text)
        else:
            return self.embedder(text)
    
    def load_hash_store(
        self,
        store_path: Path,
    ) -> None:
        """
        加载哈希存储。
        
        Args:
            store_path: 存储文件路径
        """
        import json
        
        if store_path.exists():
            with open(store_path, "r", encoding="utf-8") as f:
                self.hash_store = json.load(f)
    
    def save_hash_store(
        self,
        store_path: Path,
    ) -> None:
        """
        保存哈希存储。
        
        Args:
            store_path: 存储文件路径
        """
        import json
        
        with open(store_path, "w", encoding="utf-8") as f:
            json.dump(self.hash_store, f, indent=2)
    
    def sync_from_directory(
        self,
        skill_dir: Path,
        store_path: Optional[Path] = None,
    ) -> IncrementalImportResult:
        """
        同步目录（同步版本）。
        
        Args:
            skill_dir: 技能目录
            store_path: 哈希存储路径
            
        Returns:
            IncrementalImportResult: 同步结果
        """
        # 加载哈希存储
        if store_path:
            self.load_hash_store(store_path)
        
        # 检测变更
        changes = self.detect_changes(skill_dir)
        
        # 处理变更
        result = asyncio.run(self.process_changes(changes))
        
        # 保存哈希存储
        if store_path:
            self.save_hash_store(store_path)
        
        return result