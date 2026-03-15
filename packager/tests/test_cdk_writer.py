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
    VpcBoundService,
    VpcConfig,
    WebhookAuthConfig,
    WebhookAuthType,
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


def _webhook_auth_input() -> PackagerInput:
    """Input with webhook handler that has API key authentication."""
    return PackagerInput(
        metadata=WorkflowMetadata(
            workflow_name="auth-wf",
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
                function_name="webhook_handler",
                runtime=LambdaRuntime.PYTHON,
                handler_code="def handler(event, context):\n    return {'statusCode': 200}",
                function_type=LambdaFunctionType.WEBHOOK_HANDLER,
                source_node_name="Webhook",
                webhook_auth=WebhookAuthConfig(
                    auth_type=WebhookAuthType.API_KEY,
                    credential_parameter_path="/auth-wf/webhooks/api-key",
                ),
            ),
        ],
        credentials=[
            CredentialSpec(
                parameter_path="/auth-wf/webhooks/api-key",
                credential_type="apiKey",
                description="Webhook authentication API key",
            ),
        ],
        triggers=[
            TriggerSpec(
                trigger_type=TriggerType.WEBHOOK,
                configuration={"path": "/webhook"},
                associated_lambda_name="webhook_handler",
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

    def test_no_lambda_python_alpha_dependency(self, tmp_path: Path) -> None:
        """Test that pyproject.toml does not include the lambda python alpha dependency."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        content = (cdk_dir / "pyproject.toml").read_text()
        assert "aws-cdk.aws-lambda-python-alpha" not in content


class TestWorkflowStack:
    """Tests for the generated workflow stack."""

    def test_python_function_uses_stable_construct(self, tmp_path: Path) -> None:
        """Test that Python Lambdas use lambda_.Function, not PythonFunction."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "PythonFunction" not in code
        assert "lambda_.Function(" in code

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
        assert code.count("lambda_.Function(") == 1

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
        assert code.count("lambda_.Function(") == 4

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
        assert "oauth_refresh_google = lambda_.Function(" in code
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
        assert "oauth_refresh_google = lambda_.Function(" in code
        assert "oauth_refresh_slack_oauth = lambda_.Function(" in code
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

    def test_python_function_has_bundling_options(self, tmp_path: Path) -> None:
        """Test that Python Lambda functions use BundlingOptions with pip install."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "cdk.BundlingOptions(" in code
        assert "pip install" in code
        assert "requirements.txt" in code

    def test_no_alpha_import(self, tmp_path: Path) -> None:
        """Test that generated code does not import from aws_lambda_python_alpha."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _complex_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "aws_lambda_python_alpha" not in code
        assert "PythonFunction" not in code


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


class TestWebhookAuthentication:
    """Tests for webhook authentication CDK constructs."""

    def test_webhook_auth_env_var(self, tmp_path: Path) -> None:
        """Test that webhook auth adds WEBHOOK_AUTH_PARAMETER env var."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _webhook_auth_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert '"WEBHOOK_AUTH_PARAMETER"' in code
        assert '"/auth-wf/webhooks/api-key"' in code

    def test_webhook_auth_ssm_permission(self, tmp_path: Path) -> None:
        """Test that webhook auth adds ssm:GetParameter IAM permission."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _webhook_auth_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert 'actions=["ssm:GetParameter"]' in code
        assert "auth-wf/webhooks/api-key" in code

    def test_no_auth_no_env_var(self, tmp_path: Path) -> None:
        """Test that webhook without auth does not add env var or IAM permission."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _complex_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "WEBHOOK_AUTH_PARAMETER" not in code
        # The add_function_url should still be present
        assert "add_function_url" in code

    def test_webhook_auth_function_url_still_none(self, tmp_path: Path) -> None:
        """Test that Function URL auth type remains NONE even with webhook auth."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _webhook_auth_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "FunctionUrlAuthType.NONE" in code


def _vpc_input() -> PackagerInput:
    """Input with VPC-bound resources (RDS PostgreSQL)."""
    return PackagerInput(
        metadata=WorkflowMetadata(
            workflow_name="vpc-wf",
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
                function_name="db_query",
                runtime=LambdaRuntime.PYTHON,
                handler_code="pass",
                function_type=LambdaFunctionType.PICOFUN_API_CLIENT,
                source_node_name="Postgres",
            ),
        ],
        vpc_config=VpcConfig(
            vpc_bound_services=[VpcBoundService.RDS_POSTGRESQL],
        ),
        conversion_report=ConversionReport(
            total_nodes=2,
            confidence_score=0.9,
        ),
    )


def _vpc_multi_service_input() -> PackagerInput:
    """Input with multiple VPC-bound services."""
    return PackagerInput(
        metadata=WorkflowMetadata(
            workflow_name="vpc-multi-wf",
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
                function_name="db_query",
                runtime=LambdaRuntime.PYTHON,
                handler_code="pass",
                function_type=LambdaFunctionType.PICOFUN_API_CLIENT,
                source_node_name="Postgres",
            ),
            LambdaFunctionSpec(
                function_name="cache_lookup",
                runtime=LambdaRuntime.NODEJS,
                handler_code="exports.handler = async (e) => e;",
                function_type=LambdaFunctionType.CODE_NODE_JS,
                source_node_name="Redis",
            ),
        ],
        vpc_config=VpcConfig(
            vpc_bound_services=[
                VpcBoundService.RDS_POSTGRESQL,
                VpcBoundService.ELASTICACHE_REDIS,
            ],
        ),
        conversion_report=ConversionReport(
            total_nodes=3,
            confidence_score=0.9,
        ),
    )


