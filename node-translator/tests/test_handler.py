"""Tests for the node translator Lambda handler."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock, patch

from phaeton_node_translator.handler import handler
from phaeton_node_translator.models import Confidence, NodeTranslationResponse


class TestHandlerSuccess:
    """Tests for successful handler invocations."""

    @patch("phaeton_node_translator.handler.translate_node")
    def test_valid_event_returns_response(self, mock_translate: MagicMock) -> None:
        """Valid event payload returns translated states."""
        mock_translate.return_value = NodeTranslationResponse(
            states={"Step1": {"Type": "Pass"}},
            confidence=Confidence.HIGH,
            explanation="Direct mapping",
        )
        event = {
            "node_json": '{"type": "test"}',
            "node_type": "n8n-nodes-base.test",
            "node_name": "Test Node",
        }
        result = handler(event, None)
        assert "Step1" in result["states"]
        assert result["confidence"] == "HIGH"


class TestHandlerValidationErrors:
    """Tests for handler validation error responses."""

    def test_missing_required_fields(self) -> None:
        """Missing required fields return a 400 validation error."""
        result = handler({}, None)
        assert "error" in result
        assert result["error"]["status_code"] == 400
        assert "ValidationError" in result["error"]["error_type"]

    def test_partial_fields(self) -> None:
        """Event with only some required fields returns a validation error."""
        result = handler({"node_json": "{}"}, None)
        assert "error" in result
        assert result["error"]["status_code"] == 400


class TestHandlerErrors:
    """Tests for handler error handling."""

    @patch("phaeton_node_translator.handler.translate_node")
    def test_unexpected_error_returns_500(self, mock_translate: MagicMock) -> None:
        """Unexpected exception returns a 500 error."""
        mock_translate.side_effect = RuntimeError("boom")
        event = {
            "node_json": '{"type": "test"}',
            "node_type": "n8n-nodes-base.test",
            "node_name": "Test",
        }
        result = handler(event, None)
        assert "error" in result
        assert result["error"]["status_code"] == 500


class TestHandlerWithContext:
    """Tests for handler behaviour when a Lambda context is provided."""

    @patch("phaeton_node_translator.handler.translate_node")
    def test_lambda_context_logged(self, mock_translate: MagicMock) -> None:
        """Handler succeeds when a real LambdaContext-like object is passed."""
        mock_translate.return_value = NodeTranslationResponse(
            states={},
            confidence=Confidence.MEDIUM,
        )

        class _FakeContext:
            function_name = "phaeton-node-translator"
            invoked_function_arn = (
                "arn:aws:lambda:us-east-1:123:function:phaeton-node-translator"
            )
            aws_request_id = "test-request-id"

        event = {
            "node_json": "{}",
            "node_type": "test",
            "node_name": "Test",
        }
        result = handler(event, cast(Any, _FakeContext()))
        assert "error" not in result
