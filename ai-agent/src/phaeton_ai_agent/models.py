"""Request and response models for the AI agent Lambda contract."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class Confidence(StrEnum):
    """Confidence level for AI-generated translations."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class NodeTranslationRequest(BaseModel):
    """Request payload for translating an n8n node to ASL state(s)."""

    model_config = ConfigDict(frozen=True)

    node_json: str
    node_type: str
    node_name: str
    expressions: str = ""
    workflow_context: str = ""
    position: str = ""
    target_state_type: str = "Task"


class ExpressionTranslationRequest(BaseModel):
    """Request payload for translating a single n8n expression."""

    model_config = ConfigDict(frozen=True)

    expression: str
    node_json: str = ""
    node_type: str = ""
    workflow_context: str = ""


class AIAgentResponse(BaseModel):
    """Response from node translation."""

    model_config = ConfigDict(frozen=True)

    states: dict[str, Any] = {}
    confidence: Confidence = Confidence.LOW
    explanation: str = ""
    warnings: list[str] = []


class ExpressionResponse(BaseModel):
    """Response from expression translation."""

    model_config = ConfigDict(frozen=True)

    translated: str
    confidence: Confidence = Confidence.LOW
    explanation: str = ""
