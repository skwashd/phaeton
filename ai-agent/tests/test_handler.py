"""Tests for the AI agent Lambda handler."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from phaeton_ai_agent.handler import handler
from phaeton_ai_agent.models import AIAgentResponse, Confidence, ExpressionResponse


class TestHandlerRouting:
    """Tests for operation routing in the handler."""

    def test_unknown_operation(self) -> None:
        """Unknown operation returns a 400 error."""
        result = handler({"operation": "unknown"}, None)
        assert "error" in result
        assert result["error"]["status_code"] == 400
        assert "Unknown operation" in result["error"]["message"]

    def test_missing_operation(self) -> None:
        """Missing operation key returns a 400 error."""
        result = handler({}, None)
        assert "error" in result
        assert result["error"]["status_code"] == 400


class TestTranslateNodeHandler:
    """Tests for the translate_node operation."""

    @patch("phaeton_ai_agent.handler.translate_node")
    def test_success(self, mock_translate: MagicMock) -> None:
        """Valid payload returns translated states."""
        mock_translate.return_value = AIAgentResponse(
            states={"Step1": {"Type": "Pass"}},
            confidence=Confidence.HIGH,
            explanation="Direct mapping",
        )
        event = {
            "operation": "translate_node",
            "payload": {
                "node_json": '{"type": "test"}',
                "node_type": "n8n-nodes-base.test",
                "node_name": "Test Node",
            },
        }
        result = handler(event, None)
        assert "Step1" in result["states"]
        assert result["confidence"] == "HIGH"

    def test_validation_error(self) -> None:
        """Missing required fields return a 400 validation error."""
        event = {
            "operation": "translate_node",
            "payload": {},
        }
        result = handler(event, None)
        assert "error" in result
        assert result["error"]["status_code"] == 400
        assert "ValidationError" in result["error"]["error_type"]

    @patch("phaeton_ai_agent.handler.translate_node")
    def test_unexpected_error(self, mock_translate: MagicMock) -> None:
        """Unexpected exception returns a 500 error."""
        mock_translate.side_effect = RuntimeError("boom")
        event = {
            "operation": "translate_node",
            "payload": {
                "node_json": '{"type": "test"}',
                "node_type": "n8n-nodes-base.test",
                "node_name": "Test",
            },
        }
        result = handler(event, None)
        assert "error" in result
        assert result["error"]["status_code"] == 500


class TestTranslateExpressionHandler:
    """Tests for the translate_expression operation."""

    @patch("phaeton_ai_agent.handler.translate_expression")
    def test_success(self, mock_translate: MagicMock) -> None:
        """Valid payload returns a translated expression."""
        mock_translate.return_value = ExpressionResponse(
            translated="$.name",
            confidence=Confidence.HIGH,
            explanation="Direct field access",
        )
        event = {
            "operation": "translate_expression",
            "payload": {
                "expression": "{{ $json.name }}",
            },
        }
        result = handler(event, None)
        assert result["translated"] == "$.name"
        assert result["confidence"] == "HIGH"

    def test_validation_error(self) -> None:
        """Missing required fields return a 400 validation error."""
        event = {
            "operation": "translate_expression",
            "payload": {},
        }
        result = handler(event, None)
        assert "error" in result
        assert result["error"]["status_code"] == 400

    @patch("phaeton_ai_agent.handler.translate_expression")
    def test_unexpected_error(self, mock_translate: MagicMock) -> None:
        """Unexpected exception returns a 500 error."""
        mock_translate.side_effect = RuntimeError("boom")
        event = {
            "operation": "translate_expression",
            "payload": {
                "expression": "{{ $json.x }}",
            },
        }
        result = handler(event, None)
        assert "error" in result
        assert result["error"]["status_code"] == 500


class TestHandlerWithContext:
    """Tests for handler behaviour when a Lambda context is provided."""

    @patch("phaeton_ai_agent.handler.translate_node")
    def test_lambda_context_logged(self, mock_translate: MagicMock) -> None:
        """Handler succeeds when a real LambdaContext-like object is passed."""
        mock_translate.return_value = AIAgentResponse(
            states={},
            confidence=Confidence.MEDIUM,
        )

        class _FakeContext:
            function_name = "phaeton-ai-agent"
            invoked_function_arn = "arn:aws:lambda:us-east-1:123:function:phaeton-ai-agent"
            aws_request_id = "test-request-id"

        event = {
            "operation": "translate_node",
            "payload": {
                "node_json": "{}",
                "node_type": "test",
                "node_name": "Test",
            },
        }
        result = handler(event, _FakeContext())
        assert "error" not in result
