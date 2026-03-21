"""
CDK synthesis validation for the simple DynamoDB workflow.

Verifies that the generated CDK application for a Trigger -> DynamoDB ->
Response workflow synthesizes into a valid CloudFormation template with the
expected resources: state machine, IAM role, DLQ, and CloudWatch alarms.
"""

from __future__ import annotations

from tests.cdk_synth.conftest import SynthResult


class TestSimpleSynthSucceeds:
    """Verify that the simple DynamoDB workflow synthesizes without errors."""

    def test_synth_produces_cloudformation(
        self, simple_dynamodb_synth: SynthResult
    ) -> None:
        """CDK synth must produce a non-empty CloudFormation template."""
        resources = simple_dynamodb_synth.workflow_cfn.get("Resources", {})
        assert len(resources) > 0, "Synthesized template has no resources"

    def test_shared_stack_synth_produces_cloudformation(
        self, simple_dynamodb_synth: SynthResult
    ) -> None:
        """Shared stack must synthesize with KMS and log group resources."""
        resources = simple_dynamodb_synth.shared_cfn.get("Resources", {})
        assert len(resources) > 0, "Shared stack template has no resources"


class TestSimpleSynthStateMachine:
    """Verify the state machine resource in the synthesized template."""

    def test_has_state_machine(self, simple_dynamodb_synth: SynthResult) -> None:
        """Template must contain a Step Functions StateMachine resource."""
        simple_dynamodb_synth.workflow_template.resource_count_is(
            "AWS::StepFunctions::StateMachine", 1
        )

    def test_state_machine_has_name(self, simple_dynamodb_synth: SynthResult) -> None:
        """State machine must have a StateMachineName property."""
        simple_dynamodb_synth.workflow_template.has_resource_properties(
            "AWS::StepFunctions::StateMachine",
            {"StateMachineName": "simple-dynamodb-e2e"},
        )

    def test_state_machine_has_logging(
        self, simple_dynamodb_synth: SynthResult
    ) -> None:
        """State machine must have logging configuration enabled."""
        sm_resources = simple_dynamodb_synth.workflow_template.find_resources(
            "AWS::StepFunctions::StateMachine"
        )
        assert len(sm_resources) == 1
        sm = next(iter(sm_resources.values()))
        props = sm["Properties"]
        assert "LoggingConfiguration" in props
        assert props["LoggingConfiguration"]["Level"] == "ALL"

    def test_state_machine_has_tracing(
        self, simple_dynamodb_synth: SynthResult
    ) -> None:
        """State machine must have X-Ray tracing enabled."""
        sm_resources = simple_dynamodb_synth.workflow_template.find_resources(
            "AWS::StepFunctions::StateMachine"
        )
        sm = next(iter(sm_resources.values()))
        tracing = sm["Properties"]["TracingConfiguration"]
        assert tracing["Enabled"] is True

    def test_definition_contains_dynamodb_states(
        self, simple_dynamodb_synth: SynthResult
    ) -> None:
        """State machine definition must reference DynamoDB operations."""
        sm_resources = simple_dynamodb_synth.workflow_template.find_resources(
            "AWS::StepFunctions::StateMachine"
        )
        defn_str = str(next(iter(sm_resources.values())))
        assert "dynamodb" in defn_str.lower(), (
            "State machine definition does not reference DynamoDB"
        )


class TestSimpleSynthIAM:
    """Verify IAM resources in the synthesized template."""

    def test_has_execution_role(self, simple_dynamodb_synth: SynthResult) -> None:
        """Template must contain an IAM Role for the state machine."""
        roles = simple_dynamodb_synth.workflow_template.find_resources("AWS::IAM::Role")
        assert len(roles) >= 1, "No IAM Roles found"

    def test_execution_role_assumed_by_states(
        self, simple_dynamodb_synth: SynthResult
    ) -> None:
        """Execution role must be assumable by states.amazonaws.com."""
        simple_dynamodb_synth.workflow_template.has_resource_properties(
            "AWS::IAM::Role",
            {
                "AssumeRolePolicyDocument": {
                    "Statement": [
                        {
                            "Action": "sts:AssumeRole",
                            "Effect": "Allow",
                            "Principal": {"Service": "states.amazonaws.com"},
                        }
                    ],
                },
            },
        )

    def test_has_execution_policy(self, simple_dynamodb_synth: SynthResult) -> None:
        """Template must contain an IAM Policy with DynamoDB permissions."""
        policies = simple_dynamodb_synth.workflow_template.find_resources(
            "AWS::IAM::Policy"
        )
        assert len(policies) >= 1, "No IAM Policies found"
        policy_str = str(next(iter(policies.values())))
        assert "dynamodb" in policy_str.lower(), (
            "IAM policy does not reference DynamoDB"
        )


class TestSimpleSynthInfrastructure:
    """Verify supporting infrastructure resources."""

    def test_has_dead_letter_queue(self, simple_dynamodb_synth: SynthResult) -> None:
        """Template must contain an SQS dead-letter queue."""
        simple_dynamodb_synth.workflow_template.has_resource_properties(
            "AWS::SQS::Queue",
            {"QueueName": "simple-dynamodb-e2e-dlq"},
        )

    def test_has_cloudwatch_alarms(self, simple_dynamodb_synth: SynthResult) -> None:
        """Template must contain CloudWatch alarms for the state machine."""
        alarms = simple_dynamodb_synth.workflow_template.find_resources(
            "AWS::CloudWatch::Alarm"
        )
        assert len(alarms) >= 3, (
            f"Expected at least 3 alarms (failed, timed_out, throttled), "
            f"got {len(alarms)}"
        )

    def test_has_failed_execution_event_rule(
        self, simple_dynamodb_synth: SynthResult
    ) -> None:
        """Template must contain an EventBridge rule for failed executions."""
        rules = simple_dynamodb_synth.workflow_template.find_resources(
            "AWS::Events::Rule"
        )
        assert len(rules) >= 1, "No EventBridge rules found"
        rule_str = str(next(iter(rules.values())))
        assert "FAILED" in rule_str, "No EventBridge rule for failed executions"


class TestSimpleSynthSharedStack:
    """Verify the shared stack contains expected resources."""

    def test_has_kms_key(self, simple_dynamodb_synth: SynthResult) -> None:
        """Shared stack must contain a KMS key with rotation enabled."""
        simple_dynamodb_synth.shared_template.has_resource_properties(
            "AWS::KMS::Key",
            {"EnableKeyRotation": True},
        )

    def test_has_log_group(self, simple_dynamodb_synth: SynthResult) -> None:
        """Shared stack must contain a CloudWatch log group."""
        simple_dynamodb_synth.shared_template.resource_count_is(
            "AWS::Logs::LogGroup", 1
        )
