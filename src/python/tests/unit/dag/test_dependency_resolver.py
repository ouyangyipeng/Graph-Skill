"""
DependencyResolver 单元测试。

测试依赖解析器的所有功能。
"""

from __future__ import annotations

import pytest

from graphskill.ingestion.dag.dependency_resolver import (
    DependencyLevel,
    DependencyInfo,
    DependencyGraph,
    DependencyResolver,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def resolver() -> DependencyResolver:
    """创建解析器实例。"""
    return DependencyResolver()


@pytest.fixture
def simple_edges() -> list[tuple[str, str]]:
    """简单边列表（线性依赖）。"""
    return [
        ("skill:a", "skill:b"),  # a depends on b
        ("skill:b", "skill:c"),  # b depends on c
    ]


@pytest.fixture
def complex_edges() -> list[tuple[str, str]]:
    """复杂边列表（多层级依赖）。"""
    return [
        ("skill:a", "skill:b"),
        ("skill:a", "skill:c"),
        ("skill:b", "skill:d"),
        ("skill:c", "skill:d"),
        ("skill:d", "skill:e"),
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
def diamond_edges() -> list[tuple[str, str]]:
    """菱形依赖结构。"""
    return [
        ("skill:a", "skill:b"),
        ("skill:a", "skill:c"),
        ("skill:b", "skill:d"),
        ("skill:c", "skill:d"),
    ]


@pytest.fixture
def empty_edges() -> list[tuple[str, str]]:
    """空边列表。"""
    return []


@pytest.fixture
def single_edge() -> list[tuple[str, str]]:
    """单条边。"""
    return [("skill:a", "skill:b")]


@pytest.fixture
def isolated_nodes() -> list[str]:
    """孤立节点列表。"""
    return ["skill:isolated1", "skill:isolated2"]


# ============================================================================
# DependencyLevel Tests
# ============================================================================


class TestDependencyLevel:
    """DependencyLevel 枚举测试。"""
    
    def test_level_enum_values(self) -> None:
        """测试枚举值。"""
        assert DependencyLevel.ROOT.value == "root"
        assert DependencyLevel.LEVEL_1.value == "level_1"
        assert DependencyLevel.LEVEL_2.value == "level_2"
        assert DependencyLevel.LEVEL_3.value == "level_3"
        assert DependencyLevel.DEEP.value == "deep"
        assert DependencyLevel.UNKNOWN.value == "unknown"
    
    def test_level_enum_count(self) -> None:
        """测试枚举数量。"""
        assert len(DependencyLevel) == 6
    
    def test_level_is_string_enum(self) -> None:
        """测试是否为字符串枚举。"""
        assert isinstance(DependencyLevel.ROOT, str)
        assert DependencyLevel.ROOT == "root"


# ============================================================================
# DependencyInfo Tests
# ============================================================================


class TestDependencyInfo:
    """DependencyInfo 数据结构测试。"""
    
    def test_create_dependency_info(self) -> None:
        """测试创建依赖信息。"""
        info = DependencyInfo(
            node_uid="skill:a",
            level=DependencyLevel.LEVEL_1,
            depth=1,
            dependencies=["skill:b"],
            dependents=["skill:c"],
            transitive_dependencies=["skill:b", "skill:d"],
            is_leaf=False,
            is_root=False,
        )
        
        assert info.node_uid == "skill:a"
        assert info.level == DependencyLevel.LEVEL_1
        assert info.depth == 1
        assert info.dependencies == ["skill:b"]
        assert info.dependents == ["skill:c"]
        assert info.transitive_dependencies == ["skill:b", "skill:d"]
        assert info.is_leaf is False
        assert info.is_root is False
    
    def test_dependency_info_defaults(self) -> None:
        """测试默认值。"""
        info = DependencyInfo(
            node_uid="skill:a",
            level=DependencyLevel.ROOT,
            depth=0,
        )
        
        assert info.dependencies == []
        assert info.dependents == []
        assert info.transitive_dependencies == []
        assert info.is_leaf is False
        assert info.is_root is False
    
    def test_dependency_count_property(self) -> None:
        """测试依赖数量属性。"""
        info = DependencyInfo(
            node_uid="skill:a",
            level=DependencyLevel.LEVEL_1,
            depth=1,
            dependencies=["skill:b", "skill:c", "skill:d"],
        )
        
        assert info.dependency_count == 3
    
    def test_dependent_count_property(self) -> None:
        """测试被依赖数量属性。"""
        info = DependencyInfo(
            node_uid="skill:a",
            level=DependencyLevel.ROOT,
            depth=0,
            dependents=["skill:b", "skill:c"],
        )
        
        assert info.dependent_count == 2
    
    def test_transitive_dependency_count_property(self) -> None:
        """测试传递依赖数量属性。"""
        info = DependencyInfo(
            node_uid="skill:a",
            level=DependencyLevel.LEVEL_2,
            depth=2,
            transitive_dependencies=["skill:b", "skill:c", "skill:d", "skill:e"],
        )
        
        assert info.transitive_dependency_count == 4
    
    def test_dependency_info_to_dict(self) -> None:
        """测试转换为字典。"""
        info = DependencyInfo(
            node_uid="skill:a",
            level=DependencyLevel.LEVEL_1,
            depth=1,
            dependencies=["skill:b"],
            dependents=["skill:c"],
            transitive_dependencies=["skill:b", "skill:d"],
            is_leaf=False,
            is_root=True,
        )
        
        result = info.to_dict()
        
        assert result["node_uid"] == "skill:a"
        assert result["level"] == "level_1"
        assert result["depth"] == 1
        assert result["dependency_count"] == 1
        assert result["dependent_count"] == 1
        assert result["transitive_dependency_count"] == 2
        assert result["dependencies"] == ["skill:b"]
        assert result["dependents"] == ["skill:c"]
        assert result["transitive_dependencies"] == ["skill:b", "skill:d"]
        assert result["is_leaf"] is False
        assert result["is_root"] is True


# ============================================================================
# DependencyGraph Tests
# ============================================================================


class TestDependencyGraph:
    """DependencyGraph 数据结构测试。"""
    
    def test_create_dependency_graph(self) -> None:
        """测试创建依赖图。"""
        info = DependencyInfo(
            node_uid="skill:a",
            level=DependencyLevel.ROOT,
            depth=0,
        )
        
        graph = DependencyGraph(
            nodes={"skill:a": info},
            edges=[("skill:a", "skill:b")],
            max_depth=0,
            root_nodes=["skill:a"],
            leaf_nodes=["skill:a"],
        )
        
        assert graph.node_count == 1
        assert graph.edge_count == 1
        assert graph.max_depth == 0
        assert graph.root_nodes == ["skill:a"]
        assert graph.leaf_nodes == ["skill:a"]
    
    def test_dependency_graph_defaults(self) -> None:
        """测试默认值。"""
        graph = DependencyGraph()
        
        assert graph.nodes == {}
        assert graph.edges == []
        assert graph.max_depth == 0
        assert graph.root_nodes == []
        assert graph.leaf_nodes == []
    
    def test_node_count_property(self) -> None:
        """测试节点数量属性。"""
        info1 = DependencyInfo(node_uid="skill:a", level=DependencyLevel.ROOT, depth=0)
        info2 = DependencyInfo(node_uid="skill:b", level=DependencyLevel.LEVEL_1, depth=1)
        
        graph = DependencyGraph(nodes={"skill:a": info1, "skill:b": info2})
        
        assert graph.node_count == 2
    
    def test_edge_count_property(self) -> None:
        """测试边数量属性。"""
        graph = DependencyGraph(edges=[
            ("skill:a", "skill:b"),
            ("skill:b", "skill:c"),
        ])
        
        assert graph.edge_count == 2
    
    def test_get_node(self) -> None:
        """测试获取节点。"""
        info = DependencyInfo(node_uid="skill:a", level=DependencyLevel.ROOT, depth=0)
        graph = DependencyGraph(nodes={"skill:a": info})
        
        result = graph.get_node("skill:a")
        assert result is not None
        assert result.node_uid == "skill:a"
        
        result = graph.get_node("skill:unknown")
        assert result is None
    
    def test_get_dependencies(self) -> None:
        """测试获取依赖。"""
        info = DependencyInfo(
            node_uid="skill:a",
            level=DependencyLevel.LEVEL_1,
            depth=1,
            dependencies=["skill:b", "skill:c"],
        )
        graph = DependencyGraph(nodes={"skill:a": info})
        
        result = graph.get_dependencies("skill:a")
        assert result == ["skill:b", "skill:c"]
        
        result = graph.get_dependencies("skill:unknown")
        assert result == []
    
    def test_get_dependents(self) -> None:
        """测试获取被依赖者。"""
        info = DependencyInfo(
            node_uid="skill:a",
            level=DependencyLevel.ROOT,
            depth=0,
            dependents=["skill:b", "skill:c"],
        )
        graph = DependencyGraph(nodes={"skill:a": info})
        
        result = graph.get_dependents("skill:a")
        assert result == ["skill:b", "skill:c"]
        
        result = graph.get_dependents("skill:unknown")
        assert result == []
    
    def test_dependency_graph_to_dict(self) -> None:
        """测试转换为字典。"""
        info = DependencyInfo(node_uid="skill:a", level=DependencyLevel.ROOT, depth=0)
        graph = DependencyGraph(
            nodes={"skill:a": info},
            edges=[("skill:a", "skill:b")],
            max_depth=0,
            root_nodes=["skill:a"],
            leaf_nodes=["skill:a"],
        )
        
        result = graph.to_dict()
        
        assert result["node_count"] == 1
        assert result["edge_count"] == 1
        assert result["max_depth"] == 0
        assert result["root_nodes"] == ["skill:a"]
        assert result["leaf_nodes"] == ["skill:a"]
        assert "skill:a" in result["nodes"]


# ============================================================================
# DependencyResolver Init Tests
# ============================================================================


class TestDependencyResolverInit:
    """DependencyResolver 初始化测试。"""
    
    def test_init_default(self) -> None:
        """测试默认初始化。"""
        resolver = DependencyResolver()
        assert resolver.DEEP_THRESHOLD == 3
    
    def test_deep_threshold_constant(self) -> None:
        """测试深度阈值常量。"""
        assert DependencyResolver.DEEP_THRESHOLD == 3


# ============================================================================
# DependencyResolver Resolve Tests
# ============================================================================


class TestDependencyResolverResolve:
    """DependencyResolver resolve 方法测试。"""
    
    def test_resolve_empty_edges(
        self,
        resolver: DependencyResolver,
        empty_edges: list[tuple[str, str]],
    ) -> None:
        """测试空边列表。"""
        graph = resolver.resolve(empty_edges)
        
        assert graph.node_count == 0
        assert graph.edge_count == 0
        assert graph.max_depth == 0
    
    def test_resolve_single_edge(
        self,
        resolver: DependencyResolver,
        single_edge: list[tuple[str, str]],
    ) -> None:
        """测试单条边。"""
        graph = resolver.resolve(single_edge)
        
        assert graph.node_count == 2
        assert graph.edge_count == 1
        
        # a depends on b, so a has depth 1, b has depth 0
        info_a = graph.get_node("skill:a")
        assert info_a is not None
        assert info_a.depth == 1
        assert info_a.level == DependencyLevel.LEVEL_1
        
        info_b = graph.get_node("skill:b")
        assert info_b is not None
        assert info_b.depth == 0
        assert info_b.level == DependencyLevel.ROOT
    
    def test_resolve_simple_linear(
        self,
        resolver: DependencyResolver,
        simple_edges: list[tuple[str, str]],
    ) -> None:
        """测试线性依赖。"""
        graph = resolver.resolve(simple_edges)
        
        assert graph.node_count == 3
        assert graph.max_depth == 2
        
        # a -> b -> c
        info_a = graph.get_node("skill:a")
        assert info_a is not None
        assert info_a.depth == 2
        assert info_a.level == DependencyLevel.LEVEL_2
        
        info_b = graph.get_node("skill:b")
        assert info_b is not None
        assert info_b.depth == 1
        assert info_b.level == DependencyLevel.LEVEL_1
        
        info_c = graph.get_node("skill:c")
        assert info_c is not None
        assert info_c.depth == 0
        assert info_c.level == DependencyLevel.ROOT
    
    def test_resolve_complex_dag(
        self,
        resolver: DependencyResolver,
        complex_edges: list[tuple[str, str]],
    ) -> None:
        """测试复杂 DAG。"""
        graph = resolver.resolve(complex_edges)
        
        assert graph.node_count == 5
        assert graph.max_depth == 3
        
        # a -> b/c -> d -> e
        info_a = graph.get_node("skill:a")
        assert info_a is not None
        assert info_a.depth == 3
        assert info_a.level == DependencyLevel.LEVEL_3
        
        info_e = graph.get_node("skill:e")
        assert info_e is not None
        assert info_e.depth == 0
        assert info_e.level == DependencyLevel.ROOT
    
    def test_resolve_diamond_structure(
        self,
        resolver: DependencyResolver,
        diamond_edges: list[tuple[str, str]],
    ) -> None:
        """测试菱形结构。"""
        graph = resolver.resolve(diamond_edges)
        
        assert graph.node_count == 4
        
        # a -> b/c -> d
        info_a = graph.get_node("skill:a")
        assert info_a is not None
        assert info_a.depth == 2
        
        info_d = graph.get_node("skill:d")
        assert info_d is not None
        assert info_d.depth == 0
        assert info_d.level == DependencyLevel.ROOT
    
    def test_resolve_with_cycle(
        self,
        resolver: DependencyResolver,
        cycle_edges: list[tuple[str, str]],
    ) -> None:
        """测试有环路的图。"""
        graph = resolver.resolve(cycle_edges)
        
        # 环路中的节点应该标记为 UNKNOWN 或保持某种状态
        # 根据实际实现，环路可能导致深度计算返回 -1
        # 检查节点是否存在
        for uid in ["skill:a", "skill:b", "skill:c"]:
            info = graph.get_node(uid)
            assert info is not None
            # 环路节点的深度可能是 UNKNOWN 或者有特定处理
            # 如果深度为 -1，则 level 为 UNKNOWN
            # 否则可能是 ROOT（如果算法从某个节点开始）
            assert info.level in [DependencyLevel.UNKNOWN, DependencyLevel.ROOT]
    
    def test_resolve_with_isolated_nodes(
        self,
        resolver: DependencyResolver,
        simple_edges: list[tuple[str, str]],
        isolated_nodes: list[str],
    ) -> None:
        """测试包含孤立节点。"""
        graph = resolver.resolve(simple_edges, isolated_nodes)
        
        assert graph.node_count == 5  # 3 from edges + 2 isolated
        
        # 孤立节点应该是 ROOT
        info = graph.get_node("skill:isolated1")
        assert info is not None
        assert info.level == DependencyLevel.ROOT
        assert info.is_leaf is True
        assert info.is_root is True
    
    def test_resolve_identifies_root_nodes(
        self,
        resolver: DependencyResolver,
        simple_edges: list[tuple[str, str]],
    ) -> None:
        """测试识别根节点。"""
        graph = resolver.resolve(simple_edges)
        
        # 根节点是"无被依赖"的节点（dependents=[]）
        # 在 a -> b -> c 中，a 没有被依赖（没有人依赖 a），所以 a 是 root
        assert "skill:a" in graph.root_nodes
    
    def test_resolve_identifies_leaf_nodes(
        self,
        resolver: DependencyResolver,
        simple_edges: list[tuple[str, str]],
    ) -> None:
        """测试识别叶子节点。"""
        graph = resolver.resolve(simple_edges)
        
        # 叶子节点是"无依赖"的节点（dependencies=[]）
        # 在 a -> b -> c 中，c 没有依赖其他节点，所以 c 是 leaf
        assert "skill:c" in graph.leaf_nodes
    
    def test_resolve_transitive_dependencies(
        self,
        resolver: DependencyResolver,
        simple_edges: list[tuple[str, str]],
    ) -> None:
        """测试传递依赖。"""
        graph = resolver.resolve(simple_edges)
        
        # a -> b -> c, 所以 a 的传递依赖包括 b 和 c
        info_a = graph.get_node("skill:a")
        assert info_a is not None
        assert "skill:b" in info_a.transitive_dependencies
        assert "skill:c" in info_a.transitive_dependencies
    
    def test_resolve_deep_level(
        self,
        resolver: DependencyResolver,
    ) -> None:
        """测试深层依赖。"""
        # 创建深度 > 3 的依赖链
        edges = [
            ("skill:a", "skill:b"),
            ("skill:b", "skill:c"),
            ("skill:c", "skill:d"),
            ("skill:d", "skill:e"),
        ]
        
        graph = resolver.resolve(edges)
        
        info_a = graph.get_node("skill:a")
        assert info_a is not None
        assert info_a.depth == 4
        assert info_a.level == DependencyLevel.DEEP


# ============================================================================
# DependencyResolver Execution Order Tests
# ============================================================================


class TestDependencyResolverExecutionOrder:
    """执行顺序测试。"""
    
    def test_get_execution_order_empty(
        self,
        resolver: DependencyResolver,
        empty_edges: list[tuple[str, str]],
    ) -> None:
        """测试空图执行顺序。"""
        graph = resolver.resolve(empty_edges)
        order = resolver.get_execution_order(graph)
        
        assert order == []
    
    def test_get_execution_order_simple(
        self,
        resolver: DependencyResolver,
        simple_edges: list[tuple[str, str]],
    ) -> None:
        """测试简单图执行顺序。"""
        graph = resolver.resolve(simple_edges)
        order = resolver.get_execution_order(graph)
        
        # 执行顺序：先执行叶子（无依赖），最后执行根
        # c (depth 0) -> b (depth 1) -> a (depth 2)
        assert order[0] == "skill:c"
        assert order[-1] == "skill:a"
    
    def test_get_execution_order_includes_all_nodes(
        self,
        resolver: DependencyResolver,
        complex_edges: list[tuple[str, str]],
    ) -> None:
        """测试执行顺序包含所有节点。"""
        graph = resolver.resolve(complex_edges)
        order = resolver.get_execution_order(graph)
        
        assert len(order) == graph.node_count
        assert set(order) == set(graph.nodes.keys())


# ============================================================================
# DependencyResolver Load Order Tests
# ============================================================================


class TestDependencyResolverLoadOrder:
    """加载顺序测试。"""
    
    def test_get_load_order_simple(
        self,
        resolver: DependencyResolver,
        simple_edges: list[tuple[str, str]],
    ) -> None:
        """测试简单图加载顺序。"""
        graph = resolver.resolve(simple_edges)
        order = resolver.get_load_order(graph)
        
        # 加载顺序：先加载根（被依赖），最后加载叶子
        # a (depth 2) -> b (depth 1) -> c (depth 0)
        assert order[0] == "skill:a"
        assert order[-1] == "skill:c"
    
    def test_load_order_reverse_of_execution(
        self,
        resolver: DependencyResolver,
        simple_edges: list[tuple[str, str]],
    ) -> None:
        """测试加载顺序是执行顺序的反转。"""
        graph = resolver.resolve(simple_edges)
        execution_order = resolver.get_execution_order(graph)
        load_order = resolver.get_load_order(graph)
        
        assert load_order == list(reversed(execution_order))


# ============================================================================
# DependencyResolver Critical Path Tests
# ============================================================================


class TestDependencyResolverCriticalPath:
    """关键路径测试。"""
    
    def test_find_critical_path_empty(
        self,
        resolver: DependencyResolver,
        empty_edges: list[tuple[str, str]],
    ) -> None:
        """测试空图关键路径。"""
        graph = resolver.resolve(empty_edges)
        path = resolver.find_critical_path(graph)
        
        assert path == []
    
    def test_find_critical_path_simple(
        self,
        resolver: DependencyResolver,
        simple_edges: list[tuple[str, str]],
    ) -> None:
        """测试简单图关键路径。"""
        graph = resolver.resolve(simple_edges)
        path = resolver.find_critical_path(graph)
        
        # 关键路径：从叶子到根（c -> b -> a）
        # 源代码返回的是从叶子节点开始的路径
        assert path[0] == "skill:c"
        assert path[-1] == "skill:a"
        assert len(path) == 3
    
    def test_find_critical_path_complex(
        self,
        resolver: DependencyResolver,
        complex_edges: list[tuple[str, str]],
    ) -> None:
        """测试复杂图关键路径。"""
        graph = resolver.resolve(complex_edges)
        path = resolver.find_critical_path(graph)
        
        # 关键路径从叶子节点开始，到根节点结束
        assert path[0] == "skill:e"
        assert path[-1] == "skill:a"


# ============================================================================
# DependencyResolver Bottleneck Tests
# ============================================================================


class TestDependencyResolverBottleneck:
    """瓶颈节点测试。"""
    
    def test_get_dependency_bottleneck_empty(
        self,
        resolver: DependencyResolver,
        empty_edges: list[tuple[str, str]],
    ) -> None:
        """测试空图瓶颈。"""
        graph = resolver.resolve(empty_edges)
        bottleneck = resolver.get_dependency_bottleneck(graph)
        
        assert bottleneck is None
    
    def test_get_dependency_bottleneck_simple(
        self,
        resolver: DependencyResolver,
        simple_edges: list[tuple[str, str]],
    ) -> None:
        """测试简单图瓶颈。"""
        graph = resolver.resolve(simple_edges)
        bottleneck = resolver.get_dependency_bottleneck(graph)
        
        # 在 a -> b -> c 中，b 和 c 都被依赖
        # b 被 a 依赖，c 被 b 依赖
        # 算法返回被依赖最多的节点
        assert bottleneck in ["skill:b", "skill:c"]
    
    def test_get_dependency_bottleneck_diamond(
        self,
        resolver: DependencyResolver,
        diamond_edges: list[tuple[str, str]],
    ) -> None:
        """测试菱形结构瓶颈。"""
        graph = resolver.resolve(diamond_edges)
        bottleneck = resolver.get_dependency_bottleneck(graph)
        
        # d 被 b 和 c 依赖
        assert bottleneck == "skill:d"


# ============================================================================
# DependencyResolver Availability Tests
# ============================================================================


class TestDependencyResolverAvailability:
    """依赖可用性测试。"""
    
    def test_check_dependency_availability_all_available(
        self,
        resolver: DependencyResolver,
        simple_edges: list[tuple[str, str]],
    ) -> None:
        """测试所有依赖可用。"""
        graph = resolver.resolve(simple_edges)
        available = {"skill:a", "skill:b", "skill:c"}
        missing = resolver.check_dependency_availability(graph, available)
        
        assert missing == []
    
    def test_check_dependency_availability_missing(
        self,
        resolver: DependencyResolver,
        simple_edges: list[tuple[str, str]],
    ) -> None:
        """测试缺失依赖。"""
        graph = resolver.resolve(simple_edges)
        available = {"skill:a", "skill:b"}  # c 缺失
        missing = resolver.check_dependency_availability(graph, available)
        
        assert len(missing) >= 1
        assert "skill:c" in missing[0]
    
    def test_check_dependency_availability_empty_graph(
        self,
        resolver: DependencyResolver,
        empty_edges: list[tuple[str, str]],
    ) -> None:
        """测试空图。"""
        graph = resolver.resolve(empty_edges)
        missing = resolver.check_dependency_availability(graph, set())
        
        assert missing == []


# ============================================================================
# DependencyResolver Level Tests
# ============================================================================


class TestDependencyResolverLevel:
    """层级相关测试。"""
    
    def test_get_nodes_by_level_root(
        self,
        resolver: DependencyResolver,
        simple_edges: list[tuple[str, str]],
    ) -> None:
        """测试获取 ROOT 层级节点。"""
        graph = resolver.resolve(simple_edges)
        nodes = resolver.get_nodes_by_level(graph, DependencyLevel.ROOT)
        
        assert "skill:c" in nodes
    
    def test_get_nodes_by_level_1(
        self,
        resolver: DependencyResolver,
        simple_edges: list[tuple[str, str]],
    ) -> None:
        """测试获取 LEVEL_1 层级节点。"""
        graph = resolver.resolve(simple_edges)
        nodes = resolver.get_nodes_by_level(graph, DependencyLevel.LEVEL_1)
        
        assert "skill:b" in nodes
    
    def test_get_nodes_by_level_empty(
        self,
        resolver: DependencyResolver,
        empty_edges: list[tuple[str, str]],
    ) -> None:
        """测试空图层级节点。"""
        graph = resolver.resolve(empty_edges)
        nodes = resolver.get_nodes_by_level(graph, DependencyLevel.ROOT)
        
        assert nodes == []


# ============================================================================
# DependencyResolver Tree Tests
# ============================================================================


class TestDependencyResolverTree:
    """依赖树测试。"""
    
    def test_get_dependency_tree_simple(
        self,
        resolver: DependencyResolver,
        simple_edges: list[tuple[str, str]],
    ) -> None:
        """测试简单依赖树。"""
        graph = resolver.resolve(simple_edges)
        tree = resolver.get_dependency_tree(graph, "skill:a")
        
        assert tree["uid"] == "skill:a"
        assert tree["depth"] == 2
        assert len(tree["children"]) == 1
        assert tree["children"][0]["uid"] == "skill:b"
    
    def test_get_dependency_tree_with_max_depth(
        self,
        resolver: DependencyResolver,
        complex_edges: list[tuple[str, str]],
    ) -> None:
        """测试带深度限制的依赖树。"""
        graph = resolver.resolve(complex_edges)
        tree = resolver.get_dependency_tree(graph, "skill:a", max_depth=1)
        
        assert tree["uid"] == "skill:a"
        # max_depth=1 时，children 应该存在但可能被截断
        # 检查 children 是否存在
        assert "children" in tree
    
    def test_get_dependency_tree_not_found(
        self,
        resolver: DependencyResolver,
        simple_edges: list[tuple[str, str]],
    ) -> None:
        """测试节点不存在。"""
        graph = resolver.resolve(simple_edges)
        tree = resolver.get_dependency_tree(graph, "skill:unknown")
        
        assert tree["uid"] == "skill:unknown"
        assert tree["error"] == "not found"
    
    def test_get_dependency_tree_leaf_node(
        self,
        resolver: DependencyResolver,
        simple_edges: list[tuple[str, str]],
    ) -> None:
        """测试叶子节点依赖树。"""
        graph = resolver.resolve(simple_edges)
        tree = resolver.get_dependency_tree(graph, "skill:c")
        
        assert tree["uid"] == "skill:c"
        assert tree["depth"] == 0
        assert tree["children"] == []


# ============================================================================
# DependencyResolver Metrics Tests
# ============================================================================


class TestDependencyResolverMetrics:
    """指标计算测试。"""
    
    def test_calculate_dependency_metrics_empty(
        self,
        resolver: DependencyResolver,
        empty_edges: list[tuple[str, str]],
    ) -> None:
        """测试空图指标。"""
        graph = resolver.resolve(empty_edges)
        metrics = resolver.calculate_dependency_metrics(graph)
        
        assert metrics["node_count"] == 0
        assert metrics["edge_count"] == 0
        assert metrics["max_depth"] == 0
    
    def test_calculate_dependency_metrics_simple(
        self,
        resolver: DependencyResolver,
        simple_edges: list[tuple[str, str]],
    ) -> None:
        """测试简单图指标。"""
        graph = resolver.resolve(simple_edges)
        metrics = resolver.calculate_dependency_metrics(graph)
        
        assert metrics["node_count"] == 3
        assert metrics["edge_count"] == 2
        assert metrics["max_depth"] == 2
        assert metrics["root_count"] == 1
        assert metrics["leaf_count"] == 1
        assert metrics["total_dependencies"] == 2
        assert metrics["total_dependents"] == 2
    
    def test_calculate_metrics_level_distribution(
        self,
        resolver: DependencyResolver,
        simple_edges: list[tuple[str, str]],
    ) -> None:
        """测试层级分布。"""
        graph = resolver.resolve(simple_edges)
        metrics = resolver.calculate_dependency_metrics(graph)
        
        level_dist = metrics["level_distribution"]
        assert level_dist.get("root", 0) == 1
        assert level_dist.get("level_1", 0) == 1
        assert level_dist.get("level_2", 0) == 1
    
    def test_calculate_metrics_avg_values(
        self,
        resolver: DependencyResolver,
        complex_edges: list[tuple[str, str]],
    ) -> None:
        """测试平均值计算。"""
        graph = resolver.resolve(complex_edges)
        metrics = resolver.calculate_dependency_metrics(graph)
        
        assert "avg_dependencies" in metrics
        assert "avg_dependents" in metrics
        assert metrics["avg_dependencies"] >= 0
        assert metrics["avg_dependents"] >= 0


# ============================================================================
# Edge Cases Tests
# ============================================================================


class TestEdgeCases:
    """边界条件测试。"""
    
    def test_resolve_self_reference(
        self,
        resolver: DependencyResolver,
    ) -> None:
        """测试自引用。"""
        edges = [("skill:a", "skill:a")]
        graph = resolver.resolve(edges)
        
        # 自引用应该被检测为环路或特殊处理
        info = graph.get_node("skill:a")
        assert info is not None
        # 自引用可能导致深度 -1（标记为 UNKNOWN）或深度 0（标记为 ROOT）
        # 取决于算法实现
        assert info.level in [DependencyLevel.UNKNOWN, DependencyLevel.ROOT]
    
    def test_resolve_parallel_edges(
        self,
        resolver: DependencyResolver,
    ) -> None:
        """测试平行边。"""
        edges = [
            ("skill:a", "skill:b"),
            ("skill:a", "skill:b"),  # 平行边
        ]
        graph = resolver.resolve(edges)
        
        assert graph.node_count == 2
        assert graph.edge_count == 2
    
    def test_resolve_disconnected_graph(
        self,
        resolver: DependencyResolver,
    ) -> None:
        """测试不连通图。"""
        edges = [
            ("skill:a", "skill:b"),
            ("skill:c", "skill:d"),  # 不连通
        ]
        graph = resolver.resolve(edges)
        
        assert graph.node_count == 4
        # 两个独立的根节点
        assert len(graph.root_nodes) == 2
    
    def test_resolve_large_graph(
        self,
        resolver: DependencyResolver,
    ) -> None:
        """测试大型图。"""
        # 创建 20 个节点的依赖链
        edges = [(f"skill:n{i}", f"skill:n{i+1}") for i in range(19)]
        graph = resolver.resolve(edges)
        
        assert graph.node_count == 20
        assert graph.max_depth == 19
    
    def test_resolve_multiple_dependencies(
        self,
        resolver: DependencyResolver,
    ) -> None:
        """测试多依赖节点。"""
        edges = [
            ("skill:a", "skill:b"),
            ("skill:a", "skill:c"),
            ("skill:a", "skill:d"),
            ("skill:a", "skill:e"),
        ]
        graph = resolver.resolve(edges)
        
        info_a = graph.get_node("skill:a")
        assert info_a is not None
        assert info_a.dependency_count == 4


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """集成测试。"""
    
    def test_full_resolution_workflow(
        self,
        resolver: DependencyResolver,
        complex_edges: list[tuple[str, str]],
    ) -> None:
        """测试完整解析工作流。"""
        # 1. 解析依赖图
        graph = resolver.resolve(complex_edges)
        
        # 2. 获取执行顺序
        execution_order = resolver.get_execution_order(graph)
        assert len(execution_order) == graph.node_count
        
        # 3. 获取加载顺序
        load_order = resolver.get_load_order(graph)
        assert load_order[0] == execution_order[-1]
        
        # 4. 找关键路径
        critical_path = resolver.find_critical_path(graph)
        assert len(critical_path) > 0
        
        # 5. 找瓶颈
        bottleneck = resolver.get_dependency_bottleneck(graph)
        assert bottleneck is not None
        
        # 6. 计算指标
        metrics = resolver.calculate_dependency_metrics(graph)
        assert metrics["node_count"] == graph.node_count
    
    def test_dependency_tree_workflow(
        self,
        resolver: DependencyResolver,
        complex_edges: list[tuple[str, str]],
    ) -> None:
        """测试依赖树工作流。"""
        graph = resolver.resolve(complex_edges)
        
        # 获取每个节点的依赖树
        for uid in graph.nodes:
            tree = resolver.get_dependency_tree(graph, uid)
            assert tree["uid"] == uid
    
    def test_level_filtering_workflow(
        self,
        resolver: DependencyResolver,
        complex_edges: list[tuple[str, str]],
    ) -> None:
        """测试层级过滤工作流。"""
        graph = resolver.resolve(complex_edges)
        
        # 按层级获取节点
        for level in DependencyLevel:
            nodes = resolver.get_nodes_by_level(graph, level)
            for node in nodes:
                info = graph.get_node(node)
                assert info is not None
                assert info.level == level