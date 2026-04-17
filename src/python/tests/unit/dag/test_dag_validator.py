"""
DAG Validator 单元测试。

测试 DAG 验证器的所有组件：
- DAGValidationError 数据结构
- DAGValidationResult 数据结构
- DAGValidationErrorException 异常
- DAGValidator 类
"""

from __future__ import annotations

import pytest
from typing import Any

from graphskill.core.models import SkillEdge, EdgeType
from graphskill.ingestion.dag.cycle_detector import CycleDetectionResult, CycleInfo
from graphskill.ingestion.dag.dag_validator import (
    DAGValidationError,
    DAGValidationResult,
    DAGValidationErrorException,
    DAGValidator,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def validator() -> DAGValidator:
    """默认验证器（非严格模式）。"""
    return DAGValidator(strict_mode=False)


@pytest.fixture
def strict_validator() -> DAGValidator:
    """严格模式验证器。"""
    return DAGValidator(strict_mode=True)


@pytest.fixture
def valid_edges() -> list[tuple[str, str]]:
    """有效的边列表（无环路）。"""
    return [
        ("skill:a", "skill:b"),
        ("skill:b", "skill:c"),
        ("skill:c", "skill:d"),
        ("skill:a", "skill:d"),  # 跨层依赖
    ]


@pytest.fixture
def cycle_edges() -> list[tuple[str, str]]:
    """有环路的边列表。"""
    return [
        ("skill:a", "skill:b"),
        ("skill:b", "skill:c"),
        ("skill:c", "skill:a"),  # 环路
    ]


@pytest.fixture
def self_ref_edges() -> list[tuple[str, str]]:
    """自引用边列表。"""
    return [
        ("skill:a", "skill:b"),
        ("skill:b", "skill:b"),  # 自引用
    ]


@pytest.fixture
def mixed_edges() -> list[tuple[str, str]]:
    """混合边列表（有环路和自引用）。"""
    return [
        ("skill:a", "skill:b"),
        ("skill:b", "skill:c"),
        ("skill:c", "skill:a"),  # 环路
        ("skill:d", "skill:d"),  # 自引用
    ]


@pytest.fixture
def isolated_node_edges() -> list[tuple[str, str]]:
    """有孤立节点的边列表。"""
    return [
        ("skill:a", "skill:b"),
        ("skill:b", "skill:c"),
    ]


@pytest.fixture
def skill_edges() -> list[SkillEdge]:
    """SkillEdge 列表。"""
    return [
        SkillEdge(
            source_uid="skill:a",
            target_uid="skill:b",
            edge_type=EdgeType.REQUIRES,
            weight=1.0,
        ),
        SkillEdge(
            source_uid="skill:b",
            target_uid="skill:c",
            edge_type=EdgeType.REQUIRES,
            weight=1.0,
        ),
        SkillEdge(
            source_uid="skill:a",
            target_uid="skill:c",
            edge_type=EdgeType.ENHANCES,  # 不参与 DAG
            weight=0.8,
        ),
    ]


@pytest.fixture
def skill_edges_with_cycle() -> list[SkillEdge]:
    """有环路的 SkillEdge 列表。"""
    return [
        SkillEdge(
            source_uid="skill:a",
            target_uid="skill:b",
            edge_type=EdgeType.REQUIRES,
            weight=1.0,
        ),
        SkillEdge(
            source_uid="skill:b",
            target_uid="skill:c",
            edge_type=EdgeType.REQUIRES,
            weight=1.0,
        ),
        SkillEdge(
            source_uid="skill:c",
            target_uid="skill:a",
            edge_type=EdgeType.REQUIRES,  # 环路
            weight=1.0,
        ),
    ]


@pytest.fixture
def empty_edges() -> list[tuple[str, str]]:
    """空边列表。"""
    return []


@pytest.fixture
def single_edge() -> list[tuple[str, str]]:
    """单条边。"""
    return [("skill:a", "skill:b")]


# ============================================================================
# DAGValidationError Tests
# ============================================================================

class TestDAGValidationError:
    """DAGValidationError 数据结构测试。"""
    
    def test_create_error(self) -> None:
        """测试创建错误。"""
        error = DAGValidationError(
            error_type="cycle_detected",
            message="Circular dependency detected",
            affected_nodes=["skill:a", "skill:b"],
            affected_edges=[("skill:a", "skill:b")],
            suggestion="Remove edge",
        )
        
        assert error.error_type == "cycle_detected"
        assert error.message == "Circular dependency detected"
        assert error.affected_nodes == ["skill:a", "skill:b"]
        assert error.affected_edges == [("skill:a", "skill:b")]
        assert error.suggestion == "Remove edge"
    
    def test_error_defaults(self) -> None:
        """测试默认值。"""
        error = DAGValidationError(
            error_type="test_error",
            message="Test",
        )
        
        assert error.affected_nodes == []
        assert error.affected_edges == []
        assert error.suggestion is None
    
    def test_error_to_dict(self) -> None:
        """测试 to_dict 方法。"""
        error = DAGValidationError(
            error_type="self_reference",
            message="Self-referencing edge",
            affected_nodes=["skill:a"],
            affected_edges=[("skill:a", "skill:a")],
            suggestion="Remove self-reference",
        )
        
        result = error.to_dict()
        
        assert result["error_type"] == "self_reference"
        assert result["message"] == "Self-referencing edge"
        assert result["affected_nodes"] == ["skill:a"]
        assert result["affected_edges"] == [("skill:a", "skill:a")]
        assert result["suggestion"] == "Remove self-reference"


# ============================================================================
# DAGValidationResult Tests
# ============================================================================

class TestDAGValidationResult:
    """DAGValidationResult 数据结构测试。"""
    
    def test_create_valid_result(self) -> None:
        """测试创建有效结果。"""
        result = DAGValidationResult(
            is_valid=True,
            node_count=4,
            edge_count=3,
            max_depth=2,
        )
        
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.node_count == 4
        assert result.edge_count == 3
        assert result.max_depth == 2
    
    def test_create_invalid_result(self) -> None:
        """测试创建无效结果。"""
        errors = [
            DAGValidationError("cycle", "Cycle detected"),
        ]
        
        result = DAGValidationResult(
            is_valid=False,
            errors=errors,
        )
        
        assert result.is_valid is False
        assert len(result.errors) == 1
    
    def test_result_defaults(self) -> None:
        """测试默认值。"""
        result = DAGValidationResult(is_valid=True)
        
        assert result.errors == []
        assert result.warnings == []
        assert result.cycle_result is None
        assert result.node_count == 0
        assert result.edge_count == 0
        assert result.max_depth == 0
    
    def test_error_count_property(self) -> None:
        """测试 error_count 属性。"""
        result_no_errors = DAGValidationResult(is_valid=True)
        assert result_no_errors.error_count == 0
        
        errors = [
            DAGValidationError("e1", "Error 1"),
            DAGValidationError("e2", "Error 2"),
        ]
        result_with_errors = DAGValidationResult(is_valid=False, errors=errors)
        assert result_with_errors.error_count == 2
    
    def test_has_cycles_property(self) -> None:
        """测试 has_cycles 属性。"""
        result_no_cycle = DAGValidationResult(is_valid=True)
        assert result_no_cycle.has_cycles is False
        
        cycle_result = CycleDetectionResult(
            has_cycle=True,
            cycles=[CycleInfo(nodes=["a", "b"])],
        )
        result_with_cycle = DAGValidationResult(
            is_valid=False,
            cycle_result=cycle_result,
        )
        assert result_with_cycle.has_cycles is True
    
    def test_has_cycles_none_cycle_result(self) -> None:
        """测试 cycle_result 为 None 时 has_cycles。"""
        result = DAGValidationResult(is_valid=True, cycle_result=None)
        assert result.has_cycles is False
    
    def test_result_to_dict(self) -> None:
        """测试 to_dict 方法。"""
        errors = [
            DAGValidationError("cycle", "Cycle", ["a"], [("a", "b")]),
        ]
        warnings = ["Isolated node detected"]
        cycle_result = CycleDetectionResult(has_cycle=True)
        
        result = DAGValidationResult(
            is_valid=False,
            errors=errors,
            warnings=warnings,
            cycle_result=cycle_result,
            node_count=5,
            edge_count=4,
            max_depth=3,
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["is_valid"] is False
        assert result_dict["error_count"] == 1
        assert result_dict["has_cycles"] is True
        assert result_dict["node_count"] == 5
        assert result_dict["edge_count"] == 4
        assert result_dict["max_depth"] == 3
        assert len(result_dict["errors"]) == 1
        assert result_dict["warnings"] == ["Isolated node detected"]
        assert result_dict["cycle_result"] is not None


# ============================================================================
# DAGValidationErrorException Tests
# ============================================================================

class TestDAGValidationErrorException:
    """DAGValidationErrorException 异常测试。"""
    
    def test_exception_properties(self) -> None:
        """测试异常属性。"""
        errors = [
            DAGValidationError("cycle", "Cycle detected"),
        ]
        
        exception = DAGValidationErrorException(
            message="DAG validation failed",
            errors=errors,
        )
        
        assert str(exception) == "DAG validation failed"
        assert exception.code == "GS-3000"  # IngestionError 的默认 code
        assert len(exception.errors) == 1
    
    def test_exception_defaults(self) -> None:
        """测试默认值。"""
        exception = DAGValidationErrorException(message="Test error")
        
        assert exception.errors == []
        assert exception.cycle_result is None
    
    def test_exception_to_dict(self) -> None:
        """测试 to_dict 方法。"""
        errors = [
            DAGValidationError("e1", "Error 1"),
        ]
        cycle_result = CycleDetectionResult(
            has_cycle=True,
            cycles=[CycleInfo(nodes=["a", "b"])],
        )
        
        exception = DAGValidationErrorException(
            message="Validation failed",
            errors=errors,
            cycle_result=cycle_result,
        )
        
        result = exception.to_dict()
        
        assert result["error"]["message"] == "Validation failed"
        assert result["error"]["code"] == "GS-3000"  # IngestionError 的默认 code
        assert len(result["errors"]) == 1
        assert result["cycle_result"] is not None
    
    def test_exception_inheritance(self) -> None:
        """测试继承关系。"""
        from graphskill.core.exceptions import IngestionError
        
        exception = DAGValidationErrorException(message="Test")
        assert isinstance(exception, IngestionError)


# ============================================================================
# DAGValidator Initialization Tests
# ============================================================================

class TestDAGValidatorInit:
    """DAGValidator 初始化测试。"""
    
    def test_init_default(self) -> None:
        """测试默认初始化。"""
        validator = DAGValidator()
        
        assert validator.strict_mode is True
        assert validator.cycle_detector is not None
    
    def test_init_non_strict(self) -> None:
        """测试非严格模式初始化。"""
        validator = DAGValidator(strict_mode=False)
        
        assert validator.strict_mode is False
    
    def test_init_strict(self) -> None:
        """测试严格模式初始化。"""
        validator = DAGValidator(strict_mode=True)
        
        assert validator.strict_mode is True


# ============================================================================
# DAGValidator Validate Tests
# ============================================================================

class TestDAGValidatorValidate:
    """DAGValidator validate 方法测试。"""
    
    def test_validate_empty_edges(
        self,
        validator: DAGValidator,
        empty_edges: list,
    ) -> None:
        """测试空边列表。"""
        result = validator.validate(empty_edges)
        
        assert result.is_valid is True
        assert result.error_count == 0
        assert result.node_count == 0
        assert result.edge_count == 0
    
    def test_validate_single_edge(
        self,
        validator: DAGValidator,
        single_edge: list,
    ) -> None:
        """测试单条边。"""
        result = validator.validate(single_edge)
        
        assert result.is_valid is True
        assert result.error_count == 0
        assert result.node_count == 2
        assert result.edge_count == 1
    
    def test_validate_valid_dag(
        self,
        validator: DAGValidator,
        valid_edges: list,
    ) -> None:
        """测试有效 DAG。"""
        result = validator.validate(valid_edges)
        
        assert result.is_valid is True
        assert result.has_cycles is False
        assert result.error_count == 0
        assert result.node_count == 4
        assert result.edge_count == 4
    
    def test_validate_cycle(
        self,
        validator: DAGValidator,
        cycle_edges: list,
    ) -> None:
        """测试有环路的图。"""
        result = validator.validate(cycle_edges)
        
        assert result.is_valid is False
        assert result.has_cycles is True
        assert result.error_count >= 1
        
        # 检查错误类型
        error = result.errors[0]
        assert error.error_type == "cycle_detected"
    
    def test_validate_self_reference(
        self,
        validator: DAGValidator,
        self_ref_edges: list,
    ) -> None:
        """测试自引用。"""
        result = validator.validate(self_ref_edges)
        
        # 自引用边 b -> b 在 Tarjan 算法中 SCC 大小为 1，不被视为环路
        # 但代码会检查自引用并添加错误
        assert result.is_valid is False
        
        # 检查自引用错误
        self_ref_errors = [
            e for e in result.errors if e.error_type == "self_reference"
        ]
        # 自引用错误应该被检测到
        assert len(self_ref_errors) >= 1
    
    def test_validate_mixed_errors(
        self,
        validator: DAGValidator,
        mixed_edges: list,
    ) -> None:
        """测试混合错误。"""
        result = validator.validate(mixed_edges)
        
        assert result.is_valid is False
        assert result.error_count >= 2  # 环路 + 自引用
    
    def test_validate_isolated_nodes_warning(
        self,
        validator: DAGValidator,
        isolated_node_edges: list,
    ) -> None:
        """测试孤立节点警告。"""
        # 添加孤立节点
        nodes = ["skill:a", "skill:b", "skill:c", "skill:isolated"]
        
        result = validator.validate(isolated_node_edges, nodes)
        
        assert result.is_valid is True
        assert len(result.warnings) >= 1
        assert "isolated" in result.warnings[0].lower()
    
    def test_validate_with_explicit_nodes(
        self,
        validator: DAGValidator,
    ) -> None:
        """测试显式指定节点。"""
        edges = [("skill:a", "skill:b")]
        nodes = ["skill:a", "skill:b", "skill:c", "skill:d"]
        
        result = validator.validate(edges, nodes)
        
        assert result.node_count == 4  # 包含显式节点
    
    def test_validate_max_depth(
        self,
        validator: DAGValidator,
        valid_edges: list,
    ) -> None:
        """测试最大深度计算。"""
        result = validator.validate(valid_edges)
        
        # a -> b -> c -> d 深度为 3
        # a -> d 跨层依赖
        assert result.max_depth >= 1
    
    def test_validate_strict_mode_raises(
        self,
        strict_validator: DAGValidator,
        cycle_edges: list,
    ) -> None:
        """测试严格模式抛出异常。"""
        with pytest.raises(DAGValidationErrorException) as exc_info:
            strict_validator.validate(cycle_edges)
        
        assert "DAG validation failed" in str(exc_info.value)
    
    def test_validate_strict_mode_no_error(
        self,
        strict_validator: DAGValidator,
        valid_edges: list,
    ) -> None:
        """测试严格模式无错误时不抛异常。"""
        result = strict_validator.validate(valid_edges)
        
        assert result.is_valid is True


# ============================================================================
# DAGValidator SkillEdge Tests
# ============================================================================

class TestDAGValidatorSkillEdges:
    """SkillEdge 验证测试。"""
    
    def test_validate_skill_edges_valid(
        self,
        validator: DAGValidator,
        skill_edges: list,
    ) -> None:
        """测试有效 SkillEdge 列表。"""
        result = validator.validate_skill_edges(skill_edges)
        
        assert result.is_valid is True
        assert result.has_cycles is False
    
    def test_validate_skill_edges_with_cycle(
        self,
        validator: DAGValidator,
        skill_edges_with_cycle: list,
    ) -> None:
        """测试有环路的 SkillEdge 列表。"""
        result = validator.validate_skill_edges(skill_edges_with_cycle)
        
        assert result.is_valid is False
        assert result.has_cycles is True
    
    def test_validate_skill_edges_filters_non_requires(
        self,
        validator: DAGValidator,
        skill_edges: list,
    ) -> None:
        """测试只验证 REQUIRES 边。"""
        result = validator.validate_skill_edges(skill_edges)
        
        # ENHANCES 边不参与 DAG 验证
        assert result.edge_count == 2  # 只有 2 条 REQUIRES 边


# ============================================================================
# DAGValidator Incremental Tests
# ============================================================================

class TestDAGValidatorIncremental:
    """增量验证测试。"""
    
    def test_validate_incremental_no_cycle(
        self,
        validator: DAGValidator,
    ) -> None:
        """测试增量验证无环路。"""
        existing_edges = [("skill:a", "skill:b")]
        new_edges = [("skill:b", "skill:c")]
        
        result = validator.validate_incremental(existing_edges, new_edges)
        
        assert result.is_valid is True
    
    def test_validate_incremental_introduces_cycle(
        self,
        validator: DAGValidator,
    ) -> None:
        """测试增量验证引入环路。"""
        existing_edges = [("skill:a", "skill:b"), ("skill:b", "skill:c")]
        new_edges = [("skill:c", "skill:a")]  # 引入环路
        
        result = validator.validate_incremental(existing_edges, new_edges)
        
        assert result.is_valid is False
        assert result.has_cycles is True
        
        # 检查错误类型
        error = result.errors[0]
        assert error.error_type == "new_cycle_introduced"
    
    def test_validate_incremental_no_new_cycle(
        self,
        validator: DAGValidator,
    ) -> None:
        """测试增量验证不引入新环路。"""
        # 已有环路
        existing_edges = [("skill:a", "skill:b"), ("skill:b", "skill:a")]
        # 新边不涉及环路节点
        new_edges = [("skill:c", "skill:d")]
        
        result = validator.validate_incremental(existing_edges, new_edges)
        
        # 新边不引入新环路
        assert result.is_valid is True


# ============================================================================
# DAGValidator Report Tests
# ============================================================================

class TestDAGValidatorReport:
    """验证报告测试。"""
    
    def test_get_validation_report_valid(
        self,
        validator: DAGValidator,
        valid_edges: list,
    ) -> None:
        """测试有效结果的报告。"""
        result = validator.validate(valid_edges)
        report = validator.get_validation_report(result)
        
        assert "DAG Validation Report" in report
        assert "VALID" in report
        assert "Nodes:" in report
        assert "Edges:" in report
    
    def test_get_validation_report_invalid(
        self,
        validator: DAGValidator,
        cycle_edges: list,
    ) -> None:
        """测试无效结果的报告。"""
        result = validator.validate(cycle_edges)
        report = validator.get_validation_report(result)
        
        assert "INVALID" in report
        assert "Errors" in report
    
    def test_report_includes_errors(
        self,
        validator: DAGValidator,
        cycle_edges: list,
    ) -> None:
        """测试报告包含错误详情。"""
        result = validator.validate(cycle_edges)
        report = validator.get_validation_report(result)
        
        assert "cycle_detected" in report
        assert "Suggestion" in report
    
    def test_report_includes_warnings(
        self,
        validator: DAGValidator,
    ) -> None:
        """测试报告包含警告。"""
        edges = [("skill:a", "skill:b")]
        nodes = ["skill:a", "skill:b", "skill:isolated"]
        
        result = validator.validate(edges, nodes)
        report = validator.get_validation_report(result)
        
        # 如果有孤立节点警告
        if result.warnings:
            assert "isolated" in report.lower() or "warning" in report.lower()


# ============================================================================
# DAGValidator Helper Methods Tests
# ============================================================================

class TestDAGValidatorHelpers:
    """辅助方法测试。"""
    
    def test_find_isolated_nodes(
        self,
        validator: DAGValidator,
    ) -> None:
        """测试查找孤立节点。"""
        edges = [("skill:a", "skill:b")]
        all_nodes = {"skill:a", "skill:b", "skill:c", "skill:d"}
        
        isolated = validator._find_isolated_nodes(edges, all_nodes)
        
        assert len(isolated) == 2
        assert "skill:c" in isolated
        assert "skill:d" in isolated
    
    def test_find_isolated_nodes_none(
        self,
        validator: DAGValidator,
    ) -> None:
        """测试无孤立节点。"""
        edges = [("skill:a", "skill:b"), ("skill:b", "skill:c")]
        all_nodes = {"skill:a", "skill:b", "skill:c"}
        
        isolated = validator._find_isolated_nodes(edges, all_nodes)
        
        assert len(isolated) == 0
    
    def test_calculate_max_depth_simple(
        self,
        validator: DAGValidator,
    ) -> None:
        """测试简单图深度计算。"""
        edges = [("skill:a", "skill:b"), ("skill:b", "skill:c")]
        all_nodes = {"skill:a", "skill:b", "skill:c"}
        
        depth = validator._calculate_max_depth(edges, all_nodes)
        
        # a -> b -> c 深度为 2
        assert depth == 2
    
    def test_calculate_max_depth_branching(
        self,
        validator: DAGValidator,
    ) -> None:
        """测试分支图深度计算。"""
        edges = [
            ("skill:a", "skill:b"),
            ("skill:a", "skill:c"),
            ("skill:b", "skill:d"),
            ("skill:c", "skill:d"),
        ]
        all_nodes = {"skill:a", "skill:b", "skill:c", "skill:d"}
        
        depth = validator._calculate_max_depth(edges, all_nodes)
        
        # a -> b/c -> d 深度为 2
        assert depth == 2
    
    def test_calculate_max_depth_empty(
        self,
        validator: DAGValidator,
    ) -> None:
        """测试空图深度。"""
        edges: list[tuple[str, str]] = []
        all_nodes: set[str] = set()
        
        depth = validator._calculate_max_depth(edges, all_nodes)
        
        assert depth == 0


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """边界条件测试。"""
    
    def test_validate_disconnected_graph(
        self,
        validator: DAGValidator,
    ) -> None:
        """测试不连通图。"""
        edges = [
            ("skill:a", "skill:b"),
            ("skill:c", "skill:d"),  # 不连通
        ]
        
        result = validator.validate(edges)
        
        assert result.is_valid is True
    
    def test_validate_complex_dag(
        self,
        validator: DAGValidator,
    ) -> None:
        """测试复杂 DAG。"""
        edges = [
            ("skill:a", "skill:b"),
            ("skill:a", "skill:c"),
            ("skill:b", "skill:d"),
            ("skill:b", "skill:e"),
            ("skill:c", "skill:f"),
            ("skill:d", "skill:g"),
            ("skill:e", "skill:g"),
            ("skill:f", "skill:g"),
        ]
        
        result = validator.validate(edges)
        
        assert result.is_valid is True
        assert result.node_count == 7
        assert result.edge_count == 8
    
    def test_validate_large_cycle(
        self,
        validator: DAGValidator,
    ) -> None:
        """测试大型环路。"""
        # 创建 10 个节点的环路
        edges = [(f"skill:n{i}", f"skill:n{i+1}") for i in range(9)]
        edges.append(("skill:n9", "skill:n0"))
        
        result = validator.validate(edges)
        
        assert result.is_valid is False
        assert result.has_cycles is True
        # 使用 cycle_result.affected_node_count
        assert result.cycle_result is not None
        assert result.cycle_result.affected_node_count >= 10
    
    def test_validate_parallel_edges(
        self,
        validator: DAGValidator,
    ) -> None:
        """测试平行边。"""
        edges = [
            ("skill:a", "skill:b"),
            ("skill:a", "skill:b"),  # 平行边
        ]
        
        result = validator.validate(edges)
        
        # 平行边不形成环路
        assert result.is_valid is True
    
    def test_validate_bidirectional_edges(
        self,
        validator: DAGValidator,
    ) -> None:
        """测试双向边。"""
        edges = [
            ("skill:a", "skill:b"),
            ("skill:b", "skill:a"),  # 双向，形成环路
        ]
        
        result = validator.validate(edges)
        
        assert result.is_valid is False
        assert result.has_cycles is True


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """集成测试。"""
    
    def test_full_validation_workflow(
        self,
        validator: DAGValidator,
    ) -> None:
        """测试完整验证工作流。"""
        # 1. 验证初始边
        edges = [("skill:a", "skill:b"), ("skill:b", "skill:c")]
        result = validator.validate(edges)
        assert result.is_valid is True
        
        # 2. 增量添加边
        new_edges = [("skill:c", "skill:d")]
        result = validator.validate_incremental(edges, new_edges)
        assert result.is_valid is True
        
        # 3. 添加形成环路的边
        cycle_edges = [("skill:d", "skill:a")]
        result = validator.validate_incremental(edges + new_edges, cycle_edges)
        assert result.is_valid is False
        
        # 4. 生成报告
        report = validator.get_validation_report(result)
        assert "INVALID" in report
    
    def test_skill_edge_workflow(
        self,
        validator: DAGValidator,
        skill_edges: list[SkillEdge],
    ) -> None:
        """测试 SkillEdge 工作流。"""
        result = validator.validate_skill_edges(skill_edges)
        
        assert result.is_valid is True
        # 只验证 REQUIRES 边
        assert result.edge_count == 2
    
    def test_error_recovery_workflow(
        self,
        validator: DAGValidator,
    ) -> None:
        """测试错误恢复工作流。"""
        # 有环路的图
        cycle_edges = [
            ("skill:a", "skill:b"),
            ("skill:b", "skill:c"),
            ("skill:c", "skill:a"),
        ]
        
        result = validator.validate(cycle_edges)
        assert result.is_valid is False
        
        # 移除一条边打破环路
        fixed_edges = [
            ("skill:a", "skill:b"),
            ("skill:b", "skill:c"),
            # 移除 ("skill:c", "skill:a")
        ]
        
        result = validator.validate(fixed_edges)
        assert result.is_valid is True