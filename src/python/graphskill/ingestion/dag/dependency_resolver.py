"""
依赖解析器。

计算技能节点的依赖深度和层级。

Reference: RFC-02 Section 3.4
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DependencyLevel(str, Enum):
    """依赖层级。"""
    
    ROOT = "root"          # 无依赖
    LEVEL_1 = "level_1"    # 依赖 ROOT
    LEVEL_2 = "level_2"    # 依赖 LEVEL_1
    LEVEL_3 = "level_3"    # 依赖 LEVEL_2
    DEEP = "deep"          # 深层依赖 (>3)
    UNKNOWN = "unknown"    # 未知（可能存在环路）


@dataclass
class DependencyInfo:
    """依赖信息。"""
    
    node_uid: str
    level: DependencyLevel
    depth: int
    dependencies: list[str] = field(default_factory=list)
    dependents: list[str] = field(default_factory=list)  # 被依赖者
    transitive_dependencies: list[str] = field(default_factory=list)  # 传递依赖
    is_leaf: bool = False  # 是否叶子节点（无依赖）
    is_root: bool = False  # 是否根节点（无被依赖）
    
    @property
    def dependency_count(self) -> int:
        """直接依赖数量。"""
        return len(self.dependencies)
    
    @property
    def dependent_count(self) -> int:
        """被依赖数量。"""
        return len(self.dependents)
    
    @property
    def transitive_dependency_count(self) -> int:
        """传递依赖数量。"""
        return len(self.transitive_dependencies)
    
    def to_dict(self) -> dict:
        return {
            "node_uid": self.node_uid,
            "level": self.level.value,
            "depth": self.depth,
            "dependency_count": self.dependency_count,
            "dependent_count": self.dependent_count,
            "transitive_dependency_count": self.transitive_dependency_count,
            "dependencies": self.dependencies,
            "dependents": self.dependents,
            "transitive_dependencies": self.transitive_dependencies,
            "is_leaf": self.is_leaf,
            "is_root": self.is_root,
        }


@dataclass
class DependencyGraph:
    """依赖图结构。"""
    
    nodes: dict[str, DependencyInfo] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)
    max_depth: int = 0
    root_nodes: list[str] = field(default_factory=list)
    leaf_nodes: list[str] = field(default_factory=list)
    
    @property
    def node_count(self) -> int:
        return len(self.nodes)
    
    @property
    def edge_count(self) -> int:
        return len(self.edges)
    
    def get_node(self, uid: str) -> Optional[DependencyInfo]:
        """获取节点信息。"""
        return self.nodes.get(uid)
    
    def get_dependencies(self, uid: str) -> list[str]:
        """获取节点的所有依赖。"""
        info = self.nodes.get(uid)
        return info.dependencies if info else []
    
    def get_dependents(self, uid: str) -> list[str]:
        """获取节点的所有被依赖者。"""
        info = self.nodes.get(uid)
        return info.dependents if info else []
    
    def to_dict(self) -> dict:
        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "max_depth": self.max_depth,
            "root_nodes": self.root_nodes,
            "leaf_nodes": self.leaf_nodes,
            "nodes": {uid: info.to_dict() for uid, info in self.nodes.items()},
        }


class DependencyResolver:
    """
    依赖解析器。
    
    计算技能节点的依赖深度和层级。
    
    Features:
        - 依赖深度计算
        - 层级分类
        - 传递依赖分析
        - 根/叶节点识别
    
    Example:
        >>> resolver = DependencyResolver()
        >>> graph = resolver.resolve(edges)
        >>> print(graph.max_depth)
        >>> for uid, info in graph.nodes.items():
        ...     print(f"{uid}: depth={info.depth}, level={info.level}")
    """
    
    # 深度阈值
    DEEP_THRESHOLD = 3
    
    def __init__(self):
        """初始化解析器。"""
        pass
    
    def resolve(
        self,
        edges: list[tuple[str, str]],
        nodes: Optional[list[str]] = None,
    ) -> DependencyGraph:
        """
        解析依赖图。
        
        Args:
            edges: 边列表 [(source, target), ...] 表示 source REQUIRES target
            nodes: 节点列表（可选）
            
        Returns:
            DependencyGraph: 依赖图结构
        """
        # 提取所有节点
        all_nodes: set[str] = set()
        for source, target in edges:
            all_nodes.add(source)
            all_nodes.add(target)
        
        if nodes:
            all_nodes.update(nodes)
        
        # 构建邻接表（正向：依赖关系）
        dependency_graph: dict[str, list[str]] = {}
        for source, target in edges:
            if source not in dependency_graph:
                dependency_graph[source] = []
            dependency_graph[source].append(target)
        
        # 构建邻接表（反向：被依赖关系）
        dependent_graph: dict[str, list[str]] = {}
        for source, target in edges:
            if target not in dependent_graph:
                dependent_graph[target] = []
            dependent_graph[target].append(source)
        
        # 计算每个节点的深度
        depths: dict[str, int] = {}
        transitive_deps: dict[str, set[str]] = {}
        
        def calculate_depth(node: str, visited: set[str]) -> int:
            """计算节点深度（递归）。"""
            if node in visited:
                # 检测到环路，返回 -1 表示无效
                return -1
            
            if node in depths:
                return depths[node]
            
            visited.add(node)
            
            direct_deps = dependency_graph.get(node, [])
            if not direct_deps:
                depths[node] = 0
                transitive_deps[node] = set()
                visited.remove(node)
                return 0
            
            # 计算传递依赖
            all_transitive: set[str] = set(direct_deps)
            max_dep_depth = 0
            
            for dep in direct_deps:
                dep_depth = calculate_depth(dep, visited)
                if dep_depth < 0:
                    # 环路
                    visited.remove(node)
                    return -1
                max_dep_depth = max(max_dep_depth, dep_depth)
                # 添加传递依赖
                all_transitive.update(transitive_deps.get(dep, set()))
            
            depths[node] = max_dep_depth + 1
            transitive_deps[node] = all_transitive
            visited.remove(node)
            return depths[node]
        
        # 计算所有节点深度
        for node in all_nodes:
            if node not in depths:
                calculate_depth(node, set())
        
        # 构建节点信息
        node_infos: dict[str, DependencyInfo] = {}
        root_nodes: list[str] = []
        leaf_nodes: list[str] = []
        max_depth = 0
        
        for node in all_nodes:
            depth = depths.get(node, 0)
            if depth < 0:
                # 环路中的节点
                level = DependencyLevel.UNKNOWN
                depth = 0
            elif depth == 0:
                level = DependencyLevel.ROOT
                leaf_nodes.append(node)
            elif depth == 1:
                level = DependencyLevel.LEVEL_1
            elif depth == 2:
                level = DependencyLevel.LEVEL_2
            elif depth == 3:
                level = DependencyLevel.LEVEL_3
            else:
                level = DependencyLevel.DEEP
            
            direct_deps = dependency_graph.get(node, [])
            direct_dependents = dependent_graph.get(node, [])
            trans_deps = list(transitive_deps.get(node, set()))
            
            is_leaf = len(direct_deps) == 0
            is_root = len(direct_dependents) == 0
            
            if is_root:
                root_nodes.append(node)
            
            node_infos[node] = DependencyInfo(
                node_uid=node,
                level=level,
                depth=depth,
                dependencies=direct_deps,
                dependents=direct_dependents,
                transitive_dependencies=trans_deps,
                is_leaf=is_leaf,
                is_root=is_root,
            )
            
            max_depth = max(max_depth, depth)
        
        return DependencyGraph(
            nodes=node_infos,
            edges=edges,
            max_depth=max_depth,
            root_nodes=root_nodes,
            leaf_nodes=leaf_nodes,
        )
    
    def get_execution_order(
        self,
        graph: DependencyGraph,
    ) -> list[str]:
        """
        获取拓扑排序后的执行顺序。
        
        Args:
            graph: 依赖图
            
        Returns:
            list: 执行顺序（从叶子到根）
        """
        # 使用 Kahn 算法进行拓扑排序
        # 从叶子节点（无依赖）开始
        
        # 构建邻接表和入度计数
        in_degree: dict[str, int] = {}
        reverse_graph: dict[str, list[str]] = {}  # dep -> dependents
        
        for uid, info in graph.nodes.items():
            in_degree[uid] = info.dependency_count
            for dep in info.dependencies:
                if dep not in reverse_graph:
                    reverse_graph[dep] = []
                reverse_graph[dep].append(uid)
        
        # 初始化队列（叶子节点）
        queue: list[str] = [uid for uid, deg in in_degree.items() if deg == 0]
        result: list[str] = []
        
        while queue:
            # 按深度排序（深度小的优先）
            queue.sort(key=lambda x: graph.nodes.get(x, DependencyInfo(x, DependencyLevel.UNKNOWN, 0)).depth)
            
            node = queue.pop(0)
            result.append(node)
            
            # 减少依赖此节点的节点的入度
            for dependent in reverse_graph.get(node, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        return result
    
    def get_load_order(
        self,
        graph: DependencyGraph,
    ) -> list[str]:
        """
        获取加载顺序（从根到叶子）。
        
        Args:
            graph: 依赖图
            
        Returns:
            list: 加载顺序（先加载依赖）
        """
        # 反转执行顺序
        execution_order = self.get_execution_order(graph)
        return list(reversed(execution_order))
    
    def find_critical_path(
        self,
        graph: DependencyGraph,
    ) -> list[str]:
        """
        找到最长依赖路径（关键路径）。
        
        Args:
            graph: 依赖图
            
        Returns:
            list: 关键路径节点列表
        """
        if not graph.nodes:
            return []
        
        # 找到深度最大的节点
        max_depth_node = max(
            graph.nodes.items(),
            key=lambda x: x[1].depth
        )[0]
        
        # 从该节点回溯到根
        path: list[str] = [max_depth_node]
        current = max_depth_node
        
        while True:
            info = graph.nodes.get(current)
            if not info or not info.dependencies:
                break
            
            # 选择深度最大的依赖
            max_dep = max(
                info.dependencies,
                key=lambda x: graph.nodes.get(x, DependencyInfo(x, DependencyLevel.UNKNOWN, 0)).depth
            )
            path.append(max_dep)
            current = max_dep
        
        return list(reversed(path))
    
    def get_dependency_bottleneck(
        self,
        graph: DependencyGraph,
    ) -> Optional[str]:
        """
        找到依赖瓶颈节点（被最多节点依赖）。
        
        Args:
            graph: 依赖图
            
        Returns:
            Optional[str]: 瓶颈节点 UID
        """
        if not graph.nodes:
            return None
        
        # 找到被依赖最多的节点
        bottleneck = max(
            graph.nodes.items(),
            key=lambda x: x[1].dependent_count
        )
        
        return bottleneck[0] if bottleneck[1].dependent_count > 0 else None
    
    def check_dependency_availability(
        self,
        graph: DependencyGraph,
        available_skills: set[str],
    ) -> list[str]:
        """
        检查依赖是否可用。
        
        Args:
            graph: 依赖图
            available_skills: 可用的技能 UID 集合
            
        Returns:
            list: 缺失的依赖列表
        """
        missing: list[str] = []
        
        for uid, info in graph.nodes.items():
            for dep in info.dependencies:
                if dep not in available_skills:
                    missing.append(f"{uid} requires {dep} (missing)")
        
        return missing
    
    def get_nodes_by_level(
        self,
        graph: DependencyGraph,
        level: DependencyLevel,
    ) -> list[str]:
        """
        按层级获取节点。
        
        Args:
            graph: 依赖图
            level: 依赖层级
            
        Returns:
            list: 该层级的节点列表
        """
        return [
            uid for uid, info in graph.nodes.items()
            if info.level == level
        ]
    
    def get_dependency_tree(
        self,
        graph: DependencyGraph,
        root_uid: str,
        max_depth: Optional[int] = None,
    ) -> dict:
        """
        获取依赖树结构。
        
        Args:
            graph: 依赖图
            root_uid: 根节点 UID
            max_depth: 最大深度（可选）
            
        Returns:
            dict: 树结构
        """
        def build_tree(uid: str, current_depth: int) -> dict:
            if max_depth and current_depth > max_depth:
                return {"uid": uid, "truncated": True}
            
            info = graph.nodes.get(uid)
            if not info:
                return {"uid": uid, "error": "not found"}
            
            children = []
            for dep in info.dependencies:
                children.append(build_tree(dep, current_depth + 1))
            
            return {
                "uid": uid,
                "depth": info.depth,
                "level": info.level.value,
                "children": children,
            }
        
        return build_tree(root_uid, 0)
    
    def calculate_dependency_metrics(
        self,
        graph: DependencyGraph,
    ) -> dict:
        """
        计算依赖图指标。
        
        Args:
            graph: 依赖图
            
        Returns:
            dict: 指标字典
        """
        total_deps = sum(info.dependency_count for info in graph.nodes.values())
        total_dependents = sum(info.dependent_count for info in graph.nodes.values())
        total_transitive = sum(info.transitive_dependency_count for info in graph.nodes.values())
        
        avg_deps = total_deps / graph.node_count if graph.node_count > 0 else 0
        avg_dependents = total_dependents / graph.node_count if graph.node_count > 0 else 0
        
        # 层级分布
        level_distribution: dict[str, int] = {}
        for info in graph.nodes.values():
            level = info.level.value
            level_distribution[level] = level_distribution.get(level, 0) + 1
        
        return {
            "node_count": graph.node_count,
            "edge_count": graph.edge_count,
            "max_depth": graph.max_depth,
            "root_count": len(graph.root_nodes),
            "leaf_count": len(graph.leaf_nodes),
            "total_dependencies": total_deps,
            "total_dependents": total_dependents,
            "total_transitive_dependencies": total_transitive,
            "avg_dependencies": round(avg_deps, 2),
            "avg_dependents": round(avg_dependents, 2),
            "level_distribution": level_distribution,
        }