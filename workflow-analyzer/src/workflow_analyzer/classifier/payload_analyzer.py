"""Analyzes workflow for potential Step Functions payload size issues."""

import json

from workflow_analyzer.models.classification import ClassifiedNode
from workflow_analyzer.models.graph import WorkflowGraph
from workflow_analyzer.models.n8n_workflow import N8nNode, N8nWorkflow
from workflow_analyzer.models.payload import PayloadAnalysisResult, PayloadWarning


class PayloadAnalyzer:
    """Analyzes payload size risks in a workflow."""

    def __init__(self, payload_limit_kb: int = 256) -> None:
        """Initialize with a configurable payload limit."""
        self._payload_limit_kb = payload_limit_kb

    def analyze(
        self,
        workflow: N8nWorkflow,
        classified_nodes: list[ClassifiedNode],
        graph: WorkflowGraph,
    ) -> PayloadAnalysisResult:
        """Analyze a workflow for payload size warnings."""
        warnings: list[PayloadWarning] = []
        node_map = {cn.node.name: cn for cn in classified_nodes}

        for node in workflow.nodes:
            warnings.extend(self._check_unbounded_list(node))
            warnings.extend(self._check_large_static_payload(node))

        warnings.extend(self._check_large_map_state(workflow, node_map, graph))
        warnings.extend(self._check_accumulation_risk(workflow, node_map, graph))

        return PayloadAnalysisResult(
            warnings=warnings,
            payload_limit_kb=self._payload_limit_kb,
        )

    def _check_unbounded_list(self, node: N8nNode) -> list[PayloadWarning]:
        """Check for nodes that fetch unbounded lists."""
        params = node.parameters
        operation = params.get("operation", "")
        return_all = params.get("returnAll", False)
        has_limit = "limit" in params

        is_list_op = operation in ("getAll", "search", "list", "getMany")

        if is_list_op and (return_all or not has_limit):
            return [
                PayloadWarning(
                    node_name=node.name,
                    warning_type="unbounded_list",
                    description=f"Node '{node.name}' performs a '{operation}' operation without an explicit limit.",
                    severity="high",
                    recommendation="Set an explicit limit on this operation or paginate results.",
                )
            ]
        return []

    def _check_large_static_payload(self, node: N8nNode) -> list[PayloadWarning]:
        """Check for nodes with very large static parameter payloads."""
        param_size = len(json.dumps(node.parameters))
        threshold = (self._payload_limit_kb * 1024) // 2

        if param_size > threshold:
            return [
                PayloadWarning(
                    node_name=node.name,
                    warning_type="large_static_payload",
                    description=f"Node '{node.name}' has parameters of {param_size} bytes, exceeding 50% of the {self._payload_limit_kb}KiB payload limit.",
                    severity="low",
                    recommendation="Consider externalizing large configuration to S3 or SSM Parameter Store.",
                )
            ]
        return []

    def _check_large_map_state(
        self,
        workflow: N8nWorkflow,
        node_map: dict[str, ClassifiedNode],
        graph: WorkflowGraph,
    ) -> list[PayloadWarning]:
        """Check for unbounded data feeding into SplitInBatches (Map state)."""
        warnings: list[PayloadWarning] = []
        for node in workflow.nodes:
            if node.type != "n8n-nodes-base.splitInBatches":
                continue
            predecessors = graph.get_predecessors(node.name)
            for pred_name in predecessors:
                pred_cn = node_map.get(pred_name)
                if pred_cn is None:
                    continue
                pred_params = pred_cn.node.parameters
                operation = pred_params.get("operation", "")
                return_all = pred_params.get("returnAll", False)
                has_limit = "limit" in pred_params
                if operation in ("getAll", "search", "list", "getMany") and (
                    return_all or not has_limit
                ):
                    warnings.append(
                        PayloadWarning(
                            node_name=node.name,
                            warning_type="large_map_state",
                            description=f"SplitInBatches node '{node.name}' receives unbounded data from '{pred_name}'.",
                            severity="medium",
                            recommendation="Consider adding pagination before the Map state or using Distributed Map with S3 for large datasets.",
                        )
                    )
        return warnings

    def _check_accumulation_risk(
        self,
        workflow: N8nWorkflow,
        node_map: dict[str, ClassifiedNode],
        graph: WorkflowGraph,
    ) -> list[PayloadWarning]:
        """Check for merge nodes receiving unbounded upstream data."""
        warnings: list[PayloadWarning] = []
        merge_points = graph.get_merge_points()
        for merge_name in merge_points:
            merge_node = next((n for n in workflow.nodes if n.name == merge_name), None)
            if merge_node is None or merge_node.type != "n8n-nodes-base.merge":
                continue
            predecessors = graph.get_predecessors(merge_name)
            for pred_name in predecessors:
                pred_cn = node_map.get(pred_name)
                if pred_cn is None:
                    continue
                pred_params = pred_cn.node.parameters
                operation = pred_params.get("operation", "")
                return_all = pred_params.get("returnAll", False)
                has_limit = "limit" in pred_params
                if operation in ("getAll", "search", "list", "getMany") and (
                    return_all or not has_limit
                ):
                    warnings.append(
                        PayloadWarning(
                            node_name=merge_name,
                            warning_type="accumulation_risk",
                            description=f"Merge node '{merge_name}' receives unbounded data from '{pred_name}'.",
                            severity="medium",
                            recommendation="Filter or reduce data before merging to stay within the payload limit.",
                        )
                    )
        return warnings
