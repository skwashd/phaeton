"""Generates conversion feasibility reports from analysis results."""

from datetime import UTC, datetime

import workflow_analyzer
from workflow_analyzer.graph.cross_node_detector import CrossNodeReference
from workflow_analyzer.models.classification import ClassifiedNode, NodeCategory
from workflow_analyzer.models.expression import ClassifiedExpression, ExpressionCategory
from workflow_analyzer.models.graph import WorkflowGraph
from workflow_analyzer.models.n8n_workflow import N8nWorkflow
from workflow_analyzer.models.payload import PayloadAnalysisResult
from workflow_analyzer.models.report import ConversionReport


class ReportGenerator:
    """Generates a ConversionReport from analysis outputs."""

    def generate(
        self,
        workflow: N8nWorkflow,
        classified_nodes: list[ClassifiedNode],
        classified_expressions: list[ClassifiedExpression],
        payload_result: PayloadAnalysisResult,
        graph: WorkflowGraph,
        cross_node_refs: list[CrossNodeReference],
    ) -> ConversionReport:
        """Generate a complete conversion report."""
        classification_summary = self._count_categories(classified_nodes)
        expression_summary = self._count_expression_categories(classified_expressions)
        unsupported = [
            cn for cn in classified_nodes if cn.category == NodeCategory.UNSUPPORTED
        ]
        triggers = [
            cn for cn in classified_nodes if cn.category == NodeCategory.TRIGGER
        ]
        sub_workflows = [
            cn.node.name
            for cn in classified_nodes
            if cn.node.type == "n8n-nodes-base.executeWorkflow"
        ]
        picofun_clients = self._extract_picofun_clients(classified_nodes)
        credentials = self._extract_credentials(workflow)
        confidence = self._compute_confidence(classified_nodes, classified_expressions)
        blocking = [
            f"Unsupported node '{cn.node.name}' (type: {cn.node.type})"
            for cn in unsupported
        ]

        return ConversionReport(
            source_workflow_name=workflow.name or "Unnamed Workflow",
            source_n8n_version=None,
            analyzer_version=workflow_analyzer.__version__,
            timestamp=datetime.now(tz=UTC),
            total_nodes=len(workflow.nodes),
            classification_summary=classification_summary,
            classified_nodes=classified_nodes,
            expression_summary=expression_summary,
            classified_expressions=classified_expressions,
            payload_warnings=payload_result.warnings,
            cross_node_references=[ref.model_dump() for ref in cross_node_refs],
            unsupported_nodes=unsupported,
            trigger_nodes=triggers,
            sub_workflows_detected=sub_workflows,
            required_picofun_clients=picofun_clients,
            required_credentials=credentials,
            confidence_score=confidence,
            blocking_issues=blocking,
            graph_metadata={
                "root_nodes": graph.get_roots(),
                "leaf_nodes": graph.get_leaves(),
                "merge_points": graph.get_merge_points(),
                "has_cycles": graph.has_cycle(),
            },
        )

    def _count_categories(
        self, classified_nodes: list[ClassifiedNode]
    ) -> dict[NodeCategory, int]:
        """Count nodes per category."""
        counts: dict[NodeCategory, int] = {}
        for cn in classified_nodes:
            counts[cn.category] = counts.get(cn.category, 0) + 1
        return counts

    def _count_expression_categories(
        self, expressions: list[ClassifiedExpression]
    ) -> dict[ExpressionCategory, int]:
        """Count expressions per category."""
        counts: dict[ExpressionCategory, int] = {}
        for ce in expressions:
            counts[ce.category] = counts.get(ce.category, 0) + 1
        return counts

    def _extract_picofun_clients(
        self, classified_nodes: list[ClassifiedNode]
    ) -> list[str]:
        """Extract unique PicoFun client service names."""
        services: set[str] = set()
        for cn in classified_nodes:
            if cn.category == NodeCategory.PICOFUN_API:
                parts = cn.node.type.split(".")
                if len(parts) >= 2:
                    services.add(parts[-1])
        return sorted(services)

    def _extract_credentials(self, workflow: N8nWorkflow) -> list[str]:
        """Extract unique credential types from all nodes."""
        cred_types: set[str] = set()
        for node in workflow.nodes:
            if node.credentials:
                for cred_type in node.credentials:
                    cred_types.add(cred_type)
        return sorted(cred_types)

    def _compute_confidence(
        self,
        classified_nodes: list[ClassifiedNode],
        classified_expressions: list[ClassifiedExpression],
    ) -> float:
        """Compute the conversion confidence score as a percentage."""
        total = len(classified_nodes) + len(classified_expressions)
        if total == 0:
            return 100.0

        deterministic_nodes = sum(
            1 for cn in classified_nodes if cn.category != NodeCategory.UNSUPPORTED
        )
        category_a = sum(
            1
            for ce in classified_expressions
            if ce.category == ExpressionCategory.JSONATA_DIRECT
        )
        return round((deterministic_nodes + category_a) / total * 100, 1)
