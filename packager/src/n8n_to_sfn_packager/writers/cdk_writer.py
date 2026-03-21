"""
CDK stack generator.

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
    VpcConfig,
)
from n8n_to_sfn_packager.models.ssm import SSMParameterDefinition
from n8n_to_sfn_packager.writers.lambda_writer import (
    LayerSpec,
    analyze_shared_dependencies,
)
from n8n_to_sfn_packager.writers.picofun_writer import PicoFunOutput
from n8n_to_sfn_packager.writers.ssm_writer import SSMWriter

# 8 spaces: indentation level inside __init__ body
_BODY = "        "


def _body(template: str) -> str:
    """Dedent *template* and re-indent to the ``__init__`` body level."""
    return textwrap.indent(textwrap.dedent(template), _BODY)


class CDKWriter:
    """Generate CDK application source files."""

    def write(
        self,
        input_data: PackagerInput,
        iam_policy: dict[str, Any],
        ssm_params: list[SSMParameterDefinition],
        output_dir: Path,
        picofun_output: PicoFunOutput | None = None,
    ) -> tuple[Path, list[str]]:
        """
        Write the complete ``cdk/`` directory.

        Args:
            input_data: The packager input.
            iam_policy: The generated IAM policy document.
            ssm_params: SSM parameter definitions.
            output_dir: Root output directory.
            picofun_output: Optional PicoFun artifact metadata.

        Returns:
            Tuple of the created ``cdk/`` directory path and a list of
            warnings about unauthenticated webhook handlers.

        """
        cdk_dir = output_dir / "cdk"
        stacks_dir = cdk_dir / "stacks"
        stacks_dir.mkdir(parents=True, exist_ok=True)

        wf_name = input_data.metadata.workflow_name
        stack_prefix = wf_name.replace(" ", "-").replace("_", "-")

        self._write_app_py(cdk_dir, stack_prefix)
        self._write_cdk_json(cdk_dir, input_data)
        self._write_pyproject_toml(cdk_dir)
        self._write_shared_stack(stacks_dir, stack_prefix, input_data.vpc_config)
        self._write_stacks_init(stacks_dir)
        warnings = self._write_workflow_stack(
            stacks_dir,
            input_data,
            iam_policy,
            ssm_params,
            stack_prefix,
            picofun_output=picofun_output,
        )

        self._write_credentials_doc(output_dir, input_data)

        return cdk_dir, warnings

    @staticmethod
    def _write_credentials_doc(
        output_dir: Path,
        input_data: PackagerInput,
    ) -> None:
        """Write CREDENTIALS.md to the output directory."""
        ssm_writer = SSMWriter()
        content = ssm_writer.generate_credential_documentation(
            input_data.credentials,
            input_data.oauth_credentials,
        )
        (output_dir / "CREDENTIALS.md").write_text(content)

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

        if input_data.vpc_config:
            context["vpc_id"] = "<your-vpc-id>"
            context["subnet_ids"] = "<comma-separated-private-subnet-ids>"
            context["security_group_ids"] = "<comma-separated-security-group-ids>"

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
                "constructs==10.5.1",
            ]

            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"
        """)
        (cdk_dir / "pyproject.toml").write_text(toml)

    @staticmethod
    def _write_shared_stack(
        stacks_dir: Path,
        stack_prefix: str,
        vpc_config: VpcConfig | None = None,
    ) -> None:
        """Write the shared stack with KMS key, log group, and X-Ray group."""
        import_lines = [
            '"""Shared infrastructure: KMS key, CloudWatch log group, X-Ray group."""',
            "",
            "import aws_cdk as cdk",
            "from aws_cdk import aws_kms as kms",
            "from aws_cdk import aws_logs as logs",
        ]
        if vpc_config:
            import_lines.append("from aws_cdk import aws_ec2 as ec2")
        import_lines.extend(["from constructs import Construct", "", ""])

        base = textwrap.dedent(f"""\
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

        sections: list[str] = ["\n".join(import_lines) + "\n", base]

        if vpc_config:
            sections.append(
                "\n"
                + _body(f"""\
                # --- VPC Configuration ---
                vpc_id = self.node.try_get_context("vpc_id")
                if vpc_id:
                    self.vpc = ec2.Vpc.from_lookup(self, "VPC", vpc_id=vpc_id)
                else:
                    self.vpc = ec2.Vpc(self, "PhaethonVPC", max_azs=2, nat_gateways=1)

                # Security group for Lambda functions
                self.lambda_security_group = ec2.SecurityGroup(
                    self,
                    "LambdaSG",
                    vpc=self.vpc,
                    description="Security group for {stack_prefix} Lambda functions",
                    allow_all_outbound=False,
                )
            """)
            )

            for rule in vpc_config.security_group_rules:
                sections.append(
                    _body(f"""\
                    self.lambda_security_group.add_egress_rule(
                        ec2.Peer.any_ipv4(),
                        ec2.Port.tcp({rule["port"]}),
                        "{rule["description"]} access",
                    )
                """)
                )

            # HTTPS egress for NAT Gateway path
            sections.append(
                _body("""\
                self.lambda_security_group.add_egress_rule(
                    ec2.Peer.any_ipv4(),
                    ec2.Port.tcp(443),
                    "HTTPS outbound for AWS APIs and internet access",
                )
            """)
            )

        code = "".join(sections)
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
        picofun_output: PicoFunOutput | None = None,
    ) -> list[str]:
        """
        Write the main workflow stack.

        Returns:
            Warnings about unauthenticated webhook handlers.

        """
        has_picofun = any(
            s.function_type == LambdaFunctionType.PICOFUN_API_CLIENT
            for s in input_data.lambda_functions
        )
        layers, _ = analyze_shared_dependencies(input_data.lambda_functions)
        lambda_code, warnings = self._wf_lambda_functions(input_data, layers)

        sections = [
            self._wf_imports(input_data, has_picofun=has_picofun),
            self._wf_class_header(stack_prefix),
            self._wf_vpc_lookup(input_data),
            self._wf_ssm_parameters(ssm_params),
            self._wf_dead_letter_queue(stack_prefix),
            self._wf_lambda_layers(layers, picofun_output=picofun_output),
            lambda_code,
            self._wf_picofun_construct(input_data, picofun_output),
            self._wf_state_machine(iam_policy, stack_prefix),
            self._wf_alarms(),
            self._wf_triggers(input_data),
            self._wf_custom_domain(input_data),
            self._wf_oauth_rotation(input_data),
            self._wf_sub_workflow_params(input_data),
        ]

        (stacks_dir / "workflow_stack.py").write_text("".join(s for s in sections if s))
        return warnings

    @staticmethod
    def _wf_imports(
        input_data: PackagerInput,
        *,
        has_picofun: bool = False,
    ) -> str:
        """Return import statements."""
        has_webhook_fns = any(
            s.function_type
            in (
                LambdaFunctionType.WEBHOOK_HANDLER,
                LambdaFunctionType.CALLBACK_HANDLER,
            )
            for s in input_data.lambda_functions
        )

        lines = [
            '"""Workflow stack: state machine, Lambdas, triggers, credentials."""',
            "",
            "import json",
            "from pathlib import Path",
            "",
            "import aws_cdk as cdk",
        ]
        if has_webhook_fns:
            lines.append("from aws_cdk import aws_certificatemanager as acm")
            lines.append("from aws_cdk import aws_cloudfront as cloudfront")
            lines.append("from aws_cdk import aws_cloudfront_origins as origins")
        lines.append("from aws_cdk import aws_cloudwatch as cloudwatch")
        if input_data.vpc_config:
            lines.append("from aws_cdk import aws_ec2 as ec2")
        lines.extend(
            [
                "from aws_cdk import aws_events as events",
                "from aws_cdk import aws_events_targets as targets",
                "from aws_cdk import aws_iam as iam",
                "from aws_cdk import aws_lambda as lambda_",
            ]
        )
        if has_webhook_fns:
            lines.append("from aws_cdk import aws_route53 as route53")
            lines.append("from aws_cdk import aws_route53_targets as route53_targets")
        lines.extend(
            [
                "from aws_cdk import aws_sqs as sqs",
                "from aws_cdk import aws_ssm as ssm",
                "from aws_cdk import aws_stepfunctions as sfn",
                "from constructs import Construct",
            ]
        )
        if has_picofun:
            lines.append("from construct import PicoFunConstruct")
        lines.extend(
            [
                "",
                "from stacks.shared_stack import SharedStack",
                "",
                "",
            ]
        )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _wf_class_header(stack_prefix: str) -> str:
        """Return class definition and constructor header."""
        return textwrap.dedent(f"""\
            class WorkflowStack(cdk.Stack):
                \"\"\"Main workflow stack for {stack_prefix}.\"\"\"

                def __init__(
                    self,
                    scope: Construct,
                    construct_id: str,
                    shared_stack: SharedStack,
                    **kwargs,
                ) -> None:
                    super().__init__(scope, construct_id, **kwargs)

        """)

    @staticmethod
    def _wf_vpc_lookup(input_data: PackagerInput) -> str:
        """Return VPC resource references from the shared stack."""
        if not input_data.vpc_config:
            return ""
        return (
            _body("""\
            # --- VPC Configuration ---
            vpc = shared_stack.vpc
            lambda_sg = shared_stack.lambda_security_group
            vpc_subnets = ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
        """)
            + "\n"
        )

    @staticmethod
    def _wf_ssm_parameters(ssm_params: list[SSMParameterDefinition]) -> str:
        """Return SSM parameter constructs."""
        if not ssm_params:
            return ""
        parts = [_BODY + "# --- SSM Parameters (credentials) ---\n"]
        for param in ssm_params:
            safe_id = (
                param.parameter_path.strip("/").replace("/", "-").replace("_", "-")
            )
            parts.append(
                _body(f"""\
                ssm.StringParameter(
                    self,
                    "Param-{safe_id}",
                    parameter_name="{param.parameter_path}",
                    string_value="{param.placeholder_value}",
                    description="{param.description}",
                )
            """)
                + "\n"
            )
        return "".join(parts)

    @staticmethod
    def _wf_dead_letter_queue(stack_prefix: str) -> str:
        """Return SQS dead-letter queue construct."""
        return (
            _body(f"""\
            # --- Dead Letter Queue ---
            dlq = sqs.Queue(
                self,
                "DeadLetterQueue",
                queue_name="{stack_prefix}-dlq",
                retention_period=cdk.Duration.days(14),
            )
        """)
            + "\n"
        )

    @staticmethod
    def _wf_lambda_layers(
        layers: list[LayerSpec],
        picofun_output: PicoFunOutput | None = None,
    ) -> str:
        """Return Lambda Layer constructs for shared dependencies."""
        if not layers and not picofun_output:
            return ""

        parts = [_BODY + "# --- Lambda Layers (shared dependencies) ---\n"]

        if picofun_output:
            layer_path = picofun_output.layer_dir
            parts.append(
                _body(f"""\
                    picofun_layer = lambda_.LayerVersion(
                        self,
                        "PicoFunLayer",
                        code=lambda_.Code.from_asset(str(Path(__file__).parent.parent.parent / "{layer_path.name}")),
                        compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
                        description="PicoFun picorun runtime layer",
                    )
                """)
                + "\n"
            )

        for layer in layers:
            var_name = layer.layer_name.replace("-", "_") + "_layer"
            construct_id = (
                layer.layer_name.replace("-", " ").title().replace(" ", "") + "Layer"
            )
            dep_summary = ", ".join(
                d.split("==")[0].split("@")[0] for d in layer.dependencies
            )

            if layer.runtime == LambdaRuntime.PYTHON:
                parts.append(
                    _body(f"""\
                    # Shared Python deps: {dep_summary}
                    {var_name} = lambda_.LayerVersion(
                        self,
                        "{construct_id}",
                        code=lambda_.Code.from_asset(
                            str(Path(__file__).parent.parent.parent / "layers" / "{layer.layer_name}"),
                            bundling=cdk.BundlingOptions(
                                image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                                command=["bash", "-c", "pip install --no-cache-dir -r /asset-input/requirements.txt -t /asset-output/python"],
                            ),
                        ),
                        compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
                        description="Shared Python dependencies for workflow",
                    )
                """)
                    + "\n"
                )
            else:
                parts.append(
                    _body(f"""\
                    # Shared Node.js deps: {dep_summary}
                    {var_name} = lambda_.LayerVersion(
                        self,
                        "{construct_id}",
                        code=lambda_.Code.from_asset(str(Path(__file__).parent.parent.parent / "layers" / "{layer.layer_name}")),
                        compatible_runtimes=[lambda_.Runtime.NODEJS_20_X],
                        description="Shared Node.js dependencies for workflow",
                    )
                """)
                    + "\n"
                )
        return "".join(parts)

    @staticmethod
    def _wf_lambda_functions(
        input_data: PackagerInput,
        layers: list[LayerSpec] | None = None,
    ) -> tuple[str, list[str]]:
        """Return Lambda function constructs and unauthenticated-webhook warnings."""
        warnings: list[str] = []
        if not input_data.lambda_functions:
            return "", warnings

        non_picofun = [
            s
            for s in input_data.lambda_functions
            if s.function_type != LambdaFunctionType.PICOFUN_API_CLIENT
        ]

        parts: list[str] = [
            _BODY + "# --- Lambda Functions ---\n",
            _BODY + "lambda_functions = {}\n",
            "\n",
        ]

        for spec in non_picofun:
            construct_id = spec.function_name.replace("_", "-").title().replace("-", "")
            comment = (
                f"  # Source n8n node: {spec.source_node_name}"
                if spec.source_node_name
                else ""
            )

            # Build optional VPC and layer parameter lines
            extras: list[str] = []
            if layers:
                layer_var_names = [
                    layer.layer_name.replace("-", "_") + "_layer"
                    for layer in layers
                    if spec.function_name in layer.function_names
                ]
                if layer_var_names:
                    layer_list = ", ".join(layer_var_names)
                    extras.append(f"            layers=[{layer_list}],\n")
            if input_data.vpc_config:
                extras.extend(
                    [
                        "            vpc=vpc,\n",
                        "            vpc_subnets=vpc_subnets,\n",
                        "            security_groups=[lambda_sg],\n",
                    ]
                )
            extras_str = "".join(extras)

            if spec.runtime == LambdaRuntime.PYTHON:
                parts.append(
                    _body(f"""\
                    # {spec.description or spec.function_name}{comment}
                    lambda_functions["{spec.function_name}"] = lambda_.Function(
                        self,
                        "{construct_id}Fn",
                        runtime=lambda_.Runtime.PYTHON_3_12,
                        handler="handler.handler",
                        code=lambda_.Code.from_asset(
                            str(Path(__file__).parent.parent.parent / "lambdas" / "{spec.function_name}"),
                            bundling=cdk.BundlingOptions(
                                image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                                command=["bash", "-c", "pip install --no-cache-dir -r /asset-input/requirements.txt -t /asset-output && cp /asset-input/*.py /asset-output/"],
                            ),
                        ),
                """)
                    + extras_str
                    + _body("""\
                    tracing=lambda_.Tracing.ACTIVE,
                    dead_letter_queue=dlq,
                )
                """)
                    + "\n"
                )
            else:
                parts.append(
                    _body(f"""\
                    # {spec.description or spec.function_name}{comment}
                    lambda_functions["{spec.function_name}"] = lambda_.Function(
                        self,
                        "{construct_id}Fn",
                        runtime=lambda_.Runtime.NODEJS_20_X,
                        handler="handler.handler",
                        code=lambda_.Code.from_asset(str(Path(__file__).parent.parent.parent / "lambdas" / "{spec.function_name}")),
                """)
                    + extras_str
                    + _body("""\
                    tracing=lambda_.Tracing.ACTIVE,
                    dead_letter_queue=dlq,
                )
                """)
                    + "\n"
                )

            # Function URL for webhook / callback handlers
            if spec.function_type in (
                LambdaFunctionType.WEBHOOK_HANDLER,
                LambdaFunctionType.CALLBACK_HANDLER,
            ):
                parts.append(
                    _body(f"""\
                    fn_url_{spec.function_name} = lambda_functions["{spec.function_name}"].add_function_url(
                        auth_type=lambda_.FunctionUrlAuthType.NONE,
                    )
                """)
                    + "\n"
                )

                # Webhook authentication: SSM env var + IAM permission
                if spec.webhook_auth:
                    param_path = spec.webhook_auth.credential_parameter_path
                    param_path_stripped = param_path.strip("/")
                    parts.append(
                        _body(f"""\
                        lambda_functions["{spec.function_name}"].add_environment(
                            "WEBHOOK_AUTH_PARAMETER", "{param_path}",
                        )
                        lambda_functions["{spec.function_name}"].add_to_role_policy(
                            iam.PolicyStatement(
                                actions=["ssm:GetParameter"],
                                resources=["arn:aws:ssm:*:*:parameter/{param_path_stripped}"],
                            )
                        )
                    """)
                        + "\n"
                    )
                else:
                    warnings.append(
                        f"Webhook handler '{spec.function_name}' has no "
                        f"authentication configured. The Function URL will be "
                        f"publicly accessible."
                    )

        return "".join(parts), warnings

    @staticmethod
    def _wf_picofun_construct(
        input_data: PackagerInput,
        picofun_output: PicoFunOutput | None,
    ) -> str:
        """Generate code to instantiate the PicoFun CDK construct."""
        if not picofun_output:
            return ""

        picofun_functions = [
            s
            for s in input_data.lambda_functions
            if s.function_type == LambdaFunctionType.PICOFUN_API_CLIENT
        ]
        if not picofun_functions:
            return ""

        parts: list[str] = [_BODY + "# --- PicoFun Construct ---\n"]

        func_names = ", ".join(f'"{f.function_name}"' for f in picofun_functions)

        vpc_lines = ""
        if input_data.vpc_config:
            vpc_lines = (
                "            vpc=vpc,\n"
                "            security_groups=[lambda_sg],\n"
            )

        parts.append(
            _body(f"""\
                picofun = PicoFunConstruct(
                    self,
                    "PicoFun",
                    layer=picofun_layer,
                    function_names=[{func_names}],
            """)
            + vpc_lines
            + _body("""\
                )
            """)
            + "\n"
        )

        for spec in picofun_functions:
            parts.append(
                _body(f"""\
                    lambda_functions["{spec.function_name}"] = picofun.lambda_functions["{spec.function_name}"]
                """)
                + "\n"
            )

        return "".join(parts)

    @staticmethod
    def _wf_state_machine(
        iam_policy: dict[str, Any],
        stack_prefix: str,
    ) -> str:
        """Return state machine and IAM role constructs."""
        policy_json = json.dumps(iam_policy, indent=8)

        role_block = _body(f"""\
            # --- IAM Execution Role ---
            execution_role = iam.Role(
                self,
                "ExecutionRole",
                assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
                description="Execution role for {stack_prefix} state machine",
            )

        """)

        policy_line = f"{_BODY}policy_doc = {policy_json}\n\n"

        rest = (
            _body(f"""\
            execution_role.attach_inline_policy(
                iam.Policy(
                    self,
                    "ExecutionPolicy",
                    document=iam.PolicyDocument.from_json(policy_doc),
                ),
            )

            # --- State Machine ---
            definition_path = str(Path(__file__).parent.parent.parent / "statemachine" / "definition.asl.json")
            cfn_state_machine = sfn.CfnStateMachine(
                self,
                "StateMachine",
                state_machine_name="{stack_prefix}",
                definition_string=Path(definition_path).read_text(),
                role_arn=execution_role.role_arn,
                logging_configuration=sfn.CfnStateMachine.LoggingConfigurationProperty(
                    level="ALL",
                    include_execution_data=True,
                    destinations=[
                        sfn.CfnStateMachine.LogDestinationProperty(
                            cloud_watch_logs_log_group=sfn.CfnStateMachine.CloudWatchLogsLogGroupProperty(
                                log_group_arn=shared_stack.log_group.log_group_arn,
                            ),
                        ),
                    ],
                ),
                tracing_configuration=sfn.CfnStateMachine.TracingConfigurationProperty(
                    enabled=True,
                ),
            )
            state_machine = sfn.StateMachine.from_state_machine_arn(
                self, "StateMachineRef", cfn_state_machine.attr_arn,
            )

            # Route failed/timed-out/aborted executions to the DLQ
            events.Rule(
                self,
                "FailedExecutionDlqRule",
                event_pattern=events.EventPattern(
                    source=["aws.states"],
                    detail_type=["Step Functions Execution Status Change"],
                    detail={{
                        "status": ["FAILED", "TIMED_OUT", "ABORTED"],
                        "stateMachineArn": [cfn_state_machine.attr_arn],
                    }},
                ),
                targets=[targets.SqsQueue(dlq)],
            )
        """)
            + "\n"
        )

        return role_block + policy_line + rest

    @staticmethod
    def _wf_alarms() -> str:
        """Return CloudWatch alarm constructs for the state machine."""
        parts = [_BODY + "# --- CloudWatch Alarms ---\n"]
        for metric_method, alarm_id in [
            ("metric_failed", "FailedAlarm"),
            ("metric_timed_out", "TimedOutAlarm"),
            ("metric_throttled", "ThrottledAlarm"),
        ]:
            parts.append(
                _body(f"""\
                cloudwatch.Alarm(
                    self,
                    "{alarm_id}",
                    metric=state_machine.{metric_method}(),
                    threshold=1,
                    evaluation_periods=1,
                )
            """)
                + "\n"
            )
        return "".join(parts)

    @staticmethod
    def _wf_triggers(input_data: PackagerInput) -> str:
        """Return EventBridge schedule trigger constructs."""
        schedule_triggers = [
            t for t in input_data.triggers if t.trigger_type == TriggerType.SCHEDULE
        ]
        if not schedule_triggers:
            return ""

        parts = [_BODY + "# --- Schedule Triggers ---\n"]
        for i, trigger in enumerate(schedule_triggers):
            expr = trigger.configuration.get("schedule_expression", "rate(1 hour)")
            parts.append(
                _body(f"""\
                events.Rule(
                    self,
                    "ScheduleRule{i}",
                    schedule=events.Schedule.expression("{expr}"),
                    targets=[targets.SfnStateMachine(state_machine)],
                )
            """)
                + "\n"
            )
        return "".join(parts)

    @staticmethod
    def _wf_custom_domain(input_data: PackagerInput) -> str:
        """Return optional CloudFront + Route 53 constructs for custom domains."""
        webhook_fns = [
            s
            for s in input_data.lambda_functions
            if s.function_type
            in (
                LambdaFunctionType.WEBHOOK_HANDLER,
                LambdaFunctionType.CALLBACK_HANDLER,
            )
        ]
        if not webhook_fns:
            return ""

        parts: list[str] = [
            _body("""\
            # --- Custom Domain (opt-in via CDK context) ---
            custom_domain = self.node.try_get_context("custom_domain")
            if custom_domain:
                cert_arn = self.node.try_get_context("certificate_arn")
                hosted_zone_id = self.node.try_get_context("hosted_zone_id")
                zone = route53.HostedZone.from_hosted_zone_attributes(
                    self, "HostedZone",
                    hosted_zone_id=hosted_zone_id,
                    zone_name=".".join(custom_domain.split(".")[-2:]),
                )
        """)
        ]

        _if_body = "            "  # 12 spaces: inside 'if custom_domain:'
        for spec in webhook_fns:
            construct_suffix = (
                spec.function_name.replace("_", " ").title().replace(" ", "")
            )
            parts.append(
                textwrap.indent(
                    textwrap.dedent(f"""\

                url_domain_{spec.function_name} = cdk.Fn.select(
                    2, cdk.Fn.split("/", fn_url_{spec.function_name}.url),
                )
                distribution_{spec.function_name} = cloudfront.Distribution(
                    self, "WebhookCDN{construct_suffix}",
                    default_behavior=cloudfront.BehaviorOptions(
                        origin=origins.HttpOrigin(url_domain_{spec.function_name}),
                    ),
                    domain_names=[custom_domain],
                    certificate=acm.Certificate.from_certificate_arn(
                        self, "Cert{construct_suffix}", cert_arn,
                    ),
                )
                route53.ARecord(
                    self, "WebhookAlias{construct_suffix}",
                    zone=zone,
                    target=route53.RecordTarget.from_alias(
                        route53_targets.CloudFrontTarget(distribution_{spec.function_name}),
                    ),
                )
            """),
                    _if_body,
                )
            )

        parts.append("\n")
        return "".join(parts)

    @staticmethod
    def _wf_oauth_rotation(input_data: PackagerInput) -> str:
        """Return OAuth token rotation constructs."""
        if not input_data.oauth_credentials:
            return ""

        parts = [_BODY + "# --- OAuth Token Rotation ---\n"]
        for i, oauth in enumerate(input_data.oauth_credentials):
            cred_name = oauth.credential_spec.parameter_path.strip("/").split("/")[-1]
            schedule_expr = oauth.refresh_schedule_expression
            param_path = oauth.credential_spec.parameter_path
            token_url = oauth.token_endpoint_url
            var_name = f"oauth_refresh_{cred_name.replace('-', '_')}"
            construct_id = "OAuthRefresh" + cred_name.replace("_", " ").replace(
                "-", " "
            ).title().replace(" ", "")
            param_path_stripped = param_path.strip("/")

            parts.append(
                _body(f"""\
                # OAuth rotation for {cred_name}
                {var_name} = lambda_.Function(
                    self,
                    "{construct_id}Fn",
                    runtime=lambda_.Runtime.PYTHON_3_12,
                    handler="handler.handler",
                    code=lambda_.Code.from_asset(
                        str(Path(__file__).parent.parent.parent / "lambdas" / "{var_name}"),
                        bundling=cdk.BundlingOptions(
                            image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                            command=["bash", "-c", "pip install --no-cache-dir -r /asset-input/requirements.txt -t /asset-output && cp /asset-input/*.py /asset-output/"],
                        ),
                    ),
                    environment={{
                        "SSM_PARAMETER_PATH": "{param_path}",
                        "TOKEN_ENDPOINT_URL": "{token_url}",
                    }},
                    tracing=lambda_.Tracing.ACTIVE,
                    dead_letter_queue=dlq,
                )
                {var_name}.add_to_role_policy(
                    iam.PolicyStatement(
                        actions=["ssm:GetParameter", "ssm:PutParameter"],
                        resources=["arn:aws:ssm:*:*:parameter/{param_path_stripped}/*"],
                    )
                )

                events.Rule(
                    self,
                    "OAuthRotation{i}",
                    schedule=events.Schedule.expression("{schedule_expr}"),
                    targets=[targets.LambdaFunction({var_name})],
                )
            """)
                + "\n"
            )
        return "".join(parts)

    @staticmethod
    def _wf_sub_workflow_params(input_data: PackagerInput) -> str:
        """Return CfnParameter constructs for sub-workflow ARNs."""
        if not input_data.sub_workflows:
            return ""

        parts = [_BODY + "# --- Sub-workflow ARN Parameters ---\n"]
        for sw in input_data.sub_workflows:
            param_id = sw.name.replace("-", "_").replace(" ", "_")
            parts.append(
                _body(f"""\
                cdk.CfnParameter(
                    self,
                    "SubWorkflowArn{param_id}",
                    description="ARN of the {sw.name} sub-workflow",
                    default="<{sw.name}-arn>",
                )
            """)
                + "\n"
            )
        return "".join(parts)
