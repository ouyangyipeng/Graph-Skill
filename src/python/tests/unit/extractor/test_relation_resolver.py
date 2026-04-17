"""
Relation Resolver 单元测试。

测试关系冲突解决器的所有组件：
- ResolutionStrategy 枚举
- ConflictInfo 数据结构
- ResolvedRelation 数据结构
- ResolvedTopology 数据结构
- RelationResolver 类
"""

from __future__ import annotations

import pytest
from typing import Any

from graphskill.core.models import EdgeType
from graphskill.ingestion.extractor.topology_extractor import InferredRelation
from graphskill.ingestion.extractor.relation_resolver import (
    ResolutionStrategy,
    ConflictInfo,
    ResolvedRelation,
    ResolvedTopology,
    RelationResolver,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def resolver() -> RelationResolver:
    """默认解决器。"""
    return RelationResolver()


@pytest.fixture
def resolver_custom_strategy() -> RelationResolver:
    """自定义策略优先级的解决器。"""
    return RelationResolver(
        strategy_priority=[
            ResolutionStrategy.MERGE,
            ResolutionStrategy.KEEP_DECLARED,
            ResolutionStrategy.MANUAL_REVIEW,
        ],
        auto_resolve_threshold=0.8,
    )


@pytest.fixture
def declared_relation() -> InferredRelation:
    """人工声明的关系。"""
    return InferredRelation(
        source_uid="skill:source",
        target_uid="skill:target",
        edge_type=EdgeType.REQUIRES,
        confidence=1.0,
        reasoning="Human-declared dependency",
        is_declared=True,
    )


@pytest.fixture
def inferred_relation() -> InferredRelation:
    """LLM 推断的关系。"""
    return InferredRelation(
        source_uid="skill:source",
        target_uid="skill:target",
        edge_type=EdgeType.ENHANCES,
        confidence=0.75,
        reasoning="LLM inferred enhancement",
        is_declared=False,
    )


@pytest.fixture
def inferred_high_confidence() -> InferredRelation:
    """高置信度推断关系。"""
    return InferredRelation(
        source_uid="skill:source",
        target_uid="skill:target",
        edge_type=EdgeType.ENHANCES,
        confidence=0.95,
        reasoning="High confidence inference",
        is_declared=False,
    )


@pytest.fixture
def inferred_low_confidence() -> InferredRelation:
    """低置信度推断关系。"""
    return InferredRelation(
        source_uid="skill:source",
        target_uid="skill:target",
        edge_type=EdgeType.ENHANCES,
        confidence=0.5,
        reasoning="Low confidence inference",
        is_declared=False,
    )


@pytest.fixture
def same_type_declared() -> InferredRelation:
    """与推断相同类型的声明关系。"""
    return InferredRelation(
        source_uid="skill:source",
        target_uid="skill:target",
        edge_type=EdgeType.REQUIRES,
        confidence=1.0,
        reasoning="Declared requires",
        is_declared=True,
    )


@pytest.fixture
def same_type_inferred() -> InferredRelation:
    """与声明相同类型的推断关系。"""
    return InferredRelation(
        source_uid="skill:source",
        target_uid="skill:target",
        edge_type=EdgeType.REQUIRES,
        confidence=0.8,
        reasoning="Inferred requires",
        is_declared=False,
    )


@pytest.fixture
def multiple_declared() -> list[InferredRelation]:
    """多个人工声明关系。"""
    return [
        InferredRelation("skill:a", EdgeType.REQUIRES, 1.0, "D1", "skill:source", True),
        InferredRelation("skill:b", EdgeType.CONFLICTS_WITH, 1.0, "D2", "skill:source", True),
    ]


@pytest.fixture
def multiple_inferred() -> list[InferredRelation]:
    """多个 LLM 推断关系。"""
    return [
        InferredRelation("skill:a", EdgeType.ENHANCES, 0.8, "I1", "skill:source", False),
        InferredRelation("skill:c", EdgeType.SUBSTITUTES, 0.75, "I2", "skill:source", False),
    ]


# ============================================================================
# ResolutionStrategy Tests
# ============================================================================

class TestResolutionStrategy:
    """ResolutionStrategy 枚举测试。"""
    
    def test_strategy_enum_values(self) -> None:
        """测试枚举值。"""
        assert ResolutionStrategy.KEEP_DECLARED.value == "keep_declared"
        assert ResolutionStrategy.KEEP_INFERRED.value == "keep_inferred"
        assert ResolutionStrategy.MERGE.value == "merge"
        assert ResolutionStrategy.REJECT_BOTH.value == "reject_both"
        assert ResolutionStrategy.MANUAL_REVIEW.value == "manual_review"
    
    def test_strategy_enum_count(self) -> None:
        """测试枚举数量。"""
        assert len(ResolutionStrategy) == 5
    
    def test_strategy_is_string_enum(self) -> None:
        """测试是字符串枚举。"""
        assert isinstance(ResolutionStrategy.KEEP_DECLARED, str)
        assert ResolutionStrategy.KEEP_DECLARED == "keep_declared"


# ============================================================================
# ConflictInfo Tests
# ============================================================================

class TestConflictInfo:
    """ConflictInfo 数据结构测试。"""
    
    def test_create_conflict_info(self) -> None:
        """测试创建冲突信息。"""
        conflict = ConflictInfo(
            source_uid="skill:source",
            target_uid="skill:target",
            declared_edge_type=EdgeType.REQUIRES,
            inferred_edge_type=EdgeType.ENHANCES,
            declared_confidence=1.0,
            inferred_confidence=0.75,
            conflict_type="edge_type_conflict",
            description="Type mismatch",
        )
        
        assert conflict.source_uid == "skill:source"
        assert conflict.target_uid == "skill:target"
        assert conflict.declared_edge_type == EdgeType.REQUIRES
        assert conflict.inferred_edge_type == EdgeType.ENHANCES
        assert conflict.declared_confidence == 1.0
        assert conflict.inferred_confidence == 0.75
        assert conflict.conflict_type == "edge_type_conflict"
        assert conflict.description == "Type mismatch"
    
    def test_conflict_info_defaults(self) -> None:
        """测试默认值。"""
        conflict = ConflictInfo(
            source_uid="skill:source",
            target_uid="skill:target",
        )
        
        assert conflict.declared_edge_type is None
        assert conflict.inferred_edge_type is None
        assert conflict.declared_confidence == 1.0
        assert conflict.inferred_confidence == 0.0
        assert conflict.conflict_type == ""
        assert conflict.description == ""
    
    def test_conflict_info_to_dict(self) -> None:
        """测试 to_dict 方法。"""
        conflict = ConflictInfo(
            source_uid="skill:source",
            target_uid="skill:target",
            declared_edge_type=EdgeType.REQUIRES,
            inferred_edge_type=EdgeType.CONFLICTS_WITH,
            declared_confidence=1.0,
            inferred_confidence=0.8,
            conflict_type="edge_type_conflict",
            description="Test conflict",
        )
        
        result = conflict.to_dict()
        
        assert result["source_uid"] == "skill:source"
        assert result["target_uid"] == "skill:target"
        assert result["declared_edge_type"] == "REQUIRES"
        assert result["inferred_edge_type"] == "CONFLICTS_WITH"
        assert result["declared_confidence"] == 1.0
        assert result["inferred_confidence"] == 0.8
        assert result["conflict_type"] == "edge_type_conflict"
        assert result["description"] == "Test conflict"
    
    def test_conflict_info_to_dict_none_edge_types(self) -> None:
        """测试 to_dict 处理 None edge types。"""
        conflict = ConflictInfo(
            source_uid="skill:source",
            target_uid="skill:target",
        )
        
        result = conflict.to_dict()
        
        assert result["declared_edge_type"] is None
        assert result["inferred_edge_type"] is None


# ============================================================================
# ResolvedRelation Tests
# ============================================================================

class TestResolvedRelation:
    """ResolvedRelation 数据结构测试。"""
    
    def test_create_resolved_relation(self) -> None:
        """测试创建解决后的关系。"""
        relation = ResolvedRelation(
            source_uid="skill:source",
            target_uid="skill:target",
            edge_type=EdgeType.REQUIRES,
            confidence=1.0,
            reasoning="Resolved reasoning",
            resolution_strategy=ResolutionStrategy.KEEP_DECLARED,
        )
        
        assert relation.source_uid == "skill:source"
        assert relation.target_uid == "skill:target"
        assert relation.edge_type == EdgeType.REQUIRES
        assert relation.confidence == 1.0
        assert relation.reasoning == "Resolved reasoning"
        assert relation.resolution_strategy == ResolutionStrategy.KEEP_DECLARED
        assert relation.original_declared is None
        assert relation.original_inferred is None
    
    def test_resolved_relation_with_originals(
        self,
        declared_relation: InferredRelation,
        inferred_relation: InferredRelation,
    ) -> None:
        """测试带原始关系的解决关系。"""
        relation = ResolvedRelation(
            source_uid="skill:source",
            target_uid="skill:target",
            edge_type=EdgeType.REQUIRES,
            confidence=1.0,
            reasoning="Resolved",
            resolution_strategy=ResolutionStrategy.MERGE,
            original_declared=declared_relation,
            original_inferred=inferred_relation,
        )
        
        assert relation.original_declared == declared_relation
        assert relation.original_inferred == inferred_relation
    
    def test_resolved_relation_to_dict(self) -> None:
        """测试 to_dict 方法。"""
        relation = ResolvedRelation(
            source_uid="skill:source",
            target_uid="skill:target",
            edge_type=EdgeType.ENHANCES,
            confidence=0.85,
            reasoning="Test reasoning",
            resolution_strategy=ResolutionStrategy.KEEP_INFERRED,
        )
        
        result = relation.to_dict()
        
        assert result["source_uid"] == "skill:source"
        assert result["target_uid"] == "skill:target"
        assert result["edge_type"] == "ENHANCES"
        assert result["confidence"] == 0.85
        assert result["reasoning"] == "Test reasoning"
        assert result["resolution_strategy"] == "keep_inferred"
        assert "original_declared" not in result
        assert "original_inferred" not in result
    
    def test_resolved_relation_to_inferred_relation(self) -> None:
        """测试转换为 InferredRelation。"""
        relation = ResolvedRelation(
            source_uid="skill:source",
            target_uid="skill:target",
            edge_type=EdgeType.REQUIRES,
            confidence=1.0,
            reasoning="Resolved",
            resolution_strategy=ResolutionStrategy.KEEP_DECLARED,
        )
        
        inferred = relation.to_inferred_relation()
        
        assert inferred.source_uid == "skill:source"
        assert inferred.target_uid == "skill:target"
        assert inferred.edge_type == EdgeType.REQUIRES
        assert inferred.confidence == 1.0
        assert inferred.reasoning == "Resolved"
        assert inferred.is_declared is True
    
    def test_to_inferred_relation_non_declared_strategy(self) -> None:
        """测试非 KEEP_DECLARED 策略转换。"""
        relation = ResolvedRelation(
            source_uid="skill:source",
            target_uid="skill:target",
            edge_type=EdgeType.ENHANCES,
            confidence=0.8,
            reasoning="Inferred",
            resolution_strategy=ResolutionStrategy.KEEP_INFERRED,
        )
        
        inferred = relation.to_inferred_relation()
        
        assert inferred.is_declared is False


# ============================================================================
# ResolvedTopology Tests
# ============================================================================

class TestResolvedTopology:
    """ResolvedTopology 数据结构测试。"""
    
    def test_create_resolved_topology(self) -> None:
        """测试创建解决后的拓扑。"""
        relations = [
            ResolvedRelation(
                source_uid="skill:source",
                target_uid="skill:a",
                edge_type=EdgeType.REQUIRES,
                confidence=1.0,
                reasoning="R1",
                resolution_strategy=ResolutionStrategy.KEEP_DECLARED,
            ),
        ]
        conflicts = [
            ConflictInfo("skill:source", "skill:b", EdgeType.REQUIRES, EdgeType.ENHANCES),
        ]
        
        topology = ResolvedTopology(
            source_uid="skill:source",
            relations=relations,
            conflicts=conflicts,
            manual_review_needed=[],
            resolution_summary="Test summary",
        )
        
        assert topology.source_uid == "skill:source"
        assert len(topology.relations) == 1
        assert len(topology.conflicts) == 1
        assert len(topology.manual_review_needed) == 0
        assert topology.resolution_summary == "Test summary"
    
    def test_resolved_topology_defaults(self) -> None:
        """测试默认值。"""
        topology = ResolvedTopology(source_uid="skill:source")
        
        assert topology.relations == []
        assert topology.conflicts == []
        assert topology.manual_review_needed == []
        assert topology.resolution_summary == ""
    
    def test_relation_count_property(self) -> None:
        """测试 relation_count 属性。"""
        topology_empty = ResolvedTopology(source_uid="skill:source")
        assert topology_empty.relation_count == 0
        
        relations = [
            ResolvedRelation(
                source_uid="skill:source",
                target_uid="skill:a",
                edge_type=EdgeType.REQUIRES,
                confidence=1.0,
                reasoning="R1",
                resolution_strategy=ResolutionStrategy.KEEP_DECLARED,
            ),
            ResolvedRelation(
                source_uid="skill:source",
                target_uid="skill:b",
                edge_type=EdgeType.ENHANCES,
                confidence=0.8,
                reasoning="R2",
                resolution_strategy=ResolutionStrategy.KEEP_INFERRED,
            ),
        ]
        topology_with_relations = ResolvedTopology(
            source_uid="skill:source",
            relations=relations,
        )
        assert topology_with_relations.relation_count == 2
    
    def test_conflict_count_property(self) -> None:
        """测试 conflict_count 属性。"""
        topology_no_conflicts = ResolvedTopology(source_uid="skill:source")
        assert topology_no_conflicts.conflict_count == 0
        
        conflicts = [
            ConflictInfo("skill:source", "skill:a"),
            ConflictInfo("skill:source", "skill:b"),
        ]
        topology_with_conflicts = ResolvedTopology(
            source_uid="skill:source",
            conflicts=conflicts,
        )
        assert topology_with_conflicts.conflict_count == 2
    
    def test_needs_manual_review_property(self) -> None:
        """测试 needs_manual_review 属性。"""
        topology_no_review = ResolvedTopology(source_uid="skill:source")
        assert topology_no_review.needs_manual_review is False
        
        manual_review = [ConflictInfo("skill:source", "skill:a")]
        topology_needs_review = ResolvedTopology(
            source_uid="skill:source",
            manual_review_needed=manual_review,
        )
        assert topology_needs_review.needs_manual_review is True
    
    def test_resolved_topology_to_dict(self) -> None:
        """测试 to_dict 方法。"""
        relations = [
            ResolvedRelation(
                source_uid="skill:source",
                target_uid="skill:a",
                edge_type=EdgeType.REQUIRES,
                confidence=1.0,
                reasoning="R1",
                resolution_strategy=ResolutionStrategy.KEEP_DECLARED,
            ),
        ]
        conflicts = [
            ConflictInfo("skill:source", "skill:b", EdgeType.REQUIRES, EdgeType.ENHANCES),
        ]
        
        topology = ResolvedTopology(
            source_uid="skill:source",
            relations=relations,
            conflicts=conflicts,
            manual_review_needed=[],
            resolution_summary="Summary",
        )
        
        result = topology.to_dict()
        
        assert result["source_uid"] == "skill:source"
        assert result["relation_count"] == 1
        assert result["conflict_count"] == 1
        assert result["needs_manual_review"] is False
        assert len(result["relations"]) == 1
        assert len(result["conflicts"]) == 1
        assert result["manual_review_needed"] == []
        assert result["resolution_summary"] == "Summary"


# ============================================================================
# RelationResolver Initialization Tests
# ============================================================================

class TestRelationResolverInit:
    """RelationResolver 初始化测试。"""
    
    def test_init_default(self) -> None:
        """测试默认初始化。"""
        resolver = RelationResolver()
        
        assert resolver.strategy_priority == RelationResolver.DEFAULT_STRATEGY_PRIORITY
        assert resolver.auto_resolve_threshold == 0.7
    
    def test_init_custom_params(self) -> None:
        """测试自定义参数初始化。"""
        custom_priority = [
            ResolutionStrategy.MERGE,
            ResolutionStrategy.KEEP_DECLARED,
        ]
        resolver = RelationResolver(
            strategy_priority=custom_priority,
            auto_resolve_threshold=0.9,
        )
        
        assert resolver.strategy_priority == custom_priority
        assert resolver.auto_resolve_threshold == 0.9
    
    def test_default_strategy_priority(self) -> None:
        """测试默认策略优先级。"""
        assert RelationResolver.DEFAULT_STRATEGY_PRIORITY[0] == ResolutionStrategy.KEEP_DECLARED
    
    def test_conflict_type_constants(self) -> None:
        """测试冲突类型常量。"""
        assert RelationResolver.EDGE_TYPE_CONFLICT == "edge_type_conflict"
        assert RelationResolver.DIRECTION_CONFLICT == "direction_conflict"
        assert RelationResolver.EXISTENCE_CONFLICT == "existence_conflict"


# ============================================================================
# RelationResolver Resolve Tests
# ============================================================================

class TestRelationResolverResolve:
    """RelationResolver resolve 方法测试。"""
    
    def test_resolve_empty_inputs(self, resolver: RelationResolver) -> None:
        """测试空输入。"""
        result = resolver.resolve([], [], "skill:source")
        
        assert result.source_uid == "skill:source"
        assert result.relation_count == 0
        assert result.conflict_count == 0
        assert result.needs_manual_review is False
    
    def test_resolve_only_declared(
        self,
        resolver: RelationResolver,
        declared_relation: InferredRelation,
    ) -> None:
        """测试只有声明关系。"""
        result = resolver.resolve([declared_relation], [], "skill:source")
        
        assert result.relation_count == 1
        assert result.relations[0].resolution_strategy == ResolutionStrategy.KEEP_DECLARED
        assert result.relations[0].edge_type == EdgeType.REQUIRES
        assert result.conflict_count == 0
    
    def test_resolve_only_inferred_high_confidence(
        self,
        resolver: RelationResolver,
        inferred_high_confidence: InferredRelation,
    ) -> None:
        """测试只有高置信度推断。"""
        result = resolver.resolve([], [inferred_high_confidence], "skill:source")
        
        assert result.relation_count == 1
        assert result.relations[0].resolution_strategy == ResolutionStrategy.KEEP_INFERRED
        assert result.relations[0].confidence == 0.95
    
    def test_resolve_only_inferred_low_confidence(
        self,
        resolver: RelationResolver,
        inferred_low_confidence: InferredRelation,
    ) -> None:
        """测试只有低置信度推断（不采纳）。"""
        result = resolver.resolve([], [inferred_low_confidence], "skill:source")
        
        # 低置信度推断不采纳
        assert result.relation_count == 0
    
    def test_resolve_same_type_no_conflict(
        self,
        resolver: RelationResolver,
        same_type_declared: InferredRelation,
        same_type_inferred: InferredRelation,
    ) -> None:
        """测试相同类型无冲突。"""
        result = resolver.resolve(
            [same_type_declared],
            [same_type_inferred],
            "skill:source",
        )
        
        assert result.relation_count == 1
        assert result.conflict_count == 0
        assert result.relations[0].edge_type == EdgeType.REQUIRES
        assert result.relations[0].resolution_strategy == ResolutionStrategy.MERGE
    
    def test_resolve_different_type_conflict(
        self,
        resolver: RelationResolver,
        declared_relation: InferredRelation,
        inferred_relation: InferredRelation,
    ) -> None:
        """测试不同类型冲突。"""
        result = resolver.resolve(
            [declared_relation],
            [inferred_relation],
            "skill:source",
        )
        
        assert result.relation_count == 1
        assert result.conflict_count == 1
        # 默认策略优先级：KEEP_DECLARED
        assert result.relations[0].resolution_strategy == ResolutionStrategy.KEEP_DECLARED
        assert result.relations[0].edge_type == EdgeType.REQUIRES
    
    def test_resolve_multiple_relations(
        self,
        resolver: RelationResolver,
        multiple_declared: list[InferredRelation],
        multiple_inferred: list[InferredRelation],
    ) -> None:
        """测试多个关系。"""
        result = resolver.resolve(
            multiple_declared,
            multiple_inferred,
            "skill:source",
        )
        
        # skill:a 有冲突，skill:b 只有声明，skill:c 只有推断
        assert result.relation_count >= 2
        assert result.conflict_count >= 1
    
    def test_resolve_custom_threshold(
        self,
        resolver_custom_strategy: RelationResolver,
        inferred_relation: InferredRelation,
    ) -> None:
        """测试自定义阈值。"""
        # inferred_relation.confidence = 0.75 < 0.8 threshold
        result = resolver_custom_strategy.resolve([], [inferred_relation], "skill:source")
        
        assert result.relation_count == 0


# ============================================================================
# RelationResolver Conflict Detection Tests
# ============================================================================

class TestRelationResolverConflictDetection:
    """冲突检测测试。"""
    
    def test_detect_edge_type_conflict(
        self,
        resolver: RelationResolver,
        declared_relation: InferredRelation,
        inferred_relation: InferredRelation,
    ) -> None:
        """测试边类型冲突检测。"""
        conflict = resolver._detect_conflict(
            "skill:source",
            "skill:target",
            declared_relation,
            inferred_relation,
        )
        
        assert conflict is not None
        assert conflict.conflict_type == RelationResolver.EDGE_TYPE_CONFLICT
        assert conflict.declared_edge_type == EdgeType.REQUIRES
        assert conflict.inferred_edge_type == EdgeType.ENHANCES
    
    def test_no_conflict_same_type(
        self,
        resolver: RelationResolver,
        same_type_declared: InferredRelation,
        same_type_inferred: InferredRelation,
    ) -> None:
        """测试相同类型无冲突。"""
        conflict = resolver._detect_conflict(
            "skill:source",
            "skill:target",
            same_type_declared,
            same_type_inferred,
        )
        
        assert conflict is None


# ============================================================================
# RelationResolver Strategy Application Tests
# ============================================================================

class TestRelationResolverStrategyApplication:
    """策略应用测试。"""
    
    def test_apply_keep_declared_strategy(
        self,
        resolver: RelationResolver,
        declared_relation: InferredRelation,
        inferred_relation: InferredRelation,
    ) -> None:
        """测试 KEEP_DECLARED 策略。"""
        conflict = ConflictInfo(
            source_uid="skill:source",
            target_uid="skill:target",
            declared_edge_type=EdgeType.REQUIRES,
            inferred_edge_type=EdgeType.ENHANCES,
        )
        
        result = resolver._apply_strategy(
            ResolutionStrategy.KEEP_DECLARED,
            declared_relation,
            inferred_relation,
            conflict,
        )
        
        assert result is not None
        assert result.resolution_strategy == ResolutionStrategy.KEEP_DECLARED
        assert result.edge_type == EdgeType.REQUIRES
        assert result.confidence == 1.0
    
    def test_apply_keep_inferred_high_confidence(
        self,
        resolver: RelationResolver,
        declared_relation: InferredRelation,
        inferred_high_confidence: InferredRelation,
    ) -> None:
        """测试 KEEP_INFERRED 策略（高置信度）。"""
        conflict = ConflictInfo(
            source_uid="skill:source",
            target_uid="skill:target",
            declared_edge_type=EdgeType.REQUIRES,
            inferred_edge_type=EdgeType.ENHANCES,
        )
        
        result = resolver._apply_strategy(
            ResolutionStrategy.KEEP_INFERRED,
            declared_relation,
            inferred_high_confidence,
            conflict,
        )
        
        assert result is not None
        assert result.resolution_strategy == ResolutionStrategy.KEEP_INFERRED
        assert result.edge_type == EdgeType.ENHANCES
    
    def test_apply_keep_inferred_low_confidence(
        self,
        resolver: RelationResolver,
        declared_relation: InferredRelation,
        inferred_relation: InferredRelation,
    ) -> None:
        """测试 KEEP_INFERRED 策略（低置信度不适用）。"""
        conflict = ConflictInfo(
            source_uid="skill:source",
            target_uid="skill:target",
            declared_edge_type=EdgeType.REQUIRES,
            inferred_edge_type=EdgeType.ENHANCES,
        )
        
        result = resolver._apply_strategy(
            ResolutionStrategy.KEEP_INFERRED,
            declared_relation,
            inferred_relation,  # confidence = 0.75 < 0.9
            conflict,
        )
        
        # 低置信度不适用此策略
        assert result is None
    
    def test_apply_merge_compatible_types(
        self,
        resolver: RelationResolver,
    ) -> None:
        """测试 MERGE 策略（兼容类型）。"""
        declared = InferredRelation(
            "skill:target", EdgeType.REQUIRES, 1.0, "D", "skill:source"
        )
        inferred = InferredRelation(
            "skill:target", EdgeType.ENHANCES, 0.8, "I", "skill:source"
        )
        conflict = ConflictInfo(
            source_uid="skill:source",
            target_uid="skill:target",
            declared_edge_type=EdgeType.REQUIRES,
            inferred_edge_type=EdgeType.ENHANCES,
        )
        
        result = resolver._apply_strategy(
            ResolutionStrategy.MERGE,
            declared,
            inferred,
            conflict,
        )
        
        # REQUIRES 和 ENHANCES 是兼容的
        assert result is not None
        assert result.resolution_strategy == ResolutionStrategy.MERGE
    
    def test_apply_merge_incompatible_types(
        self,
        resolver: RelationResolver,
        declared_relation: InferredRelation,
    ) -> None:
        """测试 MERGE 策略（不兼容类型）。"""
        inferred = InferredRelation(
            "skill:target", EdgeType.CONFLICTS_WITH, 0.8, "I", "skill:source"
        )
        conflict = ConflictInfo(
            source_uid="skill:source",
            target_uid="skill:target",
            declared_edge_type=EdgeType.REQUIRES,
            inferred_edge_type=EdgeType.CONFLICTS_WITH,
        )
        
        result = resolver._apply_strategy(
            ResolutionStrategy.MERGE,
            declared_relation,
            inferred,
            conflict,
        )
        
        # REQUIRES 和 CONFLICTS_WITH 不兼容
        assert result is None
    
    def test_apply_manual_review_strategy(
        self,
        resolver: RelationResolver,
        declared_relation: InferredRelation,
        inferred_relation: InferredRelation,
    ) -> None:
        """测试 MANUAL_REVIEW 策略。"""
        conflict = ConflictInfo(
            source_uid="skill:source",
            target_uid="skill:target",
            declared_edge_type=EdgeType.REQUIRES,
            inferred_edge_type=EdgeType.ENHANCES,
        )
        
        result = resolver._apply_strategy(
            ResolutionStrategy.MANUAL_REVIEW,
            declared_relation,
            inferred_relation,
            conflict,
        )
        
        assert result is not None
        assert result.resolution_strategy == ResolutionStrategy.MANUAL_REVIEW
    
    def test_apply_reject_both_strategy(
        self,
        resolver: RelationResolver,
        declared_relation: InferredRelation,
        inferred_relation: InferredRelation,
    ) -> None:
        """测试 REJECT_BOTH 策略。"""
        conflict = ConflictInfo(
            source_uid="skill:source",
            target_uid="skill:target",
            declared_edge_type=EdgeType.REQUIRES,
            inferred_edge_type=EdgeType.ENHANCES,
        )
        
        result = resolver._apply_strategy(
            ResolutionStrategy.REJECT_BOTH,
            declared_relation,
            inferred_relation,
            conflict,
        )
        
        # REJECT_BOTH 返回 None（不保留关系）
        assert result is None


# ============================================================================
# RelationResolver Compatible Types Tests
# ============================================================================

class TestRelationResolverCompatibleTypes:
    """兼容类型检查测试。"""
    
    def test_requires_enhances_compatible(self, resolver: RelationResolver) -> None:
        """测试 REQUIRES 和 ENHANCES 兼容。"""
        assert resolver._are_compatible_types(EdgeType.REQUIRES, EdgeType.ENHANCES)
        assert resolver._are_compatible_types(EdgeType.ENHANCES, EdgeType.REQUIRES)
    
    def test_substitutes_enhances_compatible(self, resolver: RelationResolver) -> None:
        """测试 SUBSTITUTES 和 ENHANCES 兼容。"""
        assert resolver._are_compatible_types(EdgeType.SUBSTITUTES, EdgeType.ENHANCES)
        assert resolver._are_compatible_types(EdgeType.ENHANCES, EdgeType.SUBSTITUTES)
    
    def test_requires_conflicts_incompatible(self, resolver: RelationResolver) -> None:
        """测试 REQUIRES 和 CONFLICTS_WITH 不兼容。"""
        assert not resolver._are_compatible_types(EdgeType.REQUIRES, EdgeType.CONFLICTS_WITH)
        assert not resolver._are_compatible_types(EdgeType.CONFLICTS_WITH, EdgeType.REQUIRES)
    
    def test_same_type_not_compatible(self, resolver: RelationResolver) -> None:
        """测试相同类型不在兼容列表中。"""
        # 相同类型不会触发 MERGE 策略（因为无冲突时会直接合并）
        assert not resolver._are_compatible_types(EdgeType.REQUIRES, EdgeType.REQUIRES)


# ============================================================================
# RelationResolver Batch Resolve Tests
# ============================================================================

class TestRelationResolverBatchResolve:
    """批量解决测试。"""
    
    def test_batch_resolve_empty(self, resolver: RelationResolver) -> None:
        """测试空批量输入。"""
        result = resolver.batch_resolve({}, {})
        
        assert len(result) == 0
    
    def test_batch_resolve_single_uid(
        self,
        resolver: RelationResolver,
        declared_relation: InferredRelation,
        inferred_relation: InferredRelation,
    ) -> None:
        """测试单个 UID 批量解决。"""
        declared_map = {"skill:source": [declared_relation]}
        inferred_map = {"skill:source": [inferred_relation]}
        
        result = resolver.batch_resolve(declared_map, inferred_map)
        
        assert len(result) == 1
        assert "skill:source" in result
        assert result["skill:source"].relation_count == 1
    
    def test_batch_resolve_multiple_uids(
        self,
        resolver: RelationResolver,
    ) -> None:
        """测试多个 UID 批量解决。"""
        declared_map = {
            "skill:a": [InferredRelation("skill:b", EdgeType.REQUIRES, 1.0, "D1", "skill:a")],
            "skill:b": [InferredRelation("skill:c", EdgeType.ENHANCES, 1.0, "D2", "skill:b")],
        }
        inferred_map = {
            "skill:a": [InferredRelation("skill:c", EdgeType.SUBSTITUTES, 0.8, "I1", "skill:a")],
            "skill:c": [InferredRelation("skill:d", EdgeType.REQUIRES, 0.9, "I2", "skill:c")],
        }
        
        result = resolver.batch_resolve(declared_map, inferred_map)
        
        assert len(result) == 3
        assert "skill:a" in result
        assert "skill:b" in result
        assert "skill:c" in result


# ============================================================================
# RelationResolver Manual Review Tests
# ============================================================================

class TestRelationResolverManualReview:
    """人工审核测试。"""
    
    def test_get_conflicts_for_review(
        self,
        resolver: RelationResolver,
    ) -> None:
        """测试获取需审核冲突。"""
        topology1 = ResolvedTopology(
            source_uid="skill:a",
            manual_review_needed=[ConflictInfo("skill:a", "skill:b")],
        )
        topology2 = ResolvedTopology(
            source_uid="skill:c",
            manual_review_needed=[ConflictInfo("skill:c", "skill:d")],
        )
        
        conflicts = resolver.get_conflicts_for_review({
            "skill:a": topology1,
            "skill:c": topology2,
        })
        
        assert len(conflicts) == 2
    
    def test_get_conflicts_for_review_empty(
        self,
        resolver: RelationResolver,
    ) -> None:
        """测试无需审核冲突。"""
        topology = ResolvedTopology(source_uid="skill:a")
        
        conflicts = resolver.get_conflicts_for_review({"skill:a": topology})
        
        assert len(conflicts) == 0
    
    def test_apply_manual_decision_keep_declared(
        self,
        resolver: RelationResolver,
    ) -> None:
        """测试人工决策保留声明。"""
        conflict = ConflictInfo(
            source_uid="skill:source",
            target_uid="skill:target",
            declared_edge_type=EdgeType.REQUIRES,
            inferred_edge_type=EdgeType.ENHANCES,
        )
        
        result = resolver.apply_manual_decision(
            conflict,
            ResolutionStrategy.KEEP_DECLARED,
        )
        
        assert result.resolution_strategy == ResolutionStrategy.KEEP_DECLARED
        assert result.edge_type == EdgeType.REQUIRES
    
    def test_apply_manual_decision_custom_type(
        self,
        resolver: RelationResolver,
    ) -> None:
        """测试人工决策自定义类型。"""
        conflict = ConflictInfo(
            source_uid="skill:source",
            target_uid="skill:target",
            declared_edge_type=EdgeType.REQUIRES,
            inferred_edge_type=EdgeType.ENHANCES,
        )
        
        result = resolver.apply_manual_decision(
            conflict,
            ResolutionStrategy.MERGE,
            custom_edge_type=EdgeType.SUBSTITUTES,
            custom_confidence=0.9,
        )
        
        assert result.edge_type == EdgeType.SUBSTITUTES
        assert result.confidence == 0.9


# ============================================================================
# RelationResolver Summary Generation Tests
# ============================================================================

class TestRelationResolverSummary:
    """摘要生成测试。"""
    
    def test_generate_summary_basic(self, resolver: RelationResolver) -> None:
        """测试基本摘要。"""
        relations = [
            ResolvedRelation(
                source_uid="skill:source",
                target_uid="skill:a",
                edge_type=EdgeType.REQUIRES,
                confidence=1.0,
                reasoning="R1",
                resolution_strategy=ResolutionStrategy.KEEP_DECLARED,
            ),
        ]
        
        summary = resolver._generate_summary(relations, [], [])
        
        assert "Total relations: 1" in summary
        assert "Conflicts detected: 0" in summary
        assert "Manual review needed: 0" in summary
    
    def test_generate_summary_with_conflicts(self, resolver: RelationResolver) -> None:
        """测试带冲突的摘要。"""
        relations = [
            ResolvedRelation(
                source_uid="skill:source",
                target_uid="skill:a",
                edge_type=EdgeType.REQUIRES,
                confidence=1.0,
                reasoning="R1",
                resolution_strategy=ResolutionStrategy.KEEP_DECLARED,
            ),
        ]
        conflicts = [ConflictInfo("skill:source", "skill:b")]
        
        summary = resolver._generate_summary(relations, conflicts, [])
        
        assert "Conflicts detected: 1" in summary
    
    def test_generate_summary_with_strategies(self, resolver: RelationResolver) -> None:
        """测试带策略统计的摘要。"""
        relations = [
            ResolvedRelation(
                source_uid="skill:source",
                target_uid="skill:a",
                edge_type=EdgeType.REQUIRES,
                confidence=1.0,
                reasoning="R1",
                resolution_strategy=ResolutionStrategy.KEEP_DECLARED,
            ),
            ResolvedRelation(
                source_uid="skill:source",
                target_uid="skill:b",
                edge_type=EdgeType.ENHANCES,
                confidence=0.8,
                reasoning="R2",
                resolution_strategy=ResolutionStrategy.KEEP_INFERRED,
            ),
            ResolvedRelation(
                source_uid="skill:source",
                target_uid="skill:c",
                edge_type=EdgeType.SUBSTITUTES,
                confidence=0.9,
                reasoning="R3",
                resolution_strategy=ResolutionStrategy.KEEP_DECLARED,
            ),
        ]
        
        summary = resolver._generate_summary(relations, [], [])
        
        assert "keep_declared: 2" in summary
        assert "keep_inferred: 1" in summary


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """边界条件测试。"""
    
    def test_resolve_with_none_source_uid(
        self,
        resolver: RelationResolver,
        declared_relation: InferredRelation,
    ) -> None:
        """测试声明关系无 source_uid。"""
        declared_no_source = InferredRelation(
            "skill:target", EdgeType.REQUIRES, 1.0, "D", None, True
        )
        
        result = resolver.resolve([declared_no_source], [], "skill:source")
        
        assert result.relation_count == 1
    
    def test_build_relation_map_same_target_multiple_relations(
        self,
        resolver: RelationResolver,
    ) -> None:
        """测试同一目标多条关系（保留最高置信度）。"""
        relations = [
            InferredRelation("skill:a", EdgeType.REQUIRES, 0.7, "R1", "skill:source"),
            InferredRelation("skill:a", EdgeType.ENHANCES, 0.9, "R2", "skill:source"),
        ]
        
        relation_map = resolver._build_relation_map(relations)
        
        assert len(relation_map) == 1
        assert relation_map["skill:a"].confidence == 0.9
    
    def test_resolve_all_rejected(
        self,
        resolver: RelationResolver,
    ) -> None:
        """测试 REJECT_BOTH 策略返回 None 后使用默认策略。"""
        # 当 REJECT_BOTH 返回 None 时，_resolve_conflict 会使用默认策略 KEEP_DECLARED
        resolver_reject = RelationResolver(
            strategy_priority=[ResolutionStrategy.REJECT_BOTH]
        )
        
        declared = InferredRelation(
            target_uid="skill:a",
            edge_type=EdgeType.REQUIRES,
            confidence=1.0,
            reasoning="D",
            source_uid="skill:source",
        )
        inferred = InferredRelation(
            target_uid="skill:a",
            edge_type=EdgeType.CONFLICTS_WITH,
            confidence=0.8,
            reasoning="I",
            source_uid="skill:source",
        )
        
        result = resolver_reject.resolve([declared], [inferred], "skill:source")
        
        # REJECT_BOTH 返回 None 后，使用默认策略 KEEP_DECLARED
        assert result.relation_count == 1
        assert result.relations[0].resolution_strategy == ResolutionStrategy.KEEP_DECLARED


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """集成测试。"""
    
    def test_full_resolution_workflow(
        self,
        resolver: RelationResolver,
    ) -> None:
        """测试完整解决工作流。"""
        # 声明关系
        declared = [
            InferredRelation("skill:a", EdgeType.REQUIRES, 1.0, "Declared dependency", "skill:source", True),
            InferredRelation("skill:b", EdgeType.CONFLICTS_WITH, 1.0, "Declared conflict", "skill:source", True),
        ]
        
        # 推断关系
        inferred = [
            InferredRelation("skill:a", EdgeType.ENHANCES, 0.8, "Inferred enhancement", "skill:source", False),
            InferredRelation("skill:c", EdgeType.SUBSTITUTES, 0.9, "Inferred substitute", "skill:source", False),
        ]
        
        # 解决冲突
        result = resolver.resolve(declared, inferred, "skill:source")
        
        # 验证结果
        assert result.source_uid == "skill:source"
        assert result.relation_count >= 2  # skill:a + skill:b 或更多
        
        # 验证冲突检测
        assert result.conflict_count >= 1  # skill:a 有冲突
        
        # 验证 to_dict 输出
        result_dict = result.to_dict()
        assert "source_uid" in result_dict
        assert "relations" in result_dict
        assert "conflicts" in result_dict
    
    def test_batch_workflow(
        self,
        resolver: RelationResolver,
    ) -> None:
        """测试批量工作流。"""
        declared_map = {
            "skill:a": [
                InferredRelation("skill:b", EdgeType.REQUIRES, 1.0, "D1", "skill:a"),
            ],
            "skill:b": [
                InferredRelation("skill:c", EdgeType.ENHANCES, 1.0, "D2", "skill:b"),
            ],
        }
        
        inferred_map = {
            "skill:a": [
                InferredRelation("skill:c", EdgeType.SUBSTITUTES, 0.85, "I1", "skill:a"),
            ],
            "skill:c": [
                InferredRelation("skill:d", EdgeType.REQUIRES, 0.9, "I2", "skill:c"),
            ],
        }
        
        results = resolver.batch_resolve(declared_map, inferred_map)
        
        assert len(results) == 3
        
        # 检查每个结果
        for uid, topology in results.items():
            assert topology.source_uid == uid
            assert isinstance(topology.relations, list)
            assert isinstance(topology.conflicts, list)