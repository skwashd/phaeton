"""Models for Component 2 analysis output (input to this engine).

These models represent the annotated workflow graph and conversion feasibility
report produced by the workflow analyzer (Component 2). They serve as the
primary input to the translation engine.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel

from n8n_to_sfn.models.n8n import N8nNode


class NodeClassification(StrEnum):
    """Category assigned to each n8n node for translation strategy.

    Example::

        NodeClassification.AWS_NATIVE
    """

    AWS_NATIVE = "AWS_NATIVE"
    FLOW_CONTROL = "FLOW_CONTROL"
    TRIGGER = "TRIGGER"
    PICOFUN_API = "PICOFUN_API"
    GRAPHQL_API = "GRAPHQL_API"
    CODE_JS = "CODE_JS"
    CODE_PYTHON = "CODE_PYTHON"
    UNSUPPORTED = "UNSUPPORTED"


class ExpressionCategory(StrEnum):
    """Category for how an n8n expression should be translated.

    Example::

        ExpressionCategory.JSONATA_DIRECT
    """

    JSONATA_DIRECT = "JSONATA_DIRECT"
    REQUIRES_VARIABLES = "REQUIRES_VARIABLES"
    REQUIRES_LAMBDA = "REQUIRES_LAMBDA"


class ClassifiedExpression(BaseModel):
    """An expression paired with its classification result.

    Example::

        ClassifiedExpression(
            original="{{ $json.name }}",
            category=ExpressionCategory.JSONATA_DIRECT,
            node_references=[],
            parameter_path="parameters.value",
        )
    """

    original: str
    category: ExpressionCategory
    node_references: list[str] = []
    parameter_path: str = ""


class ClassifiedNode(BaseModel):
    """A node paired with its classification and analyzed expressions.

    Example::

        ClassifiedNode(
            node=N8nNode(...),
            classification=NodeClassification.AWS_NATIVE,
            expressions=[],
        )
    """

    node: N8nNode
    classification: NodeClassification
    expressions: list[ClassifiedExpression] = []
    api_spec: str | None = None
    operation_mappings: dict[str, Any] | None = None


class DependencyEdge(BaseModel):
    """A directed edge in the workflow dependency graph.

    Example::

        DependencyEdge(
            from_node="Trigger",
            to_node="Process",
            edge_type="CONNECTION",
        )
    """

    from_node: str
    to_node: str
    edge_type: Literal["CONNECTION", "DATA_REFERENCE"]
    output_index: int | None = None


class WorkflowAnalysis(BaseModel):
    """Top-level analysis result from Component 2.

    Contains all classified nodes, dependency edges, variable mappings,
    and the overall confidence score for conversion feasibility.

    Example::

        WorkflowAnalysis(
            classified_nodes=[...],
            dependency_edges=[...],
            variables_needed={},
            confidence_score=0.85,
        )
    """

    classified_nodes: list[ClassifiedNode]
    dependency_edges: list[DependencyEdge]
    variables_needed: dict[str, str] = {}
    payload_warnings: list[str] = []
    unsupported_nodes: list[str] = []
    confidence_score: float = 0.0
