"""
CDK synthesis validation for the Code node (Lambda) workflow.

Verifies that the generated CDK application for a Trigger -> Code node ->
SNS workflow synthesizes into a valid CloudFormation template with Lambda
functions, IAM roles, a state machine, and supporting infrastructure.
"""

from __future__ import annotations

from tests.cdk_synth.conftest import SynthResult


class TestLambdaSynthSucceeds:
    """Verify that the Code node workflow synthesizes without errors."""

    def test_synth_produces_cloudformation(
        self, code_node_synth: SynthResult
    ) -> None:
        """CDK synth must produce a non-empty CloudFormation template."""
        resources = code_node_synth.workflow_cfn.get("Resources", {})
        assert len(resources) > 0, "Synthesized template has no resources"


class TestLambdaSynthLambdaFunctions:
    """Verify Lambda function resources in the synthesized template."""

    def test_has_lambda_functions(
        self, code_node_synth: SynthResult
    ) -> None:
        """Template must contain at least one Lambda function."""
        lambdas = code_node_synth.workflow_template.find_resources(
            "AWS::Lambda::Function"
        )
        assert len(lambdas) >= 1, "No Lambda functions found in template"

    def test_lambda_has_tracing(
        self, code_node_synth: SynthResult
    ) -> None:
        """Lambda functions must have X-Ray tracing enabled."""
        code_node_synth.workflow_template.has_resource_properties(
            "AWS::Lambda::Function",
            {"TracingConfig": {"Mode": "Active"}},
        )

    def test_lambda_has_dlq(
        self, code_node_synth: SynthResult
    ) -> None:
        """Lambda functions must have a dead-letter queue configured."""
        lambdas = code_node_synth.workflow_template.find_resources(
            "AWS::Lambda::Function"
        )
        for logical_id, resource in lambdas.items():
            props = resource.get("Properties", {})
            assert "DeadLetterConfig" in props, (
                f"Lambda {logical_id} missing DeadLetterConfig"
            )

    def test_lambda_has_iam_role(
        self, code_node_synth: SynthResult
    ) -> None:
        """Each Lambda function must reference an IAM execution role."""
        lambdas = code_node_synth.workflow_template.find_resources(
            "AWS::Lambda::Function"
        )
        for logical_id, resource in lambdas.items():
            props = resource.get("Properties", {})
            assert "Role" in props, (
                f"Lambda {logical_id} missing Role property"
            )


class TestLambdaSynthStateMachine:
    """Verify the state machine resource in the synthesized template."""

    def test_has_state_machine(
        self, code_node_synth: SynthResult
    ) -> None:
        """Template must contain a Step Functions StateMachine resource."""
        code_node_synth.workflow_template.resource_count_is(
            "AWS::StepFunctions::StateMachine", 1
        )

    def test_state_machine_definition_references_lambda(
        self, code_node_synth: SynthResult
    ) -> None:
        """State machine definition must reference Lambda invocations."""
        sm_resources = code_node_synth.workflow_template.find_resources(
            "AWS::StepFunctions::StateMachine"
        )
        defn_str = str(next(iter(sm_resources.values())))
        assert "lambda" in defn_str.lower(), (
            "State machine definition does not reference Lambda"
        )

    def test_state_machine_has_logging(
        self, code_node_synth: SynthResult
    ) -> None:
        """State machine must have logging configuration."""
        sm_resources = code_node_synth.workflow_template.find_resources(
            "AWS::StepFunctions::StateMachine"
        )
        sm = next(iter(sm_resources.values()))
        assert "LoggingConfiguration" in sm["Properties"]

    def test_state_machine_has_tracing(
        self, code_node_synth: SynthResult
    ) -> None:
        """State machine must have X-Ray tracing enabled."""
        sm_resources = code_node_synth.workflow_template.find_resources(
            "AWS::StepFunctions::StateMachine"
        )
        sm = next(iter(sm_resources.values()))
        assert sm["Properties"]["TracingConfiguration"]["Enabled"] is True


class TestLambdaSynthIAM:
    """Verify IAM resources in the synthesized template."""

    def test_has_state_machine_execution_role(
        self, code_node_synth: SynthResult
    ) -> None:
        """Template must contain an IAM Role assumed by states service."""
        code_node_synth.workflow_template.has_resource_properties(
            "AWS::IAM::Role",
            {
                "AssumeRolePolicyDocument": {
                    "Statement": [
                        {
                            "Action": "sts:AssumeRole",
                            "Effect": "Allow",
                            "Principal": {
                                "Service": "states.amazonaws.com"
                            },
                        }
                    ],
                },
            },
        )

    def test_has_lambda_execution_roles(
        self, code_node_synth: SynthResult
    ) -> None:
        """Template must contain IAM Roles for Lambda functions."""
        roles = code_node_synth.workflow_template.find_resources(
            "AWS::IAM::Role"
        )
        lambda_roles = [
            r
            for r in roles.values()
            if "lambda.amazonaws.com"
            in str(r.get("Properties", {}).get("AssumeRolePolicyDocument", {}))
        ]
        assert len(lambda_roles) >= 1, (
            "No IAM Roles for Lambda functions found"
        )


class TestLambdaSynthInfrastructure:
    """Verify supporting infrastructure resources."""

    def test_has_dead_letter_queue(
        self, code_node_synth: SynthResult
    ) -> None:
        """Template must contain an SQS dead-letter queue."""
        queues = code_node_synth.workflow_template.find_resources(
            "AWS::SQS::Queue"
        )
        assert len(queues) >= 1, "No SQS queues found"

    def test_has_cloudwatch_alarms(
        self, code_node_synth: SynthResult
    ) -> None:
        """Template must contain CloudWatch alarms."""
        alarms = code_node_synth.workflow_template.find_resources(
            "AWS::CloudWatch::Alarm"
        )
        assert len(alarms) >= 3, (
            f"Expected at least 3 alarms, got {len(alarms)}"
        )

    def test_has_failed_execution_event_rule(
        self, code_node_synth: SynthResult
    ) -> None:
        """Template must contain an EventBridge rule for failed executions."""
        rules = code_node_synth.workflow_template.find_resources(
            "AWS::Events::Rule"
        )
        rule_str = str(rules)
        assert "FAILED" in rule_str, (
            "No EventBridge rule for failed executions"
        )
