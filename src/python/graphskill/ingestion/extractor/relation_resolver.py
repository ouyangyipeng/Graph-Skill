"""
关系冲突解决器。

处理人工声明与 LLM 推演之间的冲突。

Reference: RFC-02 Section 3.3
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from graphskill.core.models import EdgeType
from graphskill.ingestion.extractor.topology_extractor import InferredRelation


class ResolutionStrategy(str, Enum):
    """冲突解决策略。"""
    
    KEEP_DECLARED = "keep_declared"      # 保留人工声明
    KEEP_INFERRED = "keep_inferred"      # 保留推断结果
    MERGE = "merge"                      # 合并两者
    REJECT_BOTH = "reject_both"          # 拒绝两者
    MANUAL_REVIEW = "manual_review"      # 需要人工审核


@dataclass
class ConflictInfo:
    """冲突信息。"""
    
    source_uid: str
    target_uid: str
    declared_edge_type: Optional[EdgeType] = None
    inferred_edge_type: Optional[EdgeType] = None
    declared_confidence: float = 1.0
    inferred_confidence: float = 0.0
    conflict_type: str = ""
    description: str = ""
    
    def to_dict(self) -> dict:
        return {
            "source_uid": self.source_uid,
            "target_uid": self.target_uid,
            "declared_edge_type": self.declared_edge_type.value if self.declared_edge_type else None,
            "inferred_edge_type": self.inferred_edge_type.value if self.inferred_edge_type else None,
            "declared_confidence": self.declared_confidence,
            "inferred_confidence": self.inferred_confidence,
            "conflict_type": self.conflict_type,
            "description": self.description,
        }


@dataclass
class ResolvedRelation:
    """解决后的关系。"""
    
    source_uid: str
    target_uid: str
    edge_type: EdgeType
    confidence: float
    reasoning: str
    resolution_strategy: ResolutionStrategy
    original_declared: Optional[InferredRelation] = None
    original_inferred: Optional[InferredRelation] = None
    
    def to_dict(self) -> dict:
        return {
            "source_uid": self.source_uid,
            "target_uid": self.target_uid,
            "edge_type": self.edge_type.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "resolution_strategy": self.resolution_strategy.value,
        }
    
    def to_inferred_relation(self) -> InferredRelation:
        """转换为 InferredRelation。"""
        return InferredRelation(
            source_uid=self.source_uid,
            target_uid=self.target_uid,
            edge_type=self.edge_type,
            confidence=self.confidence,
            reasoning=self.reasoning,
            is_declared=self.resolution_strategy == ResolutionStrategy.KEEP_DECLARED,
        )


@dataclass
class ResolvedTopology:
    """解决后的拓扑结构。"""
    
    source_uid: str
    relations: list[ResolvedRelation] = field(default_factory=list)
    conflicts: list[ConflictInfo] = field(default_factory=list)
    manual_review_needed: list[ConflictInfo] = field(default_factory=list)
    resolution_summary: str = ""
    
    @property
    def relation_count(self) -> int:
        return len(self.relations)
    
    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)
    
    @property
    def needs_manual_review(self) -> bool:
        return len(self.manual_review_needed) > 0
    
    def to_dict(self) -> dict:
        return {
            "source_uid": self.source_uid,
            "relation_count": self.relation_count,
            "conflict_count": self.conflict_count,
            "needs_manual_review": self.needs_manual_review,
            "relations": [r.to_dict() for r in self.relations],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "manual_review_needed": [c.to_dict() for c in self.manual_review_needed],
            "resolution_summary": self.resolution_summary,
        }


class RelationResolver:
    """
    关系冲突解决器。
    
    处理人工声明与 LLM 推演之间的冲突。
    
    Features:
        - 冲突检测
        - 多种解决策略
        - 人工审核标记
        - 关系合并
    
    Example:
        >>> resolver = RelationResolver()
        >>> resolved = resolver.resolve(declared_relations, inferred_relations)
        >>> if resolved.needs_manual_review:
        ...     print("Manual review required")
    """
    
    # 冲突类型定义
    EDGE_TYPE_CONFLICT = "edge_type_conflict"      # 边类型冲突
    DIRECTION_CONFLICT = "direction_conflict"      # 方向冲突
    EXISTENCE_CONFLICT = "existence_conflict"      # 存在性冲突
    
    # 默认解决策略优先级
    DEFAULT_STRATEGY_PRIORITY = [
        ResolutionStrategy.KEEP_DECLARED,  # 人工声明优先
        ResolutionStrategy.MANUAL_REVIEW,  # 复杂冲突需人工审核
        ResolutionStrategy.MERGE,          # 尝试合并
        ResolutionStrategy.KEEP_INFERRED,  # 保留推断
        ResolutionStrategy.REJECT_BOTH,    # 拒绝
    ]
    
    def __init__(
        self,
        strategy_priority: Optional[list[ResolutionStrategy]] = None,
        auto_resolve_threshold: float = 0.7,
    ):
        """
        初始化解决器。
        
        Args:
            strategy_priority: 解决策略优先级列表
            auto_resolve_threshold: 自动解决阈值（推断置信度低于此值时自动保留声明）
        """
        self.strategy_priority = strategy_priority or self.DEFAULT_STRATEGY_PRIORITY
        self.auto_resolve_threshold = auto_resolve_threshold
    
    def resolve(
        self,
        declared_relations: list[InferredRelation],
        inferred_relations: list[InferredRelation],
        source_uid: str,
    ) -> ResolvedTopology:
        """
        解决关系冲突。
        
        Args:
            declared_relations: 人工声明的关系列表
            inferred_relations: LLM 推断的关系列表
            source_uid: 源技能 UID
            
        Returns:
            ResolvedTopology: 解决后的拓扑结构
        """
        relations: list[ResolvedRelation] = []
        conflicts: list[ConflictInfo] = []
        manual_review_needed: list[ConflictInfo] = []
        
        # 构建关系映射
        declared_map = self._build_relation_map(declared_relations)
        inferred_map = self._build_relation_map(inferred_relations)
        
        # 获取所有目标 UID
        all_targets = set(declared_map.keys()) | set(inferred_map.keys())
        
        for target_uid in all_targets:
            declared = declared_map.get(target_uid)
            inferred = inferred_map.get(target_uid)
            
            if declared and inferred:
                # 两者都存在，检查冲突
                conflict = self._detect_conflict(source_uid, target_uid, declared, inferred)
                
                if conflict:
                    conflicts.append(conflict)
                    resolved = self._resolve_conflict(declared, inferred, conflict)
                    
                    if resolved.resolution_strategy == ResolutionStrategy.MANUAL_REVIEW:
                        manual_review_needed.append(conflict)
                    
                    relations.append(resolved)
                else:
                    # 无冲突，合并
                    relations.append(self._merge_relations(declared, inferred))
            
            elif declared:
                # 只有声明
                relations.append(ResolvedRelation(
                    source_uid=source_uid,
                    target_uid=target_uid,
                    edge_type=declared.edge_type,
                    confidence=declared.confidence,
                    reasoning=declared.reasoning,
                    resolution_strategy=ResolutionStrategy.KEEP_DECLARED,
                    original_declared=declared,
                ))
            
            elif inferred:
                # 只有推断
                # 检查置信度是否足够
                if inferred.confidence >= self.auto_resolve_threshold:
                    relations.append(ResolvedRelation(
                        source_uid=source_uid,
                        target_uid=target_uid,
                        edge_type=inferred.edge_type,
                        confidence=inferred.confidence,
                        reasoning=inferred.reasoning,
                        resolution_strategy=ResolutionStrategy.KEEP_INFERRED,
                        original_inferred=inferred,
                    ))
                else:
                    # 低置信度推断，不采纳
                    pass
        
        # 生成摘要
        summary = self._generate_summary(relations, conflicts, manual_review_needed)
        
        return ResolvedTopology(
            source_uid=source_uid,
            relations=relations,
            conflicts=conflicts,
            manual_review_needed=manual_review_needed,
            resolution_summary=summary,
        )
    
    def _build_relation_map(
        self,
        relations: list[InferredRelation],
    ) -> dict[str, InferredRelation]:
        """
        构建关系映射（target_uid -> relation）。
        
        Args:
            relations: 关系列表
            
        Returns:
            dict: 映射字典
        """
        # 对于同一目标的多条关系，保留置信度最高的
        relation_map: dict[str, InferredRelation] = {}
        
        for relation in relations:
            target_uid = relation.target_uid
            if target_uid not in relation_map:
                relation_map[target_uid] = relation
            elif relation.confidence > relation_map[target_uid].confidence:
                relation_map[target_uid] = relation
        
        return relation_map
    
    def _detect_conflict(
        self,
        source_uid: str,
        target_uid: str,
        declared: InferredRelation,
        inferred: InferredRelation,
    ) -> Optional[ConflictInfo]:
        """
        检测冲突。
        
        Args:
            source_uid: 源 UID
            target_uid: 目标 UID
            declared: 声明的关系
            inferred: 推断的关系
            
        Returns:
            Optional[ConflictInfo]: 冲突信息（如果存在）
        """
        # 边类型冲突
        if declared.edge_type != inferred.edge_type:
            return ConflictInfo(
                source_uid=source_uid,
                target_uid=target_uid,
                declared_edge_type=declared.edge_type,
                inferred_edge_type=inferred.edge_type,
                declared_confidence=declared.confidence,
                inferred_confidence=inferred.confidence,
                conflict_type=self.EDGE_TYPE_CONFLICT,
                description=f"Declared as {declared.edge_type.value}, inferred as {inferred.edge_type.value}",
            )
        
        # 无冲突
        return None
    
    def _resolve_conflict(
        self,
        declared: InferredRelation,
        inferred: InferredRelation,
        conflict: ConflictInfo,
    ) -> ResolvedRelation:
        """
        解决冲突。
        
        Args:
            declared: 声明的关系
            inferred: 推断的关系
            conflict: 冲突信息
            
        Returns:
            ResolvedRelation: 解决后的关系
        """
        # 根据策略优先级解决
        for strategy in self.strategy_priority:
            resolved = self._apply_strategy(strategy, declared, inferred, conflict)
            if resolved:
                return resolved
        
        # 默认保留声明
        return ResolvedRelation(
            source_uid=declared.source_uid,
            target_uid=declared.target_uid,
            edge_type=declared.edge_type,
            confidence=declared.confidence,
            reasoning=f"Conflict resolved by default strategy: keep declared",
            resolution_strategy=ResolutionStrategy.KEEP_DECLARED,
            original_declared=declared,
            original_inferred=inferred,
        )
    
    def _apply_strategy(
        self,
        strategy: ResolutionStrategy,
        declared: InferredRelation,
        inferred: InferredRelation,
        conflict: ConflictInfo,
    ) -> Optional[ResolvedRelation]:
        """
        应用解决策略。
        
        Args:
            strategy: 解决策略
            declared: 声明的关系
            inferred: 推断的关系
            conflict: 冲突信息
            
        Returns:
            Optional[ResolvedRelation]: 解决结果
        """
        source_uid = declared.source_uid or inferred.source_uid
        target_uid = declared.target_uid
        
        if strategy == ResolutionStrategy.KEEP_DECLARED:
            return ResolvedRelation(
                source_uid=source_uid,
                target_uid=target_uid,
                edge_type=declared.edge_type,
                confidence=declared.confidence,
                reasoning=f"Keeping human-declared relation over inferred {inferred.edge_type.value}",
                resolution_strategy=strategy,
                original_declared=declared,
                original_inferred=inferred,
            )
        
        elif strategy == ResolutionStrategy.KEEP_INFERRED:
            # 仅在推断置信度很高时使用
            if inferred.confidence >= 0.9:
                return ResolvedRelation(
                    source_uid=source_uid,
                    target_uid=target_uid,
                    edge_type=inferred.edge_type,
                    confidence=inferred.confidence,
                    reasoning=f"Keeping high-confidence inferred relation over declared",
                    resolution_strategy=strategy,
                    original_declared=declared,
                    original_inferred=inferred,
                )
            return None
        
        elif strategy == ResolutionStrategy.MERGE:
            # 尝试合并（仅适用于兼容的边类型）
            if self._are_compatible_types(declared.edge_type, inferred.edge_type):
                return ResolvedRelation(
                    source_uid=source_uid,
                    target_uid=target_uid,
                    edge_type=declared.edge_type,  # 优先声明类型
                    confidence=max(declared.confidence, inferred.confidence),
                    reasoning=f"Merged declared {declared.edge_type.value} with inferred {inferred.edge_type.value}",
                    resolution_strategy=strategy,
                    original_declared=declared,
                    original_inferred=inferred,
                )
            return None
        
        elif strategy == ResolutionStrategy.MANUAL_REVIEW:
            # 标记需要人工审核
            return ResolvedRelation(
                source_uid=source_uid,
                target_uid=target_uid,
                edge_type=declared.edge_type,  # 暂时使用声明
                confidence=declared.confidence,
                reasoning="Pending manual review due to conflict",
                resolution_strategy=strategy,
                original_declared=declared,
                original_inferred=inferred,
            )
        
        elif strategy == ResolutionStrategy.REJECT_BOTH:
            # 拒绝两者（不返回关系）
            return None
        
        return None
    
    def _are_compatible_types(
        self,
        type_a: EdgeType,
        type_b: EdgeType,
    ) -> bool:
        """
        检查边类型是否兼容。
        
        Args:
            type_a: 类型 A
            type_b: 类型 B
            
        Returns:
            bool: 是否兼容
        """
        # REQUIRES 和 ENHANCES 可以兼容（依赖 + 增强）
        compatible_pairs = [
            (EdgeType.REQUIRES, EdgeType.ENHANCES),
            (EdgeType.ENHANCES, EdgeType.REQUIRES),
            (EdgeType.SUBSTITUTES, EdgeType.ENHANCES),
            (EdgeType.ENHANCES, EdgeType.SUBSTITUTES),
        ]
        
        return (type_a, type_b) in compatible_pairs
    
    def _merge_relations(
        self,
        declared: InferredRelation,
        inferred: InferredRelation,
    ) -> ResolvedRelation:
        """
        合并无冲突的关系。
        
        Args:
            declared: 声明的关系
            inferred: 推断的关系
            
        Returns:
            ResolvedRelation: 合并后的关系
        """
        # 无冲突时，使用声明的置信度，但合并推理信息
        reasoning = f"{declared.reasoning}"
        if inferred.reasoning:
            reasoning += f" | LLM: {inferred.reasoning}"
        
        return ResolvedRelation(
            source_uid=declared.source_uid,
            target_uid=declared.target_uid,
            edge_type=declared.edge_type,
            confidence=declared.confidence,  # 声明置信度为 1.0
            reasoning=reasoning,
            resolution_strategy=ResolutionStrategy.MERGE,
            original_declared=declared,
            original_inferred=inferred,
        )
    
    def _generate_summary(
        self,
        relations: list[ResolvedRelation],
        conflicts: list[ConflictInfo],
        manual_review_needed: list[ConflictInfo],
    ) -> str:
        """
        生成解决摘要。
        
        Args:
            relations: 关系列表
            conflicts: 冲突列表
            manual_review_needed: 需人工审核列表
            
        Returns:
            str: 摘要文本
        """
        total_relations = len(relations)
        total_conflicts = len(conflicts)
        manual_count = len(manual_review_needed)
        
        # 统计策略使用
        strategy_counts: dict[ResolutionStrategy, int] = {}
        for relation in relations:
            strategy = relation.resolution_strategy
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        
        summary_parts = [
            f"Total relations: {total_relations}",
            f"Conflicts detected: {total_conflicts}",
            f"Manual review needed: {manual_count}",
        ]
        
        if strategy_counts:
            strategy_str = ", ".join(
                f"{s.value}: {c}" for s, c in strategy_counts.items()
            )
            summary_parts.append(f"Resolution strategies: {strategy_str}")
        
        return " | ".join(summary_parts)
    
    def batch_resolve(
        self,
        declared_map: dict[str, list[InferredRelation]],
        inferred_map: dict[str, list[InferredRelation]],
    ) -> dict[str, ResolvedTopology]:
        """
        批量解决冲突。
        
        Args:
            declared_map: UID 到声明关系列表的映射
            inferred_map: UID 到推断关系列表的映射
            
        Returns:
            dict: UID 到解决结果的映射
        """
        results: dict[str, ResolvedTopology] = {}
        
        all_uids = set(declared_map.keys()) | set(inferred_map.keys())
        
        for uid in all_uids:
            declared = declared_map.get(uid, [])
            inferred = inferred_map.get(uid, [])
            
            results[uid] = self.resolve(declared, inferred, uid)
        
        return results
    
    def get_conflicts_for_review(
        self,
        resolved_topologies: dict[str, ResolvedTopology],
    ) -> list[ConflictInfo]:
        """
        获取需要人工审核的冲突列表。
        
        Args:
            resolved_topologies: 解决结果映射
            
        Returns:
            list: 需审核的冲突列表
        """
        conflicts: list[ConflictInfo] = []
        
        for topology in resolved_topologies.values():
            conflicts.extend(topology.manual_review_needed)
        
        return conflicts
    
    def apply_manual_decision(
        self,
        conflict: ConflictInfo,
        decision: ResolutionStrategy,
        custom_edge_type: Optional[EdgeType] = None,
        custom_confidence: Optional[float] = None,
    ) -> ResolvedRelation:
        """
        应用人工决策。
        
        Args:
            conflict: 冲突信息
            decision: 决策策略
            custom_edge_type: 自定义边类型（可选）
            custom_confidence: 自定义置信度（可选）
            
        Returns:
            ResolvedRelation: 解决后的关系
        """
        edge_type = custom_edge_type or conflict.declared_edge_type or EdgeType.REQUIRES
        confidence = custom_confidence or 1.0
        
        return ResolvedRelation(
            source_uid=conflict.source_uid,
            target_uid=conflict.target_uid,
            edge_type=edge_type,
            confidence=confidence,
            reasoning=f"Manual decision: {decision.value}",
            resolution_strategy=decision,
        )