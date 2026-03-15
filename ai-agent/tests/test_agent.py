"""Tests for AI agent translation logic."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from phaeton_ai_agent.agent import (
    _parse_json_response,
    translate_expression,
    translate_node,
)
from phaeton_ai_agent.models import (
    Confidence,
    ExpressionTranslationRequest,
    NodeTranslationRequest,
)


@pytest.fixture(autouse=True)
def _reset_agent_singleton() -> None:
    """Reset the module-level agent singleton between tests."""
    import phaeton_ai_agent.agent as agent_mod

    agent_mod._agent = None
    yield  # type: ignore[misc]
    agent_mod._agent = None


class TestParseJsonResponse:
    """Tests for JSON response parsing from agent output."""

    def test_plain_json(self) -> None:
        """Plain JSON string is parsed directly."""
        text = '{"states": {}, "confidence": "HIGH"}'
        result = _parse_json_response(text)
        assert result["confidence"] == "HIGH"

    def test_fenced_json(self) -> None:
        """JSON inside markdown code fences is extracted."""
        text = '```json\n{"states": {}, "confidence": "MEDIUM"}\n```'
        result = _parse_json_response(text)
        assert result["confidence"] == "MEDIUM"

    def test_fenced_no_language(self) -> None:
        """Code fences without a language tag are handled."""
        text = '```\n{"states": {}}\n```'
        result = _parse_json_response(text)
        assert result["states"] == {}

    def test_invalid_json_raises(self) -> None:
        """Non-JSON text raises JSONDecodeError."""
        with pytest.raises(json.JSONDecodeError):
            _parse_json_response("not valid json")


class TestTranslateNode:
    """Tests for the translate_node function."""

    @patch("phaeton_ai_agent.agent._get_agent")
    def test_successful_translation(self, mock_get_agent: MagicMock) -> None:
        """Valid agent response is parsed into an AIAgentResponse."""
        mock_agent = MagicMock()
        mock_agent.return_value = json.dumps({
            "states": {"SendEmail": {"Type": "Task", "Resource": "arn:aws:states:::ses:sendEmail"}},
            "confidence": "HIGH",
            "explanation": "Mapped to SES SendEmail",
            "warnings": [],
        })
        mock_get_agent.return_value = mock_agent

        request = NodeTranslationRequest(
            node_json='{"type": "n8n-nodes-base.emailSend"}',
            node_type="n8n-nodes-base.emailSend",
            node_name="Send Email",
        )
        result = translate_node(request)

        assert "SendEmail" in result.states
        assert result.confidence == Confidence.HIGH
        assert result.explanation == "Mapped to SES SendEmail"
        mock_agent.assert_called_once()

    @patch("phaeton_ai_agent.agent._get_agent")
    def test_agent_error_returns_low_confidence(self, mock_get_agent: MagicMock) -> None:
        """Runtime error from agent results in LOW confidence fallback."""
        mock_agent = MagicMock()
        mock_agent.side_effect = RuntimeError("Bedrock timeout")
        mock_get_agent.return_value = mock_agent

        request = NodeTranslationRequest(
            node_json='{"type": "test"}',
            node_type="n8n-nodes-base.test",
            node_name="Test Node",
        )
        result = translate_node(request)

        assert result.confidence == Confidence.LOW
        assert result.states == {}
        assert len(result.warnings) > 0
        assert "Test Node" in result.warnings[0]

    @patch("phaeton_ai_agent.agent._get_agent")
    def test_invalid_json_response_returns_low_confidence(self, mock_get_agent: MagicMock) -> None:
        """Non-JSON agent output results in LOW confidence fallback."""
        mock_agent = MagicMock()
        mock_agent.return_value = "Sorry, I cannot translate this node."
        mock_get_agent.return_value = mock_agent

        request = NodeTranslationRequest(
            node_json='{"type": "test"}',
            node_type="n8n-nodes-base.test",
            node_name="Bad Node",
        )
        result = translate_node(request)

        assert result.confidence == Confidence.LOW
        assert "Bad Node" in result.warnings[0]

    @patch("phaeton_ai_agent.agent._get_agent")
    def test_prompt_includes_request_fields(self, mock_get_agent: MagicMock) -> None:
        """All request fields appear in the prompt sent to the agent."""
        mock_agent = MagicMock()
        mock_agent.return_value = json.dumps({
            "states": {},
            "confidence": "MEDIUM",
            "explanation": "ok",
            "warnings": [],
        })
        mock_get_agent.return_value = mock_agent

        request = NodeTranslationRequest(
            node_json='{"type": "test"}',
            node_type="n8n-nodes-base.test",
            node_name="My Node",
            expressions="expr1",
            workflow_context="ctx",
            position="states.Step1",
            target_state_type="Pass",
        )
        translate_node(request)

        prompt_arg = mock_agent.call_args[0][0]
        assert "n8n-nodes-base.test" in prompt_arg
        assert "expr1" in prompt_arg
        assert "ctx" in prompt_arg
        assert "states.Step1" in prompt_arg
        assert "Pass" in prompt_arg


class TestTranslateExpression:
    """Tests for the translate_expression function."""

    @patch("phaeton_ai_agent.agent._get_agent")
    def test_successful_translation(self, mock_get_agent: MagicMock) -> None:
        """Valid agent response is parsed into an ExpressionResponse."""
        mock_agent = MagicMock()
        mock_agent.return_value = json.dumps({
            "translated": "$states.input.name",
            "confidence": "HIGH",
            "explanation": "Direct field mapping",
        })
        mock_get_agent.return_value = mock_agent

        request = ExpressionTranslationRequest(
            expression="{{ $json.name }}",
        )
        result = translate_expression(request)

        assert result.translated == "$states.input.name"
        assert result.confidence == Confidence.HIGH

    @patch("phaeton_ai_agent.agent._get_agent")
    def test_error_returns_original_expression(self, mock_get_agent: MagicMock) -> None:
        """Agent error returns the original expression unchanged."""
        mock_agent = MagicMock()
        mock_agent.side_effect = RuntimeError("Bedrock error")
        mock_get_agent.return_value = mock_agent

        request = ExpressionTranslationRequest(
            expression="{{ $json.name }}",
        )
        result = translate_expression(request)

        assert result.translated == "{{ $json.name }}"
        assert result.confidence == Confidence.LOW

    @patch("phaeton_ai_agent.agent._get_agent")
    def test_prompt_includes_expression(self, mock_get_agent: MagicMock) -> None:
        """Expression and node type appear in the prompt."""
        mock_agent = MagicMock()
        mock_agent.return_value = json.dumps({
            "translated": "$.x",
            "confidence": "MEDIUM",
            "explanation": "ok",
        })
        mock_get_agent.return_value = mock_agent

        request = ExpressionTranslationRequest(
            expression="{{ $json.x }}",
            node_type="n8n-nodes-base.set",
        )
        translate_expression(request)

        prompt_arg = mock_agent.call_args[0][0]
        assert "{{ $json.x }}" in prompt_arg
        assert "n8n-nodes-base.set" in prompt_arg
