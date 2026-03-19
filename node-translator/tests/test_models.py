"""Tests for node translator request and response models."""

from __future__ import annotations

from typing import Any

import pytest

from phaeton_node_translator.models import (
    Confidence,
    NodeTranslationRequest,
    NodeTranslationResponse,
)


class TestNodeTranslationRequest:
    """Tests for the NodeTranslationRequest model."""

    def test_required_fields(self) -> None:
        """Request with all required fields is valid."""
        request = NodeTranslationRequest(
            node_json='{"type": "test"}',
            node_type="n8n-nodes-base.test",
            node_name="Test Node",
        )
        assert request.node_json == '{"type": "test"}'
        assert request.node_type == "n8n-nodes-base.test"
        assert request.node_name == "Test Node"

    def test_default_values(self) -> None:
        """Optional fields have correct defaults."""
        request = NodeTranslationRequest(
            node_json="{}",
            node_type="test",
            node_name="Test",
        )
        assert request.expressions == ""
        assert request.workflow_context == ""
        assert request.position == ""
        assert request.target_state_type == "Task"

    def test_frozen_immutability(self) -> None:
        """Request model is immutable."""
        request = NodeTranslationRequest(
            node_json="{}",
            node_type="test",
            node_name="Test",
        )
        with pytest.raises(Exception):  # noqa: B017, PT011
            request.node_name = "Changed"

    def test_serialization_round_trip(self) -> None:
        """Request serializes and deserializes correctly."""
        request = NodeTranslationRequest(
            node_json='{"key": "value"}',
            node_type="n8n-nodes-base.set",
            node_name="Set Node",
            expressions="expr1",
            workflow_context="ctx",
            position="states.Step1",
            target_state_type="Pass",
        )
        dumped = request.model_dump(mode="json")
        restored = NodeTranslationRequest.model_validate(dumped)
        assert restored == request


class TestNodeTranslationResponse:
    """Tests for the NodeTranslationResponse model."""

    def test_default_values(self) -> None:
        """Response with no arguments has correct defaults."""
        response = NodeTranslationResponse()
        assert response.states == {}
        assert response.confidence == Confidence.LOW
        assert response.explanation == ""
        assert response.warnings == []

    def test_with_states_and_confidence(self) -> None:
        """Response with states and confidence is valid."""
        states: dict[str, Any] = {"Step1": {"Type": "Pass"}}
        response = NodeTranslationResponse(
            states=states,
            confidence=Confidence.HIGH,
            explanation="Direct mapping",
        )
        assert response.states == states
        assert response.confidence == Confidence.HIGH

    def test_frozen_immutability(self) -> None:
        """Response model is immutable."""
        response = NodeTranslationResponse()
        with pytest.raises(Exception):  # noqa: B017, PT011
            response.explanation = "Changed"

    def test_serialization_round_trip(self) -> None:
        """Response serializes and deserializes correctly."""
        response = NodeTranslationResponse(
            states={"S1": {"Type": "Task", "Resource": "arn:aws:states:::sns:publish"}},
            confidence=Confidence.MEDIUM,
            explanation="Mapped to SNS",
            warnings=["Review resource ARN"],
        )
        dumped = response.model_dump(mode="json")
        restored = NodeTranslationResponse.model_validate(dumped)
        assert restored == response

    def test_confidence_enum_values(self) -> None:
        """All Confidence enum values can be used in a response."""
        for level in Confidence:
            response = NodeTranslationResponse(confidence=level)
            assert response.confidence == level

    def test_json_serialization_confidence(self) -> None:
        """Confidence enum serializes to string in JSON mode."""
        response = NodeTranslationResponse(confidence=Confidence.HIGH)
        dumped = response.model_dump(mode="json")
        assert dumped["confidence"] == "HIGH"
