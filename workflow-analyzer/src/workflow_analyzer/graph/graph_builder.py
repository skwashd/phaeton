"""Builds a dependency graph from an n8n workflow."""

import logging

from workflow_analyzer.graph.cross_node_detector import (
    CrossNodeReference,
    detect_cross_node_references,
)
from workflow_analyzer.models.graph import DependencyEdge, WorkflowGraph
from workflow_analyzer.models.n8n_workflow import N8nNode, N8nWorkflow

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Constructs a WorkflowGraph from workflow connections and expression references."""

    def build(
        self,
        workflow: N8nWorkflow,
        expressions: list[tuple[N8nNode, str, str]],
    ) -> WorkflowGraph:
        """Build a dependency graph from the workflow and its expressions."""
        node_names = [n.name for n in workflow.nodes]
        node_name_set = set(node_names)
        edges: list[DependencyEdge] = []

        # Step 1: Add edges from explicit connections
        for source_name, conn_map in workflow.connections.items():
            for _conn_type, output_lists in conn_map.items():
                for output_idx, target_list in enumerate(output_lists):
                    for target in target_list:
                        if target.node in node_name_set:
                            edges.append(
                                DependencyEdge(
                                    source_node=source_name,
                                    target_node=target.node,
                                    edge_type="connection",
                                    output_index=output_idx,
                                    input_index=target.index,
                                )
                            )

        # Step 2: Add edges from cross-node data references
        cross_refs = detect_cross_node_references(expressions)
        edges.extend(self._cross_ref_edges(cross_refs, node_name_set))

        graph = WorkflowGraph(nodes=node_names, edges=edges)

        # Step 3: Validate DAG
        if graph.has_cycle():
            logger.warning("Workflow graph contains a cycle")

        return graph

    def _cross_ref_edges(
        self,
        refs: list[CrossNodeReference],
        node_name_set: set[str],
    ) -> list[DependencyEdge]:
        """Convert cross-node references to dependency edges."""
        edges: list[DependencyEdge] = []
        seen: set[tuple[str, str]] = set()
        for ref in refs:
            if ref.source_node_name not in node_name_set:
                continue
            key = (ref.source_node_name, ref.target_node_name)
            if key not in seen:
                edges.append(
                    DependencyEdge(
                        source_node=ref.source_node_name,
                        target_node=ref.target_node_name,
                        edge_type="data_reference",
                    )
                )
                seen.add(key)
        return edges
