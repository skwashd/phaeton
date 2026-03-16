"""
Boundary models for Translation Engine (Component 3) output.

These models represent the artifacts produced by the n8n-to-Step-Functions
translation engine. They are the canonical serialisation boundary between
Component 3 and downstream consumers such as the Packager adapter.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class LambdaRuntime(StrEnum):
    """
    Runtime for a generated Lambda function.

    Example::

        LambdaRuntime.PYTHON
    """

    PYTHON = "PYTHON"
    NODEJS = "NODEJS"


class TriggerType(StrEnum):
    """
    Type of trigger infrastructure to create.

    Example::

        TriggerType.EVENTBRIDGE_SCHEDULE
    """

    EVENTBRIDGE_SCHEDULE = "EVENTBRIDGE_SCHEDULE"
    LAMBDA_FURL = "LAMBDA_FURL"
    MANUAL = "MANUAL"


class LambdaArtifact(BaseModel):
    """
    A generated Lambda function artifact.

    Example::

        LambdaArtifact(
            function_name="process_data",
            runtime=LambdaRuntime.PYTHON,
            handler_code="def handler(event, context): ...",
        )
    """

    model_config = ConfigDict(frozen=True)

    function_name: str
    runtime: LambdaRuntime
    handler_code: str
    dependencies: list[str] = []
    directory_name: str = ""


class TriggerArtifact(BaseModel):
    """
    Infrastructure artifact for a workflow trigger.

    Example::

        TriggerArtifact(
            trigger_type=TriggerType.EVENTBRIDGE_SCHEDULE,
            config={"schedule_expression": "rate(5 minutes)"},
        )
    """

    model_config = ConfigDict(frozen=True)

    trigger_type: TriggerType
    config: dict[str, Any] = {}
    lambda_artifact: LambdaArtifact | None = None
    eventbridge_rule: dict[str, Any] | None = None


class CredentialArtifact(BaseModel):
    """
    A credential placeholder for SSM Parameter Store.

    Example::

        CredentialArtifact(
            parameter_path="/phaeton/creds/slack",
            credential_type="oauth2",
        )
    """

    model_config = ConfigDict(frozen=True)

    parameter_path: str
    credential_type: str
    auth_type: str = "api_key"
    placeholder_value: str = ""


class TranslationOutput(BaseModel):
    """
    Final output of the full translation pipeline.

    The ``state_machine`` field holds the serialised ASL definition as a
    plain dict (the result of calling ``model_dump(by_alias=True)`` on the
    engine's ``StateMachine`` Pydantic model).

    Example::

        TranslationOutput(
            state_machine={"StartAt": "S1", "States": {...}},
            lambda_artifacts=[...],
        )
    """

    model_config = ConfigDict(frozen=True)

    state_machine: dict[str, Any]
    lambda_artifacts: list[LambdaArtifact] = []
    trigger_artifacts: list[TriggerArtifact] = []
    credential_artifacts: list[CredentialArtifact] = []
    conversion_report: dict[str, Any] = {}
    warnings: list[str] = []
