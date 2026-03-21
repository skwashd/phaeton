"""Tests for flow control translator."""

from __future__ import annotations

from typing import Any

from phaeton_models.translator import (
    ClassifiedNode,
    DependencyEdge,
    NodeClassification,
    WorkflowAnalysis,
)

from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.base import TranslationContext
from n8n_to_sfn.translators.flow_control import FlowControlTranslator


def _fc_node(
    name: str,
    node_type: str,
    params: dict | None = None,
    **kwargs: Any,  # noqa: ANN401
) -> ClassifiedNode:
    """Create a flow control classified node for testing."""
    return ClassifiedNode(
        node=N8nNode(
            id=name,
            name=name,
            type=node_type,
            type_version=1,  # type: ignore[unknown-argument]
            position=[0, 0],
            parameters=params or {},
            **kwargs,
        ),
        classification=NodeClassification.FLOW_CONTROL,
    )


def _context(edges: list[DependencyEdge] | None = None) -> TranslationContext:
    """Create a translation context for testing."""
    return TranslationContext(
        analysis=WorkflowAnalysis(
            classified_nodes=[],
            dependency_edges=edges or [],
        ),
    )


class TestFlowControlTranslator:
    """Tests for FlowControlTranslator."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = FlowControlTranslator()

    def test_can_translate(self) -> None:
        """Test can_translate returns True for flow control nodes."""
        node = _fc_node("IF", "n8n-nodes-base.if")
        assert self.translator.can_translate(node)

    def test_cannot_translate_other(self) -> None:
        """Test can_translate returns False for non-flow-control nodes."""
        cn = ClassifiedNode(
            node=N8nNode(id="x", name="x", type="x", type_version=1, position=[0, 0]),  # type: ignore[missing-argument, unknown-argument]
            classification=NodeClassification.AWS_NATIVE,
        )
        assert not self.translator.can_translate(cn)

    def test_if_simple_condition(self) -> None:
        """Test IF node with simple condition becomes Choice state."""
        node = _fc_node(
            "IF",
            "n8n-nodes-base.if",
            params={
                "conditions": {
                    "conditions": [
                        {
                            "leftValue": "={{ $json.status }}",
                            "operator": {"type": "string", "operation": "equals"},
                            "rightValue": "active",
                        }
                    ]
                },
            },
        )
        edges = [
            DependencyEdge(
                from_node="IF", to_node="True", edge_type="CONNECTION", output_index=0
            ),
            DependencyEdge(
                from_node="IF", to_node="False", edge_type="CONNECTION", output_index=1
            ),
        ]
        result = self.translator.translate(node, _context(edges))
        state = result.states["IF"]
        assert state.type == "Choice"
        assert len(state.choices) == 1
        assert state.default == "False"

    def test_switch_three_cases_and_fallback(self) -> None:
        """Test Switch node with three cases and fallback."""
        node = _fc_node(
            "Switch",
            "n8n-nodes-base.switch",
            params={
                "rules": {
                    "values": [
                        {
                            "value1": "={{ $json.type }}",
                            "operation": "equal",
                            "value2": "A",
                        },
                        {
                            "value1": "={{ $json.type }}",
                            "operation": "equal",
                            "value2": "B",
                        },
                        {
                            "value1": "={{ $json.type }}",
                            "operation": "equal",
                            "value2": "C",
                        },
                    ]
                },
            },
        )
        edges = [
            DependencyEdge(
                from_node="Switch",
                to_node="HandlerA",
                edge_type="CONNECTION",
                output_index=0,
            ),
            DependencyEdge(
                from_node="Switch",
                to_node="HandlerB",
                edge_type="CONNECTION",
                output_index=1,
            ),
            DependencyEdge(
                from_node="Switch",
                to_node="HandlerC",
                edge_type="CONNECTION",
                output_index=2,
            ),
            DependencyEdge(
                from_node="Switch",
                to_node="Default",
                edge_type="CONNECTION",
                output_index=3,
            ),
        ]
        result = self.translator.translate(node, _context(edges))
        state = result.states["Switch"]
        assert state.type == "Choice"
        assert len(state.choices) == 3
        assert state.default == "Default"

    def test_split_in_batches(self) -> None:
        """Test splitInBatches becomes Map state with metadata."""
        node = _fc_node("Batch", "n8n-nodes-base.splitInBatches")
        result = self.translator.translate(node, _context())
        state = result.states["Batch"]
        assert state.type == "Map"
        assert state.max_concurrency == 1
        assert result.metadata.get("split_in_batches_node") is True
        assert result.metadata.get("batch_size") == 10

    def test_split_in_batches_custom_batch_size(self) -> None:
        """Test splitInBatches reads custom batch size from parameters."""
        node = _fc_node(
            "Batch",
            "n8n-nodes-base.splitInBatches",
            params={"batchSize": 25},
        )
        result = self.translator.translate(node, _context())
        state = result.states["Batch"]
        assert state.type == "Map"
        assert result.metadata.get("batch_size") == 25
        assert "batch_size=25" in state.comment

    def test_split_in_batches_done_output(self) -> None:
        """Test splitInBatches records the done output in metadata."""
        node = _fc_node("Batch", "n8n-nodes-base.splitInBatches")
        edges = [
            DependencyEdge(
                from_node="Batch",
                to_node="AfterLoop",
                edge_type="CONNECTION",
                output_index=0,
            ),
            DependencyEdge(
                from_node="Batch",
                to_node="LoopBody",
                edge_type="CONNECTION",
                output_index=1,
            ),
        ]
        result = self.translator.translate(node, _context(edges))
        assert result.metadata.get("done_next") == "AfterLoop"

    def test_wait_seconds(self) -> None:
        """Test Wait node with seconds."""
        node = _fc_node(
            "Wait",
            "n8n-nodes-base.wait",
            params={
                "resume": "timeInterval",
                "amount": 30,
                "unit": "seconds",
            },
        )
        result = self.translator.translate(node, _context())
        state = result.states["Wait"]
        assert state.type == "Wait"
        assert state.seconds == 30

    def test_wait_minutes(self) -> None:
        """Test Wait node with minutes."""
        node = _fc_node(
            "Wait",
            "n8n-nodes-base.wait",
            params={
                "resume": "timeInterval",
                "amount": 5,
                "unit": "minutes",
            },
        )
        result = self.translator.translate(node, _context())
        state = result.states["Wait"]
        assert state.seconds == 300

    def test_wait_timestamp(self) -> None:
        """Test Wait node with timestamp."""
        node = _fc_node(
            "Wait",
            "n8n-nodes-base.wait",
            params={
                "resume": "specificTime",
                "dateTime": "2025-06-01T12:00:00Z",
            },
        )
        result = self.translator.translate(node, _context())
        state = result.states["Wait"]
        assert state.timestamp == "2025-06-01T12:00:00Z"

    def test_noop(self) -> None:
        """Test NoOp becomes Pass state."""
        node = _fc_node("NoOp", "n8n-nodes-base.noOp")
        result = self.translator.translate(node, _context())
        state = result.states["NoOp"]
        assert state.type == "Pass"

    def test_execute_workflow_string_id(self) -> None:
        """Test executeWorkflow with plain string workflowId."""
        node = _fc_node(
            "SubWF",
            "n8n-nodes-base.executeWorkflow",
            params={
                "workflowId": "abc-123",
            },
        )
        result = self.translator.translate(node, _context())
        state = result.states["SubWF"]
        assert state.type == "Task"
        assert "startExecution" in state.resource
        assert state.arguments["StateMachineArn"] == (
            "{% $states.context.sub_workflow_arns['abc-123'] %}"
        )
        assert result.metadata["sub_workflow_references"] == ["abc-123"]

    def test_execute_workflow_dict_id(self) -> None:
        """Test executeWorkflow with dict-style workflowId containing a value key."""
        node = _fc_node(
            "SubWF",
            "n8n-nodes-base.executeWorkflow",
            params={
                "workflowId": {"value": "wf-456"},
            },
        )
        result = self.translator.translate(node, _context())
        state = result.states["SubWF"]
        assert state.type == "Task"
        assert state.arguments["StateMachineArn"] == (
            "{% $states.context.sub_workflow_arns['wf-456'] %}"
        )
        assert result.metadata["sub_workflow_references"] == ["wf-456"]

    def test_execute_workflow_empty_id(self) -> None:
        """Test executeWorkflow with empty workflowId omits ARN and metadata."""
        node = _fc_node(
            "SubWF",
            "n8n-nodes-base.executeWorkflow",
            params={
                "workflowId": "",
            },
        )
        result = self.translator.translate(node, _context())
        state = result.states["SubWF"]
        assert "StateMachineArn" not in state.arguments
        assert "sub_workflow_references" not in result.metadata

    def test_merge_produces_metadata(self) -> None:
        """Test Merge node produces merge metadata for post-processing."""
        node = _fc_node("Merge", "n8n-nodes-base.merge")
        result = self.translator.translate(node, _context())
        assert "Merge" in result.states
        assert result.metadata.get("merge_node") is True
        assert result.metadata.get("merge_mode") == "append"

    def test_merge_mode_combine(self) -> None:
        """Test Merge node with combine mode."""
        node = _fc_node("Merge", "n8n-nodes-base.merge", params={"mode": "combine"})
        result = self.translator.translate(node, _context())
        assert result.metadata.get("merge_mode") == "combine"

    def test_continue_on_fail(self) -> None:
        """Test continueOnFail on executeWorkflow."""
        node = _fc_node(
            "SubWF",
            "n8n-nodes-base.executeWorkflow",
            params={
                "workflowId": "x",
            },
            continueOnFail=True,
        )
        edges = [
            DependencyEdge(from_node="SubWF", to_node="Next", edge_type="CONNECTION"),
        ]
        result = self.translator.translate(node, _context(edges))
        # The execute workflow state should exist
        assert "SubWF" in result.states

    def test_unknown_flow_control_type(self) -> None:
        """Test unknown flow control type produces warning."""
        node = _fc_node("Unknown", "n8n-nodes-base.unknownFlowControl")
        result = self.translator.translate(node, _context())
        assert "Unknown" in result.states
        assert any(
            "unrecogni" in w.lower() or "no handler" in w.lower()
            for w in result.warnings
        )
