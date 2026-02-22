"""Items model adaptation (Patterns 1-4).

Analyzes a workflow graph and determines which n8n items-model pattern applies
to each segment, then restructures the graph accordingly:

- Pattern 1: Single-item flow (no wrapping needed)
- Pattern 2: List processing (Map state wrapping)
- Pattern 3: Multi-branch merge (Parallel + Pass)
- Pattern 4: Accumulation across nodes (Variables)
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from n8n_to_sfn.models.analysis import (
    WorkflowAnalysis,
)


class ItemsPattern(StrEnum):
    """Detected items-model pattern for a workflow segment."""

    SINGLE_ITEM = "SINGLE_ITEM"
    LIST_PROCESSING = "LIST_PROCESSING"
    MULTI_BRANCH_MERGE = "MULTI_BRANCH_MERGE"
    ACCUMULATION = "ACCUMULATION"


class SegmentInfo(BaseModel):
    """Information about a detected workflow segment and its pattern."""

    pattern: ItemsPattern
    node_names: list[str]
    root_node: str
    details: dict[str, str] = {}


_LIST_OPERATIONS = {"getAll", "search", "list", "scan", "query"}


class ItemsModelAdapter:
    """Analyzes workflow graphs and detects items-model patterns."""

    def analyze(self, analysis: WorkflowAnalysis) -> list[SegmentInfo]:
        """Detect items-model patterns in the workflow."""
        segments: list[SegmentInfo] = []

        merge_points = self._find_merge_points(analysis)
        list_producers = self._find_list_producers(analysis)
        accumulation_nodes = self._find_accumulation_nodes(analysis)

        # Pattern 3: Multi-branch merge
        for merge_node in merge_points:
            branches = self._get_incoming_branches(merge_node, analysis)
            if len(branches) >= 2:
                all_nodes = [merge_node]
                for branch in branches:
                    all_nodes.extend(branch)
                segments.append(
                    SegmentInfo(
                        pattern=ItemsPattern.MULTI_BRANCH_MERGE,
                        node_names=all_nodes,
                        root_node=merge_node,
                        details={"branch_count": str(len(branches))},
                    )
                )

        # Pattern 2: List processing
        for producer in list_producers:
            downstream = self._get_downstream_chain(producer, analysis)
            segments.append(
                SegmentInfo(
                    pattern=ItemsPattern.LIST_PROCESSING,
                    node_names=[producer, *downstream],
                    root_node=producer,
                )
            )

        # Pattern 4: Accumulation
        if accumulation_nodes:
            segments.append(
                SegmentInfo(
                    pattern=ItemsPattern.ACCUMULATION,
                    node_names=accumulation_nodes,
                    root_node=accumulation_nodes[0],
                )
            )

        # Pattern 1: Anything not covered → single-item
        covered = set()
        for seg in segments:
            covered.update(seg.node_names)
        uncovered = [
            cn.node.name
            for cn in analysis.classified_nodes
            if cn.node.name not in covered
        ]
        if uncovered:
            segments.append(
                SegmentInfo(
                    pattern=ItemsPattern.SINGLE_ITEM,
                    node_names=uncovered,
                    root_node=uncovered[0],
                )
            )

        return segments

    @staticmethod
    def _find_merge_points(analysis: WorkflowAnalysis) -> list[str]:
        """Find nodes with multiple incoming CONNECTION edges."""
        in_count: dict[str, int] = {}
        for edge in analysis.dependency_edges:
            if edge.edge_type == "CONNECTION":
                in_count[edge.to_node] = in_count.get(edge.to_node, 0) + 1
        return [name for name, count in in_count.items() if count > 1]

    @staticmethod
    def _find_list_producers(analysis: WorkflowAnalysis) -> list[str]:
        """Find nodes whose operation produces a list."""
        producers: list[str] = []
        for cn in analysis.classified_nodes:
            op = cn.node.parameters.get("operation", "")
            if op in _LIST_OPERATIONS:
                producers.append(cn.node.name)
        return producers

    @staticmethod
    def _find_accumulation_nodes(analysis: WorkflowAnalysis) -> list[str]:
        """Find nodes involved in accumulation patterns (using variables)."""
        if not analysis.variables_needed:
            return []
        return list(analysis.variables_needed.values())

    @staticmethod
    def _get_incoming_branches(
        node_name: str, analysis: WorkflowAnalysis
    ) -> list[list[str]]:
        """Get the upstream branches leading into a merge point."""
        predecessors: list[str] = []
        for edge in analysis.dependency_edges:
            if edge.to_node == node_name and edge.edge_type == "CONNECTION":
                predecessors.append(edge.from_node)

        branches: list[list[str]] = []
        for pred in predecessors:
            chain = [pred]
            current = pred
            while True:
                prev = [
                    e.from_node
                    for e in analysis.dependency_edges
                    if e.to_node == current and e.edge_type == "CONNECTION"
                ]
                if len(prev) != 1:
                    break
                current = prev[0]
                chain.append(current)
            branches.append(chain)
        return branches

    @staticmethod
    def _get_downstream_chain(node_name: str, analysis: WorkflowAnalysis) -> list[str]:
        """Get the linear downstream chain from a node."""
        chain: list[str] = []
        current = node_name
        while True:
            nexts = [
                e.to_node
                for e in analysis.dependency_edges
                if e.from_node == current and e.edge_type == "CONNECTION"
            ]
            if len(nexts) != 1:
                break
            current = nexts[0]
            if current in chain:
                break
            chain.append(current)
        return chain
