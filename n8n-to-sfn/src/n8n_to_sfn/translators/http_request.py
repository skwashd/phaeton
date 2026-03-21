"""
HTTP Request node translator.

Converts ``n8n-nodes-base.httpRequest`` nodes into Step Functions
``http:invoke`` Task states with authentication support.
"""

from __future__ import annotations

from typing import Any

from phaeton_models.translator import ClassifiedNode

from n8n_to_sfn.models.asl import RetryConfig, TaskState
from n8n_to_sfn.translators.base import (
    BaseTranslator,
    CredentialArtifact,
    TranslationContext,
    TranslationResult,
    apply_error_handling,
)

_HTTP_REQUEST_TYPE = "n8n-nodes-base.httpRequest"

_DEFAULT_RETRY = RetryConfig(  # type: ignore[missing-argument]
    error_equals=["States.TaskFailed"],  # type: ignore[unknown-argument]
    interval_seconds=2,
    max_attempts=3,
    backoff_rate=2.0,
    max_delay_seconds=30,
)

_AUTH_TYPE_MAP: dict[str, str] = {
    "genericCredentialType": "api_key",
    "predefinedCredentialType": "api_key",
    "none": "none",
}


def _build_ssm_path(workflow_name: str, credential_type: str) -> str:
    """Build the SSM parameter path for a credential."""
    safe_name = workflow_name.replace(" ", "-").lower() if workflow_name else "workflow"
    return f"/n8n-sfn/{safe_name}/{credential_type}"


def _extract_key_value_pairs(params: list[dict[str, Any]]) -> dict[str, str]:
    """
    Extract key-value pairs from n8n parameter lists.

    n8n stores header and query parameters as lists of dicts with
    ``name``/``value`` keys.
    """
    result: dict[str, str] = {}
    for item in params:
        name = item.get("name", "")
        value = item.get("value", "")
        if name:
            result[name] = str(value)
    return result


