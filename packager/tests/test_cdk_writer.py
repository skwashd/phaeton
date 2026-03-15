"""Tests for the CDK stack generator."""

from __future__ import annotations

import json
from pathlib import Path

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
from n8n_to_sfn_packager.writers.cdk_writer import CDKWriter


def _minimal_input() -> PackagerInput:
    return PackagerInput(
        metadata=WorkflowMetadata(
            workflow_name="minimal-wf",
            source_n8n_version="1.42.0",
            converter_version="0.1.0",
            timestamp="2025-06-15T10:30:00Z",
            confidence_score=0.9,
        ),
        state_machine=StateMachineDefinition(
            asl={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
        ),
        lambda_functions=[
            LambdaFunctionSpec(
                function_name="slack_api",
                runtime=LambdaRuntime.PYTHON,
                handler_code="pass",
                function_type=LambdaFunctionType.PICOFUN_API_CLIENT,
                source_node_name="Slack",
            ),
        ],
        credentials=[
            CredentialSpec(
                parameter_path="/minimal-wf/creds/token",
                credential_type="apiKey",
            ),
        ],
        conversion_report=ConversionReport(
            total_nodes=2,
            confidence_score=0.9,
        ),
    )


def _complex_input() -> PackagerInput:
    return PackagerInput(
        metadata=WorkflowMetadata(
            workflow_name="complex-wf",
            source_n8n_version="1.42.0",
            converter_version="0.1.0",
            timestamp="2025-06-15T10:30:00Z",
            confidence_score=0.75,
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
            LambdaFunctionSpec(
                function_name="slack_api",
                runtime=LambdaRuntime.PYTHON,
                handler_code="pass",
                function_type=LambdaFunctionType.PICOFUN_API_CLIENT,
                source_node_name="Slack",
            ),
            LambdaFunctionSpec(
                function_name="code_transform",
                runtime=LambdaRuntime.NODEJS,
                handler_code="exports.handler = async (e) => e;",
                function_type=LambdaFunctionType.CODE_NODE_JS,
                source_node_name="Code",
            ),
        ],
        credentials=[
            CredentialSpec(
                parameter_path="/complex-wf/creds/slack",
                credential_type="apiKey",
            ),
        ],
        oauth_credentials=[
            OAuthCredentialSpec(
                credential_spec=CredentialSpec(
                    parameter_path="/complex-wf/creds/google",
                    credential_type="oauth2",
                    associated_node_names=["Google Sheets"],
                ),
                token_endpoint_url="https://oauth2.googleapis.com/token",  # noqa: S106
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
                source_workflow_file="sub.json",
            ),
        ],
        conversion_report=ConversionReport(
            total_nodes=8,
            confidence_score=0.75,
            ai_assisted_nodes=["Transform Data"],
        ),
    )


def _make_iam_policy() -> dict:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["lambda:InvokeFunction"],
                "Resource": ["arn:aws:lambda:*:*:function:slack_api"],
            },
        ],
    }


def _make_ssm_params() -> list[SSMParameterDefinition]:
    return [
        SSMParameterDefinition(
            parameter_path="/wf/creds/token",
            description="API token",
            placeholder_value="<your-token>",
        ),
    ]


class TestFileCreation:
    """Tests for CDK file creation."""

    def test_all_files_created(self, tmp_path: Path) -> None:
        """Test that all expected CDK files are created."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        assert (cdk_dir / "app.py").exists()
        assert (cdk_dir / "cdk.json").exists()
        assert (cdk_dir / "pyproject.toml").exists()
        assert (cdk_dir / "stacks" / "shared_stack.py").exists()
        assert (cdk_dir / "stacks" / "workflow_stack.py").exists()
        assert (cdk_dir / "stacks" / "__init__.py").exists()
        assert (tmp_path / "CREDENTIALS.md").exists()

    def test_cdk_dir_path(self, tmp_path: Path) -> None:
        """Test that the CDK directory is at the expected path."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        assert cdk_dir == tmp_path / "cdk"


class TestAppPy:
    """Tests for the generated app.py."""

    def test_syntactically_valid(self, tmp_path: Path) -> None:
        """Test that app.py is syntactically valid Python."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "app.py").read_text()
        compile(code, "app.py", "exec")

    def test_contains_stack_references(self, tmp_path: Path) -> None:
        """Test that app.py references both stacks."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "app.py").read_text()
        assert "SharedStack" in code
        assert "WorkflowStack" in code


