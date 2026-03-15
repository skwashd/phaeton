"""SaaS integration node translators.

Provides a base class for translating n8n SaaS nodes (Slack, Gmail,
Google Sheets, Notion, Airtable, etc.) into Step Functions ``http:invoke``
Task states that call each service's REST API.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
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

_DEFAULT_RETRY = RetryConfig(
    error_equals=["States.TaskFailed"],
    interval_seconds=2,
    max_attempts=3,
    backoff_rate=2.0,
    max_delay_seconds=30,
)


def _build_ssm_path(workflow_name: str, credential_type: str) -> str:
    """Build the SSM parameter path for a credential."""
    safe_name = workflow_name.replace(" ", "-").lower() if workflow_name else "workflow"
    return f"/n8n-sfn/{safe_name}/{credential_type}"


@dataclass
class OperationMapping:
    """Maps an n8n resource/operation pair to an HTTP API call."""

    method: str
    endpoint_template: str
    body_builder: str | None = None


class BaseSaaSTranslator(BaseTranslator):
    """Base class for SaaS integration translators.

    Subclasses define the n8n node type, API base URL, credential type,
    and operation mappings.  The base class handles the common translation
    logic of building ``http:invoke`` Task states with credential artifacts.
    """

    @property
    @abstractmethod
    def node_type(self) -> str:
        """The n8n node type string (e.g. ``n8n-nodes-base.slack``)."""

    @property
    @abstractmethod
    def api_base_url(self) -> str:
        """Base URL for the SaaS API (e.g. ``https://slack.com/api``)."""

    @property
    @abstractmethod
    def credential_type(self) -> str:
        """Credential type name for SSM storage."""

    @property
    @abstractmethod
    def auth_type(self) -> str:
        """Authentication type (``oauth2``, ``api_key``, ``bearer``)."""

    @property
    @abstractmethod
    def operations(self) -> dict[str, OperationMapping]:
        """Map of ``resource:operation`` keys to :class:`OperationMapping`."""

    def can_translate(self, node: ClassifiedNode) -> bool:
        """Return True if this translator handles the node type."""
        return node.node.type == self.node_type

    def translate(
        self, node: ClassifiedNode, context: TranslationContext
    ) -> TranslationResult:
        """Translate a SaaS node into an ``http:invoke`` Task state."""
        params = node.node.parameters
        resource = str(params.get("resource", ""))
        operation = str(params.get("operation", ""))
        op_key = f"{resource}:{operation}" if resource else operation

        mapping = self.operations.get(op_key)
        warnings: list[str] = []

        if mapping is None:
            warnings.append(
                f"Unsupported operation '{op_key}' for node "
                f"'{node.node.name}' ({self.node_type}). "
                f"Using default POST to base URL."
            )
            method = "POST"
            endpoint = self.api_base_url
        else:
            method = mapping.method
            endpoint = self._resolve_endpoint(mapping.endpoint_template, params)

        arguments: dict[str, Any] = {
            "ApiEndpoint": endpoint,
            "Method": method,
            "Headers": self._build_headers(context),
        }

        body = self._build_request_body(op_key, params, mapping)
        if body:
            arguments["RequestBody"] = body

        credential_artifacts = self._build_credential_artifacts(context)

        state = TaskState(
            resource="arn:aws:states:::http:invoke",
            arguments=arguments,
            end=True,
            retry=[_DEFAULT_RETRY],
        )
        state = apply_error_handling(state, node, default_retry=_DEFAULT_RETRY)

        return TranslationResult(
            states={node.node.name: state},
            credential_artifacts=credential_artifacts,
            warnings=warnings,
            metadata={"saas_service": self.node_type, "operation": op_key},
        )

    def _resolve_endpoint(
        self, template: str, params: dict[str, Any]
    ) -> str:
        """Resolve placeholders in endpoint templates from node parameters."""
        result = template
        for key, value in params.items():
            placeholder = f"{{{key}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        return result

    def _build_headers(self, context: TranslationContext) -> dict[str, str]:
        """Build default headers including auth token placeholder."""
        ssm_path = _build_ssm_path(context.workflow_name, self.credential_type)
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer ${{{ssm_path}}}",
        }

    def _build_request_body(
        self,
        op_key: str,
        params: dict[str, Any],
        mapping: OperationMapping | None,
    ) -> dict[str, Any]:
        """Build the request body from node parameters.

        Subclasses can override for service-specific body construction.
        The default extracts all non-routing parameters.
        """
        skip_keys = {"resource", "operation"}
        return {k: v for k, v in params.items() if k not in skip_keys}

    def _build_credential_artifacts(
        self, context: TranslationContext
    ) -> list[CredentialArtifact]:
        """Create the credential artifact for this SaaS service."""
        ssm_path = _build_ssm_path(context.workflow_name, self.credential_type)
        return [
            CredentialArtifact(
                parameter_path=ssm_path,
                credential_type=self.credential_type,
                auth_type=self.auth_type,
                placeholder_value=f"<your-{self.credential_type}-token>",
            ),
        ]
