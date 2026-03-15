"""Tests for shared n8n workflow models."""

import json

from phaeton_models import ConnectionTarget, N8nNode, N8nWorkflow, WorkflowSettings

_FULL_NODE_JSON = json.dumps(
    {
        "id": "abc-123",
        "name": "HTTP Request",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [250, 300],
        "parameters": {"url": "https://api.example.com", "method": "POST"},
        "credentials": {"httpBasicAuth": {"id": "1", "name": "My Creds"}},
        "disabled": False,
        "notes": "Calls the API",
        "continueOnFail": True,
        "onError": "continueRegularOutput",
        "retryOnFail": True,
        "maxTries": 3,
        "waitBetweenTries": 2000,
        "executeOnce": False,
    }
)


def test_n8n_node_round_trip_all_aliased_fields() -> None:
    """Create N8nNode from JSON, serialize back, and verify round-trip fidelity."""
    node = N8nNode.model_validate_json(_FULL_NODE_JSON)

    assert node.id == "abc-123"
    assert node.name == "HTTP Request"
    assert node.type == "n8n-nodes-base.httpRequest"
    assert node.type_version == 4.2
    assert node.position == [250, 300]
    assert node.parameters["method"] == "POST"
    assert node.credentials is not None
    assert node.disabled is False
    assert node.notes == "Calls the API"
    assert node.continue_on_fail is True
    assert node.on_error == "continueRegularOutput"
    assert node.retry_on_fail is True
    assert node.max_tries == 3
    assert node.wait_between_tries == 2000
    assert node.execute_once is False

    dumped = json.loads(node.model_dump_json(by_alias=True))
    assert dumped["typeVersion"] == 4.2
    assert dumped["continueOnFail"] is True
    assert dumped["onError"] == "continueRegularOutput"
    assert dumped["retryOnFail"] is True
    assert dumped["maxTries"] == 3
    assert dumped["waitBetweenTries"] == 2000
    assert dumped["executeOnce"] is False

    node2 = N8nNode.model_validate(dumped)
    assert node2 == node


def test_workflow_round_trip() -> None:
    """Create a full N8nWorkflow, serialize, and verify round-trip."""
    data = {
        "name": "Test Workflow",
        "nodes": [
            {
                "id": "1",
                "name": "Trigger",
                "type": "n8n-nodes-base.manualTrigger",
                "typeVersion": 1,
                "position": [0, 0],
            },
            json.loads(_FULL_NODE_JSON),
        ],
        "connections": {
            "Trigger": {
                "main": [[{"node": "HTTP Request", "type": "main", "index": 0}]]
            }
        },
        "settings": {
            "executionOrder": "v1",
            "timezone": "America/New_York",
            "saveManualExecutions": True,
            "callerPolicy": "workflowsFromSameOwner",
        },
        "pinData": {"Trigger": [{"json": {"key": "value"}}]},
        "active": True,
        "id": "wf-001",
        "tags": [{"id": "1", "name": "production"}],
    }

    wf = N8nWorkflow.model_validate(data)
    json_str = wf.model_dump_json(by_alias=True)
    wf2 = N8nWorkflow.model_validate_json(json_str)

    assert wf2.name == wf.name
    assert len(wf2.nodes) == len(wf.nodes)
    for n1, n2 in zip(wf.nodes, wf2.nodes, strict=True):
        assert n1.id == n2.id
        assert n1.name == n2.name
        assert n1.type_version == n2.type_version

    assert wf2.settings is not None
    assert wf2.settings.execution_order == "v1"
    assert wf2.settings.timezone == "America/New_York"
    assert wf2.settings.save_manual_executions is True
    assert wf2.settings.caller_policy == "workflowsFromSameOwner"
    assert wf2.pin_data is not None
    assert wf2.active is True


def test_connection_target_identity() -> None:
    """Verify ConnectionTarget fields."""
    ct = ConnectionTarget(node="Next", type="main", index=0)
    assert ct.node == "Next"
    assert ct.type == "main"
    assert ct.index == 0


def test_workflow_settings_identity() -> None:
    """Verify WorkflowSettings fields and aliases."""
    settings = WorkflowSettings.model_validate(
        {"executionOrder": "v1", "timezone": "UTC"}
    )
    assert settings.execution_order == "v1"
    assert settings.timezone == "UTC"
    dumped = settings.model_dump(by_alias=True)
    assert dumped["executionOrder"] == "v1"


def test_isinstance_across_imports() -> None:
    """Verify isinstance works for the canonical class across import paths."""
    node = N8nNode(
        id="1",
        name="Test",
        type="n8n-nodes-base.noOp",
        typeVersion=1,
        position=[0, 0],
    )
    assert isinstance(node, N8nNode)

    ct = ConnectionTarget(node="A", type="main", index=0)
    assert isinstance(ct, ConnectionTarget)

    settings = WorkflowSettings(execution_order="v1")
    assert isinstance(settings, WorkflowSettings)
