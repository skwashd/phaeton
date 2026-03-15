"""Tests for AI agent request/response models."""

from __future__ import annotations

from phaeton_ai_agent.models import (
    AIAgentResponse,
    Confidence,
    ExpressionResponse,
    ExpressionTranslationRequest,
    NodeTranslationRequest,
)


class TestConfidence:
    """Tests for the Confidence enum."""

    def test_values(self) -> None:
        """All three confidence levels are present."""
        assert Confidence.HIGH == "HIGH"
        assert Confidence.MEDIUM == "MEDIUM"
        assert Confidence.LOW == "LOW"


class TestNodeTranslationRequest:
    """Tests for NodeTranslationRequest construction and serialization."""

    def test_minimal_construction(self) -> None:
        """Required fields only; optional fields get defaults."""
        req = NodeTranslationRequest(
            node_json='{"type": "test"}',
            node_type="n8n-nodes-base.test",
            node_name="Test Node",
        )
        assert req.node_json == '{"type": "test"}'
        assert req.node_type == "n8n-nodes-base.test"
        assert req.node_name == "Test Node"
        assert req.expressions == ""
        assert req.workflow_context == ""
        assert req.position == ""
        assert req.target_state_type == "Task"

    def test_full_construction(self) -> None:
        """All fields populated explicitly."""
        req = NodeTranslationRequest(
            node_json='{"type": "test"}',
            node_type="n8n-nodes-base.test",
            node_name="Test Node",
            expressions="expr1, expr2",
            workflow_context="context info",
            position="states.Step1",
            target_state_type="Pass",
        )
        assert req.expressions == "expr1, expr2"
        assert req.workflow_context == "context info"
        assert req.position == "states.Step1"
        assert req.target_state_type == "Pass"

    def test_serialization(self) -> None:
        """Model serializes to a JSON-compatible dict."""
        req = NodeTranslationRequest(
            node_json='{"type": "test"}',
            node_type="n8n-nodes-base.test",
            node_name="Test Node",
        )
        data = req.model_dump(mode="json")
        assert data["node_json"] == '{"type": "test"}'
        assert data["node_type"] == "n8n-nodes-base.test"
        assert data["node_name"] == "Test Node"

    def test_deserialization(self) -> None:
        """Model validates from a raw dict."""
        data = {
            "node_json": '{"type": "test"}',
            "node_type": "n8n-nodes-base.test",
            "node_name": "Test Node",
        }
        req = NodeTranslationRequest.model_validate(data)
        assert req.node_json == '{"type": "test"}'


class TestExpressionTranslationRequest:
    """Tests for ExpressionTranslationRequest construction."""

    def test_minimal_construction(self) -> None:
        """Only expression is required."""
        req = ExpressionTranslationRequest(expression="{{ $json.name }}")
        assert req.expression == "{{ $json.name }}"
        assert req.node_json == ""
        assert req.node_type == ""
        assert req.workflow_context == ""

    def test_full_construction(self) -> None:
        """All fields populated explicitly."""
        req = ExpressionTranslationRequest(
            expression="{{ $json.name }}",
            node_json='{"type": "test"}',
            node_type="n8n-nodes-base.test",
            workflow_context="context",
        )
        assert req.node_json == '{"type": "test"}'


class TestAIAgentResponse:
    """Tests for AIAgentResponse defaults and serialization."""

    def test_defaults(self) -> None:
        """Empty response uses LOW confidence and empty collections."""
        resp = AIAgentResponse()
        assert resp.states == {}
        assert resp.confidence == Confidence.LOW
        assert resp.explanation == ""
        assert resp.warnings == []

    def test_full_construction(self) -> None:
        """All fields populated explicitly."""
        resp = AIAgentResponse(
            states={"Step1": {"Type": "Task", "Resource": "arn:aws:..."}},
            confidence=Confidence.HIGH,
            explanation="Direct mapping to DynamoDB PutItem",
            warnings=["Check IAM permissions"],
        )
        assert "Step1" in resp.states
        assert resp.confidence == Confidence.HIGH

    def test_serialization_roundtrip(self) -> None:
        """Model survives a dump/validate round-trip."""
        resp = AIAgentResponse(
            states={"Step1": {"Type": "Pass"}},
            confidence=Confidence.MEDIUM,
            explanation="test",
        )
        data = resp.model_dump(mode="json")
        restored = AIAgentResponse.model_validate(data)
        assert restored.states == resp.states
        assert restored.confidence == resp.confidence


class TestExpressionResponse:
    """Tests for ExpressionResponse construction and serialization."""

    def test_construction(self) -> None:
        """Fields are stored correctly."""
        resp = ExpressionResponse(
            translated="$.name",
            confidence=Confidence.HIGH,
            explanation="Direct field access",
        )
        assert resp.translated == "$.name"
        assert resp.confidence == Confidence.HIGH

    def test_serialization(self) -> None:
        """Model serializes with string confidence."""
        resp = ExpressionResponse(translated="$.name")
        data = resp.model_dump(mode="json")
        assert data["translated"] == "$.name"
        assert data["confidence"] == "LOW"
