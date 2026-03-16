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

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class WebhookAuthType(StrEnum):
    """
    Supported webhook authentication methods.

    Example::

        WebhookAuthType.API_KEY
    """

    API_KEY = "api_key"
    HMAC_SHA256 = "hmac_sha256"


class VpcBoundService(StrEnum):
    """
    Services that require VPC access for Lambda functions.

    Example::

        VpcBoundService.RDS_MYSQL
    """

    RDS_MYSQL = "rds_mysql"
    RDS_POSTGRESQL = "rds_postgresql"
    ELASTICACHE_REDIS = "elasticache_redis"
    ELASTICACHE_MEMCACHED = "elasticache_memcached"
    REDSHIFT = "redshift"


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

    model_config = ConfigDict(frozen=True)

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

    model_config = ConfigDict(frozen=True)

    asl: dict[str, Any]
    query_language: str = "JSONata"


class VpcConfig(BaseModel):
    """
    VPC configuration for Lambda functions that access VPC-bound resources.

    Example::

        VpcConfig(vpc_bound_services=[VpcBoundService.RDS_MYSQL])
    """

    model_config = ConfigDict(frozen=True)

    vpc_bound_services: list[VpcBoundService] = Field(..., min_length=1)

    @property
    def security_group_rules(self) -> list[dict[str, Any]]:
        """Derive egress rules from the declared VPC-bound services."""
        port_map: dict[VpcBoundService, tuple[int, str]] = {
            VpcBoundService.RDS_MYSQL: (3306, "MySQL"),
            VpcBoundService.RDS_POSTGRESQL: (5432, "PostgreSQL"),
            VpcBoundService.ELASTICACHE_REDIS: (6379, "Redis"),
            VpcBoundService.ELASTICACHE_MEMCACHED: (11211, "Memcached"),
            VpcBoundService.REDSHIFT: (5439, "Redshift"),
        }
        rules = []
        for svc in self.vpc_bound_services:
            port, desc = port_map[svc]
            rules.append({"port": port, "description": desc})
        return rules


class WebhookAuthConfig(BaseModel):
    """
    Authentication configuration for webhook/callback Lambda handlers.

    Example::

        WebhookAuthConfig(
            auth_type=WebhookAuthType.API_KEY,
            credential_parameter_path="/phaeton/creds/webhook-secret",
        )
    """

    model_config = ConfigDict(frozen=True)

    auth_type: WebhookAuthType
    credential_parameter_path: str
    header_name: str = "x-api-key"

    @field_validator("credential_parameter_path")
    @classmethod
    def validate_credential_path(cls, v: str) -> str:
        """SSM parameter paths must start with '/'."""
        if not v.startswith("/"):
            msg = f"credential_parameter_path must start with '/': {v!r}"
            raise ValueError(msg)
        return v


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

    model_config = ConfigDict(frozen=True)

    function_name: str = Field(..., min_length=1, max_length=64)
    runtime: LambdaRuntime
    handler_code: str
    description: str = ""
    source_node_name: str = ""
    dependencies: list[str] = Field(default_factory=list)
    function_type: LambdaFunctionType
    webhook_auth: WebhookAuthConfig | None = None

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

    model_config = ConfigDict(frozen=True)

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


class OAuthCredentialSpec(BaseModel):
    """
    Extended credential spec for OAuth2 credentials requiring token rotation.

    Example::

        OAuthCredentialSpec(
            credential_spec=CredentialSpec(
                parameter_path="/phaeton/creds/oauth",
                credential_type="oauth2",
            ),
            token_endpoint_url="https://oauth.example.com/token",
        )
    """

    model_config = ConfigDict(frozen=True)

    credential_spec: CredentialSpec
    token_endpoint_url: str
    refresh_schedule_expression: str = "rate(50 minutes)"
    scopes: list[str] = Field(default_factory=list)


class TriggerSpec(BaseModel):
    """
    Specification for a workflow trigger.

    Example::

        TriggerSpec(trigger_type=TriggerType.SCHEDULE)
    """

    model_config = ConfigDict(frozen=True)

    trigger_type: TriggerType
    configuration: dict[str, Any] = Field(default_factory=dict)
    associated_lambda_name: str | None = None


class SubWorkflowReference(BaseModel):
    """
    Reference to a sub-workflow that must be deployed separately.

    Example::

        SubWorkflowReference(
            name="process-order",
            source_workflow_file="process_order.json",
        )
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., min_length=1)
    source_workflow_file: str
    description: str = ""


class ConversionReport(BaseModel):
    """
    Conversion feasibility report produced by the Translation Engine.

    Example::

        ConversionReport(total_nodes=5, confidence_score=0.85)
    """

    model_config = ConfigDict(frozen=True)

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

    model_config = ConfigDict(frozen=True)

    metadata: WorkflowMetadata
    state_machine: StateMachineDefinition
    lambda_functions: list[LambdaFunctionSpec] = Field(default_factory=list)
    credentials: list[CredentialSpec] = Field(default_factory=list)
    oauth_credentials: list[OAuthCredentialSpec] = Field(default_factory=list)
    triggers: list[TriggerSpec] = Field(default_factory=list)
    sub_workflows: list[SubWorkflowReference] = Field(default_factory=list)
    vpc_config: VpcConfig | None = None
    conversion_report: ConversionReport