class TestCdkJson:
    """Tests for the generated cdk.json."""

    def test_valid_json(self, tmp_path: Path) -> None:
        """Test that cdk.json is valid JSON."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        data = json.loads((cdk_dir / "cdk.json").read_text())
        assert isinstance(data, dict)

    def test_app_uses_uv(self, tmp_path: Path) -> None:
        """Test that cdk.json uses uv to run the app."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        data = json.loads((cdk_dir / "cdk.json").read_text())
        assert "uv run python app.py" in data["app"]

    def test_sub_workflow_context(self, tmp_path: Path) -> None:
        """Test that sub-workflow context is included in cdk.json."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _complex_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        data = json.loads((cdk_dir / "cdk.json").read_text())
        assert "sub_workflow_arn_sub_process" in data["context"]


class TestPyprojectToml:
    """Tests for the generated pyproject.toml."""

    def test_valid_toml(self, tmp_path: Path) -> None:
        """Test that pyproject.toml is valid TOML."""
        import tomllib

        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        content = (cdk_dir / "pyproject.toml").read_text()
        data = tomllib.loads(content)
        assert "project" in data

    def test_includes_lambda_python_alpha(self, tmp_path: Path) -> None:
        """Test that pyproject.toml includes the lambda python alpha dependency."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        content = (cdk_dir / "pyproject.toml").read_text()
        assert "aws-cdk.aws-lambda-python-alpha" in content


