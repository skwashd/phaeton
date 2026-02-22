"""Models for node classification results."""

from enum import StrEnum

from pydantic import BaseModel

from workflow_analyzer.models.n8n_workflow import N8nNode


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

    node: N8nNode
    category: NodeCategory
    translation_strategy: str
    notes: str | None = None
