"""Tests for the workflow parser and accessor modules."""

import json
from pathlib import Path

import pytest

from workflow_analyzer.models.exceptions import WorkflowParseError
from workflow_analyzer.parser.accessors import WorkflowAccessor
from workflow_analyzer.parser.workflow_parser import WorkflowParser


@pytest.fixture
def parser() -> WorkflowParser:
    return WorkflowParser()


def test_parse_file_simple_linear(parser: WorkflowParser, fixtures_dir: Path) -> None:
    wf = parser.parse_file(fixtures_dir / "simple_linear.json")
    assert len(wf.nodes) == 4
    assert wf.name == "Simple Linear Workflow"


def test_parse_file_branching(parser: WorkflowParser, fixtures_dir: Path) -> None:
    wf = parser.parse_file(fixtures_dir / "branching.json")
    assert len(wf.nodes) == 5


def test_parse_file_merge(parser: WorkflowParser, fixtures_dir: Path) -> None:
    wf = parser.parse_file(fixtures_dir / "merge_workflow.json")
    assert len(wf.nodes) == 5


def test_parse_string(parser: WorkflowParser, fixtures_dir: Path) -> None:
    text = (fixtures_dir / "simple_linear.json").read_text()
    wf = parser.parse_string(text)
    assert wf.name == "Simple Linear Workflow"


def test_parse_dict(parser: WorkflowParser, fixtures_dir: Path) -> None:
    data = json.loads((fixtures_dir / "simple_linear.json").read_text())
    wf = parser.parse_dict(data)
    assert wf.name == "Simple Linear Workflow"


def test_parse_error_invalid_json(parser: WorkflowParser) -> None:
    with pytest.raises(WorkflowParseError, match="Invalid JSON") as exc_info:
        parser.parse_string("{not valid json}")
    assert exc_info.value.original_error is not None


def test_parse_error_missing_fields(parser: WorkflowParser) -> None:
    with pytest.raises(WorkflowParseError, match="Workflow validation failed"):
        parser.parse_string('{"connections": {}}')


def test_parse_error_nonexistent_file(parser: WorkflowParser) -> None:
    with pytest.raises(WorkflowParseError, match="Failed to read"):
        parser.parse_file(Path("/nonexistent/file.json"))


# --- Accessor tests ---


def _accessor_from_fixture(
    parser: WorkflowParser, fixtures_dir: Path, name: str
) -> WorkflowAccessor:
    wf = parser.parse_file(fixtures_dir / name)
    return WorkflowAccessor(wf)


def test_get_node_by_name(parser: WorkflowParser, fixtures_dir: Path) -> None:
    acc = _accessor_from_fixture(parser, fixtures_dir, "simple_linear.json")
    node = acc.get_node_by_name("Set")
    assert node is not None
    assert node.type == "n8n-nodes-base.set"


def test_get_node_by_name_missing(parser: WorkflowParser, fixtures_dir: Path) -> None:
    acc = _accessor_from_fixture(parser, fixtures_dir, "simple_linear.json")
    assert acc.get_node_by_name("Nonexistent") is None


def test_get_node_by_id(parser: WorkflowParser, fixtures_dir: Path) -> None:
    acc = _accessor_from_fixture(parser, fixtures_dir, "simple_linear.json")
    node = acc.get_node_by_id("a1b2c3d4-0001-4000-8000-000000000001")
    assert node is not None
    assert node.name == "Manual Trigger"


def test_get_nodes_by_type(parser: WorkflowParser, fixtures_dir: Path) -> None:
    acc = _accessor_from_fixture(parser, fixtures_dir, "branching.json")
    ses_nodes = acc.get_nodes_by_type("n8n-nodes-base.awsSes")
    assert len(ses_nodes) == 1
    assert ses_nodes[0].name == "Send Welcome Email"


def test_get_downstream_nodes(parser: WorkflowParser, fixtures_dir: Path) -> None:
    acc = _accessor_from_fixture(parser, fixtures_dir, "simple_linear.json")
    downstream = acc.get_downstream_nodes("Set")
    assert len(downstream) == 1
    assert downstream[0].name == "HTTP Request"


def test_get_downstream_nodes_branching(
    parser: WorkflowParser, fixtures_dir: Path
) -> None:
    acc = _accessor_from_fixture(parser, fixtures_dir, "branching.json")
    downstream = acc.get_downstream_nodes("Check Status")
    names = {n.name for n in downstream}
    assert names == {"Send Welcome Email", "Log Inactive"}


def test_get_upstream_nodes(parser: WorkflowParser, fixtures_dir: Path) -> None:
    acc = _accessor_from_fixture(parser, fixtures_dir, "simple_linear.json")
    upstream = acc.get_upstream_nodes("HTTP Request")
    assert len(upstream) == 1
    assert upstream[0].name == "Set"


def test_get_upstream_nodes_merge(parser: WorkflowParser, fixtures_dir: Path) -> None:
    acc = _accessor_from_fixture(parser, fixtures_dir, "merge_workflow.json")
    upstream = acc.get_upstream_nodes("Merge")
    names = {n.name for n in upstream}
    assert names == {"Fetch Details", "Enrich Data"}


def test_get_trigger_nodes(parser: WorkflowParser, fixtures_dir: Path) -> None:
    acc = _accessor_from_fixture(parser, fixtures_dir, "simple_linear.json")
    triggers = acc.get_trigger_nodes()
    assert len(triggers) == 1
    assert triggers[0].name == "Manual Trigger"


def test_get_trigger_nodes_webhook(parser: WorkflowParser, fixtures_dir: Path) -> None:
    acc = _accessor_from_fixture(parser, fixtures_dir, "merge_workflow.json")
    triggers = acc.get_trigger_nodes()
    assert len(triggers) == 1
    assert triggers[0].name == "Webhook"


def test_get_all_expressions(parser: WorkflowParser, fixtures_dir: Path) -> None:
    acc = _accessor_from_fixture(parser, fixtures_dir, "simple_linear.json")
    expressions = acc.get_all_expressions()
    assert len(expressions) > 0
    # Verify expressions are found in nested parameters
    expr_strings = [e[2] for e in expressions]
    assert any("$json.name" in s for s in expr_strings)
    assert any("toISOString" in s for s in expr_strings)


def test_get_all_expressions_nested(parser: WorkflowParser, fixtures_dir: Path) -> None:
    acc = _accessor_from_fixture(parser, fixtures_dir, "simple_linear.json")
    expressions = acc.get_all_expressions()
    # The HTTP Request node has an expression nested in bodyParameters.parameters[0].value
    http_exprs = [(n, p, e) for n, p, e in expressions if n.name == "HTTP Request"]
    assert len(http_exprs) > 0
    paths = [p for _, p, _ in http_exprs]
    assert any("bodyParameters" in p for p in paths)


def test_get_all_expressions_branching(
    parser: WorkflowParser, fixtures_dir: Path
) -> None:
    acc = _accessor_from_fixture(parser, fixtures_dir, "branching.json")
    expressions = acc.get_all_expressions()
    assert len(expressions) > 0
    # The IF node has an expression in conditions
    node_names = {n.name for n, _, _ in expressions}
    assert "Check Status" in node_names
