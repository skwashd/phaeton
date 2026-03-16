"""
Adapter converting Translation Engine output to Packager input.

Bridges the contract gap between Component 3 (``TranslationOutput``) and
Component 4 (``PackagerInput``) by mapping enum values, field names, and
structural differences.
"""

from __future__ import annotations

from datetime import UTC, datetime

from phaeton_models.packager_input import (
    ConversionReport,
    CredentialSpec,
    LambdaFunctionSpec,
    LambdaFunctionType,
    OAuthCredentialSpec,
    PackagerInput,
    StateMachineDefinition,
    TriggerSpec,
    WorkflowMetadata,
)
from phaeton_models.packager_input import (
    LambdaRuntime as PkgLambdaRuntime,
)
from phaeton_models.packager_input import (
    TriggerType as PkgTriggerType,
)
from phaeton_models.translator_output import (
    CredentialArtifact,
    LambdaArtifact,
    TranslationOutput,
    TriggerArtifact,
)
from phaeton_models.translator_output import (
    LambdaRuntime as EngLambdaRuntime,
)
from phaeton_models.translator_output import (
    TriggerType as EngTriggerType,
)

_RUNTIME_MAP: dict[EngLambdaRuntime, PkgLambdaRuntime] = {
    EngLambdaRuntime.PYTHON: PkgLambdaRuntime.PYTHON,
    EngLambdaRuntime.NODEJS: PkgLambdaRuntime.NODEJS,
}

_TRIGGER_TYPE_MAP: dict[EngTriggerType, PkgTriggerType] = {
    EngTriggerType.EVENTBRIDGE_SCHEDULE: PkgTriggerType.SCHEDULE,
    EngTriggerType.LAMBDA_FURL: PkgTriggerType.WEBHOOK,
    EngTriggerType.MANUAL: PkgTriggerType.MANUAL,
}


def convert_output_to_packager_input(
    output: TranslationOutput,
    workflow_name: str,
) -> PackagerInput:
    """
    Convert a ``TranslationOutput`` into a ``PackagerInput``.

    Maps all enum values, field names, and structural differences between
    the translation engine output and the packager input contract.

    Parameters
    ----------
    output:
        The translation pipeline output.
    workflow_name:
        Human-readable name for the workflow.

    Returns
    -------
    PackagerInput
        The input model expected by the packager.

    """
    lambda_functions = [_convert_lambda(a) for a in output.lambda_artifacts]
    triggers = [_convert_trigger(a) for a in output.trigger_artifacts]

    credentials: list[CredentialSpec] = []
    oauth_credentials: list[OAuthCredentialSpec] = []
    for artifact in output.credential_artifacts:
        cred = _convert_credential(artifact)
        if artifact.auth_type == "oauth2":
            oauth_credentials.append(
                _convert_oauth_credential(artifact, cred),
            )
        else:
            credentials.append(cred)

    report = output.conversion_report
    confidence = _normalise_confidence(report.get("confidence_score", 0.0))

    metadata = WorkflowMetadata(
        workflow_name=workflow_name,
        source_n8n_version=report.get("source_n8n_version", "unknown"),
        converter_version=report.get("converter_version", "0.1.0"),
        timestamp=report.get("timestamp", datetime.now(tz=UTC).isoformat()),
        confidence_score=confidence,
    )

    state_machine = StateMachineDefinition(asl=output.state_machine)

    conversion_report = ConversionReport(
        total_nodes=report.get("total_nodes", 0),
        classification_breakdown=report.get("classification_breakdown", {}),
        expression_breakdown=report.get("expression_breakdown", {}),
        unsupported_nodes=report.get("unsupported_nodes", []),
        payload_warnings=report.get("payload_warnings", []),
        confidence_score=confidence,
        ai_assisted_nodes=report.get("ai_assisted_nodes", []),
    )

    return PackagerInput(
        metadata=metadata,
        state_machine=state_machine,
        lambda_functions=lambda_functions,
        credentials=credentials,
        oauth_credentials=oauth_credentials,
        triggers=triggers,
        conversion_report=conversion_report,
    )


