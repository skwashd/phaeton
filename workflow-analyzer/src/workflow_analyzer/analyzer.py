"""Orchestrator that wires all analysis components together."""

from pathlib import Path
from typing import Any

from phaeton_models.analyzer import ConversionReport

from workflow_analyzer.classifier.node_classifier import NodeClassifier
from workflow_analyzer.classifier.payload_analyzer import PayloadAnalyzer
from workflow_analyzer.expressions.expression_classifier import ExpressionClassifier
from workflow_analyzer.graph.cross_node_detector import detect_cross_node_references
from workflow_analyzer.graph.graph_builder import GraphBuilder
from workflow_analyzer.parser.accessors import WorkflowAccessor
from workflow_analyzer.parser.workflow_parser import WorkflowParser
from workflow_analyzer.report.report_generator import ReportGenerator


class WorkflowAnalyzer:
    """Main entry point for analyzing n8n workflows."""

    def __init__(self, payload_limit_kb: int = 256) -> None:
        """Initialize with configurable payload limit."""
        self._payload_limit_kb = payload_limit_kb

    def analyze(self, workflow_path: Path) -> ConversionReport:
        """Analyze an n8n workflow JSON file and return a conversion report."""
        parser = WorkflowParser()
        workflow = parser.parse_file(workflow_path)

        accessor = WorkflowAccessor(workflow)
        expressions = accessor.get_all_expressions()

        classified_nodes = NodeClassifier().classify_all(workflow.nodes)

        graph = GraphBuilder().build(workflow, expressions)

        cross_refs = detect_cross_node_references(expressions)

        classified_exprs = ExpressionClassifier().classify_all(expressions)

        payload_result = PayloadAnalyzer(
            payload_limit_kb=self._payload_limit_kb
        ).analyze(workflow, classified_nodes, graph)

        return ReportGenerator().generate(
            workflow,
            classified_nodes,
            classified_exprs,
            payload_result,
            graph,
            cross_refs,
        )

    def analyze_dict(self, data: dict[str, Any]) -> ConversionReport:
        """Analyze an n8n workflow from a pre-parsed dictionary."""
        parser = WorkflowParser()
        workflow = parser.parse_dict(data)

        accessor = WorkflowAccessor(workflow)
        expressions = accessor.get_all_expressions()

        classified_nodes = NodeClassifier().classify_all(workflow.nodes)

        graph = GraphBuilder().build(workflow, expressions)

        cross_refs = detect_cross_node_references(expressions)

        classified_exprs = ExpressionClassifier().classify_all(expressions)

        payload_result = PayloadAnalyzer(
            payload_limit_kb=self._payload_limit_kb
        ).analyze(workflow, classified_nodes, graph)

        return ReportGenerator().generate(
            workflow,
            classified_nodes,
            classified_exprs,
            payload_result,
            graph,
            cross_refs,
        )
