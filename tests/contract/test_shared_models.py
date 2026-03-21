"""
Contract tests for shared phaeton-models used across components.

Verifies that N8nNode, ConnectionTarget, and WorkflowSettings from
phaeton-models are the same classes imported by both workflow-analyzer
and n8n-to-sfn, and that JSON round-trips preserve all aliased fields.
"""

from __future__ import annotations

from typing import Any

from n8n_to_sfn.models.n8n import (
    N8nConnectionTarget as SfnConnectionTarget,
)
from n8n_to_sfn.models.n8n import (
    N8nNode as SfnNode,
)
from n8n_to_sfn.models.n8n import (
    N8nSettings as SfnSettings,
)
from n8n_to_sfn.models.n8n import (
    N8nWorkflow as SfnWorkflow,
)
from phaeton_models.n8n_workflow import (
    ConnectionTarget,
    N8nNode,
    N8nWorkflow,
    WorkflowSettings,
)
from workflow_analyzer.models.n8n_workflow import (
    ConnectionTarget as WAConnectionTarget,
)
from workflow_analyzer.models.n8n_workflow import (
    N8nNode as WANode,
)
from workflow_analyzer.models.n8n_workflow import (
    N8nWorkflow as WAWorkflow,
)
from workflow_analyzer.models.n8n_workflow import (
    WorkflowSettings as WASettings,
)


class TestSharedModelIdentity:
    """Shared models are the exact same classes in both components."""

    def test_n8n_node_is_same_class(self) -> None:
        """workflow-analyzer imports the same N8nNode class."""
        assert WANode is N8nNode

    def test_connection_target_is_same_class(self) -> None:
        """workflow-analyzer imports the same ConnectionTarget class."""
        assert WAConnectionTarget is ConnectionTarget

    def test_workflow_settings_is_same_class(self) -> None:
        """workflow-analyzer imports the same WorkflowSettings class."""
        assert WASettings is WorkflowSettings

    def test_n8n_workflow_is_same_class(self) -> None:
        """workflow-analyzer imports the same N8nWorkflow class."""
        assert WAWorkflow is N8nWorkflow

    def test_n8n_node_same_in_translator(self) -> None:
        """n8n-to-sfn imports the same N8nNode class."""
        assert SfnNode is N8nNode

    def test_connection_target_same_in_translator(self) -> None:
        """n8n-to-sfn imports the same ConnectionTarget class."""
        assert SfnConnectionTarget is ConnectionTarget

    def test_workflow_settings_same_in_translator(self) -> None:
        """n8n-to-sfn imports the same WorkflowSettings class."""
        assert SfnSettings is WorkflowSettings

    def test_n8n_workflow_same_in_translator(self) -> None:
        """n8n-to-sfn imports the same N8nWorkflow class."""
        assert SfnWorkflow is N8nWorkflow


