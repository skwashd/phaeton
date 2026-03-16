"""
Pydantic v2 models defining the Packager's input contract.

This module re-exports the canonical boundary models from ``phaeton_models``
so that all internal packager code can continue to import from here without
change.
"""

from phaeton_models.packager_input import (
    ConversionReport,
    CredentialSpec,
    LambdaFunctionSpec,
    LambdaFunctionType,
    LambdaRuntime,
    OAuthCredentialSpec,
    PackagerInput,
    StateMachineDefinition,
    SubWorkflowReference,
    TriggerSpec,
    TriggerType,
    VpcBoundService,
    VpcConfig,
    WebhookAuthConfig,
    WebhookAuthType,
    WorkflowMetadata,
)

__all__ = [
    "ConversionReport",
    "CredentialSpec",
    "LambdaFunctionSpec",
    "LambdaFunctionType",
    "LambdaRuntime",
    "OAuthCredentialSpec",
    "PackagerInput",
    "StateMachineDefinition",
    "SubWorkflowReference",
    "TriggerSpec",
    "TriggerType",
    "VpcBoundService",
    "VpcConfig",
    "WebhookAuthConfig",
    "WebhookAuthType",
    "WorkflowMetadata",
]
