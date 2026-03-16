"""Tests for the shared PackagerInput model and supporting types."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

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
    VpcBoundService,
    VpcConfig,
    WebhookAuthConfig,
    WebhookAuthType,
    WorkflowMetadata,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_packager_input(**overrides: object) -> PackagerInput:
    """Build a minimal valid ``PackagerInput``."""
    defaults: dict = {
        "metadata": WorkflowMetadata(
            workflow_name="test-wf",
            source_n8n_version="1.0.0",
            converter_version="0.1.0",
            timestamp="2025-01-01T00:00:00Z",
            confidence_score=0.9,
        ),
        "state_machine": StateMachineDefinition(
            asl={"StartAt": "S1", "States": {"S1": {"Type": "Pass", "End": True}}},
        ),
        "conversion_report": ConversionReport(total_nodes=1, confidence_score=0.9),
    }
    defaults.update(overrides)
    return PackagerInput(**defaults)


# ---------------------------------------------------------------------------
# VpcConfig
# ---------------------------------------------------------------------------


class TestVpcConfig:
    """Tests for the VpcConfig model."""

    def test_construction(self) -> None:
        """VpcConfig can be constructed with a list of services."""
        vpc = VpcConfig(vpc_bound_services=[VpcBoundService.RDS_MYSQL])
        assert vpc.vpc_bound_services == [VpcBoundService.RDS_MYSQL]

    def test_security_group_rules(self) -> None:
        """Security group rules are derived from services."""
        vpc = VpcConfig(
            vpc_bound_services=[
                VpcBoundService.RDS_MYSQL,
                VpcBoundService.ELASTICACHE_REDIS,
            ],
        )
        rules = vpc.security_group_rules
        assert len(rules) == 2
        assert rules[0] == {"port": 3306, "description": "MySQL"}
        assert rules[1] == {"port": 6379, "description": "Redis"}

    def test_empty_services_rejected(self) -> None:
        """An empty service list is rejected."""
        with pytest.raises(ValidationError):
            VpcConfig(vpc_bound_services=[])

    def test_all_services_have_rules(self) -> None:
        """Every VpcBoundService maps to a security group rule."""
        vpc = VpcConfig(vpc_bound_services=list(VpcBoundService))
        rules = vpc.security_group_rules
        assert len(rules) == len(VpcBoundService)


# ---------------------------------------------------------------------------
# WebhookAuthConfig
# ---------------------------------------------------------------------------


class TestWebhookAuthConfig:
    """Tests for the WebhookAuthConfig model."""

    def test_api_key_construction(self) -> None:
        """API key auth config can be constructed."""
        auth = WebhookAuthConfig(
            auth_type=WebhookAuthType.API_KEY,
            credential_parameter_path="/phaeton/creds/webhook-key",
        )
        assert auth.header_name == "x-api-key"

    def test_hmac_construction(self) -> None:
        """HMAC auth config can be constructed with custom header."""
        auth = WebhookAuthConfig(
            auth_type=WebhookAuthType.HMAC_SHA256,
            credential_parameter_path="/phaeton/creds/hmac-secret",
            header_name="x-hub-signature-256",
        )
        assert auth.header_name == "x-hub-signature-256"

    def test_missing_leading_slash_rejected(self) -> None:
        """Credential paths without leading slash are rejected."""
        with pytest.raises(ValidationError, match="credential_parameter_path"):
            WebhookAuthConfig(
                auth_type=WebhookAuthType.API_KEY,
                credential_parameter_path="no/slash",
            )


# ---------------------------------------------------------------------------
# OAuthCredentialSpec
# ---------------------------------------------------------------------------


class TestOAuthCredentialSpec:
    """Tests for the OAuthCredentialSpec model."""

    def test_construction_with_defaults(self) -> None:
        """OAuth spec has sensible defaults for schedule and scopes."""
        oauth = OAuthCredentialSpec(
            credential_spec=CredentialSpec(
                parameter_path="/creds/oauth",
                credential_type="oauth2",
            ),
            token_endpoint_url="https://example.com/token",  # noqa: S106
        )
        assert oauth.refresh_schedule_expression == "rate(50 minutes)"
        assert oauth.scopes == []

    def test_construction_with_scopes(self) -> None:
        """OAuth spec accepts scopes."""
        oauth = OAuthCredentialSpec(
            credential_spec=CredentialSpec(
                parameter_path="/creds/google",
                credential_type="oauth2",
            ),
            token_endpoint_url="https://oauth2.googleapis.com/token",  # noqa: S106
            scopes=["spreadsheets", "drive.readonly"],
        )
        assert len(oauth.scopes) == 2


# ---------------------------------------------------------------------------
# SubWorkflowReference
# ---------------------------------------------------------------------------


class TestSubWorkflowReference:
    """Tests for the SubWorkflowReference model."""

    def test_construction(self) -> None:
        """SubWorkflowReference can be constructed."""
        ref = SubWorkflowReference(
            name="child-workflow",
            source_workflow_file="child.json",
            description="A child workflow",
        )
        assert ref.name == "child-workflow"

    def test_empty_name_rejected(self) -> None:
        """Empty names are rejected."""
        with pytest.raises(ValidationError):
            SubWorkflowReference(name="", source_workflow_file="x.json")


# ---------------------------------------------------------------------------
# LambdaFunctionSpec with webhook_auth
# ---------------------------------------------------------------------------


class TestLambdaFunctionSpecWebhookAuth:
    """Tests for webhook_auth on LambdaFunctionSpec."""

    def test_webhook_auth_none_by_default(self) -> None:
        """webhook_auth defaults to None."""
        spec = LambdaFunctionSpec(
            function_name="my-fn",
            runtime=LambdaRuntime.PYTHON,
            handler_code="pass",
            function_type=LambdaFunctionType.CODE_NODE_PYTHON,
        )
        assert spec.webhook_auth is None

    def test_webhook_auth_set(self) -> None:
        """webhook_auth can be set on a function spec."""
        auth = WebhookAuthConfig(
            auth_type=WebhookAuthType.API_KEY,
            credential_parameter_path="/creds/key",
        )
        spec = LambdaFunctionSpec(
            function_name="webhook-fn",
            runtime=LambdaRuntime.PYTHON,
            handler_code="pass",
            function_type=LambdaFunctionType.WEBHOOK_HANDLER,
            webhook_auth=auth,
        )
        assert spec.webhook_auth is not None
        assert spec.webhook_auth.auth_type == WebhookAuthType.API_KEY


# ---------------------------------------------------------------------------
# PackagerInput new fields
# ---------------------------------------------------------------------------


class TestPackagerInputNewFields:
    """Tests for the new fields on PackagerInput."""

    def test_defaults_are_empty(self) -> None:
        """New fields default to empty/None."""
        inp = _minimal_packager_input()
        assert inp.oauth_credentials == []
        assert inp.sub_workflows == []
        assert inp.vpc_config is None

    def test_with_all_new_fields(self) -> None:
        """PackagerInput can be constructed with all new fields."""
        inp = _minimal_packager_input(
            oauth_credentials=[
                OAuthCredentialSpec(
                    credential_spec=CredentialSpec(
                        parameter_path="/creds/oauth",
                        credential_type="oauth2",
                    ),
                    token_endpoint_url="https://example.com/token",  # noqa: S106
                ),
            ],
            sub_workflows=[
                SubWorkflowReference(
                    name="child",
                    source_workflow_file="child.json",
                ),
            ],
            vpc_config=VpcConfig(
                vpc_bound_services=[VpcBoundService.RDS_POSTGRESQL],
            ),
        )
        assert len(inp.oauth_credentials) == 1
        assert len(inp.sub_workflows) == 1
        assert inp.vpc_config is not None

    def test_json_roundtrip_with_new_fields(self) -> None:
        """New fields survive a JSON round-trip."""
        inp = _minimal_packager_input(
            oauth_credentials=[
                OAuthCredentialSpec(
                    credential_spec=CredentialSpec(
                        parameter_path="/creds/oauth",
                        credential_type="oauth2",
                    ),
                    token_endpoint_url="https://example.com/token",  # noqa: S106
                    scopes=["read", "write"],
                ),
            ],
            sub_workflows=[
                SubWorkflowReference(
                    name="child",
                    source_workflow_file="child.json",
                    description="Child flow",
                ),
            ],
            vpc_config=VpcConfig(
                vpc_bound_services=[VpcBoundService.REDSHIFT],
            ),
        )

        json_str = inp.model_dump_json()
        restored = PackagerInput.model_validate_json(json_str)

        assert len(restored.oauth_credentials) == 1
        assert (
            restored.oauth_credentials[0].token_endpoint_url
            == "https://example.com/token"  # noqa: S105
        )
        assert restored.oauth_credentials[0].scopes == ["read", "write"]
        assert len(restored.sub_workflows) == 1
        assert restored.sub_workflows[0].name == "child"
        assert restored.vpc_config is not None
        assert restored.vpc_config.vpc_bound_services == [VpcBoundService.REDSHIFT]

    def test_dict_roundtrip_with_new_fields(self) -> None:
        """New fields survive a dict -> JSON -> dict round-trip."""
        inp = _minimal_packager_input(
            vpc_config=VpcConfig(
                vpc_bound_services=[VpcBoundService.RDS_MYSQL],
            ),
        )

        data = inp.model_dump()
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        restored = PackagerInput.model_validate(parsed)

        assert restored.vpc_config is not None
        assert restored.vpc_config.vpc_bound_services == [VpcBoundService.RDS_MYSQL]
