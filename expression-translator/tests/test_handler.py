"""Tests for the expression translator Lambda handler."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock, patch

from phaeton_expression_translator.handler import handler
from phaeton_expression_translator.models import (
    Confidence,
    ExpressionTranslationResponse,
)


class TestHandlerSuccess:
    """Tests for successful handler invocations."""

    @patch("phaeton_expression_translator.handler.translate_expression")
    def test_valid_event_returns_response(self, mock_translate: MagicMock) -> None:
        """Valid event payload returns translated expression."""
        mock_translate.return_value = ExpressionTranslationResponse(
            translated="$states.input.name",
            confidence=Confidence.HIGH,
            explanation="Direct field mapping",
        )
        event = {
            "expression": "{{ $json.name }}",
        }
        result = handler(event, None)
        assert result["translated"] == "$states.input.name"
        assert result["confidence"] == "HIGH"


class TestHandlerValidationErrors:
    """Tests for handler validation error responses."""

    def test_missing_required_fields(self) -> None:
        """Missing required fields return a 400 validation error."""
        result = handler({}, None)
        assert "error" in result
        assert result["error"]["status_code"] == 400
        assert "ValidationError" in result["error"]["error_type"]


class TestHandlerErrors:
    """Tests for handler error handling."""

    @patch("phaeton_expression_translator.handler.translate_expression")
    def test_unexpected_error_returns_500(self, mock_translate: MagicMock) -> None:
        """Unexpected exception returns a 500 error."""
        mock_translate.side_effect = RuntimeError("boom")
        event = {
            "expression": "{{ $json.x }}",
        }
        result = handler(event, None)
        assert "error" in result
        assert result["error"]["status_code"] == 500


class TestHandlerWithContext:
    """Tests for handler behaviour when a Lambda context is provided."""

    @patch("phaeton_expression_translator.handler.translate_expression")
    def test_lambda_context_logged(self, mock_translate: MagicMock) -> None:
        """Handler succeeds when a real LambdaContext-like object is passed."""
        mock_translate.return_value = ExpressionTranslationResponse(
            translated="$.x",
            confidence=Confidence.MEDIUM,
        )

        class _FakeContext:
            function_name = "phaeton-expression-translator"
            invoked_function_arn = (
                "arn:aws:lambda:us-east-1:123:function:phaeton-expression-translator"
            )
            aws_request_id = "test-request-id"

        event = {
            "expression": "{{ $json.x }}",
        }
        result = handler(event, cast(Any, _FakeContext()))
        assert "error" not in result
