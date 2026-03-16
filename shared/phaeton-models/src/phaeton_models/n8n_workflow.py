"""Pydantic v2 models representing the structure of an n8n workflow JSON export."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConnectionTarget(BaseModel):
    """A single connection target pointing to a downstream node."""

    model_config = ConfigDict(frozen=True)

    node: str
    type: str
    index: int


class N8nNode(BaseModel):
    """A single node definition within an n8n workflow."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, frozen=True)

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


class WorkflowSettings(BaseModel):
    """Execution settings for a workflow."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, frozen=True)

    execution_order: str | None = Field(default=None, alias="executionOrder")
    timezone: str | None = None
    save_manual_executions: bool | None = Field(
        default=None, alias="saveManualExecutions"
    )
    caller_policy: str | None = Field(default=None, alias="callerPolicy")


class N8nWorkflow(BaseModel):
    """Top-level model for an n8n workflow JSON export."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, frozen=True)

    name: str | None = None
    nodes: list[N8nNode]
    connections: dict[str, dict[str, list[list[ConnectionTarget]]]]
    settings: WorkflowSettings | None = None
    pin_data: dict[str, Any] | None = Field(default=None, alias="pinData")
    active: bool | None = None
    id: str | None = None
    tags: list[Any] | None = None
