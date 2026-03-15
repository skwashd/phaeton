"""CDK stack generator.

Generates source code files for a deployable CDK application: ``app.py``,
``cdk.json``, ``pyproject.toml``, and the stack modules (``shared_stack.py``
and ``workflow_stack.py``).
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

from n8n_to_sfn_packager.models.inputs import (
    LambdaFunctionType,
    LambdaRuntime,
    PackagerInput,
    TriggerType,
)
from n8n_to_sfn_packager.models.ssm import SSMParameterDefinition


class CDKWriter:
    """Generate CDK application source files."""

    def write(
        self,
        input_data: PackagerInput,
        iam_policy: dict[str, Any],
        ssm_params: list[SSMParameterDefinition],
        output_dir: Path,
    ) -> Path:
        """Write the complete ``cdk/`` directory.

        Args:
            input_data: The packager input.
            iam_policy: The generated IAM policy document.
            ssm_params: SSM parameter definitions.
            output_dir: Root output directory.

        Returns:
            Path to the created ``cdk/`` directory.

        """
        cdk_dir = output_dir / "cdk"
        stacks_dir = cdk_dir / "stacks"
        stacks_dir.mkdir(parents=True, exist_ok=True)

        wf_name = input_data.metadata.workflow_name
        stack_prefix = wf_name.replace(" ", "-").replace("_", "-")

        self._write_app_py(cdk_dir, stack_prefix)
        self._write_cdk_json(cdk_dir, input_data)
        self._write_pyproject_toml(cdk_dir)
        self._write_shared_stack(stacks_dir, stack_prefix)
        self._write_stacks_init(stacks_dir)
        self._write_workflow_stack(
            stacks_dir,
            input_data,
            iam_policy,
            ssm_params,
            stack_prefix,
        )

        return cdk_dir

    @staticmethod
    def _write_app_py(cdk_dir: Path, stack_prefix: str) -> None:
        """Write the CDK app entry point."""
        code = textwrap.dedent(f"""\
            #!/usr/bin/env python3
            \"\"\"CDK application entry point for the {stack_prefix} workflow.\"\"\"

            import aws_cdk as cdk

            from stacks.shared_stack import SharedStack
            from stacks.workflow_stack import WorkflowStack

            app = cdk.App()

            shared = SharedStack(app, "{stack_prefix}-shared")
            WorkflowStack(
                app,
                "{stack_prefix}-workflow",
                shared_stack=shared,
            )

            app.synth()
        """)
        (cdk_dir / "app.py").write_text(code)

    @staticmethod
    def _write_cdk_json(cdk_dir: Path, input_data: PackagerInput) -> None:
        """Write the CDK configuration file."""
        context: dict[str, str] = {}
        for sw in input_data.sub_workflows:
            key = f"sub_workflow_arn_{sw.name.replace('-', '_')}"
            context[key] = f"<ARN for {sw.name}>"

        config = {
            "app": "uv run python app.py",
            "context": context,
        }
        (cdk_dir / "cdk.json").write_text(json.dumps(config, indent=2) + "\n")

    @staticmethod
    def _write_pyproject_toml(cdk_dir: Path) -> None:
        """Write the pyproject.toml for the generated CDK app."""
        toml = textwrap.dedent("""\
            [project]
            name = "cdk-app"
            version = "1.0.0"
            requires-python = ">=3.12"
            dependencies = [
                "aws-cdk-lib==2.239.0",
                "aws-cdk.aws-lambda-python-alpha==2.239.0a0",
                "constructs==10.5.1",
            ]

            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"
        """)
        (cdk_dir / "pyproject.toml").write_text(toml)

    @staticmethod
    def _write_shared_stack(stacks_dir: Path, stack_prefix: str) -> None:
        """Write the shared stack with KMS key, log group, and X-Ray group."""
        code = textwrap.dedent(f"""\
            \"\"\"Shared infrastructure: KMS key, CloudWatch log group, X-Ray group.\"\"\"

            import aws_cdk as cdk
            from aws_cdk import aws_kms as kms
            from aws_cdk import aws_logs as logs
            from constructs import Construct


            class SharedStack(cdk.Stack):
                \"\"\"Shared resources used by the workflow stack.\"\"\"

                def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
                    super().__init__(scope, construct_id, **kwargs)

                    # KMS key for encrypting state machine data, SSM parameters, and logs
                    self.kms_key = kms.Key(
                        self,
                        "WorkflowKey",
                        alias="{stack_prefix}-key",
                        description="Encryption key for {stack_prefix} workflow",
                        enable_key_rotation=True,
                    )

                    # CloudWatch log group for Step Functions execution logs
                    self.log_group = logs.LogGroup(
                        self,
                        "ExecutionLogs",
                        log_group_name="/aws/stepfunctions/{stack_prefix}",
                        retention=logs.RetentionDays.ONE_MONTH,
                        encryption_key=self.kms_key,
                    )
        """)
        (stacks_dir / "shared_stack.py").write_text(code)

    @staticmethod
    def _write_stacks_init(stacks_dir: Path) -> None:
        """Write the stacks package init."""
        (stacks_dir / "__init__.py").write_text(
            '"""CDK stack definitions."""\n',
        )

    def _write_workflow_stack(
        self,
        stacks_dir: Path,
        input_data: PackagerInput,
        iam_policy: dict[str, Any],
        ssm_params: list[SSMParameterDefinition],
        stack_prefix: str,
    ) -> None:
        """Write the main workflow stack."""
        lines: list[str] = []

        self._wf_imports(lines, input_data)
        self._wf_class_header(lines, stack_prefix)
        self._wf_ssm_parameters(lines, ssm_params)
        self._wf_dead_letter_queue(lines, stack_prefix)
        self._wf_lambda_functions(lines, input_data)
        self._wf_state_machine(lines, iam_policy, stack_prefix)
        self._wf_alarms(lines)
        self._wf_triggers(lines, input_data)
        self._wf_oauth_rotation(lines, input_data)
        self._wf_sub_workflow_params(lines, input_data)

        (stacks_dir / "workflow_stack.py").write_text("\n".join(lines) + "\n")

    @staticmethod
    def _wf_imports(lines: list[str], input_data: PackagerInput) -> None:
        """Append import statements."""
        lines.append(
            '"""Workflow stack: state machine, Lambdas, triggers, credentials."""'
        )
        lines.append("")
        lines.append("import json")
        lines.append("from pathlib import Path")
        lines.append("")
        lines.append("import aws_cdk as cdk")
        lines.append("from aws_cdk import aws_cloudwatch as cloudwatch")
        lines.append("from aws_cdk import aws_events as events")
        lines.append("from aws_cdk import aws_events_targets as targets")
        lines.append("from aws_cdk import aws_iam as iam")
        lines.append("from aws_cdk import aws_lambda as lambda_")
        lines.append("from aws_cdk import aws_sqs as sqs")
        lines.append("from aws_cdk import aws_ssm as ssm")
        lines.append("from aws_cdk import aws_stepfunctions as sfn")

        has_python_lambda = any(
            s.runtime == LambdaRuntime.PYTHON for s in input_data.lambda_functions
        )
        if has_python_lambda or input_data.oauth_credentials:
            lines.append(
                "from aws_cdk.aws_lambda_python_alpha import PythonFunction",
            )

        lines.append("from constructs import Construct")
        lines.append("")
        lines.append("from stacks.shared_stack import SharedStack")
        lines.append("")
        lines.append("")

    @staticmethod
    def _wf_class_header(lines: list[str], stack_prefix: str) -> None:
        """Append class definition and constructor header."""
        lines.append("class WorkflowStack(cdk.Stack):")
        lines.append(f'    """Main workflow stack for {stack_prefix}."""')
        lines.append("")
        lines.append(
            "    def __init__(",
        )
        lines.append("        self,")
        lines.append("        scope: Construct,")
        lines.append("        construct_id: str,")
        lines.append("        shared_stack: SharedStack,")
        lines.append("        **kwargs,")
        lines.append("    ) -> None:")
        lines.append("        super().__init__(scope, construct_id, **kwargs)")
        lines.append("")

    @staticmethod
    def _wf_ssm_parameters(
        lines: list[str],
        ssm_params: list[SSMParameterDefinition],
    ) -> None:
        """Append SSM parameter constructs."""
        if not ssm_params:
            return
        lines.append("        # --- SSM Parameters (credentials) ---")
        for param in ssm_params:
            safe_id = (
                param.parameter_path.strip("/").replace("/", "-").replace("_", "-")
            )
            lines.append("        ssm.StringParameter(")
            lines.append("            self,")
            lines.append(f'            "Param-{safe_id}",')
            lines.append(
                f'            parameter_name="{param.parameter_path}",',
            )
            lines.append(
                f'            string_value="{param.placeholder_value}",',
            )
            lines.append(f'            description="{param.description}",')
            lines.append("        )")
            lines.append("")

    @staticmethod
    def _wf_dead_letter_queue(lines: list[str], stack_prefix: str) -> None:
        """Append SQS dead-letter queue construct."""
        lines.append("        # --- Dead Letter Queue ---")
        lines.append("        dlq = sqs.Queue(")
        lines.append("            self,")
        lines.append('            "DeadLetterQueue",')
        lines.append(
            f'            queue_name="{stack_prefix}-dlq",'
        )
        lines.append("            retention_period=cdk.Duration.days(14),")
        lines.append("        )")
        lines.append("")

    @staticmethod
    def _wf_lambda_functions(lines: list[str], input_data: PackagerInput) -> None:
        """Append Lambda function constructs."""
        if not input_data.lambda_functions:
            return
        lines.append("        # --- Lambda Functions ---")
        lines.append("        lambda_functions = {}")
        lines.append("")

        for spec in input_data.lambda_functions:
            construct_id = spec.function_name.replace("_", "-").title().replace("-", "")
            comment = (
                f"  # Source n8n node: {spec.source_node_name}"
                if spec.source_node_name
                else ""
            )

            if spec.runtime == LambdaRuntime.PYTHON:
                lines.append(
                    f"        # {spec.description or spec.function_name}{comment}",
                )
                lines.append(
                    f'        lambda_functions["{spec.function_name}"] = PythonFunction('
                )
                lines.append("            self,")
                lines.append(f'            "{construct_id}Fn",')
                lines.append(
                    f'            entry=str(Path(__file__).parent.parent.parent / "lambdas" / "{spec.function_name}"),',
                )
                lines.append("            runtime=lambda_.Runtime.PYTHON_3_12,")
                lines.append('            index="handler.py",')
                lines.append('            handler="handler",')
                lines.append("            tracing=lambda_.Tracing.ACTIVE,")
                lines.append("            dead_letter_queue=dlq,")
                lines.append("        )")
            else:
                lines.append(
                    f"        # {spec.description or spec.function_name}{comment}",
                )
                lines.append(
                    f'        lambda_functions["{spec.function_name}"] = lambda_.Function('
                )
                lines.append("            self,")
                lines.append(f'            "{construct_id}Fn",')
                lines.append(
                    "            runtime=lambda_.Runtime.NODEJS_20_X,",
                )
                lines.append(
                    '            handler="handler.handler",',
                )
                lines.append(
                    f'            code=lambda_.Code.from_asset(str(Path(__file__).parent.parent.parent / "lambdas" / "{spec.function_name}")),',
                )
                lines.append("            tracing=lambda_.Tracing.ACTIVE,")
                lines.append("            dead_letter_queue=dlq,")
                lines.append("        )")
            lines.append("")

            # Function URL for webhook / callback handlers
            if spec.function_type in (
                LambdaFunctionType.WEBHOOK_HANDLER,
                LambdaFunctionType.CALLBACK_HANDLER,
            ):
                lines.append(
                    f'        lambda_functions["{spec.function_name}"].add_function_url(',
                )
                lines.append(
                    "            auth_type=lambda_.FunctionUrlAuthType.NONE,",
                )
                lines.append("        )")
                lines.append("")

    @staticmethod
    def _wf_state_machine(
        lines: list[str],
        iam_policy: dict[str, Any],
        stack_prefix: str,
    ) -> None:
        """Append state machine and IAM role constructs."""
        lines.append("        # --- IAM Execution Role ---")
        lines.append("        execution_role = iam.Role(")
        lines.append("            self,")
        lines.append('            "ExecutionRole",')
        lines.append(
            '            assumed_by=iam.ServicePrincipal("states.amazonaws.com"),',
        )
        lines.append(
            f'            description="Execution role for {stack_prefix} state machine",'
        )
        lines.append("        )")
        lines.append("")

        policy_json = json.dumps(iam_policy, indent=8)
        lines.append(f"        policy_doc = {policy_json}")
        lines.append("")
        lines.append("        execution_role.attach_inline_policy(")
        lines.append("            iam.Policy(")
        lines.append("                self,")
        lines.append('                "ExecutionPolicy",')
        lines.append(
            "                document=iam.PolicyDocument.from_json(policy_doc),",
        )
        lines.append("            ),")
        lines.append("        )")
        lines.append("")

        lines.append("        # --- State Machine ---")
        lines.append(
            '        definition_path = str(Path(__file__).parent.parent.parent / "statemachine" / "definition.asl.json")',
        )
        lines.append("        cfn_state_machine = sfn.CfnStateMachine(")
        lines.append("            self,")
        lines.append('            "StateMachine",')
        lines.append(
            f'            state_machine_name="{stack_prefix}",',
        )
        lines.append(
            "            definition_string=Path(definition_path).read_text(),",
        )
        lines.append("            role_arn=execution_role.role_arn,")
        lines.append(
            "            logging_configuration=sfn.CfnStateMachine.LoggingConfigurationProperty("
        )
        lines.append('                level="ALL",')
        lines.append("                include_execution_data=True,")
        lines.append("                destinations=[")
        lines.append("                    sfn.CfnStateMachine.LogDestinationProperty(")
        lines.append(
            "                        cloud_watch_logs_log_group=sfn.CfnStateMachine.CloudWatchLogsLogGroupProperty("
        )
        lines.append(
            "                            log_group_arn=shared_stack.log_group.log_group_arn,"
        )
        lines.append("                        ),")
        lines.append("                    ),")
        lines.append("                ],")
        lines.append("            ),")
        lines.append(
            "            tracing_configuration=sfn.CfnStateMachine.TracingConfigurationProperty("
        )
        lines.append("                enabled=True,")
        lines.append("            ),")
        lines.append("        )")
        lines.append("        state_machine = sfn.StateMachine.from_state_machine_arn(")
        lines.append('            self, "StateMachineRef", cfn_state_machine.attr_arn,')
        lines.append("        )")
        lines.append("")
        lines.append(
            "        # Route failed/timed-out/aborted executions to the DLQ"
        )
        lines.append("        events.Rule(")
        lines.append("            self,")
        lines.append('            "FailedExecutionDlqRule",')
        lines.append("            event_pattern=events.EventPattern(")
        lines.append('                source=["aws.states"],')
        lines.append(
            '                detail_type=["Step Functions Execution Status Change"],'
        )
        lines.append("                detail={")
        lines.append(
            '                    "status": ["FAILED", "TIMED_OUT", "ABORTED"],'
        )
        lines.append(
            '                    "stateMachineArn": [cfn_state_machine.attr_arn],'
        )
        lines.append("                },")
        lines.append("            ),")
        lines.append("            targets=[targets.SqsQueue(dlq)],")
        lines.append("        )")
        lines.append("")

    @staticmethod
    def _wf_alarms(lines: list[str]) -> None:
        """Append CloudWatch alarm constructs for the state machine."""
        lines.append("        # --- CloudWatch Alarms ---")
        for metric_method, alarm_id in [
            ("metric_failed", "FailedAlarm"),
            ("metric_timed_out", "TimedOutAlarm"),
            ("metric_throttled", "ThrottledAlarm"),
        ]:
            lines.append("        cloudwatch.Alarm(")
            lines.append("            self,")
            lines.append(f'            "{alarm_id}",')
            lines.append(
                f"            metric=state_machine.{metric_method}(),"
            )
            lines.append("            threshold=1,")
            lines.append("            evaluation_periods=1,")
            lines.append("        )")
            lines.append("")

    @staticmethod
    def _wf_triggers(lines: list[str], input_data: PackagerInput) -> None:
        """Append EventBridge schedule trigger constructs."""
        schedule_triggers = [
            t for t in input_data.triggers if t.trigger_type == TriggerType.SCHEDULE
        ]
        if not schedule_triggers:
            return

        lines.append("        # --- Schedule Triggers ---")
        for i, trigger in enumerate(schedule_triggers):
            expr = trigger.configuration.get("schedule_expression", "rate(1 hour)")
            lines.append("        events.Rule(")
            lines.append("            self,")
            lines.append(f'            "ScheduleRule{i}",')
            lines.append(f'            schedule=events.Schedule.expression("{expr}"),')
            lines.append(
                "            targets=[targets.SfnStateMachine(state_machine)],",
            )
            lines.append("        )")
            lines.append("")

    @staticmethod
    def _wf_oauth_rotation(lines: list[str], input_data: PackagerInput) -> None:
        """Append OAuth token rotation constructs."""
        if not input_data.oauth_credentials:
            return

        lines.append("        # --- OAuth Token Rotation ---")
        for i, oauth in enumerate(input_data.oauth_credentials):
            cred_name = oauth.credential_spec.parameter_path.strip("/").split("/")[-1]
            schedule_expr = oauth.refresh_schedule_expression
            param_path = oauth.credential_spec.parameter_path
            token_url = oauth.token_endpoint_url
            var_name = f"oauth_refresh_{cred_name.replace('-', '_')}"
            construct_id = (
                "OAuthRefresh"
                + cred_name.replace("_", " ").replace("-", " ").title().replace(" ", "")
            )

            # Lambda function for OAuth token refresh
            lines.append(f"        # OAuth rotation for {cred_name}")
            lines.append(f"        {var_name} = PythonFunction(")
            lines.append("            self,")
            lines.append(f'            "{construct_id}Fn",')
            lines.append(
                f'            entry=str(Path(__file__).parent.parent.parent / "lambdas" / "{var_name}"),',
            )
            lines.append("            runtime=lambda_.Runtime.PYTHON_3_12,")
            lines.append('            index="handler.py",')
            lines.append('            handler="handler",')
            lines.append("            environment={")
            lines.append(f'                "SSM_PARAMETER_PATH": "{param_path}",')
            lines.append(f'                "TOKEN_ENDPOINT_URL": "{token_url}",')
            lines.append("            },")
            lines.append("            tracing=lambda_.Tracing.ACTIVE,")
            lines.append("            dead_letter_queue=dlq,")
            lines.append("        )")

            # IAM permissions to read/write SSM parameters for this credential
            param_path_stripped = param_path.strip("/")
            lines.append(f"        {var_name}.add_to_role_policy(")
            lines.append("            iam.PolicyStatement(")
            lines.append(
                '                actions=["ssm:GetParameter", "ssm:PutParameter"],'
            )
            lines.append(
                f'                resources=["arn:aws:ssm:*:*:parameter/{param_path_stripped}/*"],',
            )
            lines.append("            )")
            lines.append("        )")
            lines.append("")

            # EventBridge rule targeting the refresh Lambda
            lines.append("        events.Rule(")
            lines.append("            self,")
            lines.append(f'            "OAuthRotation{i}",')
            lines.append(
                f'            schedule=events.Schedule.expression("{schedule_expr}"),',
            )
            lines.append(
                f"            targets=[targets.LambdaFunction({var_name})],",
            )
            lines.append("        )")
            lines.append("")

    @staticmethod
    def _wf_sub_workflow_params(
        lines: list[str],
        input_data: PackagerInput,
    ) -> None:
        """Append CfnParameter constructs for sub-workflow ARNs."""
        if not input_data.sub_workflows:
            return

        lines.append("        # --- Sub-workflow ARN Parameters ---")
        for sw in input_data.sub_workflows:
            param_id = sw.name.replace("-", "_").replace(" ", "_")
            lines.append("        cdk.CfnParameter(")
            lines.append("            self,")
            lines.append(f'            "SubWorkflowArn{param_id}",')
            lines.append(
                f'            description="ARN of the {sw.name} sub-workflow",'
            )
            lines.append(f'            default="<{sw.name}-arn>",')
            lines.append("        )")
            lines.append("")
