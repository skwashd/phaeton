"""Tests for n8n workflow Pydantic models."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from workflow_analyzer.models.n8n_workflow import (
    ConnectionTarget,
    N8nNode,
    N8nWorkflow,
)


def _load_fixture(fixtures_dir: Path, name: str) -> N8nWorkflow:
    data = json.loads((fixtures_dir / name).read_text())
    return N8nWorkflow.model_validate(data)


def test_parse_simple_linear(fixtures_dir: Path) -> None:
    wf = _load_fixture(fixtures_dir, "simple_linear.json")
    assert len(wf.nodes) == 4
    assert wf.nodes[0].type == "n8n-nodes-base.manualTrigger"
    assert wf.nodes[0].name == "Manual Trigger"
    assert wf.name == "Simple Linear Workflow"


def test_parse_branching(fixtures_dir: Path) -> None:
    wf = _load_fixture(fixtures_dir, "branching.json")
    assert len(wf.nodes) == 5
    node_types = [n.type for n in wf.nodes]
    assert "n8n-nodes-base.if" in node_types


def test_parse_merge_workflow(fixtures_dir: Path) -> None:
    wf = _load_fixture(fixtures_dir, "merge_workflow.json")
    assert len(wf.nodes) == 5
    node_types = [n.type for n in wf.nodes]
    assert "n8n-nodes-base.merge" in node_types


def test_connection_targets(fixtures_dir: Path) -> None:
    wf = _load_fixture(fixtures_dir, "simple_linear.json")
    trigger_conns = wf.connections["Manual Trigger"]["main"][0]
    assert len(trigger_conns) == 1
    target = trigger_conns[0]
    assert isinstance(target, ConnectionTarget)
    assert target.node == "Set"
    assert target.type == "main"
    assert target.index == 0


def test_branching_connections(fixtures_dir: Path) -> None:
    wf = _load_fixture(fixtures_dir, "branching.json")
    if_outputs = wf.connections["Check Status"]["main"]
    assert len(if_outputs) == 2
    assert if_outputs[0][0].node == "Send Welcome Email"
    assert if_outputs[1][0].node == "Log Inactive"


def test_node_fields(fixtures_dir: Path) -> None:
    wf = _load_fixture(fixtures_dir, "simple_linear.json")
    http_node = next(n for n in wf.nodes if n.name == "HTTP Request")
    assert http_node.type_version == 4.2
    assert http_node.credentials is not None
    assert "httpBasicAuth" in http_node.credentials
    assert http_node.parameters["method"] == "POST"


def test_workflow_settings(fixtures_dir: Path) -> None:
    wf = _load_fixture(fixtures_dir, "simple_linear.json")
    assert wf.settings is not None
    assert wf.settings.execution_order == "v1"
    assert wf.settings.timezone == "America/New_York"


def test_invalid_json_missing_nodes() -> None:
    with pytest.raises(ValidationError):
        N8nWorkflow.model_validate({"connections": {}})


def test_invalid_node_missing_required() -> None:
    with pytest.raises(ValidationError):
        N8nNode.model_validate({"id": "1", "name": "test"})


def test_extra_fields_allowed(fixtures_dir: Path) -> None:
    data = json.loads((fixtures_dir / "simple_linear.json").read_text())
    data["customField"] = "extra"
    wf = N8nWorkflow.model_validate(data)
    assert wf.name == "Simple Linear Workflow"


def test_optional_fields_default_none() -> None:
    node = N8nNode.model_validate(
        {
            "id": "1",
            "name": "Test",
            "type": "n8n-nodes-base.noOp",
            "typeVersion": 1,
            "position": [0, 0],
        }
    )
    assert node.disabled is None
    assert node.credentials is None
    assert node.notes is None
    assert node.continue_on_fail is None
