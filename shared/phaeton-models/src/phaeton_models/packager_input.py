"""
Boundary models for the Packager (Component 4) input contract.

These models represent the serialisation boundary between Component 3
(Translation Engine) and Component 4 (Packager). The Translation Engine
produces a JSON file conforming to ``PackagerInput``, and the Packager
consumes it.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class LambdaFunctionType(StrEnum):
    """
    Classification of generated Lambda functions.

    Example::

        LambdaFunctionType.CODE_NODE_PYTHON
    """

    PICOFUN_API_CLIENT = "picofun_api_client"
    CODE_NODE_JS = "code_node_js"
    CODE_NODE_PYTHON = "code_node_python"
    WEBHOOK_HANDLER = "webhook_handler"
    CALLBACK_HANDLER = "callback_handler"
    OAUTH_REFRESH = "oauth_refresh"


class LambdaRuntime(StrEnum):
    """
    Supported Lambda runtimes.

    Example::

        LambdaRuntime.PYTHON
    """

    NODEJS = "nodejs"
    PYTHON = "python"


class TriggerType(StrEnum):
    """
    Classification of workflow triggers.

    Example::

        TriggerType.SCHEDULE
    """

    SCHEDULE = "schedule"
    WEBHOOK = "webhook"
    MANUAL = "manual"
    APP_EVENT = "app_event"


class WorkflowMetadata(BaseModel):
    """
    Metadata about the source n8n workflow and the conversion.

    Example::

        WorkflowMetadata(
            workflow_name="my-workflow",
            source_n8n_version="1.0.0",
            converter_version="0.1.0",
            timestamp="2024-01-01T00:00:00Z",
            confidence_score=0.85,
        )
    """

    workflow_name: str = Field(..., min_length=1)
    source_n8n_version: str
    converter_version: str
    timestamp: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)


class StateMachineDefinition(BaseModel):
    """
    The ASL state-machine definition produced by the Translation Engine.

    Example::

        StateMachineDefinition(
            asl={"StartAt": "S1", "States": {"S1": {"Type": "Pass", "End": True}}},
        )
    """

    asl: dict[str, Any]
    query_language: str = "JSONata"


class LambdaFunctionSpec(BaseModel):
    """
    Specification for a single Lambda function to generate.

    Example::

        LambdaFunctionSpec(
            function_name="process_data",
            runtime=LambdaRuntime.PYTHON,
            handler_code="def handler(event, context): ...",
            function_type=LambdaFunctionType.CODE_NODE_PYTHON,
        )
    """

    function_name: str = Field(..., min_length=1, max_length=64)
    runtime: LambdaRuntime
    handler_code: str
    description: str = ""
    source_node_name: str = ""
    dependencies: list[str] = Field(default_factory=list)
    function_type: LambdaFunctionType

    @field_validator("function_name")
    @classmethod
    def validate_function_name(cls, v: str) -> str:
        """Ensure the function name is a valid Lambda / directory name."""
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            msg = (
                f"function_name must contain only alphanumerics, hyphens, "
                f"and underscores: {v!r}"
            )
            raise ValueError(msg)
        return v


class CredentialSpec(BaseModel):
    """
    Specification for a single SSM parameter holding a credential.

    Example::

        CredentialSpec(
            parameter_path="/phaeton/creds/slack",
            credential_type="oauth2",
        )
    """

    parameter_path: str
    description: str = ""
    credential_type: str
    placeholder_value: str = ""
    associated_node_names: list[str] = Field(default_factory=list)

    @field_validator("parameter_path")
    @classmethod
    def validate_parameter_path(cls, v: str) -> str:
        """SSM parameter paths must start with '/'."""
        if not v.startswith("/"):
            msg = f"parameter_path must start with '/': {v!r}"
            raise ValueError(msg)
        return v


class TriggerSpec(BaseModel):
    """
    Specification for a workflow trigger.

    Example::

        TriggerSpec(trigger_type=TriggerType.SCHEDULE)
    """

    trigger_type: TriggerType
    configuration: dict[str, Any] = Field(default_factory=dict)
    associated_lambda_name: str | None = None


class ConversionReport(BaseModel):
    """
    Conversion feasibility report produced by the Translation Engine.

    Example::

        ConversionReport(total_nodes=5, confidence_score=0.85)
    """

    total_nodes: int = Field(..., ge=0)
    classification_breakdown: dict[str, int] = Field(default_factory=dict)
    expression_breakdown: dict[str, int] = Field(default_factory=dict)
    unsupported_nodes: list[str] = Field(default_factory=list)
    payload_warnings: list[str] = Field(default_factory=list)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    ai_assisted_nodes: list[str] = Field(default_factory=list)


class PackagerInput(BaseModel):
    """
    Top-level input to the Packager.

    This is the serialisation contract between the Translation Engine
    (Component 3) and the Packager (Component 4).

    Example::

        PackagerInput(
            metadata=WorkflowMetadata(...),
            state_machine=StateMachineDefinition(asl={...}),
            conversion_report=ConversionReport(total_nodes=0, confidence_score=0.0),
        )
    """

    metadata: WorkflowMetadata
    state_machine: StateMachineDefinition
    lambda_functions: list[LambdaFunctionSpec] = Field(default_factory=list)
    credentials: list[CredentialSpec] = Field(default_factory=list)
    triggers: list[TriggerSpec] = Field(default_factory=list)
    conversion_report: ConversionReport
