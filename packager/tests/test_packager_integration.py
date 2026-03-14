"""Integration tests for the top-level Packager orchestrator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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
from n8n_to_sfn_packager.packager import Packager, PackagerError


def _schema_path() -> Path:
    return (
        Path(__file__).resolve().parents[1] / ".." / "docs" / "asl_schema.json"
    ).resolve()


def _simple_asl() -> dict:
    """Return ASL for: webhook -> Slack API -> DynamoDB write."""
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


def _simple_input() -> PackagerInput:
    """Realistic fixture: webhook -> Slack API -> DynamoDB write."""
    return PackagerInput(
        metadata=WorkflowMetadata(
            workflow_name="slack-notify",
            source_n8n_version="1.42.0",
            converter_version="0.1.0",
            timestamp="2025-06-15T10:30:00Z",
            confidence_score=0.9,
        ),
        state_machine=StateMachineDefinition(asl=_simple_asl()),
        lambda_functions=[
            LambdaFunctionSpec(
                function_name="webhook_handler",
                runtime=LambdaRuntime.PYTHON,
                handler_code=(
                    "import json\n\n"
                    "def handler(event, context):\n"
                    '    return {"statusCode": 200, "body": json.dumps(event)}\n'
                ),
                description="Webhook entry point",
                source_node_name="Webhook",
                dependencies=["aws-lambda-powertools==2.40.0"],
                function_type=LambdaFunctionType.WEBHOOK_HANDLER,
            ),
            LambdaFunctionSpec(
                function_name="slack_api",
                runtime=LambdaRuntime.PYTHON,
                handler_code=(
                    "import httpx\n\n"
                    "def handler(event, context):\n"
                    '    return {"ok": True}\n'
                ),
                description="PicoFun Slack API client",
                source_node_name="Slack",
                dependencies=["httpx==0.27.0"],
                function_type=LambdaFunctionType.PICOFUN_API_CLIENT,
            ),
        ],
        credentials=[
            CredentialSpec(
                parameter_path="/slack-notify/credentials/slack_token",
                description="Slack Bot Token",
                credential_type="apiKey",
                placeholder_value="<your-slack-bot-token>",
                associated_node_names=["Slack"],
            ),
        ],
        triggers=[
            TriggerSpec(
                trigger_type=TriggerType.WEBHOOK,
                configuration={"path": "/slack-events"},
                associated_lambda_name="webhook_handler",
            ),
        ],
        conversion_report=ConversionReport(
            total_nodes=4,
            classification_breakdown={"direct_map": 2, "picofun": 1, "trigger": 1},
            expression_breakdown={"jsonata": 5},
            confidence_score=0.9,
        ),
    )


def _complex_asl() -> dict:
    """Return ASL with Choice, Map, and multiple integrations."""
    return {
        "QueryLanguage": "JSONata",
        "StartAt": "CheckMode",
        "States": {
            "CheckMode": {
                "Type": "Choice",
                "Choices": [
                    {
                        "Condition": "{% $states.input.mode = 'batch' %}",
                        "Next": "BatchProcess",
                    },
                ],
                "Default": "SingleProcess",
            },
            "BatchProcess": {
                "Type": "Map",
                "ItemProcessor": {
                    "StartAt": "ProcessItem",
                    "States": {
                        "ProcessItem": {
                            "Type": "Task",
                            "Resource": "arn:aws:states:::lambda:invoke",
                            "Parameters": {"FunctionName": "process_item"},
                            "End": True,
                        },
                    },
                },
                "Next": "Done",
            },
            "SingleProcess": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {"FunctionName": "slack_api"},
                "Next": "WriteS3",
            },
            "WriteS3": {
                "Type": "Task",
                "Resource": "arn:aws:states:::aws-sdk:S3:PutObject",
                "Parameters": {
                    "Bucket": "my-bucket",
                    "Key": "output.json",
                },
                "Next": "Done",
            },
            "Done": {
                "Type": "Succeed",
            },
        },
    }


def _complex_input() -> PackagerInput:
    """Complex fixture with all features."""
    return PackagerInput(
        metadata=WorkflowMetadata(
            workflow_name="complex-pipeline",
            source_n8n_version="1.42.0",
            converter_version="0.1.0",
            timestamp="2025-06-15T10:30:00Z",
            confidence_score=0.75,
        ),
        state_machine=StateMachineDefinition(
            asl=_complex_asl(),
            query_language="JSONata",
        ),
        lambda_functions=[
            LambdaFunctionSpec(
                function_name="webhook_handler",
                runtime=LambdaRuntime.PYTHON,
                handler_code="def handler(event, context): return event",
                function_type=LambdaFunctionType.WEBHOOK_HANDLER,
                source_node_name="Webhook",
            ),
            LambdaFunctionSpec(
                function_name="slack_api",
                runtime=LambdaRuntime.PYTHON,
                handler_code="def handler(event, context): return {}",
                dependencies=["httpx==0.27.0"],
                function_type=LambdaFunctionType.PICOFUN_API_CLIENT,
                source_node_name="Slack",
            ),
            LambdaFunctionSpec(
                function_name="code_transform",
                runtime=LambdaRuntime.NODEJS,
                handler_code="const result = items.map(i => i);",
                dependencies=["luxon@3.4.4"],
                function_type=LambdaFunctionType.CODE_NODE_JS,
                source_node_name="Code",
            ),
            LambdaFunctionSpec(
                function_name="code_python_merge",
                runtime=LambdaRuntime.PYTHON,
                handler_code="def handler(event, context): return event",
                function_type=LambdaFunctionType.CODE_NODE_PYTHON,
                source_node_name="Merge Code",
            ),
            LambdaFunctionSpec(
                function_name="oauth_refresh",
                runtime=LambdaRuntime.PYTHON,
                handler_code="def handler(event, context): pass",
                function_type=LambdaFunctionType.OAUTH_REFRESH,
                source_node_name="OAuth Refresh",
            ),
        ],
        credentials=[
            CredentialSpec(
                parameter_path="/complex-pipeline/credentials/slack",
                credential_type="apiKey",
                placeholder_value="<your-slack-token>",
                associated_node_names=["Slack"],
            ),
        ],
        oauth_credentials=[
            OAuthCredentialSpec(
                credential_spec=CredentialSpec(
                    parameter_path="/complex-pipeline/credentials/google",
                    credential_type="oauth2",
                    associated_node_names=["Google Sheets"],
                ),
                token_endpoint_url="https://oauth2.googleapis.com/token",  # noqa: S106
                scopes=["https://www.googleapis.com/auth/spreadsheets"],
            ),
        ],
        triggers=[
            TriggerSpec(
                trigger_type=TriggerType.WEBHOOK,
                configuration={"path": "/webhook"},
                associated_lambda_name="webhook_handler",
            ),
            TriggerSpec(
                trigger_type=TriggerType.SCHEDULE,
                configuration={"schedule_expression": "rate(1 hour)"},
            ),
        ],
        sub_workflows=[
            SubWorkflowReference(
                name="sub-process",
                source_workflow_file="sub_process.json",
                description="Sub-workflow for order processing",
            ),
        ],
        conversion_report=ConversionReport(
            total_nodes=10,
            classification_breakdown={
                "direct_map": 4,
                "picofun": 2,
                "code_node": 2,
                "trigger": 2,
            },
            expression_breakdown={"jsonata": 12, "ai_assisted": 3},
            payload_warnings=["State 'BatchProcess' may exceed 256KB payload limit"],
            confidence_score=0.75,
            ai_assisted_nodes=["Merge Code", "Code"],
        ),
    )


class TestSimpleWorkflow:
    """Tests for simple workflow packaging."""

    def test_complete_output_structure(self, tmp_path: Path) -> None:
        """Test that all expected output files are created."""
        packager = Packager(schema_path=_schema_path())
        output = packager.package(_simple_input(), tmp_path / "output")

        # ASL
        assert (output / "statemachine" / "definition.asl.json").exists()
        asl = json.loads(
            (output / "statemachine" / "definition.asl.json").read_text(),
        )
        assert "StartAt" in asl

        # Lambdas
        assert (output / "lambdas" / "webhook_handler" / "handler.py").exists()
        assert (output / "lambdas" / "webhook_handler" / "pyproject.toml").exists()
        assert (output / "lambdas" / "webhook_handler" / "uv.lock").exists()
        assert (output / "lambdas" / "slack_api" / "handler.py").exists()
        assert (output / "lambdas" / "slack_api" / "pyproject.toml").exists()
        assert (output / "lambdas" / "slack_api" / "uv.lock").exists()

        # CDK
        assert (output / "cdk" / "app.py").exists()
        assert (output / "cdk" / "cdk.json").exists()
        assert (output / "cdk" / "pyproject.toml").exists()
        assert (output / "cdk" / "stacks" / "shared_stack.py").exists()
        assert (output / "cdk" / "stacks" / "workflow_stack.py").exists()

        # Reports
        assert (output / "MIGRATE.md").exists()
        assert (output / "reports" / "conversion_report.json").exists()
        assert (output / "reports" / "conversion_report.md").exists()
        assert (output / "README.md").exists()

    def test_no_requirements_txt(self, tmp_path: Path) -> None:
        """Test that no requirements.txt files are generated anywhere."""
        packager = Packager(schema_path=_schema_path())
        output = packager.package(_simple_input(), tmp_path / "output")

        # No requirements.txt anywhere
        for req in output.rglob("requirements.txt"):
            pytest.fail(f"Found requirements.txt at {req}")

    def test_cdk_files_syntactically_valid(self, tmp_path: Path) -> None:
        """Test that generated CDK files are syntactically valid Python."""
        packager = Packager(schema_path=_schema_path())
        output = packager.package(_simple_input(), tmp_path / "output")

        app_code = (output / "cdk" / "app.py").read_text()
        compile(app_code, "app.py", "exec")


class TestComplexWorkflow:
    """Tests for complex workflow packaging."""

    def test_complete_output_structure(self, tmp_path: Path) -> None:
        """Test that all expected output files are created for complex input."""
        packager = Packager(schema_path=_schema_path())
        output = packager.package(_complex_input(), tmp_path / "output")

        # Python Lambdas have pyproject.toml + uv.lock
        for name in [
            "webhook_handler",
            "slack_api",
            "code_python_merge",
            "oauth_refresh",
        ]:
            assert (output / "lambdas" / name / "handler.py").exists()
            assert (output / "lambdas" / name / "pyproject.toml").exists()
            assert (output / "lambdas" / name / "uv.lock").exists()

        # Node.js Lambda has package.json
        assert (output / "lambdas" / "code_transform" / "handler.js").exists()
        assert (output / "lambdas" / "code_transform" / "package.json").exists()

    def test_migrate_md_content(self, tmp_path: Path) -> None:
        """Test that MIGRATE.md contains expected content."""
        packager = Packager(schema_path=_schema_path())
        output = packager.package(_complex_input(), tmp_path / "output")

        content = (output / "MIGRATE.md").read_text()
        assert "sub-process" in content
        assert "uv sync" in content
        assert "uv run cdk deploy" in content
        assert "AI-Translated" in content

    def test_conversion_report_json(self, tmp_path: Path) -> None:
        """Test that conversion_report.json has correct content."""
        packager = Packager(schema_path=_schema_path())
        output = packager.package(_complex_input(), tmp_path / "output")

        report = json.loads(
            (output / "reports" / "conversion_report.json").read_text(),
        )
        assert report["total_nodes"] == 10
        assert report["confidence_score"] == 0.75

    def test_sub_workflow_in_cdk_json(self, tmp_path: Path) -> None:
        """Test that sub-workflow references appear in cdk.json."""
        packager = Packager(schema_path=_schema_path())
        output = packager.package(_complex_input(), tmp_path / "output")

        cdk_config = json.loads((output / "cdk" / "cdk.json").read_text())
        assert "context" in cdk_config
        assert any("sub_process" in k for k in cdk_config["context"])

    def test_workflow_stack_has_all_constructs(self, tmp_path: Path) -> None:
        """Test that the workflow stack includes all expected constructs."""
        packager = Packager(schema_path=_schema_path())
        output = packager.package(_complex_input(), tmp_path / "output")

        code = (output / "cdk" / "stacks" / "workflow_stack.py").read_text()
        assert "PythonFunction(" in code
        assert "lambda_.Function(" in code
        assert "add_function_url" in code
        assert "OAuthRotation" in code
        assert "ScheduleRule" in code
        assert "CfnParameter" in code


class TestErrorHandling:
    """Tests for error handling in the packager."""

    def test_invalid_asl_raises_early(self, tmp_path: Path) -> None:
        """Test that invalid ASL raises PackagerError early."""
        inp = _simple_input().model_copy(
            update={
                "state_machine": StateMachineDefinition(
                    asl={"States": {"Foo": {"Type": "Succeed"}}},
                ),
            },
        )
        packager = Packager(schema_path=_schema_path())
        with pytest.raises(PackagerError, match="ASL validation failed"):
            packager.package(inp, tmp_path / "output")
