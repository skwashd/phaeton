"""Tests for payload size analyzer."""

from pathlib import Path

from workflow_analyzer.classifier.node_classifier import NodeClassifier
from workflow_analyzer.classifier.payload_analyzer import PayloadAnalyzer
from workflow_analyzer.graph.graph_builder import GraphBuilder
from workflow_analyzer.models.n8n_workflow import N8nWorkflow
from workflow_analyzer.parser.accessors import WorkflowAccessor
from workflow_analyzer.parser.workflow_parser import WorkflowParser


def _make_workflow_with_node(
    node_type: str, parameters: dict, name: str = "TestNode"
) -> tuple:
    data = {
        "nodes": [
            {
                "id": "1",
                "name": name,
                "type": node_type,
                "typeVersion": 1,
                "position": [0, 0],
                "parameters": parameters,
            }
        ],
        "connections": {},
    }
    wf = N8nWorkflow.model_validate(data)
    classifier = NodeClassifier()
    classified = classifier.classify_all(wf.nodes)
    accessor = WorkflowAccessor(wf)
    builder = GraphBuilder()
    graph = builder.build(wf, accessor.get_all_expressions())
    return wf, classified, graph


def test_unbounded_list_warning() -> None:
    wf, classified, graph = _make_workflow_with_node(
        "n8n-nodes-base.httpRequest",
        {"operation": "getAll", "returnAll": True},
    )
    analyzer = PayloadAnalyzer()
    result = analyzer.analyze(wf, classified, graph)
    unbounded = [w for w in result.warnings if w.warning_type == "unbounded_list"]
    assert len(unbounded) == 1
    assert unbounded[0].severity == "high"


def test_no_warning_with_limit() -> None:
    wf, classified, graph = _make_workflow_with_node(
        "n8n-nodes-base.httpRequest",
        {"operation": "getAll", "limit": 100},
    )
    analyzer = PayloadAnalyzer()
    result = analyzer.analyze(wf, classified, graph)
    unbounded = [w for w in result.warnings if w.warning_type == "unbounded_list"]
    assert len(unbounded) == 0


def test_large_static_payload() -> None:
    # Create a large parameters dict
    large_params = {"data": "x" * 200_000}
    wf, classified, graph = _make_workflow_with_node("n8n-nodes-base.set", large_params)
    analyzer = PayloadAnalyzer()
    result = analyzer.analyze(wf, classified, graph)
    large = [w for w in result.warnings if w.warning_type == "large_static_payload"]
    assert len(large) == 1
    assert large[0].severity == "low"


def test_configurable_payload_limit() -> None:
    # With a 1KB limit, even a moderate payload triggers warning
    params = {"data": "x" * 600}
    wf, classified, graph = _make_workflow_with_node("n8n-nodes-base.set", params)
    analyzer = PayloadAnalyzer(payload_limit_kb=1)
    result = analyzer.analyze(wf, classified, graph)
    assert result.payload_limit_kb == 1
    large = [w for w in result.warnings if w.warning_type == "large_static_payload"]
    assert len(large) == 1


def test_simple_fixtures_minimal_warnings(fixtures_dir: Path) -> None:
    parser = WorkflowParser()
    classifier = NodeClassifier()
    analyzer = PayloadAnalyzer()
    for name in ["simple_linear.json", "branching.json"]:
        wf = parser.parse_file(fixtures_dir / name)
        classified = classifier.classify_all(wf.nodes)
        accessor = WorkflowAccessor(wf)
        builder = GraphBuilder()
        graph = builder.build(wf, accessor.get_all_expressions())
        result = analyzer.analyze(wf, classified, graph)
        # These simple workflows shouldn't have payload warnings
        assert len(result.warnings) == 0


def test_getall_without_limit_or_returnall() -> None:
    wf, classified, graph = _make_workflow_with_node(
        "n8n-nodes-base.httpRequest",
        {"operation": "getAll"},
    )
    analyzer = PayloadAnalyzer()
    result = analyzer.analyze(wf, classified, graph)
    unbounded = [w for w in result.warnings if w.warning_type == "unbounded_list"]
    assert len(unbounded) == 1
