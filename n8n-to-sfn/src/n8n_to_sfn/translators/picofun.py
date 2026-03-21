"""PicoFun API client node translator."""

from __future__ import annotations

import logging
from typing import Any

from phaeton_models.translator import ClassifiedNode, NodeClassification

from n8n_to_sfn.models.asl import RetryConfig, TaskState
from n8n_to_sfn.translators.base import (
    BaseTranslator,
    CredentialArtifact,
    LambdaArtifact,
    LambdaRuntime,
    TranslationContext,
    TranslationResult,
    apply_error_handling,
)
from n8n_to_sfn.translators.picofun_bridge import PicoFunBridge
from n8n_to_sfn.translators.picofun_operation_mapper import (
    resolve_operation_to_endpoint,
)

logger = logging.getLogger(__name__)

_DEFAULT_RETRY = RetryConfig(
    error_equals=["States.TaskFailed"],
    interval_seconds=2,
    max_attempts=3,
    backoff_rate=2.0,
    max_delay_seconds=30,
)

_AUTH_TYPE_MAP: dict[str, str] = {
    "apiKey": "api_key",
    "oAuth2": "oauth2",
    "oAuth1": "oauth1",
    "basicAuth": "basic",
    "headerAuth": "api_key",
}


def _infer_auth_type(credential_type: str) -> str:
    """Infer the auth type from the credential type name."""
    lower = credential_type.lower()
    for key, val in _AUTH_TYPE_MAP.items():
        if key.lower() in lower:
            return val
    return "api_key"


def _build_ssm_path(workflow_name: str, credential_type: str) -> str:
    """Build the SSM parameter path for a credential."""
    safe_name = workflow_name.replace(" ", "-").lower() if workflow_name else "workflow"
    return f"/n8n-sfn/{safe_name}/{credential_type}"


class PicoFunTranslator(BaseTranslator):
    """Translates PicoFun-classified nodes into Lambda invoke Task states."""

    def __init__(self, bridge: PicoFunBridge | None = None) -> None:
        """Initialize translator with an optional PicoFun bridge."""
        self._bridge = bridge

    def can_translate(self, node: ClassifiedNode) -> bool:
        """Return True for PICOFUN_API classifications."""
        return node.classification == NodeClassification.PICOFUN_API

    def translate(
        self, node: ClassifiedNode, context: TranslationContext
    ) -> TranslationResult:
        """Translate a PicoFun node into a Lambda Task state + artifacts."""
        func_name = f"picofun_{node.node.name.replace(' ', '_').lower()}"

        # Build Lambda invocation arguments
        operation = node.node.parameters.get("operation", "default")
        resource = node.node.parameters.get("resource", "")
        arguments: dict[str, Any] = {
            "FunctionName": func_name,
            "Payload": {
                "operation": f"{resource}.{operation}" if resource else operation,
                "parameters": self._extract_api_params(node),
            },
        }

        # Add credential path if credentials exist
        credential_artifacts: list[CredentialArtifact] = []
        if node.node.credentials:
            for cred_type in node.node.credentials:
                ssm_path = _build_ssm_path(context.workflow_name, cred_type)
                arguments["Payload"]["credential_path"] = ssm_path
                credential_artifacts.append(
                    CredentialArtifact(
                        parameter_path=ssm_path,
                        credential_type=cred_type,
                        auth_type=_infer_auth_type(cred_type),
                        placeholder_value=f"<your-{cred_type}-credential>",
                    )
                )
                break  # Use first credential

        state = TaskState(
            resource="arn:aws:states:::lambda:invoke",
            arguments=arguments,
            end=True,
            retry=[_DEFAULT_RETRY],
        )
        state = apply_error_handling(state, node, default_retry=_DEFAULT_RETRY)

        # Attempt real PicoFun code generation, fall back to placeholder
        namespace = func_name
        generated = self._generate_handler_code(node, namespace)

        if generated is not None:
            handler_code = generated["handler_code"]
            dependencies = ["picorun", "requests", "aws-lambda-powertools"]
            if node.node.credentials:
                dependencies.append("boto3")
            metadata: dict[str, Any] = {
                "picofun_spec": generated["spec"],
                "picofun_function_names": generated["function_names"],
                "picofun_namespace": namespace,
            }
        else:
            handler_code = (
                f"# PicoFun-generated client for {node.node.type}\n"
                f"# API spec: {node.api_spec or 'unknown'}\n"
                f"# WARNING: PicoFun code generation was not available.\n"
                f"# This code is generated externally by PicoFun.\n"
            )
            dependencies = []
            metadata = {}

        lambda_artifact = LambdaArtifact(
            function_name=func_name,
            runtime=LambdaRuntime.PYTHON,
            handler_code=handler_code,
            dependencies=dependencies,
            directory_name=func_name,
            metadata=metadata,
        )

        return TranslationResult(
            states={node.node.name: state},
            lambda_artifacts=[lambda_artifact],
            credential_artifacts=credential_artifacts,
        )

    def _generate_handler_code(
        self, node: ClassifiedNode, namespace: str
    ) -> dict[str, Any] | None:
        """
        Attempt real PicoFun code generation.

        Returns a dict with handler_code, spec, function_names on success,
        or None if any step fails or preconditions are not met.
        """
        if self._bridge is None:
            return None
        if not node.api_spec:
            return None

        try:
            endpoint_info = resolve_operation_to_endpoint(
                node.node.parameters, node.operation_mappings
            )
            if endpoint_info is None:
                logger.warning("No operation mapping for node '%s'", node.node.name)
                return None

            method, path = endpoint_info

            api_spec = self._bridge.load_api_spec(node.api_spec)

            endpoint = self._bridge.find_endpoint(api_spec, method, path)
            if endpoint is None:
                logger.warning(
                    "Endpoint %s %s not found in spec '%s'",
                    method,
                    path,
                    node.api_spec,
                )
                return None

            base_url = api_spec.servers[0]["url"] if api_spec.servers else ""

            handler_code = self._bridge.render_endpoint(base_url, endpoint, namespace)
        except OSError, KeyError, ValueError, TypeError, RuntimeError:
            logger.warning(
                "PicoFun code generation failed for node '%s'",
                node.node.name,
                exc_info=True,
            )
            return None
        else:
            return {
                "handler_code": handler_code,
                "spec": node.api_spec,
                "function_names": [namespace],
            }

    @staticmethod
    def _extract_api_params(node: ClassifiedNode) -> dict[str, str]:
        """Extract API parameters from node params, excluding metadata fields."""
        skip_keys = {"resource", "operation", "authentication"}
        params: dict[str, str] = {}
        for key, value in node.node.parameters.items():
            if key not in skip_keys:
                params[key] = str(value)
        return params
