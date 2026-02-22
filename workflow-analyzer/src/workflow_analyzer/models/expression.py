"""Models for expression classification results."""

from enum import StrEnum

from pydantic import BaseModel


class ExpressionCategory(StrEnum):
    """Category for how an n8n expression should be translated."""

    JSONATA_DIRECT = "JSONATA_DIRECT"
    VARIABLE_REFERENCE = "VARIABLE_REFERENCE"
    LAMBDA_REQUIRED = "LAMBDA_REQUIRED"


class ClassifiedExpression(BaseModel):
    """An expression paired with its classification result."""

    node_name: str
    parameter_path: str
    raw_expression: str
    category: ExpressionCategory
    jsonata_preview: str | None = None
    referenced_nodes: list[str] = []
    reason: str = ""
