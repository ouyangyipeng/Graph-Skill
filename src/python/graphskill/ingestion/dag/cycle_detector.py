"""
DAG 环路检测器。

使用 Tarjan 算法检测 REQUIRES 依赖图中的环路。

Reference: RFC-02 Section 3.4
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class NodeState(Enum):
    """Tarjan 算法节点状态。"""
    
    UNVISITED = 0
    VISITING = 1
    VISITED = 2


@dataclass
class CycleInfo:
    """单个环路信息。"""
    
    nodes: list[str]
    path: Optional[list[str]] = None
    severity: str = "error"
    description: str = ""
    
    @property
    def node_count(self) -> int:
        """节点数量。"""
        return len(self.nodes)
    
    def to_dict(self) -> dict:
        return {
            "nodes": self.nodes,
            "path": self.path,
            "node_count": self.node_count,
            "severity": self.severity,
            "description": self.description,
        }


@dataclass
class CycleDetectionResult:
    """环路检测结果。"""
    
    has_cycle: bool
    cycles: list[CycleInfo] = field(default_factory=list)
    affected_nodes: set[str] = field(default_factory=set)
    sccs: list[list[str]] = field(default_factory=list)  # 所有强连通分量
    
    @property
    def cycle_count(self) -> int:
        """环路数量。"""
        return len(self.cycles)
    
    @property
    def affected_node_count(self) -> int:
        """受影响节点数量。"""
        return len(self.affected_nodes)
    
    def to_dict(self) -> dict:
        return {
            "has_cycle": self.has_cycle,
            "cycle_count": self.cycle_count,
            "affected_node_count": self.affected_node_count,
            "cycles": [c.to_dict() for c in self.cycles],
            "affected_nodes": list(self.affected_nodes),
        }
    
    def get_cycle_for_node(self, node: str) -> Optional[CycleInfo]:
        """获取包含指定节点的环路。"""
        for cycle in self.cycles:
            if node in cycle.nodes:
                return cycle
        return None


class TarjanCycleDetector:
    """
    Tarjan 算法环路检测器。
    
    检测有向图中的所有强连通分量 (SCC)，
    大于 1 的 SCC 即为环路。
    
    Time Complexity: O(V + E)
    Space Complexity: O(V)
    
    Features:
        - 检测所有环路
        - 提取环路路径
        - 识别受影响节点
        - 支持增量检测
    
    Example:
        >>> detector = TarjanCycleDetector()
        >>> edges = [("A", "B"), ("B", "C"), ("C", "A")]
        >>> result = detector.detect(edges)
        >>> print(result.has_cycle)  # True
        >>> print(result.cycles)  # [CycleInfo(nodes=["A", "B", "C"])]
    """
    
    def __init__(self):
        """初始化检测器。"""
        pass
    
    def detect(
        self,
        edges: list[tuple[str, str]],
        nodes: Optional[list[str]] = None,
    ) -> CycleDetectionResult:
        """
        检测环路。
        
        Args:
            edges: 边列表 [(source, target), ...]
            nodes: 节点列表 (可选，从 edges 推断)
            
        Returns:
            CycleDetectionResult: 检测结果
        """
        # 构建邻接表
        graph: dict[str, list[str]] = {}
        all_nodes: set[str] = set()
        
        for source, target in edges:
            if source not in graph:
                graph[source] = []
            graph[source].append(target)
            all_nodes.add(source)
            all_nodes.add(target)
        
        if nodes:
            all_nodes.update(nodes)
        
        # Tarjan 算法变量
        index_counter = [0]
        stack: list[str] = []
        lowlink: dict[str, int] = {}
        index: dict[str, int] = {}
        on_stack: dict[str, bool] = {}
        sccs: list[list[str]] = []
        
        def strongconnect(node: str) -> None:
            """Tarjan 强连通分量算法核心。"""
            # 设置节点索引
            index[node] = index_counter[0]
            lowlink[node] = index_counter[0]
            index_counter[0] += 1
            stack.append(node)
            on_stack[node] = True
            
            # 遍历邻居
            for successor in graph.get(node, []):
                if successor not in index:
                    # 未访问的节点
                    strongconnect(successor)
                    lowlink[node] = min(lowlink[node], lowlink[successor])
                elif on_stack.get(successor, False):
                    # 在栈中的节点 (回边)
                    lowlink[node] = min(lowlink[node], index[successor])
            
            # 如果 node 是 SCC 根节点
            if lowlink[node] == index[node]:
                scc: list[str] = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    scc.append(w)
                    if w == node:
                        break
                sccs.append(scc)
        
        # 执行算法
        for node in all_nodes:
            if node not in index:
                strongconnect(node)
        
        # 提取环路 (SCC 大于 1)
        cycles: list[CycleInfo] = []
        affected_nodes: set[str] = set()
        
        for scc in sccs:
            if len(scc) > 1:
                # 找到环路路径
                path = self._find_cycle_path(edges, scc)
                
                cycle_info = CycleInfo(
                    nodes=scc,
                    path=path,
                    severity="error",
                    description=f"Circular dependency detected: {len(scc)} nodes in cycle",
                )
                cycles.append(cycle_info)
                affected_nodes.update(scc)
        
        return CycleDetectionResult(
            has_cycle=len(cycles) > 0,
            cycles=cycles,
            affected_nodes=affected_nodes,
            sccs=sccs,
        )
    
    def _find_cycle_path(
        self,
        edges: list[tuple[str, str]],
        cycle_nodes: list[str],
    ) -> Optional[list[str]]:
        """
        找到环路的具体路径。
        
        Args:
            edges: 边列表
            cycle_nodes: 环路节点
            
        Returns:
            Optional[list]: 环路路径 (如果存在)
        """
        # 构建环路子图
        cycle_graph: dict[str, list[str]] = {}
        for source, target in edges:
            if source in cycle_nodes and target in cycle_nodes:
                if source not in cycle_graph:
                    cycle_graph[source] = []
                cycle_graph[source].append(target)
        
        # DFS 找路径
        start = cycle_nodes[0]
        path: list[str] = [start]
        visited: set[str] = {start}
        
        def dfs(node: str) -> Optional[list[str]]:
            for neighbor in cycle_graph.get(node, []):
                if neighbor == start and len(path) > 1:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    path.append(neighbor)
                    result = dfs(neighbor)
                    if result:
                        return result
                    path.pop()
                    visited.remove(neighbor)
            return None
        
        return dfs(start)
    
    def detect_incremental(
        self,
        existing_edges: list[tuple[str, str]],
        new_edges: list[tuple[str, str]],
        existing_result: Optional[CycleDetectionResult] = None,
    ) -> CycleDetectionResult:
        """
        增量检测环路。
        
        仅检测新边是否引入新环路。
        
        Args:
            existing_edges: 已存在的边
            new_edges: 新添加的边
            existing_result: 已有的检测结果（可选）
            
        Returns:
            CycleDetectionResult: 检测结果
        """
        # 合并边
        all_edges = existing_edges + new_edges
        
        # 如果新边不涉及已有环路的节点，可以简化检测
        if existing_result and not existing_result.has_cycle:
            # 检查新边是否只涉及新节点
            existing_nodes = set()
            for source, target in existing_edges:
                existing_nodes.add(source)
                existing_nodes.add(target)
            
            new_nodes = set()
            for source, target in new_edges:
                new_nodes.add(source)
                new_nodes.add(target)
            
            # 如果新边只涉及已有节点，需要完整检测
            if new_nodes - existing_nodes:
                # 有新节点，需要完整检测
                return self.detect(all_edges)
            
            # 否则可以只检测涉及新边的部分
            # 但为了安全，仍进行完整检测
            return self.detect(all_edges)
        
        # 完整检测
        return self.detect(all_edges)
    
    def check_single_edge(
        self,
        existing_edges: list[tuple[str, str]],
        new_edge: tuple[str, str],
    ) -> bool:
        """
        检查单条新边是否会引入环路。
        
        Args:
            existing_edges: 已存在的边
            new_edge: 新边
            
        Returns:
            bool: 是否会引入环路
        """
        source, target = new_edge
        
        # 快速检查：如果 target -> source 已存在路径，则添加 source -> target 会形成环路
        # 使用 BFS/DFS 检查是否存在 target -> source 的路径
        
        # 构建邻接表
        graph: dict[str, list[str]] = {}
        for s, t in existing_edges:
            if s not in graph:
                graph[s] = []
            graph[s].append(t)
        
        # BFS 检查 target -> source
        visited: set[str] = {target}
        queue: list[str] = [target]
        
        while queue:
            node = queue.pop(0)
            if node == source:
                return True  # 会形成环路
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        
        return False  # 不会形成环路
    
    def get_cycle_breaking_suggestions(
        self,
        result: CycleDetectionResult,
        edges: list[tuple[str, str]],
    ) -> list[dict]:
        """
        获取打破环路的建议。
        
        Args:
            result: 检测结果
            edges: 边列表
            
        Returns:
            list: 建议列表
        """
        suggestions: list[dict] = []
        
        for cycle in result.cycles:
            # 找到环路中的边
            cycle_edges: list[tuple[str, str]] = []
            for source, target in edges:
                if source in cycle.nodes and target in cycle.nodes:
                    cycle_edges.append((source, target))
            
            # 建议移除每条边
            for edge in cycle_edges:
                suggestions.append({
                    "cycle": cycle.nodes,
                    "edge_to_remove": edge,
                    "description": f"Remove edge {edge[0]} -> {edge[1]} to break cycle",
                    "impact": f"Will break dependency chain in cycle of {len(cycle.nodes)} nodes",
                })
        
        return suggestions
    
    def validate_dag(
        self,
        edges: list[tuple[str, str]],
    ) -> tuple[bool, Optional[CycleDetectionResult]]:
        """
        验证是否为 DAG。
        
        Args:
            edges: 边列表
            
        Returns:
            tuple: (是否为 DAG, 检测结果)
        """
        result = self.detect(edges)
        return (not result.has_cycle, result)