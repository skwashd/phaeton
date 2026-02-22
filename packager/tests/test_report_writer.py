"""Tests for the report generators."""

from __future__ import annotations

import json

from n8n_to_sfn_packager.models.inputs import (
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
    WorkflowMetadata,
)
from n8n_to_sfn_packager.models.ssm import SSMParameterDefinition
from n8n_to_sfn_packager.writers.report_writer import ReportWriter


def _make_input(
    *,
    with_warnings: bool = False,
    with_sub_workflows: bool = False,
) -> PackagerInput:
    return PackagerInput(
        metadata=WorkflowMetadata(
            workflow_name="test-workflow",
            source_n8n_version="1.42.0",
            converter_version="0.1.0",
            timestamp="2025-06-15T10:30:00Z",
            confidence_score=0.85,
        ),
        state_machine=StateMachineDefinition(
            asl={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
        ),
        lambda_functions=[
            LambdaFunctionSpec(
                function_name="webhook_handler",
                runtime=LambdaRuntime.PYTHON,
                handler_code="pass",
                function_type=LambdaFunctionType.WEBHOOK_HANDLER,
                source_node_name="Webhook",
            ),
        ],
        credentials=[
            CredentialSpec(
                parameter_path="/test-workflow/credentials/slack",
                credential_type="apiKey",
                placeholder_value="<your-slack-token>",
            ),
        ],
        oauth_credentials=[
            OAuthCredentialSpec(
                credential_spec=CredentialSpec(
                    parameter_path="/test-workflow/credentials/google",
                    credential_type="oauth2",
                    associated_node_names=["Google Sheets"],
                ),
                token_endpoint_url="https://oauth2.googleapis.com/token",
            ),
        ],
        triggers=[
            TriggerSpec(
                trigger_type=TriggerType.WEBHOOK,
                configuration={"path": "/webhook"},
                associated_lambda_name="webhook_handler",
            ),
        ],
        sub_workflows=[
            SubWorkflowReference(
                name="sub-process",
                source_workflow_file="sub.json",
            ),
        ]
        if with_sub_workflows
        else [],
        conversion_report=ConversionReport(
            total_nodes=5,
            classification_breakdown={"direct_map": 3, "picofun": 2},
            expression_breakdown={"jsonata": 8},
            unsupported_nodes=[],
            payload_warnings=["Large payload at node X (>256KB)"]
            if with_warnings
            else [],
            confidence_score=0.85,
            ai_assisted_nodes=["Transform Data"],
        ),
    )


def _make_ssm_params() -> list[SSMParameterDefinition]:
    return [
        SSMParameterDefinition(
            parameter_path="/test-workflow/credentials/slack",
            description="Slack API token",
            placeholder_value="<your-slack-token>",
        ),
        SSMParameterDefinition(
            parameter_path="/test-workflow/credentials/google/access_token",
            description="Google OAuth access token",
            placeholder_value="<oauth2-access-token>",
        ),
        SSMParameterDefinition(
            parameter_path="/test-workflow/credentials/google/refresh_token",
            description="Google OAuth refresh token",
            placeholder_value="<oauth2-refresh-token>",
        ),
    ]


class TestMigrateMd:
    def test_contains_all_sections(self, tmp_path):
        writer = ReportWriter()
        inp = _make_input()
        path = writer.write_migrate_md(inp, _make_ssm_params(), tmp_path)
        content = path.read_text()

        assert "## Pre-deployment" in content
        assert "## Deployment" in content
        assert "## Post-deployment" in content

    def test_ssm_parameter_entries(self, tmp_path):
        writer = ReportWriter()
        params = _make_ssm_params()
        path = writer.write_migrate_md(_make_input(), params, tmp_path)
        content = path.read_text()

        for param in params:
            assert param.parameter_path in content

    def test_deployment_uses_uv(self, tmp_path):
        writer = ReportWriter()
        path = writer.write_migrate_md(_make_input(), [], tmp_path)
        content = path.read_text()

        assert "uv sync" in content
        assert "uv run cdk deploy" in content
        assert "pip" not in content
        assert "requirements.txt" not in content

    def test_webhook_urls_documented(self, tmp_path):
        writer = ReportWriter()
        path = writer.write_migrate_md(_make_input(), [], tmp_path)
        content = path.read_text()
        assert "webhook_handler" in content

    def test_with_sub_workflows(self, tmp_path):
        writer = ReportWriter()
        inp = _make_input(with_sub_workflows=True)
        path = writer.write_migrate_md(inp, [], tmp_path)
        content = path.read_text()
        assert "sub-process" in content

    def test_with_warnings(self, tmp_path):
        writer = ReportWriter()
        inp = _make_input(with_warnings=True)
        path = writer.write_migrate_md(inp, [], tmp_path)
        content = path.read_text()
        assert "Large payload" in content

    def test_no_warnings(self, tmp_path):
        writer = ReportWriter()
        inp = _make_input(with_warnings=False)
        path = writer.write_migrate_md(inp, [], tmp_path)
        content = path.read_text()
        # Should still be valid even with no warnings
        assert "## Pre-deployment" in content


class TestConversionReportJson:
    def test_valid_json(self, tmp_path):
        writer = ReportWriter()
        path = writer.write_conversion_report_json(_make_input(), tmp_path)
        data = json.loads(path.read_text())
        assert isinstance(data, dict)

    def test_contains_metadata(self, tmp_path):
        writer = ReportWriter()
        path = writer.write_conversion_report_json(_make_input(), tmp_path)
        data = json.loads(path.read_text())
        assert data["metadata"]["converter_version"] == "0.1.0"
        assert data["metadata"]["workflow_name"] == "test-workflow"

    def test_contains_report_fields(self, tmp_path):
        writer = ReportWriter()
        path = writer.write_conversion_report_json(_make_input(), tmp_path)
        data = json.loads(path.read_text())
        assert data["total_nodes"] == 5
        assert data["confidence_score"] == 0.85


class TestConversionReportMd:
    def test_contains_sections(self, tmp_path):
        writer = ReportWriter()
        path = writer.write_conversion_report_md(_make_input(), tmp_path)
        content = path.read_text()

        assert "## Overview" in content
        assert "## Node Classification Breakdown" in content
        assert "## Expression Translation Summary" in content
        assert "## Warnings" in content
        assert "## AI-Assisted Translations" in content
        assert "## Recommendations" in content

    def test_no_warnings_output(self, tmp_path):
        writer = ReportWriter()
        inp = _make_input(with_warnings=False)
        path = writer.write_conversion_report_md(inp, tmp_path)
        content = path.read_text()
        assert "No warnings" in content


class TestReadme:
    def test_contains_quickstart(self, tmp_path):
        writer = ReportWriter()
        path = writer.write_readme(_make_input(), tmp_path)
        content = path.read_text()

        assert "## Quickstart" in content
        assert "uv sync" in content
        assert "uv run cdk deploy" in content

    def test_references_migrate_md(self, tmp_path):
        writer = ReportWriter()
        path = writer.write_readme(_make_input(), tmp_path)
        content = path.read_text()
        assert "MIGRATE.md" in content
