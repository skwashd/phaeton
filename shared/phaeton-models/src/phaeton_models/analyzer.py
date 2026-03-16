"""
Models for the workflow analyzer (Component 2) output.

These models represent the conversion feasibility report produced by the
workflow analyzer. They are the canonical definitions consumed by
downstream adapters and pipeline stages.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from phaeton_models.n8n_workflow import N8nNode


class NodeCategory(StrEnum):
    """Category assigned to each n8n node for translation strategy."""

    AWS_NATIVE = "AWS_NATIVE"
    FLOW_CONTROL = "FLOW_CONTROL"
    TRIGGER = "TRIGGER"
    PICOFUN_API = "PICOFUN_API"
    GRAPHQL_API = "GRAPHQL_API"
    CODE_JS = "CODE_JS"
    CODE_PYTHON = "CODE_PYTHON"
    UNSUPPORTED = "UNSUPPORTED"


class ClassifiedNode(BaseModel):
    """A node paired with its classification result."""

    model_config = ConfigDict(frozen=True)

    node: N8nNode
    category: NodeCategory
    translation_strategy: str
    notes: str | None = None


class ExpressionCategory(StrEnum):
    """Category for how an n8n expression should be translated."""

    JSONATA_DIRECT = "JSONATA_DIRECT"
    VARIABLE_REFERENCE = "VARIABLE_REFERENCE"
    LAMBDA_REQUIRED = "LAMBDA_REQUIRED"


class ClassifiedExpression(BaseModel):
    """An expression paired with its classification result."""

    model_config = ConfigDict(frozen=True)

    node_name: str
    parameter_path: str
    raw_expression: str
    category: ExpressionCategory
    jsonata_preview: str | None = None
    referenced_nodes: list[str] = []
    reason: str = ""


class PayloadWarning(BaseModel):
    """A warning about potential payload size issues."""

    model_config = ConfigDict(frozen=True)

    node_name: str
    warning_type: str
    description: str
    severity: Literal["low", "medium", "high"]
    recommendation: str


class PayloadAnalysisResult(BaseModel):
    """Result of payload size analysis for a workflow."""

    model_config = ConfigDict(frozen=True)

    warnings: list[PayloadWarning] = []
    payload_limit_kb: int = 256


class ConversionReport(BaseModel):
    """Complete conversion feasibility report."""

    model_config = ConfigDict(frozen=True)

    source_workflow_name: str
    source_n8n_version: str | None = None
    analyzer_version: str
    timestamp: datetime
    total_nodes: int
    classification_summary: dict[NodeCategory, int]
    classified_nodes: list[ClassifiedNode]
    expression_summary: dict[ExpressionCategory, int]
    classified_expressions: list[ClassifiedExpression]
    payload_warnings: list[PayloadWarning]
    cross_node_references: list[Any]
    unsupported_nodes: list[ClassifiedNode]
    trigger_nodes: list[ClassifiedNode]
    sub_workflows_detected: list[str]
    required_picofun_clients: list[str]
    required_credentials: list[str]
    confidence_score: float
    blocking_issues: list[str]
    graph_metadata: dict[str, Any]
