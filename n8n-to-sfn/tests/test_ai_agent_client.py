"""Tests for the AI agent Lambda client."""

from __future__ import annotations

import json
import sys
from typing import Any
from unittest.mock import MagicMock, patch

from phaeton_models.n8n_workflow import N8nNode
from phaeton_models.translator import (
    ClassifiedNode,
    NodeClassification,
    WorkflowAnalysis,
)

from n8n_to_sfn.ai_agent.client import (
    AIAgentClient,
    _format_context,
    _format_expressions,
)
from n8n_to_sfn.translators.base import TranslationContext


def _make_node(
    name: str = "Test Node",
    node_type: str = "n8n-nodes-base.test",
    parameters: dict[str, Any] | None = None,
) -> ClassifiedNode:
    """Create a minimal ClassifiedNode for testing."""
    return ClassifiedNode(
        node=N8nNode(
            id="test-id",
            name=name,
            type=node_type,
            typeVersion=1,
            position=[0.0, 0.0],
            parameters=parameters or {},
        ),
        classification=NodeClassification.AWS_NATIVE,
    )


def _make_context() -> TranslationContext:
    """Create a minimal TranslationContext for testing."""
    return TranslationContext(
        analysis=WorkflowAnalysis(
            classified_nodes=[],
            dependency_edges=[],
            confidence_score=1.0,
        ),
    )


def _mock_lambda_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Build a mock boto3 Lambda invoke response."""
    return {
        "Payload": MagicMock(read=MagicMock(return_value=json.dumps(payload).encode())),
        "StatusCode": 200,
    }


def _create_client_with_mock(mock_invoke: MagicMock) -> AIAgentClient:
    """
    Create an AIAgentClient with a mocked boto3 Lambda client.

    Injects a mock ``boto3`` module so the lazy import inside
    ``AIAgentClient.__init__`` resolves without the real package.
    """
    mock_boto3 = MagicMock()
    mock_lambda_client = MagicMock()
    mock_lambda_client.invoke = mock_invoke
    mock_boto3.client.return_value = mock_lambda_client

    with patch.dict(sys.modules, {"boto3": mock_boto3}):
        return AIAgentClient(function_name="phaeton-ai-agent")


class TestTranslateNode:
    """Tests for AIAgentClient.translate_node."""

    def test_success(self) -> None:
        """Successful Lambda invocation returns TranslationResult with ai_generated metadata."""
        mock_invoke = MagicMock(return_value=_mock_lambda_response({
            "states": {"SendEmail": {"Type": "Task", "Resource": "arn:aws:states:::ses:sendEmail"}},
            "confidence": "HIGH",
            "explanation": "Mapped to SES",
            "warnings": [],
        }))
        client = _create_client_with_mock(mock_invoke)
        node = _make_node(name="Send Email")
        result = client.translate_node(node, _make_context())

        assert "SendEmail" in result.states
        assert result.metadata["ai_generated"] is True
        assert result.metadata["confidence"] == "HIGH"
        assert result.metadata["explanation"] == "Mapped to SES"

    def test_error_response(self) -> None:
        """Lambda error response returns TranslationResult with warning."""
        mock_invoke = MagicMock(return_value=_mock_lambda_response({
            "error": {
                "status_code": 500,
                "error_type": "RuntimeError",
                "message": "Agent failed",
            },
        }))
        client = _create_client_with_mock(mock_invoke)
        result = client.translate_node(_make_node(), _make_context())

        assert result.states == {}
        assert result.metadata["ai_error"] is True
        assert any("Agent failed" in w for w in result.warnings)

    def test_boto3_exception(self) -> None:
        """boto3 exception returns graceful fallback with warning."""
        mock_invoke = MagicMock(side_effect=Exception("Connection refused"))
        client = _create_client_with_mock(mock_invoke)
        result = client.translate_node(_make_node(), _make_context())

        assert result.states == {}
        assert result.metadata["ai_error"] is True
        assert len(result.warnings) > 0

    def test_invocation_payload(self) -> None:
        """Lambda is invoked with the correct operation and payload fields."""
        mock_invoke = MagicMock(return_value=_mock_lambda_response({
            "states": {},
            "confidence": "MEDIUM",
            "explanation": "",
            "warnings": [],
        }))
        client = _create_client_with_mock(mock_invoke)
        node = _make_node(name="My Node", node_type="n8n-nodes-base.custom")
        client.translate_node(node, _make_context())

        call_args = mock_invoke.call_args
        payload = json.loads(call_args[1]["Payload"])
        assert payload["operation"] == "translate_node"
        assert payload["payload"]["node_type"] == "n8n-nodes-base.custom"
        assert payload["payload"]["node_name"] == "My Node"


class TestTranslateExpression:
    """Tests for AIAgentClient.translate_expression."""

    def test_success(self) -> None:
        """Successful invocation returns the translated expression string."""
        mock_invoke = MagicMock(return_value=_mock_lambda_response({
            "translated": "$states.input.name",
            "confidence": "HIGH",
            "explanation": "Direct field access",
        }))
        client = _create_client_with_mock(mock_invoke)
        result = client.translate_expression(
            "{{ $json.name }}", _make_node(), _make_context()
        )

        assert result == "$states.input.name"

    def test_error_returns_original(self) -> None:
        """Lambda error response returns the original expression."""
        mock_invoke = MagicMock(return_value=_mock_lambda_response({
            "error": {
                "status_code": 500,
                "error_type": "RuntimeError",
                "message": "Agent failed",
            },
        }))
        client = _create_client_with_mock(mock_invoke)
        result = client.translate_expression(
            "{{ $json.name }}", _make_node(), _make_context()
        )

        assert result == "{{ $json.name }}"

    def test_boto3_exception_returns_original(self) -> None:
        """boto3 exception returns the original expression."""
        mock_invoke = MagicMock(side_effect=Exception("Network error"))
        client = _create_client_with_mock(mock_invoke)
        result = client.translate_expression(
            "{{ $json.x }}", _make_node(), _make_context()
        )

        assert result == "{{ $json.x }}"


class TestFormatExpressions:
    """Tests for the _format_expressions helper."""

    def test_with_expressions(self) -> None:
        """Parameters containing {{ are extracted."""
        node = _make_node(parameters={"value": "{{ $json.name }}", "key": "static"})
        result = _format_expressions(node)
        assert "value" in result
        assert "{{ $json.name }}" in result
        assert "key" not in result

    def test_no_expressions(self) -> None:
        """Static-only parameters yield 'None'."""
        node = _make_node(parameters={"key": "static"})
        result = _format_expressions(node)
        assert result == "None"

    def test_empty_parameters(self) -> None:
        """Empty parameters yield 'None'."""
        node = _make_node()
        result = _format_expressions(node)
        assert result == "None"


class TestFormatContext:
    """Tests for the _format_context helper."""

    def test_with_workflow_name(self) -> None:
        """Workflow name is included in context string."""
        ctx = _make_context().model_copy(update={"workflow_name": "My Workflow"})
        result = _format_context(ctx)
        assert "My Workflow" in result

    def test_with_variables(self) -> None:
        """Resolved variable names are included in context string."""
        ctx = _make_context().model_copy(
            update={"resolved_variables": {"var1": "value1"}},
        )
        result = _format_context(ctx)
        assert "var1" in result

    def test_minimal_context(self) -> None:
        """Minimal context includes total nodes."""
        ctx = _make_context()
        result = _format_context(ctx)
        assert "Total nodes" in result