class TestWorkflowStack:
    """Tests for the generated workflow stack."""

    def test_python_function_import(self, tmp_path: Path) -> None:
        """Test that PythonFunction is imported in the workflow stack."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "PythonFunction" in code

    def test_correct_number_of_functions_minimal(self, tmp_path: Path) -> None:
        """Test that minimal input produces the correct number of functions."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        # Minimal input has 1 Python Lambda
        assert code.count("PythonFunction(") == 1

    def test_correct_number_of_functions_complex(self, tmp_path: Path) -> None:
        """Test that complex input produces the correct number of functions."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _complex_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        # Complex: 2 Python Lambdas + 1 Node.js Lambda + 1 OAuth refresh Lambda
        assert code.count("PythonFunction(") == 3
        assert code.count("lambda_.Function(") == 1

    def test_webhook_function_url(self, tmp_path: Path) -> None:
        """Test that webhook function URL is configured."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _complex_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "add_function_url" in code

    def test_ssm_parameters_present(self, tmp_path: Path) -> None:
        """Test that SSM parameters are present in the workflow stack."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "StringParameter(" in code

    def test_oauth_rotation(self, tmp_path: Path) -> None:
        """Test that OAuth rotation construct targets a Lambda function."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _complex_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "OAuthRotation" in code
        # Lambda function is defined and used as target
        assert "oauth_refresh_google = PythonFunction(" in code
        assert "targets=[targets.LambdaFunction(oauth_refresh_google)]" in code
        # Environment variables for the Lambda
        assert '"SSM_PARAMETER_PATH": "/complex-wf/creds/google"' in code
        assert '"TOKEN_ENDPOINT_URL": "https://oauth2.googleapis.com/token"' in code
        # IAM permissions for SSM
        assert "ssm:GetParameter" in code
        assert "ssm:PutParameter" in code

    def test_oauth_rotation_multiple_credentials(self, tmp_path: Path) -> None:
        """Test that multiple OAuth credentials each get their own Lambda and rule."""
        inp = _complex_input()
        inp.oauth_credentials.append(
            OAuthCredentialSpec(
                credential_spec=CredentialSpec(
                    parameter_path="/complex-wf/creds/slack-oauth",
                    credential_type="oauth2",
                    associated_node_names=["Slack"],
                ),
                token_endpoint_url="https://slack.com/api/oauth.v2.access",  # noqa: S106
                refresh_schedule_expression="rate(30 minutes)",
            ),
        )
        writer = CDKWriter()
        cdk_dir = writer.write(
            inp,
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        # Each credential gets its own Lambda and rule
        assert "oauth_refresh_google = PythonFunction(" in code
        assert "oauth_refresh_slack_oauth = PythonFunction(" in code
        assert "targets=[targets.LambdaFunction(oauth_refresh_google)]" in code
        assert "targets=[targets.LambdaFunction(oauth_refresh_slack_oauth)]" in code
        assert "OAuthRotation0" in code
        assert "OAuthRotation1" in code
        # Each has correct schedule
        assert 'expression("rate(50 minutes)")' in code
        assert 'expression("rate(30 minutes)")' in code

    def test_schedule_trigger(self, tmp_path: Path) -> None:
        """Test that schedule trigger is present with state machine target."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _complex_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "ScheduleRule" in code
        assert "targets.SfnStateMachine(state_machine)" in code

    def test_state_machine_variable_defined(self, tmp_path: Path) -> None:
        """Test that cfn_state_machine and state_machine variables are defined."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "cfn_state_machine = sfn.CfnStateMachine(" in code
        assert "state_machine = sfn.StateMachine.from_state_machine_arn(" in code

    def test_sub_workflow_params(self, tmp_path: Path) -> None:
        """Test that sub-workflow parameters are present."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _complex_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "CfnParameter" in code
        assert "sub_process" in code

    def test_source_node_comments(self, tmp_path: Path) -> None:
        """Test that source node comments are present."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "Source n8n node: Slack" in code


class TestObservability:
    """Tests for X-Ray tracing, DLQ, and CloudWatch alarm constructs."""

    def test_imports_include_sqs_and_cloudwatch(self, tmp_path: Path) -> None:
        """Test that generated code imports aws_sqs and aws_cloudwatch."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "from aws_cdk import aws_sqs as sqs" in code
        assert "from aws_cdk import aws_cloudwatch as cloudwatch" in code

    def test_dlq_construct_created(self, tmp_path: Path) -> None:
        """Test that an SQS dead-letter queue construct is generated."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "dlq = sqs.Queue(" in code
        assert '"DeadLetterQueue"' in code
        assert "retention_period=cdk.Duration.days(14)" in code

    def test_lambda_xray_tracing_active(self, tmp_path: Path) -> None:
        """Test that Lambda functions include active X-Ray tracing."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "tracing=lambda_.Tracing.ACTIVE" in code

    def test_lambda_dead_letter_queue(self, tmp_path: Path) -> None:
        """Test that Lambda functions reference the DLQ."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "dead_letter_queue=dlq" in code

    def test_nodejs_lambda_tracing_and_dlq(self, tmp_path: Path) -> None:
        """Test that Node.js Lambda functions also get tracing and DLQ."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _complex_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        # Node.js lambda_.Function should also have tracing and DLQ
        assert code.count("tracing=lambda_.Tracing.ACTIVE") >= 3

    def test_oauth_lambda_tracing_and_dlq(self, tmp_path: Path) -> None:
        """Test that OAuth refresh Lambda functions get tracing and DLQ."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _complex_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        # 3 workflow Lambdas + 1 OAuth refresh Lambda = 4 total tracing entries
        assert code.count("tracing=lambda_.Tracing.ACTIVE") == 4
        assert code.count("dead_letter_queue=dlq") == 4

    def test_state_machine_xray_tracing(self, tmp_path: Path) -> None:
        """Test that state machine includes X-Ray tracing configuration."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "TracingConfigurationProperty(" in code
        assert "enabled=True" in code

    def test_state_machine_failed_execution_dlq_rule(self, tmp_path: Path) -> None:
        """Test that an EventBridge rule routes failed executions to the DLQ."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert '"FailedExecutionDlqRule"' in code
        assert 'source=["aws.states"]' in code
        assert "targets=[targets.SqsQueue(dlq)]" in code

    def test_cloudwatch_alarms_created(self, tmp_path: Path) -> None:
        """Test that CloudWatch alarms are created for state machine metrics."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "cloudwatch.Alarm(" in code
        assert '"FailedAlarm"' in code
        assert '"TimedOutAlarm"' in code
        assert '"ThrottledAlarm"' in code
        assert "state_machine.metric_failed()" in code
        assert "state_machine.metric_timed_out()" in code
        assert "state_machine.metric_throttled()" in code


class TestCredentialsMd:
    """Tests for the generated CREDENTIALS.md file."""

    def test_credentials_md_created(self, tmp_path: Path) -> None:
        """Test that CREDENTIALS.md is created in the output directory."""
        writer = CDKWriter()
        writer.write(_minimal_input(), _make_iam_policy(), _make_ssm_params(), tmp_path)
        assert (tmp_path / "CREDENTIALS.md").exists()

    def test_credentials_md_lists_parameter_paths(self, tmp_path: Path) -> None:
        """Test that CREDENTIALS.md lists the SSM parameter paths from input."""
        writer = CDKWriter()
        writer.write(_minimal_input(), _make_iam_policy(), _make_ssm_params(), tmp_path)
        content = (tmp_path / "CREDENTIALS.md").read_text()
        assert "/minimal-wf/creds/token" in content

    def test_credentials_md_has_placeholder_warning(self, tmp_path: Path) -> None:
        """Test that CREDENTIALS.md warns about placeholder values."""
        writer = CDKWriter()
        writer.write(_minimal_input(), _make_iam_policy(), _make_ssm_params(), tmp_path)
        content = (tmp_path / "CREDENTIALS.md").read_text()
        assert "WARNING" in content
        assert "will fail" in content

    def test_credentials_md_includes_oauth(self, tmp_path: Path) -> None:
        """Test that CREDENTIALS.md includes OAuth credential sections."""
        writer = CDKWriter()
        writer.write(
            _complex_input(), _make_iam_policy(), _make_ssm_params(), tmp_path,
        )
        content = (tmp_path / "CREDENTIALS.md").read_text()
        assert "OAuth Credentials" in content
        assert "/complex-wf/creds/google/access_token" in content
        assert "oauth2.googleapis.com" in content
