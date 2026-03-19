"""Request and response models for the expression translator Lambda contract."""

from __future__ import annotations

from phaeton_models import Confidence
from pydantic import BaseModel, ConfigDict


class ExpressionTranslationRequest(BaseModel):
    """Request payload for translating a single n8n expression to JSONata."""

    model_config = ConfigDict(frozen=True)

    expression: str
    node_json: str = ""
    node_type: str = ""
    workflow_context: str = ""


class ExpressionTranslationResponse(BaseModel):
    """Response from expression translation with JSONata and confidence."""

    model_config = ConfigDict(frozen=True)

    translated: str
    confidence: Confidence = Confidence.LOW
    explanation: str = ""
