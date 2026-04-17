"""
DAG 验证器。

验证技能依赖图是否满足 DAG 约束。

Reference: RFC-01 Section 3.3, RFC-02 Section 3.4
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from graphskill.core.exceptions import IngestionError
from graphskill.core.models import SkillEdge, EdgeType
from graphskill.ingestion.dag.cycle_detector import (
    TarjanCycleDetector,
    CycleDetectionResult,
    CycleInfo,
)


@dataclass
class DAGValidationError:
    """DAG 验证错误。"""
    
    error_type: str
    message: str
    affected_nodes: list[str] = field(default_factory=list)
    affected_edges: list[tuple[str, str]] = field(default_factory=list)
    suggestion: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "affected_nodes": self.affected_nodes,
            "affected_edges": self.affected_edges,
            "suggestion": self.suggestion,
        }


@dataclass
class DAGValidationResult:
    """DAG 验证结果。"""
    
    is_valid: bool
    errors: list[DAGValidationError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    cycle_result: Optional[CycleDetectionResult] = None
    node_count: int = 0
    edge_count: int = 0
    max_depth: int = 0
    
    @property
    def error_count(self) -> int:
        return len(self.errors)
    
    @property
    def has_cycles(self) -> bool:
        return self.cycle_result is not None and self.cycle_result.has_cycle
    
    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "error_count": self.error_count,
            "has_cycles": self.has_cycles,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "max_depth": self.max_depth,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": self.warnings,
            "cycle_result": self.cycle_result.to_dict() if self.cycle_result else None,
        }


class DAGValidationErrorException(IngestionError):
    """DAG 验证错误异常。
    
    Error Code: GS-2030
    """
    
    def __init__(
        self,
        message: str,
        errors: Optional[list[DAGValidationError]] = None,
        cycle_result: Optional[CycleDetectionResult] = None,
    ):
        details = {}
        if errors:
            details["errors"] = [e.to_dict() for e in errors]
        if cycle_result:
            details["cycle_result"] = cycle_result.to_dict()
        super().__init__(message, details=details)
        self._errors = errors or []
        self._cycle_result = cycle_result
    
    @property
    def errors(self) -> list[DAGValidationError]:
        return self._errors
    
    @property
    def cycle_result(self) -> Optional[CycleDetectionResult]:
        return self._cycle_result
    
    def to_dict(self) -> dict:
        result = super().to_dict()
        result["errors"] = [e.to_dict() for e in self._errors]
        if self._cycle_result:
            result["cycle_result"] = self._cycle_result.to_dict()
        return result


class DAGValidator:
    """
    DAG 验证器。
    
    验证技能依赖图是否满足 DAG 约束。
    
    Features:
        - 环路检测
        - 节点唯一性验证
        - 边完整性验证
        - 依赖深度计算
        - 验证报告生成
    
    Example:
        >>> validator = DAGValidator()
        >>> result = validator.validate(edges)
        >>> if not result.is_valid:
        ...     print(f"Found {result.error_count} errors")
    """
    
    def __init__(self, strict_mode: bool = True):
        """
        初始化验证器。
        
        Args:
            strict_mode: 严格模式，启用时对验证失败抛出异常
        """
        self.strict_mode = strict_mode
        self.cycle_detector = TarjanCycleDetector()
    
    def validate(
        self,
        edges: list[tuple[str, str]],
        nodes: Optional[list[str]] = None,
    ) -> DAGValidationResult:
        """
        验证依赖图。
        
        Args:
            edges: 边列表 [(source, target), ...]
            nodes: 节点列表（可选）
            
        Returns:
            DAGValidationResult: 验证结果
        """
        errors: list[DAGValidationError] = []
        warnings: list[str] = []
        
        # 提取所有节点
        all_nodes: set[str] = set()
        for source, target in edges:
            all_nodes.add(source)
            all_nodes.add(target)
        
        if nodes:
            all_nodes.update(nodes)
        
        # 1. 环路检测
        cycle_result = self.cycle_detector.detect(edges, list(all_nodes))
        
        if cycle_result.has_cycle:
            for cycle in cycle_result.cycles:
                cycle_edges = [
                    (s, t) for s, t in edges
                    if s in cycle.nodes and t in cycle.nodes
                ]
                errors.append(DAGValidationError(
                    error_type="cycle_detected",
                    message=f"Circular dependency detected: {cycle.description}",
                    affected_nodes=cycle.nodes,
                    affected_edges=cycle_edges,
                    suggestion="Remove one of the edges in the cycle to break the dependency loop",
                ))
        
        # 2. 检查孤立节点（无依赖）
        isolated_nodes = self._find_isolated_nodes(edges, all_nodes)
        if isolated_nodes:
            warnings.append(f"Found {len(isolated_nodes)} isolated nodes: {isolated_nodes}")
        
        # 3. 检查自引用
        self_ref_edges = [(s, t) for s, t in edges if s == t]
        if self_ref_edges:
            for edge in self_ref_edges:
                errors.append(DAGValidationError(
                    error_type="self_reference",
                    message=f"Self-referencing edge detected: {edge[0]} -> {edge[0]}",
                    affected_nodes=[edge[0]],
                    affected_edges=[edge],
                    suggestion="Remove self-referencing edges",
                ))
        
        # 4. 计算最大深度
        max_depth = 0
        if not cycle_result.has_cycle:
            max_depth = self._calculate_max_depth(edges, all_nodes)
        
        result = DAGValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            cycle_result=cycle_result,
            node_count=len(all_nodes),
            edge_count=len(edges),
            max_depth=max_depth,
        )
        
        if self.strict_mode and not result.is_valid:
            raise DAGValidationErrorException(
                f"DAG validation failed with {len(errors)} errors",
                errors=errors,
                cycle_result=cycle_result,
            )
        
        return result
    
    def validate_skill_edges(
        self,
        skill_edges: list[SkillEdge],
    ) -> DAGValidationResult:
        """
        验证 SkillEdge 列表。
        
        Args:
            skill_edges: SkillEdge 对象列表
            
        Returns:
            DAGValidationResult: 验证结果
        """
        # 只验证 REQUIRES 边（其他边类型不参与 DAG）
        requires_edges = [
            (e.source_uid, e.target_uid)
            for e in skill_edges
            if e.edge_type == EdgeType.REQUIRES
        ]
        
        # 提取所有节点
        all_nodes: set[str] = set()
        for edge in skill_edges:
            all_nodes.add(edge.source_uid)
            all_nodes.add(edge.target_uid)
        
        return self.validate(requires_edges, list(all_nodes))
    
    def _find_isolated_nodes(
        self,
        edges: list[tuple[str, str]],
        all_nodes: set[str],
    ) -> list[str]:
        """
        查找孤立节点。
        
        Args:
            edges: 边列表
            all_nodes: 所有节点
            
        Returns:
            list: 孤立节点列表
        """
        connected_nodes: set[str] = set()
        for source, target in edges:
            connected_nodes.add(source)
            connected_nodes.add(target)
        
        return list(all_nodes - connected_nodes)
    
    def _calculate_max_depth(
        self,
        edges: list[tuple[str, str]],
        all_nodes: set[str],
    ) -> int:
        """
        计算最大依赖深度。
        
        Args:
            edges: 边列表
            all_nodes: 所有节点
            
        Returns:
            int: 最大深度
        """
        # 构建邻接表，排除自引用边
        graph: dict[str, list[str]] = {}
        for source, target in edges:
            # 排除自引用边，避免无限递归
            if source == target:
                continue
            if source not in graph:
                graph[source] = []
            graph[source].append(target)
        
        # 计算每个节点的深度
        depths: dict[str, int] = {}
        visiting: set[str] = set()  # 用于检测循环
        
        def get_depth(node: str) -> int:
            if node in depths:
                return depths[node]
            
            # 检测循环（环路情况），返回 0 避免无限递归
            if node in visiting:
                return 0
            
            if node not in graph or not graph[node]:
                depths[node] = 0
                return 0
            
            visiting.add(node)
            max_child_depth = max(get_depth(child) for child in graph[node])
            visiting.remove(node)
            
            depths[node] = max_child_depth + 1
            return depths[node]
        
        for node in all_nodes:
            get_depth(node)
        
        return max(depths.values()) if depths else 0
    
    def validate_incremental(
        self,
        existing_edges: list[tuple[str, str]],
        new_edges: list[tuple[str, str]],
    ) -> DAGValidationResult:
        """
        增量验证。
        
        Args:
            existing_edges: 已存在的边
            new_edges: 新添加的边
            
        Returns:
            DAGValidationResult: 验证结果
        """
        # 合并边
        all_edges = existing_edges + new_edges
        
        # 增量环路检测
        cycle_result = self.cycle_detector.detect_incremental(
            existing_edges, new_edges
        )
        
        errors: list[DAGValidationError] = []
        warnings: list[str] = []
        
        if cycle_result.has_cycle:
            # 只报告新引入的环路
            for cycle in cycle_result.cycles:
                # 检查是否是新边引入的
                new_cycle_edges = [
                    (s, t) for s, t in new_edges
                    if s in cycle.nodes and t in cycle.nodes
                ]
                
                if new_cycle_edges:
                    errors.append(DAGValidationError(
                        error_type="new_cycle_introduced",
                        message=f"New edges introduce circular dependency",
                        affected_nodes=cycle.nodes,
                        affected_edges=new_cycle_edges,
                        suggestion="Remove the new edges that create the cycle",
                    ))
        
        # 提取节点
        all_nodes: set[str] = set()
        for source, target in all_edges:
            all_nodes.add(source)
            all_nodes.add(target)
        
        return DAGValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            cycle_result=cycle_result,
            node_count=len(all_nodes),
            edge_count=len(all_edges),
        )
    
    def get_validation_report(
        self,
        result: DAGValidationResult,
    ) -> str:
        """
        生成验证报告。
        
        Args:
            result: 验证结果
            
        Returns:
            str: 报告文本
        """
        lines: list[str] = []
        
        lines.append("=" * 60)
        lines.append("DAG Validation Report")
        lines.append("=" * 60)
        
        lines.append(f"\nStatus: {'VALID' if result.is_valid else 'INVALID'}")
        lines.append(f"Nodes: {result.node_count}")
        lines.append(f"Edges: {result.edge_count}")
        lines.append(f"Max Depth: {result.max_depth}")
        
        if result.errors:
            lines.append(f"\nErrors ({result.error_count}):")
            for i, error in enumerate(result.errors, 1):
                lines.append(f"  {i}. [{error.error_type}] {error.message}")
                if error.affected_nodes:
                    lines.append(f"     Affected nodes: {', '.join(error.affected_nodes)}")
                if error.suggestion:
                    lines.append(f"     Suggestion: {error.suggestion}")
        
        if result.warnings:
            lines.append(f"\nWarnings ({len(result.warnings)}):")
            for i, warning in enumerate(result.warnings, 1):
                lines.append(f"  {i}. {warning}")
        
        if result.cycle_result and result.cycle_result.has_cycle:
            lines.append(f"\nCycle Details:")
            lines.append(f"  Cycles found: {result.cycle_result.cycle_count}")
            lines.append(f"  Affected nodes: {result.cycle_result.affected_node_count}")
            for cycle in result.cycle_result.cycles:
                lines.append(f"  - Cycle: {cycle.nodes}")
                if cycle.path:
                    lines.append(f"    Path: {' -> '.join(cycle.path)}")
        
        lines.append("\n" + "=" * 60)
        
        return "\n".join(lines)
    
    def suggest_cycle_breaks(
        self,
        result: DAGValidationResult,
        edges: list[tuple[str, str]],
    ) -> list[dict]:
        """
        建议如何打破环路。
        
        Args:
            result: 验证结果
            edges: 边列表
            
        Returns:
            list: 建议列表
        """
        if not result.cycle_result:
            return []
        
        return self.cycle_detector.get_cycle_breaking_suggestions(
            result.cycle_result, edges
        )
    
    def check_edge_addition(
        self,
        existing_edges: list[tuple[str, str]],
        new_edge: tuple[str, str],
    ) -> bool:
        """
        检查添加单条边是否会破坏 DAG。
        
        Args:
            existing_edges: 已存在的边
            new_edge: 新边
            
        Returns:
            bool: 是否可以安全添加
        """
        return not self.cycle_detector.check_single_edge(existing_edges, new_edge)