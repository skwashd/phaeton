"""Pydantic models for n8n workflow input.

These models represent the structure of an n8n workflow JSON export file.
They are used as input to the translation engine.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class N8nConnectionTarget(BaseModel):
    """A single connection endpoint pointing to a downstream node.

    Example::

        N8nConnectionTarget(node="Send Email", type="main", index=0)
    """

    node: str
    type: str
    index: int


class N8nNode(BaseModel):
    """A single node definition within an n8n workflow.

    Example::

        N8nNode(
            id="abc-123",
            name="HTTP Request",
            type="n8n-nodes-base.httpRequest",
            type_version=1,
            position=[250, 300],
            parameters={"url": "https://api.example.com"},
        )
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str
    name: str
    type: str
    type_version: int | float = Field(alias="typeVersion")
    position: list[float]
    parameters: dict[str, Any] = {}
    credentials: dict[str, Any] | None = None
    disabled: bool | None = None
    notes: str | None = None
    continue_on_fail: bool | None = Field(default=None, alias="continueOnFail")
    on_error: str | None = Field(default=None, alias="onError")
    retry_on_fail: bool | None = Field(default=None, alias="retryOnFail")
    max_tries: int | None = Field(default=None, alias="maxTries")
    wait_between_tries: int | None = Field(default=None, alias="waitBetweenTries")
    execute_once: bool | None = Field(default=None, alias="executeOnce")


class N8nSettings(BaseModel):
    """Execution settings for an n8n workflow.

    Example::

        N8nSettings(execution_order="v1", timezone="America/New_York")
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    execution_order: str | None = Field(default=None, alias="executionOrder")
    timezone: str | None = None
    save_manual_executions: bool | None = Field(
        default=None, alias="saveManualExecutions"
    )
    caller_policy: str | None = Field(default=None, alias="callerPolicy")


class N8nWorkflow(BaseModel):
    """Top-level model for an n8n workflow JSON export.

    Example::

        N8nWorkflow(
            name="My Workflow",
            nodes=[...],
            connections={...},
        )
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    name: str | None = None
    nodes: list[N8nNode]
    connections: dict[str, dict[str, list[list[N8nConnectionTarget]]]]
    settings: N8nSettings | None = None
    pin_data: dict[str, Any] | None = Field(default=None, alias="pinData")
    active: bool | None = None
    id: str | None = None
    tags: list[Any] | None = None
