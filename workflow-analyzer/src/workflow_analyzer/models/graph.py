"""Models for the workflow dependency graph."""

from collections import defaultdict
from typing import Literal

from pydantic import BaseModel


class DependencyEdge(BaseModel):
    """A directed edge in the workflow dependency graph."""

    source_node: str
    target_node: str
    edge_type: Literal["connection", "data_reference"]
    output_index: int | None = None
    input_index: int | None = None


class WorkflowGraph(BaseModel):
    """Directed graph representing workflow dependencies."""

    nodes: list[str]
    edges: list[DependencyEdge]

    def _adjacency(self) -> dict[str, list[str]]:
        """Build adjacency list from edges."""
        adj: dict[str, list[str]] = defaultdict(list)
        for edge in self.edges:
            if edge.target_node not in adj[edge.source_node]:
                adj[edge.source_node].append(edge.target_node)
        return dict(adj)

    def _reverse_adjacency(self) -> dict[str, list[str]]:
        """Build reverse adjacency list from edges."""
        adj: dict[str, list[str]] = defaultdict(list)
        for edge in self.edges:
            if edge.source_node not in adj[edge.target_node]:
                adj[edge.target_node].append(edge.source_node)
        return dict(adj)

    def get_successors(self, node_name: str) -> list[str]:
        """Return nodes directly downstream of the given node."""
        return self._adjacency().get(node_name, [])

    def get_predecessors(self, node_name: str) -> list[str]:
        """Return nodes directly upstream of the given node."""
        return self._reverse_adjacency().get(node_name, [])

    def get_roots(self) -> list[str]:
        """Return nodes with no predecessors (entry points)."""
        has_predecessor: set[str] = set()
        for edge in self.edges:
            has_predecessor.add(edge.target_node)
        return [n for n in self.nodes if n not in has_predecessor]

    def get_leaves(self) -> list[str]:
        """Return nodes with no successors (terminal states)."""
        has_successor: set[str] = set()
        for edge in self.edges:
            has_successor.add(edge.source_node)
        return [n for n in self.nodes if n not in has_successor]

    def topological_sort(self) -> list[str]:
        """Return a topological ordering of node names using Kahn's algorithm."""
        in_degree: dict[str, int] = dict.fromkeys(self.nodes, 0)
        adj = self._adjacency()
        for edge in self.edges:
            in_degree[edge.target_node] = in_degree.get(edge.target_node, 0) + 1

        queue = [n for n in self.nodes if in_degree[n] == 0]
        result: list[str] = []
        while queue:
            queue.sort()
            node = queue.pop(0)
            result.append(node)
            for successor in adj.get(node, []):
                in_degree[successor] -= 1
                if in_degree[successor] == 0:
                    queue.append(successor)
        return result

    def has_cycle(self) -> bool:
        """Check if the graph contains a cycle."""
        return len(self.topological_sort()) != len(self.nodes)

    def get_parallel_branches(self, node_name: str) -> list[list[str]]:
        """Return separate downstream chains from a node with multiple outputs."""
        branches: list[list[str]] = []
        adj = self._adjacency()
        successors = adj.get(node_name, [])
        for successor in successors:
            chain = self._trace_chain(successor, adj)
            branches.append(chain)
        return branches

    def _trace_chain(self, start: str, adj: dict[str, list[str]]) -> list[str]:
        """Trace a linear chain from start until branching or end."""
        chain: list[str] = [start]
        current = start
        while True:
            nexts = adj.get(current, [])
            if len(nexts) != 1:
                break
            current = nexts[0]
            if current in chain:
                break
            chain.append(current)
        return chain

    def get_merge_points(self) -> list[str]:
        """Return nodes that receive edges from multiple predecessors."""
        in_count: dict[str, int] = defaultdict(int)
        for edge in self.edges:
            in_count[edge.target_node] += 1
        return [n for n in self.nodes if in_count[n] > 1]
