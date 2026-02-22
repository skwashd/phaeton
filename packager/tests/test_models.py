"""Tests for Pydantic input models."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from n8n_to_sfn_packager.models import (
    ConversionReport,
    CredentialSpec,
    LambdaFunctionSpec,
    LambdaFunctionType,
    LambdaRuntime,
    OAuthCredentialSpec,
    PackagerInput,
    SSMParameterDefinition,
    StateMachineDefinition,
    SubWorkflowReference,
    TriggerSpec,
    TriggerType,
    WorkflowMetadata,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_metadata() -> WorkflowMetadata:
    return WorkflowMetadata(
        workflow_name="slack-notification-workflow",
        source_n8n_version="1.42.0",
        converter_version="0.1.0",
        timestamp="2025-06-15T10:30:00Z",
        confidence_score=0.85,
    )


def _make_asl() -> dict:
    return {
        "StartAt": "InvokeSlackApi",
        "States": {
            "InvokeSlackApi": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName": "slack_api",
                    "Payload.$": "$",
                },
                "Next": "WriteDynamoDB",
            },
            "WriteDynamoDB": {
                "Type": "Task",
                "Resource": "arn:aws:states:::aws-sdk:DynamoDB:PutItem",
                "Parameters": {
                    "TableName": "notifications",
                    "Item": {"id": {"S.$": "$.id"}},
                },
                "End": True,
            },
        },
    }


def _make_conversion_report() -> ConversionReport:
    return ConversionReport(
        total_nodes=5,
        classification_breakdown={"direct_map": 3, "picofun": 2},
        expression_breakdown={"jsonata": 8, "ai_assisted": 1},
        unsupported_nodes=[],
        payload_warnings=[],
        confidence_score=0.85,
        ai_assisted_nodes=["Transform Data"],
    )


def _make_packager_input() -> PackagerInput:
    """Build a realistic fixture: webhook -> Slack API -> DynamoDB write."""
    return PackagerInput(
        metadata=_make_metadata(),
        state_machine=StateMachineDefinition(asl=_make_asl()),
        lambda_functions=[
            LambdaFunctionSpec(
                function_name="webhook_handler",
                runtime=LambdaRuntime.PYTHON,
                handler_code='def handler(event, context):\n    return {"statusCode": 200}',
                description="Webhook entry point for Slack events",
                source_node_name="Webhook",
                dependencies=["httpx==0.27.0", "aws-lambda-powertools==2.40.0"],
                function_type=LambdaFunctionType.WEBHOOK_HANDLER,
            ),
            LambdaFunctionSpec(
                function_name="slack_api",
                runtime=LambdaRuntime.PYTHON,
                handler_code='def handler(event, context):\n    return {"ok": True}',
                description="PicoFun-generated Slack API client",
                source_node_name="Slack",
                dependencies=["httpx==0.27.0"],
                function_type=LambdaFunctionType.PICOFUN_API_CLIENT,
            ),
            LambdaFunctionSpec(
                function_name="code_node_process_data",
                runtime=LambdaRuntime.NODEJS,
                handler_code="exports.handler = async (event) => { return event; };",
                description="Lift-and-shift JS code node",
                source_node_name="Code",
                dependencies=["luxon@3.4.4"],
                function_type=LambdaFunctionType.CODE_NODE_JS,
            ),
        ],
        credentials=[
            CredentialSpec(
                parameter_path="/slack-notification-workflow/credentials/slack_token",
                description="Slack Bot OAuth Token",
                credential_type="apiKey",
                placeholder_value="<your-slack-bot-token>",
                associated_node_names=["Slack"],
            ),
        ],
        oauth_credentials=[],
        triggers=[
            TriggerSpec(
                trigger_type=TriggerType.WEBHOOK,
                configuration={"path": "/slack-events"},
                associated_lambda_name="webhook_handler",
            ),
        ],
        sub_workflows=[],
        conversion_report=_make_conversion_report(),
    )


# ---------------------------------------------------------------------------
# Valid construction tests
# ---------------------------------------------------------------------------


class TestValidModels:
    def test_workflow_metadata(self):
        m = _make_metadata()
        assert m.workflow_name == "slack-notification-workflow"
        assert m.confidence_score == 0.85

    def test_state_machine_definition(self):
        sm = StateMachineDefinition(asl=_make_asl())
        assert sm.query_language == "JSONata"
        assert "StartAt" in sm.asl

    def test_lambda_function_spec_python(self):
        spec = LambdaFunctionSpec(
            function_name="my_func",
            runtime=LambdaRuntime.PYTHON,
            handler_code="def handler(event, context): pass",
            function_type=LambdaFunctionType.PICOFUN_API_CLIENT,
        )
        assert spec.function_name == "my_func"
        assert spec.runtime == LambdaRuntime.PYTHON

    def test_lambda_function_spec_nodejs(self):
        spec = LambdaFunctionSpec(
            function_name="js-handler",
            runtime=LambdaRuntime.NODEJS,
            handler_code="exports.handler = async () => {};",
            function_type=LambdaFunctionType.CODE_NODE_JS,
        )
        assert spec.runtime == LambdaRuntime.NODEJS

    def test_credential_spec(self):
        cred = CredentialSpec(
            parameter_path="/workflow/creds/api_key",
            credential_type="apiKey",
            placeholder_value="<your-api-key>",
        )
        assert cred.parameter_path.startswith("/")

    def test_oauth_credential_spec(self):
        oauth = OAuthCredentialSpec(
            credential_spec=CredentialSpec(
                parameter_path="/workflow/creds/oauth",
                credential_type="oauth2",
            ),
            token_endpoint_url="https://oauth.example.com/token",
            scopes=["chat:write", "channels:read"],
        )
        assert oauth.refresh_schedule_expression == "rate(50 minutes)"

    def test_trigger_spec_schedule(self):
        trigger = TriggerSpec(
            trigger_type=TriggerType.SCHEDULE,
            configuration={"schedule_expression": "rate(1 hour)"},
        )
        assert trigger.associated_lambda_name is None

    def test_trigger_spec_webhook(self):
        trigger = TriggerSpec(
            trigger_type=TriggerType.WEBHOOK,
            configuration={"path": "/hooks/incoming"},
            associated_lambda_name="webhook_handler",
        )
        assert trigger.associated_lambda_name == "webhook_handler"

    def test_sub_workflow_reference(self):
        ref = SubWorkflowReference(
            name="process-order",
            source_workflow_file="process_order.json",
            description="Handles order processing",
        )
        assert ref.name == "process-order"

    def test_conversion_report(self):
        report = _make_conversion_report()
        assert report.total_nodes == 5
        assert report.confidence_score == 0.85

    def test_ssm_parameter_definition(self):
        param = SSMParameterDefinition(
            parameter_path="/workflow/creds/token",
            description="API token",
            placeholder_value="<your-token>",
        )
        assert param.parameter_type == "SecureString"

    def test_packager_input_full(self):
        inp = _make_packager_input()
        assert len(inp.lambda_functions) == 3
        assert len(inp.credentials) == 1
        assert len(inp.triggers) == 1


# ---------------------------------------------------------------------------
# Validation error tests
# ---------------------------------------------------------------------------


class TestValidationErrors:
    def test_invalid_function_name_spaces(self):
        with pytest.raises(ValidationError, match="function_name"):
            LambdaFunctionSpec(
                function_name="bad name with spaces",
                runtime=LambdaRuntime.PYTHON,
                handler_code="pass",
                function_type=LambdaFunctionType.PICOFUN_API_CLIENT,
            )

    def test_invalid_function_name_special_chars(self):
        with pytest.raises(ValidationError, match="function_name"):
            LambdaFunctionSpec(
                function_name="bad/name",
                runtime=LambdaRuntime.PYTHON,
                handler_code="pass",
                function_type=LambdaFunctionType.PICOFUN_API_CLIENT,
            )

    def test_empty_function_name(self):
        with pytest.raises(ValidationError):
            LambdaFunctionSpec(
                function_name="",
                runtime=LambdaRuntime.PYTHON,
                handler_code="pass",
                function_type=LambdaFunctionType.PICOFUN_API_CLIENT,
            )

    def test_ssm_path_no_leading_slash(self):
        with pytest.raises(ValidationError, match="parameter_path"):
            CredentialSpec(
                parameter_path="no/leading/slash",
                credential_type="apiKey",
            )

    def test_ssm_definition_path_no_leading_slash(self):
        with pytest.raises(ValidationError, match="parameter_path"):
            SSMParameterDefinition(
                parameter_path="bad/path",
            )

    def test_confidence_score_out_of_range(self):
        with pytest.raises(ValidationError):
            WorkflowMetadata(
                workflow_name="test",
                source_n8n_version="1.0.0",
                converter_version="0.1.0",
                timestamp="2025-01-01T00:00:00Z",
                confidence_score=1.5,
            )

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            PackagerInput()  # type: ignore[call-arg]

    def test_empty_workflow_name(self):
        with pytest.raises(ValidationError):
            WorkflowMetadata(
                workflow_name="",
                source_n8n_version="1.0.0",
                converter_version="0.1.0",
                timestamp="2025-01-01T00:00:00Z",
                confidence_score=0.5,
            )


# ---------------------------------------------------------------------------
# JSON round-trip (inter-component contract)
# ---------------------------------------------------------------------------


class TestJsonRoundTrip:
    def test_packager_input_serialisation_roundtrip(self):
        original = _make_packager_input()
        json_str = original.model_dump_json(indent=2)

        # Deserialise from JSON string
        restored = PackagerInput.model_validate_json(json_str)

        assert restored.metadata.workflow_name == original.metadata.workflow_name
        assert restored.state_machine.asl == original.state_machine.asl
        assert len(restored.lambda_functions) == len(original.lambda_functions)
        assert len(restored.credentials) == len(original.credentials)
        assert len(restored.triggers) == len(original.triggers)
        assert (
            restored.conversion_report.total_nodes
            == original.conversion_report.total_nodes
        )

    def test_packager_input_dict_roundtrip(self):
        original = _make_packager_input()
        data = original.model_dump()

        # Verify it's JSON-serialisable
        json_str = json.dumps(data)
        parsed = json.loads(json_str)

        # Reconstruct from dict
        restored = PackagerInput.model_validate(parsed)
        assert restored == original

    def test_packager_input_with_oauth_and_subworkflows(self):
        inp = _make_packager_input()
        inp = inp.model_copy(
            update={
                "oauth_credentials": [
                    OAuthCredentialSpec(
                        credential_spec=CredentialSpec(
                            parameter_path="/workflow/creds/google_oauth",
                            credential_type="oauth2",
                            placeholder_value="<your-google-oauth-token>",
                            associated_node_names=["Google Sheets"],
                        ),
                        token_endpoint_url="https://oauth2.googleapis.com/token",
                        scopes=["https://www.googleapis.com/auth/spreadsheets"],
                    ),
                ],
                "sub_workflows": [
                    SubWorkflowReference(
                        name="process-order",
                        source_workflow_file="process_order.json",
                        description="Order processing sub-workflow",
                    ),
                ],
            },
        )

        json_str = inp.model_dump_json()
        restored = PackagerInput.model_validate_json(json_str)

        assert len(restored.oauth_credentials) == 1
        assert len(restored.sub_workflows) == 1
        assert (
            restored.oauth_credentials[0].token_endpoint_url
            == "https://oauth2.googleapis.com/token"
        )
