"""Shared test fixtures for the expression-translator test suite."""

from __future__ import annotations

import json
from collections.abc import Generator

import pytest

from phaeton_expression_translator.models import ExpressionTranslationRequest


@pytest.fixture(autouse=True)
def _reset_agent_singleton() -> Generator[None]:
    """Reset the module-level agent singleton between tests."""
    import phaeton_expression_translator.agent as agent_mod

    agent_mod._agent = None
    yield
    agent_mod._agent = None


@pytest.fixture
def sample_request() -> ExpressionTranslationRequest:
    """Return a minimal valid ExpressionTranslationRequest for testing."""
    return ExpressionTranslationRequest(
        expression="{{ $json.name }}",
    )


@pytest.fixture
def successful_agent_response() -> str:
    """Return a JSON string mimicking a successful agent response."""
    return json.dumps(
        {
            "translated": "$states.input.name",
            "confidence": "HIGH",
            "explanation": "Direct field mapping",
        }
    )
