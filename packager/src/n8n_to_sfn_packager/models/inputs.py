"""Pydantic v2 models defining the Packager's input contract.

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

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class LambdaFunctionType(StrEnum):
    """Classification of generated Lambda functions."""

    PICOFUN_API_CLIENT = "picofun_api_client"
    CODE_NODE_JS = "code_node_js"
    CODE_NODE_PYTHON = "code_node_python"
    WEBHOOK_HANDLER = "webhook_handler"
    CALLBACK_HANDLER = "callback_handler"
    OAUTH_REFRESH = "oauth_refresh"


class LambdaRuntime(StrEnum):
    """Supported Lambda runtimes."""

    NODEJS = "nodejs"
    PYTHON = "python"


class TriggerType(StrEnum):
    """Classification of workflow triggers."""

    SCHEDULE = "schedule"
    WEBHOOK = "webhook"
    MANUAL = "manual"
    APP_EVENT = "app_event"


class WebhookAuthType(StrEnum):
    """Supported webhook authentication methods."""

    API_KEY = "api_key"
    HMAC_SHA256 = "hmac_sha256"


class VpcBoundService(StrEnum):
    """Services that require VPC access for Lambda functions."""

    RDS_MYSQL = "rds_mysql"
    RDS_POSTGRESQL = "rds_postgresql"
    ELASTICACHE_REDIS = "elasticache_redis"
    ELASTICACHE_MEMCACHED = "elasticache_memcached"
    REDSHIFT = "redshift"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class VpcConfig(BaseModel):
    """VPC configuration for Lambda functions that access VPC-bound resources."""

    vpc_bound_services: list[VpcBoundService] = Field(
        ...,
        min_length=1,
        description="List of VPC-bound services the workflow accesses.",
    )

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
    """Authentication configuration for webhook/callback Lambda handlers."""

    auth_type: WebhookAuthType = Field(
        ...,
        description="Type of authentication to apply.",
    )
    credential_parameter_path: str = Field(
        ...,
        description="SSM Parameter Store path for the authentication secret.",
    )
    header_name: str = Field(
        default="x-api-key",
        description="HTTP header containing the API key or HMAC signature.",
    )

    @field_validator("credential_parameter_path")
    @classmethod
    def validate_credential_path(cls, v: str) -> str:
        """SSM parameter paths must start with '/'."""
        if not v.startswith("/"):
            msg = f"credential_parameter_path must start with '/': {v!r}"
            raise ValueError(msg)
        return v


class WorkflowMetadata(BaseModel):
    """Metadata about the source n8n workflow and the conversion."""

    workflow_name: str = Field(
        ...,
        min_length=1,
        description="Human-readable name of the n8n workflow.",
    )
    source_n8n_version: str = Field(
        ...,
        description="Version of n8n that produced the source workflow.",
    )
    converter_version: str = Field(
        ...,
        description="Version of the n8n-to-sfn converter.",
    )
    timestamp: str = Field(
        ...,
        description="ISO-8601 timestamp of the conversion.",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall conversion confidence (0.0-1.0).",
    )


class StateMachineDefinition(BaseModel):
    """The ASL state-machine definition produced by the Translation Engine."""

    asl: dict[str, Any] = Field(
        ...,
        description="Complete ASL definition as a JSON-serialisable dict.",
    )
    query_language: str = Field(
        default="JSONata",
        description="ASL QueryLanguage setting.",
    )


class LambdaFunctionSpec(BaseModel):
    """Specification for a single Lambda function to generate."""

    function_name: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Lambda function name (used as directory name and CDK construct ID).",
    )
    runtime: LambdaRuntime = Field(
        ...,
        description="Lambda runtime.",
    )
    handler_code: str = Field(
        ...,
        description="Source code for the handler file.",
    )
    description: str = Field(
        default="",
        description="Description tying this function back to the source n8n node.",
    )
    source_node_name: str = Field(
        default="",
        description="Name of the originating n8n node.",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Package dependencies with versions (e.g. 'httpx==0.27.0').",
    )
    function_type: LambdaFunctionType = Field(
        ...,
        description="Classification of this Lambda function.",
    )
    webhook_auth: WebhookAuthConfig | None = Field(
        default=None,
        description="Authentication configuration for webhook/callback handlers.",
    )

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
    """Specification for a single SSM parameter holding a credential."""

    parameter_path: str = Field(
        ...,
        description="SSM Parameter Store path (must start with '/').",
    )
    description: str = Field(
        default="",
        description="Human-readable description of the credential.",
    )
    credential_type: str = Field(
        ...,
        description="Type of credential (e.g. 'oauth2', 'apiKey').",
    )
    placeholder_value: str = Field(
        default="",
        description="Descriptive placeholder (e.g. '<your-slack-oauth-token>').",
    )
    associated_node_names: list[str] = Field(
        default_factory=list,
        description="n8n node names that use this credential.",
    )

    @field_validator("parameter_path")
    @classmethod
    def validate_parameter_path(cls, v: str) -> str:
        """SSM parameter paths must start with '/'."""
        if not v.startswith("/"):
            msg = f"parameter_path must start with '/': {v!r}"
            raise ValueError(msg)
        return v


class OAuthCredentialSpec(BaseModel):
    """Extended credential spec for OAuth2 credentials requiring token rotation."""

    credential_spec: CredentialSpec = Field(
        ...,
        description="Base credential specification.",
    )
    token_endpoint_url: str = Field(
        ...,
        description="OAuth2 token endpoint URL for refreshing tokens.",
    )
    refresh_schedule_expression: str = Field(
        default="rate(50 minutes)",
        description="EventBridge schedule expression for token rotation.",
    )
    scopes: list[str] = Field(
        default_factory=list,
        description="OAuth2 scopes requested during token refresh.",
    )


class TriggerSpec(BaseModel):
    """Specification for a workflow trigger."""

    trigger_type: TriggerType = Field(
        ...,
        description="Type of trigger.",
    )
    configuration: dict[str, Any] = Field(
        default_factory=dict,
        description="Trigger-specific configuration (schedule expression, webhook path, etc.).",
    )
    associated_lambda_name: str | None = Field(
        default=None,
        description="Name of the associated Lambda function (for webhook/app-event triggers).",
    )


class SubWorkflowReference(BaseModel):
    """Reference to a sub-workflow that must be deployed separately."""

    name: str = Field(
        ...,
        min_length=1,
        description="Name of the sub-workflow.",
    )
    source_workflow_file: str = Field(
        ...,
        description="Path to the source n8n workflow file.",
    )
    description: str = Field(
        default="",
        description="Human-readable description.",
    )


class ConversionReport(BaseModel):
    """Conversion feasibility report produced by the Translation Engine."""

    total_nodes: int = Field(
        ...,
        ge=0,
        description="Total number of nodes in the source workflow.",
    )
    classification_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description="Node classification counts (e.g. {'direct_map': 5, 'picofun': 3}).",
    )
    expression_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description="Expression translation counts (e.g. {'jsonata': 10, 'ai_assisted': 2}).",
    )
    unsupported_nodes: list[str] = Field(
        default_factory=list,
        description="List of node types that could not be converted.",
    )
    payload_warnings: list[str] = Field(
        default_factory=list,
        description="Warnings about potential payload size issues.",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Conversion confidence (0.0-1.0).",
    )
    ai_assisted_nodes: list[str] = Field(
        default_factory=list,
        description="Node names where AI-assisted translation was used.",
    )


# ---------------------------------------------------------------------------
# Top-level input model
# ---------------------------------------------------------------------------


class PackagerInput(BaseModel):
    """Top-level input to the Packager.

    This is the serialisation contract between the Translation Engine
    (Component 3) and the Packager (Component 4). The Translation Engine
    writes a JSON file conforming to this schema, and the Packager reads it.
    """

    metadata: WorkflowMetadata = Field(
        ...,
        description="Workflow and conversion metadata.",
    )
    state_machine: StateMachineDefinition = Field(
        ...,
        description="ASL state-machine definition.",
    )
    lambda_functions: list[LambdaFunctionSpec] = Field(
        default_factory=list,
        description="Lambda functions to generate.",
    )
    credentials: list[CredentialSpec] = Field(
        default_factory=list,
        description="Standard credential SSM parameters.",
    )
    oauth_credentials: list[OAuthCredentialSpec] = Field(
        default_factory=list,
        description="OAuth2 credentials requiring token rotation.",
    )
    triggers: list[TriggerSpec] = Field(
        default_factory=list,
        description="Workflow triggers.",
    )
    sub_workflows: list[SubWorkflowReference] = Field(
        default_factory=list,
        description="Sub-workflows referenced by this workflow.",
    )
    vpc_config: VpcConfig | None = Field(
        default=None,
        description="VPC configuration when workflow accesses VPC-bound resources.",
    )
    conversion_report: ConversionReport = Field(
        ...,
        description="Conversion feasibility report.",
    )
