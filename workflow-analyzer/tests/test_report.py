"""Tests for report generation and rendering."""

import json
from pathlib import Path

from workflow_analyzer.classifier.node_classifier import NodeClassifier
from workflow_analyzer.classifier.payload_analyzer import PayloadAnalyzer
from workflow_analyzer.expressions.expression_classifier import ExpressionClassifier
from workflow_analyzer.graph.cross_node_detector import detect_cross_node_references
from workflow_analyzer.graph.graph_builder import GraphBuilder
from workflow_analyzer.models.report import ConversionReport
from workflow_analyzer.parser.accessors import WorkflowAccessor
from workflow_analyzer.parser.workflow_parser import WorkflowParser
from workflow_analyzer.report import json_renderer, markdown_renderer
from workflow_analyzer.report.report_generator import ReportGenerator


def _generate_report(fixtures_dir: Path, name: str) -> ConversionReport:
    parser = WorkflowParser()
    wf = parser.parse_file(fixtures_dir / name)
    accessor = WorkflowAccessor(wf)
    expressions = accessor.get_all_expressions()
    classified_nodes = NodeClassifier().classify_all(wf.nodes)
    builder = GraphBuilder()
    graph = builder.build(wf, expressions)
    cross_refs = detect_cross_node_references(expressions)
    classified_exprs = ExpressionClassifier().classify_all(expressions)
    payload_result = PayloadAnalyzer().analyze(wf, classified_nodes, graph)
    generator = ReportGenerator()
    return generator.generate(
        wf, classified_nodes, classified_exprs, payload_result, graph, cross_refs
    )


def test_report_simple_linear(fixtures_dir: Path) -> None:
    report = _generate_report(fixtures_dir, "simple_linear.json")
    assert report.total_nodes == 4
    assert report.source_workflow_name == "Simple Linear Workflow"
    assert report.analyzer_version == "0.1.0"


def test_report_confidence_between_0_and_100(fixtures_dir: Path) -> None:
    for name in ["simple_linear.json", "branching.json", "merge_workflow.json"]:
        report = _generate_report(fixtures_dir, name)
        assert 0 <= report.confidence_score <= 100


def test_report_no_unsupported_in_fixtures(fixtures_dir: Path) -> None:
    for name in ["simple_linear.json", "branching.json", "merge_workflow.json"]:
        report = _generate_report(fixtures_dir, name)
        assert len(report.unsupported_nodes) == 0


def test_report_trigger_nodes(fixtures_dir: Path) -> None:
    report = _generate_report(fixtures_dir, "simple_linear.json")
    assert len(report.trigger_nodes) == 1
    assert report.trigger_nodes[0].node.name == "Manual Trigger"


def test_report_credentials(fixtures_dir: Path) -> None:
    report = _generate_report(fixtures_dir, "simple_linear.json")
    assert "httpBasicAuth" in report.required_credentials


def test_report_graph_metadata(fixtures_dir: Path) -> None:
    report = _generate_report(fixtures_dir, "simple_linear.json")
    assert "root_nodes" in report.graph_metadata
    assert "leaf_nodes" in report.graph_metadata
    assert report.graph_metadata["has_cycles"] is False


def test_markdown_renderer(fixtures_dir: Path) -> None:
    report = _generate_report(fixtures_dir, "simple_linear.json")
    md = markdown_renderer.render(report)
    assert "# Conversion Feasibility Report" in md
    assert "## Summary" in md
    assert "## Node Classification" in md
    assert "## Expression Analysis" in md
    assert "## Recommendations" in md
    assert str(report.confidence_score) in md


def test_json_renderer_roundtrip(fixtures_dir: Path) -> None:
    report = _generate_report(fixtures_dir, "simple_linear.json")
    json_str = json_renderer.render(report)
    data = json.loads(json_str)
    restored = ConversionReport.model_validate(data)
    assert restored.source_workflow_name == report.source_workflow_name
    assert restored.total_nodes == report.total_nodes
    assert restored.confidence_score == report.confidence_score


def test_report_cross_references(fixtures_dir: Path) -> None:
    report = _generate_report(fixtures_dir, "cross_references.json")
    assert len(report.cross_node_references) > 0


def test_report_branching(fixtures_dir: Path) -> None:
    report = _generate_report(fixtures_dir, "branching.json")
    assert report.total_nodes == 5
    assert len(report.classified_nodes) == 5


def test_markdown_cross_references(fixtures_dir: Path) -> None:
    report = _generate_report(fixtures_dir, "cross_references.json")
    md = markdown_renderer.render(report)
    assert "## Cross-Node References" in md
    assert "Fetch Config" in md


def test_markdown_credentials(fixtures_dir: Path) -> None:
    report = _generate_report(fixtures_dir, "simple_linear.json")
    md = markdown_renderer.render(report)
    assert "## Required Credentials" in md
    assert "httpBasicAuth" in md


def test_markdown_api_clients(fixtures_dir: Path) -> None:
    report = _generate_report(fixtures_dir, "simple_linear.json")
    md = markdown_renderer.render(report)
    assert "## Required API Clients" in md


def test_markdown_low_confidence() -> None:
    from datetime import UTC, datetime

    from workflow_analyzer.models.classification import ClassifiedNode, NodeCategory
    from workflow_analyzer.models.n8n_workflow import N8nNode

    node = N8nNode.model_validate(
        {
            "id": "1",
            "name": "Test",
            "type": "community.unsupported",
            "typeVersion": 1,
            "position": [0, 0],
        }
    )
    cn = ClassifiedNode(
        node=node,
        category=NodeCategory.UNSUPPORTED,
        translation_strategy="Manual",
    )
    report = ConversionReport(
        source_workflow_name="Low Confidence",
        analyzer_version="0.1.0",
        timestamp=datetime.now(tz=UTC),
        total_nodes=1,
        classification_summary={NodeCategory.UNSUPPORTED: 1},
        classified_nodes=[cn],
        expression_summary={},
        classified_expressions=[],
        payload_warnings=[],
        cross_node_references=[],
        unsupported_nodes=[cn],
        trigger_nodes=[],
        sub_workflows_detected=[],
        required_picofun_clients=[],
        required_credentials=[],
        confidence_score=0.0,
        blocking_issues=["Unsupported node 'Test' (type: community.unsupported)"],
        graph_metadata={},
    )
    md = markdown_renderer.render(report)
    assert "low confidence" in md.lower()
    assert "Unsupported node" in md


def test_markdown_moderate_confidence() -> None:
    from datetime import UTC, datetime

    report = ConversionReport(
        source_workflow_name="Moderate",
        analyzer_version="0.1.0",
        timestamp=datetime.now(tz=UTC),
        total_nodes=2,
        classification_summary={},
        classified_nodes=[],
        expression_summary={},
        classified_expressions=[],
        payload_warnings=[],
        cross_node_references=[],
        unsupported_nodes=[],
        trigger_nodes=[],
        sub_workflows_detected=[],
        required_picofun_clients=[],
        required_credentials=[],
        confidence_score=60.0,
        blocking_issues=[],
        graph_metadata={},
    )
    md = markdown_renderer.render(report)
    assert "moderate confidence" in md.lower()
