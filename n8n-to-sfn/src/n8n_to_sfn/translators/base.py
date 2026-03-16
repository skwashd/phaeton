"""Abstract base translator interface and shared translation models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from phaeton_models.translator import ClassifiedNode, WorkflowAnalysis
from pydantic import BaseModel, ConfigDict

from n8n_to_sfn.models.asl import (
    CatchConfig,
    RetryConfig,
    StateMachine,
    TaskState,
)


class LambdaRuntime(StrEnum):
    """Runtime for a generated Lambda function."""

    PYTHON = "PYTHON"
    NODEJS = "NODEJS"


class LambdaArtifact(BaseModel):
    """A generated Lambda function artifact."""

    model_config = ConfigDict(frozen=True)

    function_name: str
    runtime: LambdaRuntime
    handler_code: str
    dependencies: list[str] = []
    directory_name: str = ""


class TriggerType(StrEnum):
    """Type of trigger infrastructure to create."""

    EVENTBRIDGE_SCHEDULE = "EVENTBRIDGE_SCHEDULE"
    LAMBDA_FURL = "LAMBDA_FURL"
    MANUAL = "MANUAL"


class TriggerArtifact(BaseModel):
    """Infrastructure artifact for a workflow trigger."""

    model_config = ConfigDict(frozen=True)

    trigger_type: TriggerType
    config: dict[str, Any] = {}
    lambda_artifact: LambdaArtifact | None = None
    eventbridge_rule: dict[str, Any] | None = None


class CredentialArtifact(BaseModel):
    """A credential placeholder for SSM Parameter Store."""

    model_config = ConfigDict(frozen=True)

    parameter_path: str
    credential_type: str
    auth_type: str = "api_key"
    placeholder_value: str = ""


class TranslationContext(BaseModel):
    """Context available during translation of each node."""

    model_config = ConfigDict(frozen=True)

    analysis: WorkflowAnalysis
    state_machine: StateMachine | None = None
    resolved_variables: dict[str, Any] = {}
    payload_size_limit: int = 256_000
    rate_limits: dict[str, int] = {}
    workflow_name: str = ""


class TranslationResult(BaseModel):
    """Result of translating a single node."""

    model_config = ConfigDict(frozen=True)

    states: dict[str, Any] = {}
    lambda_artifacts: list[LambdaArtifact] = []
    trigger_artifacts: list[TriggerArtifact] = []
    credential_artifacts: list[CredentialArtifact] = []
    variables_to_assign: dict[str, Any] = {}
    warnings: list[str] = []
    metadata: dict[str, Any] = {}


class BaseTranslator(ABC):
    """Abstract base class for node translators."""

    @abstractmethod
    def can_translate(self, node: ClassifiedNode) -> bool:
        """Return True if this translator handles this node classification."""

    @abstractmethod
    def translate(
        self, node: ClassifiedNode, context: TranslationContext
    ) -> TranslationResult:
        """Translate a single classified node into ASL state(s) and artifacts."""


def build_error_handling(
    node: ClassifiedNode,
    next_state_name: str | None = None,
    default_retry: RetryConfig | None = None,
) -> tuple[list[RetryConfig], list[CatchConfig]]:
    """
    Build Retry and Catch configs from n8n node error settings.

    Merges explicit node settings with an optional default retry config.
    Explicit settings take precedence over defaults.
    """
    retries: list[RetryConfig] = []
    catches: list[CatchConfig] = []

    n8n_node = node.node

    if n8n_node.retry_on_fail:
        max_attempts = n8n_node.max_tries if n8n_node.max_tries is not None else 3
        wait_ms = (
            n8n_node.wait_between_tries
            if n8n_node.wait_between_tries is not None
            else 1000
        )
        retries.append(
            RetryConfig(
                error_equals=["States.ALL"],
                max_attempts=max_attempts,
                interval_seconds=wait_ms // 1000,
                backoff_rate=2.0,
            )
        )
    elif default_retry is not None:
        retries.append(default_retry)

    if n8n_node.continue_on_fail and next_state_name:
        catches.append(
            CatchConfig(
                error_equals=["States.ALL"],
                next=next_state_name,
            )
        )

    return retries, catches


def apply_error_handling(
    state: TaskState,
    node: ClassifiedNode,
    next_state_name: str | None = None,
    default_retry: RetryConfig | None = None,
) -> TaskState:
    """Apply error handling to a TaskState based on n8n node settings."""
    retries, catches = build_error_handling(node, next_state_name, default_retry)
    updates: dict[str, Any] = {}
    if retries:
        updates["retry"] = retries
    if catches:
        updates["catch"] = catches
    if updates:
        return state.model_copy(update=updates)
    return state