def map_runtime(runtime: EngLambdaRuntime) -> PkgLambdaRuntime:
    """
    Map a Translation Engine ``LambdaRuntime`` to the Packager equivalent.

    Raises
    ------
    ValueError
        If the runtime value is not recognised.

    """
    try:
        return _RUNTIME_MAP[runtime]
    except KeyError:
        msg = f"Unknown LambdaRuntime: {runtime!r}"
        raise ValueError(msg) from None


def map_trigger_type(trigger_type: EngTriggerType) -> PkgTriggerType:
    """
    Map a Translation Engine ``TriggerType`` to the Packager equivalent.

    Raises
    ------
    ValueError
        If the trigger type value is not recognised.

    """
    try:
        return _TRIGGER_TYPE_MAP[trigger_type]
    except KeyError:
        msg = f"Unknown TriggerType: {trigger_type!r}"
        raise ValueError(msg) from None


def _convert_lambda(artifact: LambdaArtifact) -> LambdaFunctionSpec:
    """Convert a ``LambdaArtifact`` to a ``LambdaFunctionSpec``."""
    runtime = map_runtime(artifact.runtime)
    function_type = _infer_function_type(artifact, runtime)
    return LambdaFunctionSpec(
        function_name=artifact.function_name,
        runtime=runtime,
        handler_code=artifact.handler_code,
        dependencies=artifact.dependencies,
        function_type=function_type,
    )


def _convert_trigger(artifact: TriggerArtifact) -> TriggerSpec:
    """Convert a ``TriggerArtifact`` to a ``TriggerSpec``."""
    trigger_type = map_trigger_type(artifact.trigger_type)
    associated_lambda_name = (
        artifact.lambda_artifact.function_name if artifact.lambda_artifact else None
    )
    return TriggerSpec(
        trigger_type=trigger_type,
        configuration=artifact.config,
        associated_lambda_name=associated_lambda_name,
    )


def _convert_credential(artifact: CredentialArtifact) -> CredentialSpec:
    """Convert a ``CredentialArtifact`` to a ``CredentialSpec``."""
    path = artifact.parameter_path
    if not path.startswith("/"):
        path = f"/{path}"
    return CredentialSpec(
        parameter_path=path,
        credential_type=artifact.credential_type,
        placeholder_value=artifact.placeholder_value,
    )


def _convert_oauth_credential(
    artifact: CredentialArtifact,
    cred: CredentialSpec,
) -> OAuthCredentialSpec:
    """Convert an OAuth2 ``CredentialArtifact`` to an ``OAuthCredentialSpec``."""
    return OAuthCredentialSpec(
        credential_spec=cred,
        token_endpoint_url=artifact.placeholder_value
        or "https://oauth.example.com/token",
    )


def _infer_function_type(
    artifact: LambdaArtifact,
    runtime: PkgLambdaRuntime,
) -> LambdaFunctionType:
    """
    Infer the ``LambdaFunctionType`` from artifact metadata.

    Uses the function name as a heuristic, falling back to a
    runtime-based default.
    """
    name = artifact.function_name.lower()
    if "webhook" in name:
        return LambdaFunctionType.WEBHOOK_HANDLER
    if "callback" in name:
        return LambdaFunctionType.CALLBACK_HANDLER
    if "oauth" in name or "refresh_token" in name:
        return LambdaFunctionType.OAUTH_REFRESH
    if "picofun" in name or "api_client" in name:
        return LambdaFunctionType.PICOFUN_API_CLIENT
    if runtime == PkgLambdaRuntime.PYTHON:
        return LambdaFunctionType.CODE_NODE_PYTHON
    return LambdaFunctionType.CODE_NODE_JS


def _normalise_confidence(value: float) -> float:
    """Normalise a confidence score to the 0.0-1.0 range."""
    score = float(value)
    if score > 1.0:
        return score / 100.0
    return score
