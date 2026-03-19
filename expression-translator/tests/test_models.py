"""Tests for expression translator request and response models."""

from __future__ import annotations

import pytest

from phaeton_expression_translator.models import (
    Confidence,
    ExpressionTranslationRequest,
    ExpressionTranslationResponse,
)


class TestExpressionTranslationRequest:
    """Tests for the ExpressionTranslationRequest model."""

    def test_required_fields(self) -> None:
        """Request with the required expression field is valid."""
        request = ExpressionTranslationRequest(
            expression="{{ $json.name }}",
        )
        assert request.expression == "{{ $json.name }}"

    def test_default_values(self) -> None:
        """Optional fields have correct defaults."""
        request = ExpressionTranslationRequest(
            expression="{{ $json.x }}",
        )
        assert request.node_json == ""
        assert request.node_type == ""
        assert request.workflow_context == ""

    def test_frozen_immutability(self) -> None:
        """Request model is immutable."""
        request = ExpressionTranslationRequest(
            expression="{{ $json.x }}",
        )
        with pytest.raises(Exception):  # noqa: B017, PT011
            request.expression = "changed"

    def test_serialization_round_trip(self) -> None:
        """Request serializes and deserializes correctly."""
        request = ExpressionTranslationRequest(
            expression="{{ $json.field }}",
            node_json='{"type": "test"}',
            node_type="n8n-nodes-base.set",
            workflow_context="ctx",
        )
        dumped = request.model_dump(mode="json")
        restored = ExpressionTranslationRequest.model_validate(dumped)
        assert restored == request


class TestExpressionTranslationResponse:
    """Tests for the ExpressionTranslationResponse model."""

    def test_required_translated_field(self) -> None:
        """Response requires the translated field."""
        response = ExpressionTranslationResponse(translated="$.name")
        assert response.translated == "$.name"

    def test_default_values(self) -> None:
        """Optional fields have correct defaults."""
        response = ExpressionTranslationResponse(translated="$.x")
        assert response.confidence == Confidence.LOW
        assert response.explanation == ""

    def test_with_confidence(self) -> None:
        """Response with explicit confidence is valid."""
        response = ExpressionTranslationResponse(
            translated="$states.input.name",
            confidence=Confidence.HIGH,
            explanation="Direct field mapping",
        )
        assert response.confidence == Confidence.HIGH
        assert response.explanation == "Direct field mapping"

    def test_frozen_immutability(self) -> None:
        """Response model is immutable."""
        response = ExpressionTranslationResponse(translated="$.x")
        with pytest.raises(Exception):  # noqa: B017, PT011
            response.translated = "changed"

    def test_serialization_round_trip(self) -> None:
        """Response serializes and deserializes correctly."""
        response = ExpressionTranslationResponse(
            translated="$states.input.field",
            confidence=Confidence.MEDIUM,
            explanation="Mapped field access",
        )
        dumped = response.model_dump(mode="json")
        restored = ExpressionTranslationResponse.model_validate(dumped)
        assert restored == response

    def test_confidence_enum_values(self) -> None:
        """All Confidence enum values can be used in a response."""
        for level in Confidence:
            response = ExpressionTranslationResponse(
                translated="$.x", confidence=level
            )
            assert response.confidence == level

    def test_json_serialization_confidence(self) -> None:
        """Confidence enum serializes to string in JSON mode."""
        response = ExpressionTranslationResponse(
            translated="$.x", confidence=Confidence.HIGH
        )
        dumped = response.model_dump(mode="json")
        assert dumped["confidence"] == "HIGH"
