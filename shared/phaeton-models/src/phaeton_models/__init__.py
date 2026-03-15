"""Shared Pydantic v2 models for the Phaeton pipeline."""

from phaeton_models.n8n_workflow import (
    ConnectionTarget,
    N8nNode,
    N8nWorkflow,
    WorkflowSettings,
)

__all__ = [
    "ConnectionTarget",
    "N8nNode",
    "N8nWorkflow",
    "WorkflowSettings",
]
