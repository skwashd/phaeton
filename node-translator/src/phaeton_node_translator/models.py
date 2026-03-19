"""Request and response models for the node translator Lambda contract."""

from __future__ import annotations

from typing import Any

from phaeton_models import Confidence
from pydantic import BaseModel, ConfigDict


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


class NodeTranslationResponse(BaseModel):
    """Response from node translation with ASL states and confidence."""

    model_config = ConfigDict(frozen=True)

    states: dict[str, Any] = {}
    confidence: Confidence = Confidence.LOW
    explanation: str = ""
    warnings: list[str] = []
