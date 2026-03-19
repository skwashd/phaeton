"""Shared test fixtures for the node-translator test suite."""

from __future__ import annotations

import json
from collections.abc import Generator

import pytest

from phaeton_node_translator.models import NodeTranslationRequest


@pytest.fixture(autouse=True)
def _reset_agent_singleton() -> Generator[None]:
    """Reset the module-level agent singleton between tests."""
    import phaeton_node_translator.agent as agent_mod

    agent_mod._agent = None
    yield
    agent_mod._agent = None


@pytest.fixture
def sample_request() -> NodeTranslationRequest:
    """Return a minimal valid NodeTranslationRequest for testing."""
    return NodeTranslationRequest(
        node_json=json.dumps({"type": "n8n-nodes-base.emailSend"}),
        node_type="n8n-nodes-base.emailSend",
        node_name="Send Email",
    )


@pytest.fixture
def successful_agent_response() -> str:
    """Return a JSON string mimicking a successful agent response."""
    return json.dumps(
        {
            "states": {
                "SendEmail": {
                    "Type": "Task",
                    "Resource": "arn:aws:states:::ses:sendEmail",
                }
            },
            "confidence": "HIGH",
            "explanation": "Mapped to SES SendEmail",
            "warnings": [],
        }
    )