class TestVpcConfiguration:
    """Tests for VPC configuration in CDK constructs."""

    def test_shared_stack_vpc_constructs(self, tmp_path: Path) -> None:
        """Test that shared stack includes VPC constructs when VPC config is present."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _vpc_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "shared_stack.py").read_text()
        assert "from aws_cdk import aws_ec2 as ec2" in code
        assert "ec2.Vpc.from_lookup" in code
        assert "ec2.Vpc(self" in code
        assert 'ec2.SecurityGroup(' in code

    def test_shared_stack_no_vpc_without_config(self, tmp_path: Path) -> None:
        """Test that shared stack omits VPC constructs when no VPC config."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "shared_stack.py").read_text()
        assert "ec2" not in code
        assert "vpc" not in code.lower()

    def test_vpc_security_group_rules_postgresql(self, tmp_path: Path) -> None:
        """Test that PostgreSQL security group rules are generated."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _vpc_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "shared_stack.py").read_text()
        assert "ec2.Port.tcp(5432)" in code
        assert "PostgreSQL access" in code

    def test_vpc_security_group_rules_multiple_services(self, tmp_path: Path) -> None:
        """Test that security group rules are generated for each VPC-bound service."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _vpc_multi_service_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "shared_stack.py").read_text()
        assert "ec2.Port.tcp(5432)" in code
        assert "ec2.Port.tcp(6379)" in code
        assert "PostgreSQL access" in code
        assert "Redis access" in code

    def test_vpc_https_egress_for_nat(self, tmp_path: Path) -> None:
        """Test that HTTPS egress rule is added for NAT Gateway path."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _vpc_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "shared_stack.py").read_text()
        assert "ec2.Port.tcp(443)" in code
        assert "HTTPS outbound" in code

    def test_lambda_vpc_params_python(self, tmp_path: Path) -> None:
        """Test that Python Lambda functions include VPC parameters."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _vpc_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "vpc=vpc," in code
        assert "vpc_subnets=vpc_subnets," in code
        assert "security_groups=[lambda_sg]," in code

    def test_lambda_vpc_params_nodejs(self, tmp_path: Path) -> None:
        """Test that Node.js Lambda functions include VPC parameters."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _vpc_multi_service_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        # Both Python and Node.js lambdas should have VPC config
        assert code.count("vpc=vpc,") == 2
        assert code.count("security_groups=[lambda_sg],") == 2

    def test_no_vpc_params_without_config(self, tmp_path: Path) -> None:
        """Test that Lambda functions do not include VPC params without VPC config."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "vpc=vpc" not in code
        assert "vpc_subnets" not in code
        assert "security_groups" not in code

    def test_workflow_stack_ec2_import(self, tmp_path: Path) -> None:
        """Test that workflow stack imports ec2 when VPC is configured."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _vpc_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "from aws_cdk import aws_ec2 as ec2" in code

    def test_workflow_stack_no_ec2_import_without_vpc(self, tmp_path: Path) -> None:
        """Test that workflow stack does not import ec2 without VPC config."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "aws_ec2" not in code

    def test_vpc_subnet_selection(self, tmp_path: Path) -> None:
        """Test that VPC subnet selection uses PRIVATE_WITH_EGRESS."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _vpc_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "ec2.SubnetType.PRIVATE_WITH_EGRESS" in code

    def test_cdk_json_vpc_context_variables(self, tmp_path: Path) -> None:
        """Test that cdk.json includes VPC context variables."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _vpc_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        data = json.loads((cdk_dir / "cdk.json").read_text())
        assert "vpc_id" in data["context"]
        assert "subnet_ids" in data["context"]
        assert "security_group_ids" in data["context"]

    def test_cdk_json_no_vpc_context_without_config(self, tmp_path: Path) -> None:
        """Test that cdk.json does not include VPC context without VPC config."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        data = json.loads((cdk_dir / "cdk.json").read_text())
        assert "vpc_id" not in data.get("context", {})

    def test_vpc_lookup_from_context(self, tmp_path: Path) -> None:
        """Test that VPC lookup uses context variables."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _vpc_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "shared_stack.py").read_text()
        assert 'self.node.try_get_context("vpc_id")' in code
        assert "Vpc.from_lookup" in code

    def test_shared_stack_allow_all_outbound_false(self, tmp_path: Path) -> None:
        """Test that the security group does not allow all outbound by default."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _vpc_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "shared_stack.py").read_text()
        assert "allow_all_outbound=False" in code


class TestCustomDomainWebhooks:
    """Tests for optional custom domain support via CloudFront and Route 53."""

    def test_custom_domain_imports_with_webhooks(self, tmp_path: Path) -> None:
        """Test that CloudFront, Route 53, and ACM imports are included with webhooks."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _complex_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "from aws_cdk import aws_certificatemanager as acm" in code
        assert "from aws_cdk import aws_cloudfront as cloudfront" in code
        assert "from aws_cdk import aws_cloudfront_origins as origins" in code
        assert "from aws_cdk import aws_route53 as route53" in code
        assert "from aws_cdk import aws_route53_targets as route53_targets" in code

    def test_no_custom_domain_imports_without_webhooks(self, tmp_path: Path) -> None:
        """Test that custom domain imports are omitted when no webhook handlers exist."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "aws_certificatemanager" not in code
        assert "aws_cloudfront" not in code
        assert "aws_cloudfront_origins" not in code
        assert "aws_route53" not in code
        assert "aws_route53_targets" not in code

    def test_custom_domain_context_check(self, tmp_path: Path) -> None:
        """Test that generated code checks for custom_domain context variable."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _complex_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert 'self.node.try_get_context("custom_domain")' in code
        assert 'self.node.try_get_context("certificate_arn")' in code
        assert 'self.node.try_get_context("hosted_zone_id")' in code

    def test_cloudfront_distribution_generated(self, tmp_path: Path) -> None:
        """Test that CloudFront distribution is generated for webhook functions."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _complex_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "cloudfront.Distribution(" in code
        assert "origins.HttpOrigin(" in code
        assert "domain_names=[custom_domain]" in code

    def test_route53_alias_record_generated(self, tmp_path: Path) -> None:
        """Test that Route 53 alias record is generated for webhook functions."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _complex_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "route53.ARecord(" in code
        assert "route53.RecordTarget.from_alias(" in code
        assert "route53_targets.CloudFrontTarget(" in code

    def test_acm_certificate_reference(self, tmp_path: Path) -> None:
        """Test that ACM certificate reference is generated."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _complex_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "acm.Certificate.from_certificate_arn(" in code

    def test_hosted_zone_lookup(self, tmp_path: Path) -> None:
        """Test that Route 53 hosted zone is looked up from context."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _complex_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "route53.HostedZone.from_hosted_zone_attributes(" in code
        assert "hosted_zone_id=hosted_zone_id" in code

    def test_no_custom_domain_without_webhooks(self, tmp_path: Path) -> None:
        """Test that custom domain code is not generated without webhook handlers."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "custom_domain" not in code
        assert "cloudfront.Distribution" not in code
        assert "route53.ARecord" not in code

    def test_function_url_stored_in_variable(self, tmp_path: Path) -> None:
        """Test that function URL result is stored for use by custom domain."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _complex_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "fn_url_webhook_handler = " in code
        assert "add_function_url(" in code

    def test_default_behavior_unchanged(self, tmp_path: Path) -> None:
        """Test that Function URLs are used directly when custom domain is disabled."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _complex_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "FunctionUrlAuthType.NONE" in code
        assert "if custom_domain:" in code


def _shared_deps_input() -> PackagerInput:
    """Input with multiple functions sharing dependencies."""
    return PackagerInput(
        metadata=WorkflowMetadata(
            workflow_name="shared-deps-wf",
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
                function_name="code_transform_a",
                runtime=LambdaRuntime.NODEJS,
                handler_code="exports.handler = async (e) => e;",
                function_type=LambdaFunctionType.CODE_NODE_JS,
                source_node_name="CodeA",
                dependencies=["luxon@3.4.4", "lodash@4.17.21"],
            ),
            LambdaFunctionSpec(
                function_name="code_transform_b",
                runtime=LambdaRuntime.NODEJS,
                handler_code="exports.handler = async (e) => e;",
                function_type=LambdaFunctionType.CODE_NODE_JS,
                source_node_name="CodeB",
                dependencies=["luxon@3.4.4", "axios@1.6.0"],
            ),
        ],
        conversion_report=ConversionReport(
            total_nodes=3,
            confidence_score=0.9,
        ),
    )


def _mixed_runtime_shared_deps_input() -> PackagerInput:
    """Input with shared deps across both Node.js and Python runtimes."""
    return PackagerInput(
        metadata=WorkflowMetadata(
            workflow_name="mixed-layers-wf",
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
                function_name="js_fn_a",
                runtime=LambdaRuntime.NODEJS,
                handler_code="exports.handler = async (e) => e;",
                function_type=LambdaFunctionType.CODE_NODE_JS,
                source_node_name="CodeA",
                dependencies=["luxon@3.4.4"],
            ),
            LambdaFunctionSpec(
                function_name="js_fn_b",
                runtime=LambdaRuntime.NODEJS,
                handler_code="exports.handler = async (e) => e;",
                function_type=LambdaFunctionType.CODE_NODE_JS,
                source_node_name="CodeB",
                dependencies=["luxon@3.4.4"],
            ),
            LambdaFunctionSpec(
                function_name="py_fn_a",
                runtime=LambdaRuntime.PYTHON,
                handler_code="def handler(event, context): pass",
                function_type=LambdaFunctionType.CODE_NODE_PYTHON,
                source_node_name="PyA",
                dependencies=["httpx==0.27.0"],
            ),
            LambdaFunctionSpec(
                function_name="py_fn_b",
                runtime=LambdaRuntime.PYTHON,
                handler_code="def handler(event, context): pass",
                function_type=LambdaFunctionType.CODE_NODE_PYTHON,
                source_node_name="PyB",
                dependencies=["httpx==0.27.0"],
            ),
        ],
        conversion_report=ConversionReport(
            total_nodes=5,
            confidence_score=0.9,
        ),
    )


class TestLambdaLayers:
    """Tests for Lambda Layer CDK generation."""

    def test_shared_deps_create_layer_construct(self, tmp_path: Path) -> None:
        """Test that shared deps generate a LayerVersion construct."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _shared_deps_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "nodejs_shared_layer = lambda_.LayerVersion(" in code
        assert "NodejsSharedLayer" in code
        assert "compatible_runtimes=[lambda_.Runtime.NODEJS_20_X]" in code

    def test_shared_deps_functions_reference_layer(self, tmp_path: Path) -> None:
        """Test that functions referencing shared deps have layers= parameter."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _shared_deps_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "layers=[nodejs_shared_layer]" in code

    def test_no_shared_deps_no_layer(self, tmp_path: Path) -> None:
        """Test that no layers are generated when there are no shared deps."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "LayerVersion(" not in code
        assert "layers=[" not in code

    def test_mixed_runtimes_both_layers(self, tmp_path: Path) -> None:
        """Test that both Node.js and Python layers are generated."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _mixed_runtime_shared_deps_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "nodejs_shared_layer = lambda_.LayerVersion(" in code
        assert "python_shared_layer = lambda_.LayerVersion(" in code
        assert "PythonSharedLayer" in code

    def test_python_layer_uses_stable_layer_version(self, tmp_path: Path) -> None:
        """Test that Python layers use lambda_.LayerVersion, not PythonLayerVersion."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _mixed_runtime_shared_deps_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "PythonLayerVersion" not in code
        assert "lambda_.LayerVersion(" in code

    def test_python_layer_has_bundling_options(self, tmp_path: Path) -> None:
        """Test that Python layers use BundlingOptions targeting python/ subdir."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _mixed_runtime_shared_deps_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "cdk.BundlingOptions(" in code
        assert "/asset-output/python" in code

    def test_layer_description_includes_dep_names(self, tmp_path: Path) -> None:
        """Test that layer comments include dependency names."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _shared_deps_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert "Shared Node.js deps: luxon" in code

    def test_layer_asset_path(self, tmp_path: Path) -> None:
        """Test that the layer construct points to the correct asset path."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _shared_deps_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        assert '"layers" / "nodejs-shared"' in code

    def test_workflow_stack_syntactically_valid_with_layers(
        self, tmp_path: Path
    ) -> None:
        """Test that workflow stack with layers is syntactically valid Python."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _shared_deps_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        compile(code, "workflow_stack.py", "exec")

    def test_existing_tests_still_pass_complex_input(self, tmp_path: Path) -> None:
        """Test that complex input (no shared deps) still generates correctly."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _complex_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        # No layers because no deps are shared across functions of same runtime
        assert "LayerVersion(" not in code
        assert "lambda_.Function(" in code


class TestWorkflowStackCompile:
    """Compile-check workflow_stack.py from all major fixtures."""

    def test_complex_input_syntactically_valid(self, tmp_path: Path) -> None:
        """Test that workflow stack from complex input is valid Python."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _complex_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        compile(code, "workflow_stack.py", "exec")

    def test_vpc_input_syntactically_valid(self, tmp_path: Path) -> None:
        """Test that workflow stack from VPC input is valid Python."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _vpc_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        compile(code, "workflow_stack.py", "exec")

    def test_minimal_input_syntactically_valid(self, tmp_path: Path) -> None:
        """Test that workflow stack from minimal input is valid Python."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()
        compile(code, "workflow_stack.py", "exec")


class TestSharedStackCompile:
    """Compile-check shared_stack.py from all major fixtures."""

    def test_minimal_input_syntactically_valid(self, tmp_path: Path) -> None:
        """Test that shared stack from minimal input is valid Python."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _minimal_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "shared_stack.py").read_text()
        compile(code, "shared_stack.py", "exec")

    def test_vpc_input_syntactically_valid(self, tmp_path: Path) -> None:
        """Test that shared stack from VPC input is valid Python."""
        writer = CDKWriter()
        cdk_dir = writer.write(
            _vpc_input(),
            _make_iam_policy(),
            _make_ssm_params(),
            tmp_path,
        )
        code = (cdk_dir / "stacks" / "shared_stack.py").read_text()
        compile(code, "shared_stack.py", "exec")
