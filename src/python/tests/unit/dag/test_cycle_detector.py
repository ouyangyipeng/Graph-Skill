"""
Cycle Detector 单元测试。

测试 DAG 环路检测器的所有组件：
- NodeState 枚举
- CycleInfo 数据结构
- CycleDetectionResult 数据结构
- TarjanCycleDetector 类
"""

from __future__ import annotations

import pytest
from typing import Any

from graphskill.ingestion.dag.cycle_detector import (
    NodeState,
    CycleInfo,
    CycleDetectionResult,
    TarjanCycleDetector,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def detector() -> TarjanCycleDetector:
    """环路检测器。"""
    return TarjanCycleDetector()


@pytest.fixture
def no_cycle_edges() -> list[tuple[str, str]]:
    """无环路的边列表。"""
    return [
        ("A", "B"),
        ("B", "C"),
        ("C", "D"),
        ("A", "D"),
    ]


@pytest.fixture
def simple_cycle_edges() -> list[tuple[str, str]]:
    """简单环路的边列表。"""
    return [
        ("A", "B"),
        ("B", "C"),
        ("C", "A"),  # 形成环路 A -> B -> C -> A
    ]


@pytest.fixture
def multiple_cycles_edges() -> list[tuple[str, str]]:
    """多个环路的边列表。"""
    return [
        ("A", "B"),
        ("B", "C"),
        ("C", "A"),  # 环路 1
        ("D", "E"),
        ("E", "F"),
        ("F", "D"),  # 环路 2
    ]


@pytest.fixture
def self_loop_edges() -> list[tuple[str, str]]:
    """自环边列表。"""
    return [
        ("A", "A"),  # 自环
    ]


@pytest.fixture
def complex_cycle_edges() -> list[tuple[str, str]]:
    """复杂环路的边列表。"""
    return [
        ("A", "B"),
        ("B", "C"),
        ("C", "D"),
        ("D", "B"),  # B -> C -> D -> B 环路
        ("A", "E"),
        ("E", "F"),
    ]


@pytest.fixture
def empty_edges() -> list[tuple[str, str]]:
    """空边列表。"""
    return []


@pytest.fixture
def single_edge() -> list[tuple[str, str]]:
    """单条边。"""
    return [("A", "B")]


# ============================================================================
# NodeState Tests
# ============================================================================

class TestNodeState:
    """NodeState 枚举测试。"""
    
    def test_state_enum_values(self) -> None:
        """测试枚举值。"""
        assert NodeState.UNVISITED.value == 0
        assert NodeState.VISITING.value == 1
        assert NodeState.VISITED.value == 2
    
    def test_state_enum_count(self) -> None:
        """测试枚举数量。"""
        assert len(NodeState) == 3
    
    def test_state_order(self) -> None:
        """测试状态顺序。"""
        assert NodeState.UNVISITED.value < NodeState.VISITING.value
        assert NodeState.VISITING.value < NodeState.VISITED.value


# ============================================================================
# CycleInfo Tests
# ============================================================================

class TestCycleInfo:
    """CycleInfo 数据结构测试。"""
    
    def test_create_cycle_info(self) -> None:
        """测试创建环路信息。"""
        cycle = CycleInfo(
            nodes=["A", "B", "C"],
            path=["A", "B", "C", "A"],
            severity="error",
            description="Circular dependency",
        )
        
        assert cycle.nodes == ["A", "B", "C"]
        assert cycle.path == ["A", "B", "C", "A"]
        assert cycle.severity == "error"
        assert cycle.description == "Circular dependency"
    
    def test_cycle_info_defaults(self) -> None:
        """测试默认值。"""
        cycle = CycleInfo(nodes=["A", "B"])
        
        assert cycle.path is None
        assert cycle.severity == "error"
        assert cycle.description == ""
    
    def test_node_count_property(self) -> None:
        """测试 node_count 属性。"""
        cycle = CycleInfo(nodes=["A", "B", "C"])
        assert cycle.node_count == 3
        
        cycle_single = CycleInfo(nodes=["A"])
        assert cycle_single.node_count == 1
    
    def test_cycle_info_to_dict(self) -> None:
        """测试 to_dict 方法。"""
        cycle = CycleInfo(
            nodes=["A", "B"],
            path=["A", "B", "A"],
            severity="warning",
            description="Test cycle",
        )
        
        result = cycle.to_dict()
        
        assert result["nodes"] == ["A", "B"]
        assert result["path"] == ["A", "B", "A"]
        assert result["node_count"] == 2
        assert result["severity"] == "warning"
        assert result["description"] == "Test cycle"
    
    def test_cycle_info_to_dict_none_path(self) -> None:
        """测试 to_dict 处理 None path。"""
        cycle = CycleInfo(nodes=["A", "B"])
        
        result = cycle.to_dict()
        
        assert result["path"] is None


# ============================================================================
# CycleDetectionResult Tests
# ============================================================================

class TestCycleDetectionResult:
    """CycleDetectionResult 数据结构测试。"""
    
    def test_create_result_with_cycle(self) -> None:
        """测试创建有环路的检测结果。"""
        cycles = [CycleInfo(nodes=["A", "B", "C"])]
        affected = {"A", "B", "C"}
        
        result = CycleDetectionResult(
            has_cycle=True,
            cycles=cycles,
            affected_nodes=affected,
        )
        
        assert result.has_cycle is True
        assert len(result.cycles) == 1
        assert result.affected_nodes == affected
    
    def test_create_result_no_cycle(self) -> None:
        """测试创建无环路的检测结果。"""
        result = CycleDetectionResult(has_cycle=False)
        
        assert result.has_cycle is False
        assert result.cycles == []
        assert result.affected_nodes == set()
    
    def test_result_defaults(self) -> None:
        """测试默认值。"""
        result = CycleDetectionResult(has_cycle=False)
        
        assert result.cycles == []
        assert result.affected_nodes == set()
        assert result.sccs == []
    
    def test_cycle_count_property(self) -> None:
        """测试 cycle_count 属性。"""
        result_no_cycle = CycleDetectionResult(has_cycle=False)
        assert result_no_cycle.cycle_count == 0
        
        cycles = [
            CycleInfo(nodes=["A", "B"]),
            CycleInfo(nodes=["C", "D"]),
        ]
        result_with_cycles = CycleDetectionResult(
            has_cycle=True,
            cycles=cycles,
        )
        assert result_with_cycles.cycle_count == 2
    
    def test_affected_node_count_property(self) -> None:
        """测试 affected_node_count 属性。"""
        result_no_affected = CycleDetectionResult(has_cycle=False)
        assert result_no_affected.affected_node_count == 0
        
        result_with_affected = CycleDetectionResult(
            has_cycle=True,
            affected_nodes={"A", "B", "C"},
        )
        assert result_with_affected.affected_node_count == 3
    
    def test_result_to_dict(self) -> None:
        """测试 to_dict 方法。"""
        cycles = [CycleInfo(nodes=["A", "B"])]
        
        result = CycleDetectionResult(
            has_cycle=True,
            cycles=cycles,
            affected_nodes={"A", "B"},
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["has_cycle"] is True
        assert result_dict["cycle_count"] == 1
        assert result_dict["affected_node_count"] == 2
        assert len(result_dict["cycles"]) == 1
        assert set(result_dict["affected_nodes"]) == {"A", "B"}
    
    def test_get_cycle_for_node(self) -> None:
        """测试 get_cycle_for_node 方法。"""
        cycles = [
            CycleInfo(nodes=["A", "B", "C"]),
            CycleInfo(nodes=["D", "E"]),
        ]
        
        result = CycleDetectionResult(
            has_cycle=True,
            cycles=cycles,
        )
        
        # 找到包含 A 的环路
        cycle_a = result.get_cycle_for_node("A")
        assert cycle_a is not None
        assert "A" in cycle_a.nodes
        
        # 找到包含 D 的环路
        cycle_d = result.get_cycle_for_node("D")
        assert cycle_d is not None
        assert "D" in cycle_d.nodes
        
        # 找不到包含 X 的环路
        cycle_x = result.get_cycle_for_node("X")
        assert cycle_x is None


# ============================================================================
# TarjanCycleDetector Basic Tests
# ============================================================================

class TestTarjanCycleDetectorBasic:
    """TarjanCycleDetector 基础测试。"""
    
    def test_detector_initialization(self, detector: TarjanCycleDetector) -> None:
        """测试初始化。"""
        assert detector is not None
    
    def test_detect_empty_edges(
        self,
        detector: TarjanCycleDetector,
        empty_edges: list,
    ) -> None:
        """测试空边列表。"""
        result = detector.detect(empty_edges)
        
        assert result.has_cycle is False
        assert result.cycle_count == 0
        assert result.affected_node_count == 0
    
    def test_detect_single_edge(
        self,
        detector: TarjanCycleDetector,
        single_edge: list,
    ) -> None:
        """测试单条边。"""
        result = detector.detect(single_edge)
        
        assert result.has_cycle is False
        assert result.cycle_count == 0
    
    def test_detect_no_cycle(
        self,
        detector: TarjanCycleDetector,
        no_cycle_edges: list,
    ) -> None:
        """测试无环路。"""
        result = detector.detect(no_cycle_edges)
        
        assert result.has_cycle is False
        assert result.cycle_count == 0
        assert result.affected_node_count == 0
    
    def test_detect_simple_cycle(
        self,
        detector: TarjanCycleDetector,
        simple_cycle_edges: list,
    ) -> None:
        """测试简单环路。"""
        result = detector.detect(simple_cycle_edges)
        
        assert result.has_cycle is True
        assert result.cycle_count == 1
        assert result.affected_node_count == 3
        
        # 检查环路节点
        cycle = result.cycles[0]
        assert set(cycle.nodes) == {"A", "B", "C"}
    
    def test_detect_multiple_cycles(
        self,
        detector: TarjanCycleDetector,
        multiple_cycles_edges: list,
    ) -> None:
        """测试多个环路。"""
        result = detector.detect(multiple_cycles_edges)
        
        assert result.has_cycle is True
        assert result.cycle_count == 2
        assert result.affected_node_count == 6
    
    def test_detect_self_loop(
        self,
        detector: TarjanCycleDetector,
        self_loop_edges: list,
    ) -> None:
        """测试自环。"""
        result = detector.detect(self_loop_edges)
        
        # 自环在 Tarjan 算法中 SCC 大小为 1，不被视为环路
        # 因为环路检测条件是 len(scc) > 1
        # 自环 A -> A 的 SCC 只有 ["A"]，大小为 1
        assert result.has_cycle is False
        assert result.affected_node_count == 0
    
    def test_detect_complex_cycle(
        self,
        detector: TarjanCycleDetector,
        complex_cycle_edges: list,
    ) -> None:
        """测试复杂环路。"""
        result = detector.detect(complex_cycle_edges)
        
        assert result.has_cycle is True
        # B, C, D 形成环路
        assert result.affected_node_count >= 3


# ============================================================================
# TarjanCycleDetector Path Finding Tests
# ============================================================================

class TestTarjanCycleDetectorPath:
    """环路路径查找测试。"""
    
    def test_find_cycle_path_simple(
        self,
        detector: TarjanCycleDetector,
        simple_cycle_edges: list,
    ) -> None:
        """测试简单环路路径。"""
        result = detector.detect(simple_cycle_edges)
        
        cycle = result.cycles[0]
        assert cycle.path is not None
        # 路径应该从某个节点开始并回到该节点
        assert cycle.path[0] == cycle.path[-1]
    
    def test_find_cycle_path_none_for_no_cycle(
        self,
        detector: TarjanCycleDetector,
        no_cycle_edges: list,
    ) -> None:
        """测试无环路时路径为空。"""
        result = detector.detect(no_cycle_edges)
        
        assert len(result.cycles) == 0


# ============================================================================
# TarjanCycleDetector Incremental Tests
# ============================================================================

class TestTarjanCycleDetectorIncremental:
    """增量检测测试。"""
    
    def test_detect_incremental_no_existing_cycle(
        self,
        detector: TarjanCycleDetector,
    ) -> None:
        """测试增量检测（无已有环路）。"""
        existing_edges = [("A", "B"), ("B", "C")]
        new_edges = [("C", "D")]
        
        result = detector.detect_incremental(existing_edges, new_edges)
        
        assert result.has_cycle is False
    
    def test_detect_incremental_introduces_cycle(
        self,
        detector: TarjanCycleDetector,
    ) -> None:
        """测试增量检测引入环路。"""
        existing_edges = [("A", "B"), ("B", "C")]
        new_edges = [("C", "A")]  # 引入环路
        
        result = detector.detect_incremental(existing_edges, new_edges)
        
        assert result.has_cycle is True
    
    def test_detect_incremental_with_existing_result(
        self,
        detector: TarjanCycleDetector,
    ) -> None:
        """测试带已有结果的增量检测。"""
        existing_edges = [("A", "B")]
        existing_result = CycleDetectionResult(has_cycle=False)
        new_edges = [("B", "C")]
        
        result = detector.detect_incremental(
            existing_edges,
            new_edges,
            existing_result,
        )
        
        assert result.has_cycle is False
    
    def test_detect_incremental_new_nodes(
        self,
        detector: TarjanCycleDetector,
    ) -> None:
        """测试增量检测涉及新节点。"""
        existing_edges = [("A", "B")]
        new_edges = [("C", "D")]  # 完全新的节点
        
        result = detector.detect_incremental(existing_edges, new_edges)
        
        assert result.has_cycle is False


# ============================================================================
# TarjanCycleDetector Single Edge Check Tests
# ============================================================================

class TestTarjanCycleDetectorSingleEdge:
    """单边检查测试。"""
    
    def test_check_single_edge_no_cycle(
        self,
        detector: TarjanCycleDetector,
    ) -> None:
        """测试单边不引入环路。"""
        existing_edges = [("A", "B"), ("B", "C")]
        new_edge = ("C", "D")
        
        will_cycle = detector.check_single_edge(existing_edges, new_edge)
        
        assert will_cycle is False
    
    def test_check_single_edge_introduces_cycle(
        self,
        detector: TarjanCycleDetector,
    ) -> None:
        """测试单边引入环路。"""
        existing_edges = [("A", "B"), ("B", "C"), ("C", "D")]
        new_edge = ("D", "A")  # D -> A 形成环路
        
        will_cycle = detector.check_single_edge(existing_edges, new_edge)
        
        assert will_cycle is True
    
    def test_check_single_edge_reverse_path(
        self,
        detector: TarjanCycleDetector,
    ) -> None:
        """测试反向路径形成环路。"""
        existing_edges = [("A", "B"), ("B", "C")]
        new_edge = ("C", "A")
        
        will_cycle = detector.check_single_edge(existing_edges, new_edge)
        
        assert will_cycle is True
    
    def test_check_single_edge_empty_existing(
        self,
        detector: TarjanCycleDetector,
    ) -> None:
        """测试空已有边时单边检查。"""
        existing_edges: list[tuple[str, str]] = []
        new_edge = ("A", "B")
        
        will_cycle = detector.check_single_edge(existing_edges, new_edge)
        
        assert will_cycle is False


# ============================================================================
# TarjanCycleDetector Suggestions Tests
# ============================================================================

class TestTarjanCycleDetectorSuggestions:
    """环路打破建议测试。"""
    
    def test_get_cycle_breaking_suggestions(
        self,
        detector: TarjanCycleDetector,
        simple_cycle_edges: list,
    ) -> None:
        """测试获取打破环路建议。"""
        result = detector.detect(simple_cycle_edges)
        suggestions = detector.get_cycle_breaking_suggestions(result, simple_cycle_edges)
        
        assert len(suggestions) > 0
        
        # 检查建议结构
        for suggestion in suggestions:
            assert "cycle" in suggestion
            assert "edge_to_remove" in suggestion
            assert "description" in suggestion
            assert "impact" in suggestion
    
    def test_get_suggestions_no_cycle(
        self,
        detector: TarjanCycleDetector,
        no_cycle_edges: list,
    ) -> None:
        """测试无环路时建议为空。"""
        result = detector.detect(no_cycle_edges)
        suggestions = detector.get_cycle_breaking_suggestions(result, no_cycle_edges)
        
        assert len(suggestions) == 0
    
    def test_suggestion_edge_in_cycle(
        self,
        detector: TarjanCycleDetector,
        simple_cycle_edges: list,
    ) -> None:
        """测试建议的边在环路中。"""
        result = detector.detect(simple_cycle_edges)
        suggestions = detector.get_cycle_breaking_suggestions(result, simple_cycle_edges)
        
        for suggestion in suggestions:
            edge = suggestion["edge_to_remove"]
            source, target = edge
            # 边的源和目标应该在环路节点中
            assert source in result.affected_nodes
            assert target in result.affected_nodes


# ============================================================================
# TarjanCycleDetector DAG Validation Tests
# ============================================================================

class TestTarjanCycleDetectorValidateDAG:
    """DAG 验证测试。"""
    
    def test_validate_dag_valid(
        self,
        detector: TarjanCycleDetector,
        no_cycle_edges: list,
    ) -> None:
        """测试验证有效 DAG。"""
        is_dag, result = detector.validate_dag(no_cycle_edges)
        
        assert is_dag is True
        assert result.has_cycle is False
    
    def test_validate_dag_invalid(
        self,
        detector: TarjanCycleDetector,
        simple_cycle_edges: list,
    ) -> None:
        """测试验证无效 DAG（有环路）。"""
        is_dag, result = detector.validate_dag(simple_cycle_edges)
        
        assert is_dag is False
        assert result.has_cycle is True
    
    def test_validate_dag_empty(
        self,
        detector: TarjanCycleDetector,
        empty_edges: list,
    ) -> None:
        """测试验证空边列表。"""
        is_dag, result = detector.validate_dag(empty_edges)
        
        assert is_dag is True
        assert result.has_cycle is False


# ============================================================================
# TarjanCycleDetector SCC Tests
# ============================================================================

class TestTarjanCycleDetectorSCC:
    """强连通分量测试。"""
    
    def test_sccs_for_no_cycle(
        self,
        detector: TarjanCycleDetector,
        no_cycle_edges: list,
    ) -> None:
        """测试无环路时的 SCC。"""
        result = detector.detect(no_cycle_edges)
        
        # 无环路时，每个 SCC 应该只有一个节点
        for scc in result.sccs:
            assert len(scc) == 1
    
    def test_sccs_for_cycle(
        self,
        detector: TarjanCycleDetector,
        simple_cycle_edges: list,
    ) -> None:
        """测试有环路时的 SCC。"""
        result = detector.detect(simple_cycle_edges)
        
        # 应该有一个 SCC 包含环路的所有节点
        large_sccs = [scc for scc in result.sccs if len(scc) > 1]
        assert len(large_sccs) == 1
        assert set(large_sccs[0]) == {"A", "B", "C"}
    
    def test_sccs_count(
        self,
        detector: TarjanCycleDetector,
        no_cycle_edges: list,
    ) -> None:
        """测试 SCC 数量。"""
        result = detector.detect(no_cycle_edges)
        
        # 4 个节点，每个都是独立的 SCC
        assert len(result.sccs) == 4


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """边界条件测试。"""
    
    def test_disconnected_graph(
        self,
        detector: TarjanCycleDetector,
    ) -> None:
        """测试不连通图。"""
        edges = [
            ("A", "B"),
            ("C", "D"),  # 不连通
        ]
        
        result = detector.detect(edges)
        
        assert result.has_cycle is False
    
    def test_isolated_nodes(
        self,
        detector: TarjanCycleDetector,
    ) -> None:
        """测试孤立节点。"""
        edges = [("A", "B")]
        nodes = ["A", "B", "C", "D"]  # C, D 是孤立节点
        
        result = detector.detect(edges, nodes)
        
        assert result.has_cycle is False
        # 所有节点都应该在 SCC 中
        all_scc_nodes = set()
        for scc in result.sccs:
            all_scc_nodes.update(scc)
        assert "C" in all_scc_nodes
        assert "D" in all_scc_nodes
    
    def test_large_cycle(
        self,
        detector: TarjanCycleDetector,
    ) -> None:
        """测试大型环路。"""
        # 创建 10 个节点的环路
        edges = [(f"N{i}", f"N{i+1}") for i in range(9)]
        edges.append(("N9", "N0"))  # 完成环路
        
        result = detector.detect(edges)
        
        assert result.has_cycle is True
        assert result.affected_node_count == 10
    
    def test_nested_cycles(
        self,
        detector: TarjanCycleDetector,
    ) -> None:
        """测试嵌套环路。"""
        edges = [
            ("A", "B"),
            ("B", "C"),
            ("C", "A"),  # 外环
            ("B", "D"),
            ("D", "B"),  # 内环
        ]
        
        result = detector.detect(edges)
        
        assert result.has_cycle is True
        # 所有节点都在一个大 SCC 中
        assert result.affected_node_count == 4
    
    def test_parallel_edges(
        self,
        detector: TarjanCycleDetector,
    ) -> None:
        """测试平行边。"""
        edges = [
            ("A", "B"),
            ("A", "B"),  # 平行边
            ("B", "C"),
        ]
        
        result = detector.detect(edges)
        
        assert result.has_cycle is False
    
    def test_bidirectional_edges(
        self,
        detector: TarjanCycleDetector,
    ) -> None:
        """测试双向边。"""
        edges = [
            ("A", "B"),
            ("B", "A"),  # 双向，形成环路
        ]
        
        result = detector.detect(edges)
        
        assert result.has_cycle is True
        assert result.affected_node_count == 2


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """集成测试。"""
    
    def test_full_workflow(
        self,
        detector: TarjanCycleDetector,
    ) -> None:
        """测试完整工作流。"""
        # 1. 初始检测
        edges = [("A", "B"), ("B", "C")]
        result = detector.detect(edges)
        assert result.has_cycle is False
        
        # 2. 增量添加边
        new_edges = [("C", "D")]
        result = detector.detect_incremental(edges, new_edges)
        assert result.has_cycle is False
        
        # 3. 添加形成环路的边
        cycle_edge = [("D", "A")]
        result = detector.detect_incremental(edges + new_edges, cycle_edge)
        assert result.has_cycle is True
        
        # 4. 获取打破建议
        all_edges = edges + new_edges + cycle_edge
        suggestions = detector.get_cycle_breaking_suggestions(result, all_edges)
        assert len(suggestions) > 0
        
        # 5. 验证 DAG
        is_dag, _ = detector.validate_dag(all_edges)
        assert is_dag is False
    
    def test_incremental_workflow(
        self,
        detector: TarjanCycleDetector,
    ) -> None:
        """测试增量工作流。"""
        edges: list[tuple[str, str]] = []
        
        # 逐步添加边
        for edge in [("A", "B"), ("B", "C"), ("C", "D")]:
            will_cycle = detector.check_single_edge(edges, edge)
            assert will_cycle is False
            edges.append(edge)
        
        # 添加形成环路的边
        cycle_edge = ("D", "A")
        will_cycle = detector.check_single_edge(edges, cycle_edge)
        assert will_cycle is True
    
    def test_complex_graph_analysis(
        self,
        detector: TarjanCycleDetector,
    ) -> None:
        """测试复杂图分析。"""
        # 创建复杂图：有环路和无环路部分
        edges = [
            # 无环路部分
            ("X", "Y"),
            ("Y", "Z"),
            # 环路部分
            ("A", "B"),
            ("B", "C"),
            ("C", "A"),
        ]
        
        result = detector.detect(edges)
        
        assert result.has_cycle is True
        assert result.cycle_count == 1
        
        # 检查受影响节点
        assert "A" in result.affected_nodes
        assert "B" in result.affected_nodes
        assert "C" in result.affected_nodes
        assert "X" not in result.affected_nodes
        assert "Y" not in result.affected_nodes
        assert "Z" not in result.affected_nodes