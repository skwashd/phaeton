"""Models for the conversion feasibility report."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from workflow_analyzer.models.classification import ClassifiedNode, NodeCategory
from workflow_analyzer.models.expression import ClassifiedExpression, ExpressionCategory
from workflow_analyzer.models.payload import PayloadWarning


class ConversionReport(BaseModel):
    """Complete conversion feasibility report."""

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