class HttpRequestTranslator(BaseTranslator):
    """Translates HTTP Request nodes into ``http:invoke`` Task states."""

    def can_translate(self, node: ClassifiedNode) -> bool:
        """Return True for ``n8n-nodes-base.httpRequest`` nodes."""
        return node.node.type == _HTTP_REQUEST_TYPE

    def translate(
        self, node: ClassifiedNode, context: TranslationContext
    ) -> TranslationResult:
        """Translate an HTTP Request node into an http:invoke Task state."""
        params = node.node.parameters
        method = str(params.get("method", "GET")).upper()
        url = params.get("url", "")

        arguments: dict[str, Any] = {
            "ApiEndpoint": url,
            "Method": method,
        }

        headers = self._extract_headers(params)
        if headers:
            arguments["Headers"] = headers

        query_params = self._extract_query_params(params)
        if query_params:
            arguments["QueryParameters"] = query_params

        body = self._extract_body(params)
        if body is not None:
            arguments["RequestBody"] = body

        # Handle authentication
        credential_artifacts: list[CredentialArtifact] = []
        warnings: list[str] = []
        auth_type = str(params.get("authentication", "none"))

        if auth_type != "none":
            cred_artifacts, _auth_config = self._build_auth(
                node,
                context,
                auth_type,
                arguments,
                warnings,
            )
            credential_artifacts.extend(cred_artifacts)

        state = TaskState(  # type: ignore[missing-argument]
            resource="arn:aws:states:::http:invoke",  # type: ignore[unknown-argument]
            arguments=arguments,
            end=True,
            retry=[_DEFAULT_RETRY],
        )
        state = apply_error_handling(state, node, default_retry=_DEFAULT_RETRY)

        return TranslationResult(
            states={node.node.name: state},
            credential_artifacts=credential_artifacts,
            warnings=warnings,
        )

    @staticmethod
    def _extract_headers(params: dict[str, Any]) -> dict[str, str]:
        """Extract headers from n8n node parameters."""
        header_params = params.get("headerParameters", {})
        if isinstance(header_params, dict):
            items = header_params.get("parameters", [])
        elif isinstance(header_params, list):
            items = header_params
        else:
            return {}
        return _extract_key_value_pairs(items)

    @staticmethod
    def _extract_query_params(params: dict[str, Any]) -> dict[str, str]:
        """Extract query parameters from n8n node parameters."""
        query_params = params.get("queryParameters", {})
        if isinstance(query_params, dict):
            items = query_params.get("parameters", [])
        elif isinstance(query_params, list):
            items = query_params
        else:
            return {}
        return _extract_key_value_pairs(items)

    @staticmethod
    def _extract_body(params: dict[str, Any]) -> dict[str, Any] | str | None:
        """Extract request body from n8n node parameters."""
        # Check for JSON body first
        json_body = params.get("jsonBody")
        if json_body is not None:
            return json_body

        # Check for body parameters (form-style)
        body_params = params.get("bodyParameters", {})
        if isinstance(body_params, dict):
            items = body_params.get("parameters", [])
        elif isinstance(body_params, list):
            items = body_params
        else:
            return None

        if items:
            return _extract_key_value_pairs(items)
        return None

    def _build_auth(
        self,
        node: ClassifiedNode,
        context: TranslationContext,
        auth_type: str,
        arguments: dict[str, Any],
        warnings: list[str],
    ) -> tuple[list[CredentialArtifact], dict[str, Any]]:
        """Build authentication configuration and credential artifacts."""
        credential_artifacts: list[CredentialArtifact] = []
        auth_config: dict[str, Any] = {}

        if auth_type == "genericCredentialType":
            credential_artifacts, auth_config = self._build_generic_auth(
                node,
                context,
                arguments,
                warnings,
            )
        elif auth_type == "predefinedCredentialType":
            credential_artifacts, auth_config = self._build_predefined_auth(
                node,
                context,
                arguments,
                warnings,
            )

        return credential_artifacts, auth_config

    def _build_generic_auth(
        self,
        node: ClassifiedNode,
        context: TranslationContext,
        arguments: dict[str, Any],
        warnings: list[str],
    ) -> tuple[list[CredentialArtifact], dict[str, Any]]:
        """Build auth for genericCredentialType (API key, bearer, basic)."""
        params = node.node.parameters
        generic_type = str(params.get("genericAuthType", ""))

        if generic_type == "httpHeaderAuth":
            return self._build_bearer_or_header_auth(
                node,
                context,
                arguments,
            )
        if generic_type == "httpBasicAuth":
            return self._build_basic_auth(node, context, arguments)
        if generic_type == "httpQueryAuth":
            return self._build_query_auth(node, context, arguments)

        warnings.append(
            f"Unsupported generic auth type '{generic_type}' for node "
            f"'{node.node.name}'. Authentication skipped."
        )
        return [], {}

    def _build_predefined_auth(
        self,
        node: ClassifiedNode,
        context: TranslationContext,
        arguments: dict[str, Any],
        warnings: list[str],
    ) -> tuple[list[CredentialArtifact], dict[str, Any]]:
        """Build auth for predefinedCredentialType (OAuth2, etc.)."""
        params = node.node.parameters
        cred_type = str(params.get("nodeCredentialType", ""))

        if not cred_type:
            # Fall back to credentials dict
            if node.node.credentials:
                cred_type = next(iter(node.node.credentials))
            else:
                warnings.append(
                    f"No credential type found for node '{node.node.name}'."
                )
                return [], {}

        ssm_path = _build_ssm_path(context.workflow_name, cred_type)
        auth_type = "oauth2" if "oauth2" in cred_type.lower() else "api_key"

        arguments["Authentication"] = {
            "ConnectionArn.$": f"$.credentials.{cred_type}",
        }

        return [
            CredentialArtifact(
                parameter_path=ssm_path,
                credential_type=cred_type,
                auth_type=auth_type,
                placeholder_value=f"<your-{cred_type}-credential>",
            ),
        ], {}

    @staticmethod
    def _build_bearer_or_header_auth(
        node: ClassifiedNode,
        context: TranslationContext,
        arguments: dict[str, Any],
    ) -> tuple[list[CredentialArtifact], dict[str, Any]]:
        """Build bearer token or header-based auth."""
        cred_type = "httpHeaderAuth"
        if node.node.credentials:
            cred_type = next(iter(node.node.credentials), cred_type)

        ssm_path = _build_ssm_path(context.workflow_name, cred_type)

        # Inject Authorization header placeholder; actual value comes from SSM
        headers = arguments.get("Headers", {})
        headers["Authorization"] = f"${{{ssm_path}}}"
        arguments["Headers"] = headers

        return [
            CredentialArtifact(
                parameter_path=ssm_path,
                credential_type=cred_type,
                auth_type="api_key",
                placeholder_value="<your-bearer-token>",
            ),
        ], {}

    @staticmethod
    def _build_basic_auth(
        node: ClassifiedNode,
        context: TranslationContext,
        arguments: dict[str, Any],
    ) -> tuple[list[CredentialArtifact], dict[str, Any]]:
        """Build HTTP Basic auth."""
        cred_type = "httpBasicAuth"
        if node.node.credentials:
            cred_type = next(iter(node.node.credentials), cred_type)

        ssm_path = _build_ssm_path(context.workflow_name, cred_type)

        headers = arguments.get("Headers", {})
        headers["Authorization"] = f"${{{ssm_path}}}"
        arguments["Headers"] = headers

        return [
            CredentialArtifact(
                parameter_path=ssm_path,
                credential_type=cred_type,
                auth_type="basic",
                placeholder_value="<your-basic-auth-credential>",
            ),
        ], {}

    @staticmethod
    def _build_query_auth(
        node: ClassifiedNode,
        context: TranslationContext,
        arguments: dict[str, Any],
    ) -> tuple[list[CredentialArtifact], dict[str, Any]]:
        """Build query parameter auth (API key in query string)."""
        cred_type = "httpQueryAuth"
        if node.node.credentials:
            cred_type = next(iter(node.node.credentials), cred_type)

        ssm_path = _build_ssm_path(context.workflow_name, cred_type)

        query_params = arguments.get("QueryParameters", {})
        query_params["api_key"] = f"${{{ssm_path}}}"
        arguments["QueryParameters"] = query_params

        return [
            CredentialArtifact(
                parameter_path=ssm_path,
                credential_type=cred_type,
                auth_type="api_key",
                placeholder_value="<your-api-key>",
            ),
        ], {}
