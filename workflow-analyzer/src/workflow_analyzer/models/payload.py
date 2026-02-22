"""Models for payload size analysis results."""

from typing import Literal

from pydantic import BaseModel


class PayloadWarning(BaseModel):
    """A warning about potential payload size issues."""

    node_name: str
    warning_type: str
    description: str
    severity: Literal["low", "medium", "high"]
    recommendation: str


class PayloadAnalysisResult(BaseModel):
    """Result of payload size analysis for a workflow."""

    warnings: list[PayloadWarning] = []
    payload_limit_kb: int = 256
