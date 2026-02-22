"""Accessor utilities for navigating a parsed n8n workflow."""

import re

from workflow_analyzer.models.n8n_workflow import N8nNode, N8nWorkflow

_EXPRESSION_PATTERN = re.compile(r"\{\{.*?\}\}", re.DOTALL)
_EXPRESSION_PREFIX = "="


class WorkflowAccessor:
    """Provides convenient lookup methods over a parsed N8nWorkflow."""

    def __init__(self, workflow: N8nWorkflow) -> None:
        """Initialize with a parsed workflow."""
        self._workflow = workflow
        self._nodes_by_name: dict[str, N8nNode] = {n.name: n for n in workflow.nodes}
        self._nodes_by_id: dict[str, N8nNode] = {n.id: n for n in workflow.nodes}

    def get_node_by_name(self, name: str) -> N8nNode | None:
        """Look up a node by its display name."""
        return self._nodes_by_name.get(name)

    def get_node_by_id(self, node_id: str) -> N8nNode | None:
        """Look up a node by its unique id."""
        return self._nodes_by_id.get(node_id)

    def get_nodes_by_type(self, type_str: str) -> list[N8nNode]:
        """Return all nodes matching a given type string."""
        return [n for n in self._workflow.nodes if n.type == type_str]

    def get_downstream_nodes(self, node_name: str) -> list[N8nNode]:
        """Return the immediate downstream nodes connected from a given node."""
        conns = self._workflow.connections.get(node_name, {})
        result: list[N8nNode] = []
        seen: set[str] = set()
        for output_lists in conns.values():
            for target_list in output_lists:
                for target in target_list:
                    if target.node not in seen:
                        node = self.get_node_by_name(target.node)
                        if node is not None:
                            result.append(node)
                            seen.add(target.node)
        return result

    def get_upstream_nodes(self, node_name: str) -> list[N8nNode]:
        """Return nodes that connect into the given node."""
        result: list[N8nNode] = []
        seen: set[str] = set()
        for source_name, conn_map in self._workflow.connections.items():
            for output_lists in conn_map.values():
                for target_list in output_lists:
                    for target in target_list:
                        if target.node == node_name and source_name not in seen:
                            node = self.get_node_by_name(source_name)
                            if node is not None:
                                result.append(node)
                                seen.add(source_name)
        return result

    def get_trigger_nodes(self) -> list[N8nNode]:
        """Return nodes whose type contains 'Trigger' or 'trigger'."""
        return [
            n
            for n in self._workflow.nodes
            if "trigger" in n.type.lower() or "webhook" in n.type.lower()
        ]

    def get_all_expressions(self) -> list[tuple[N8nNode, str, str]]:
        """Extract all n8n expressions from every node's parameters."""
        results: list[tuple[N8nNode, str, str]] = []
        for node in self._workflow.nodes:
            self._walk_params(node, node.parameters, "", results)
        return results

    def _walk_params(
        self,
        node: N8nNode,
        obj: str | dict | list | int | float | bool | None,
        path: str,
        results: list[tuple[N8nNode, str, str]],
    ) -> None:
        """Recursively walk parameters to find expression strings."""
        if isinstance(obj, str):
            if self._is_expression(obj):
                results.append((node, path, obj))
        elif isinstance(obj, dict):
            for key, value in obj.items():
                child_path = f"{path}.{key}" if path else key
                self._walk_params(node, value, child_path, results)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                child_path = f"{path}[{i}]"
                self._walk_params(node, item, child_path, results)

    @staticmethod
    def _is_expression(value: str) -> bool:
        """Check if a string is an n8n expression."""
        if value.startswith(_EXPRESSION_PREFIX):
            return True
        return bool(_EXPRESSION_PATTERN.search(value))