class TestN8nNodeJsonRoundTrip:
    """N8nNode serializes and deserializes with all aliased fields intact."""

    def test_aliased_fields_round_trip(self) -> None:
        """Fields with aliases survive JSON serialization by alias."""
        node = N8nNode.model_validate(
            {
                "id": "abc",
                "name": "Test",
                "type": "n8n-nodes-base.set",
                "typeVersion": 2,
                "position": [100.0, 200.0],
                "parameters": {"key": "value"},
                "continueOnFail": True,
                "onError": "continueRegularOutput",
                "retryOnFail": True,
                "maxTries": 3,
                "waitBetweenTries": 1000,
                "executeOnce": True,
            }
        )
        json_data = node.model_dump(by_alias=True)
        assert "typeVersion" in json_data
        assert "continueOnFail" in json_data
        assert "onError" in json_data
        assert "retryOnFail" in json_data
        assert "maxTries" in json_data
        assert "waitBetweenTries" in json_data
        assert "executeOnce" in json_data

        restored = N8nNode.model_validate(json_data)
        assert restored.type_version == 2
        assert restored.continue_on_fail is True
        assert restored.max_tries == 3

    def test_python_field_names_round_trip(self) -> None:
        """Python-style field names also deserialize correctly."""
        node = N8nNode.model_validate(
            {
                "id": "abc",
                "name": "Test",
                "type": "n8n-nodes-base.set",
                "type_version": 2,
                "position": [0.0, 0.0],
            }
        )
        json_data = node.model_dump()
        restored = N8nNode.model_validate(json_data)
        assert restored.type_version == 2

    def test_json_string_round_trip(self) -> None:
        """JSON string serialization preserves all fields."""
        node = N8nNode(
            id="x",
            name="Node",
            type="n8n-nodes-base.code",
            type_version=1,
            position=[0.0, 0.0],
            parameters={"code": "return items;"},
            credentials={"slack": {"id": "1"}},
            disabled=False,
            notes="test note",
        )
        json_str = node.model_dump_json(by_alias=True)
        restored = N8nNode.model_validate_json(json_str)
        assert restored.name == "Node"
        assert restored.parameters == {"code": "return items;"}
        assert restored.credentials == {"slack": {"id": "1"}}
        assert restored.notes == "test note"

    def test_extra_fields_preserved(self) -> None:
        """N8nNode allows extra fields (ConfigDict extra='allow')."""
        data: dict[str, Any] = {
            "id": "1",
            "name": "N",
            "type": "t",
            "typeVersion": 1,
            "position": [0.0, 0.0],
            "customField": "hello",
        }
        node = N8nNode.model_validate(data)
        dumped = node.model_dump(by_alias=True)
        assert dumped["customField"] == "hello"


class TestConnectionTargetRoundTrip:
    """ConnectionTarget serializes and deserializes correctly."""

    def test_round_trip(self) -> None:
        """All fields survive round-trip."""
        target = ConnectionTarget(node="Next", type="main", index=0)
        json_data = target.model_dump(mode="json")
        restored = ConnectionTarget.model_validate(json_data)
        assert restored.node == "Next"
        assert restored.type == "main"
        assert restored.index == 0


class TestWorkflowSettingsRoundTrip:
    """WorkflowSettings handles aliased fields correctly."""

    def test_aliased_fields_round_trip(self) -> None:
        """Aliased fields survive JSON serialization."""
        settings = WorkflowSettings.model_validate(
            {
                "executionOrder": "v1",
                "timezone": "UTC",
                "saveManualExecutions": True,
                "callerPolicy": "workflowsFromSameOwner",
            }
        )
        json_data = settings.model_dump(by_alias=True)
        assert "executionOrder" in json_data
        assert "saveManualExecutions" in json_data
        assert "callerPolicy" in json_data

        restored = WorkflowSettings.model_validate(json_data)
        assert restored.execution_order == "v1"
        assert restored.save_manual_executions is True
        assert restored.caller_policy == "workflowsFromSameOwner"


class TestN8nWorkflowRoundTrip:
    """Full N8nWorkflow model serializes correctly."""

    def test_full_workflow_round_trip(self) -> None:
        """A complete workflow survives JSON round-trip."""
        workflow = N8nWorkflow(
            name="Test Workflow",
            nodes=[
                N8nNode(
                    id="1",
                    name="Start",
                    type="n8n-nodes-base.start",
                    type_version=1,
                    position=[0.0, 0.0],
                ),
            ],
            connections={
                "Start": {
                    "main": [
                        [ConnectionTarget(node="End", type="main", index=0)],
                    ],
                },
            },
            settings=WorkflowSettings(timezone="UTC"),
            active=True,
        )
        json_str = workflow.model_dump_json(by_alias=True)
        restored = N8nWorkflow.model_validate_json(json_str)
        assert restored.name == "Test Workflow"
        assert len(restored.nodes) == 1
        assert restored.active is True
        assert restored.settings is not None
        assert restored.settings.timezone == "UTC"
