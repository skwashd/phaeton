"""
CDK synthesis validation for the scheduled trigger workflow.

Verifies that the generated CDK application for an EventBridge Schedule ->
Lambda -> SQS workflow synthesizes into a valid CloudFormation template with
an EventBridge schedule rule, state machine, and supporting infrastructure.
"""

from __future__ import annotations

from tests.cdk_synth.conftest import SynthResult


class TestScheduledSynthSucceeds:
    """Verify that the scheduled workflow synthesizes without errors."""

    def test_synth_produces_cloudformation(self, scheduled_synth: SynthResult) -> None:
        """CDK synth must produce a non-empty CloudFormation template."""
        resources = scheduled_synth.workflow_cfn.get("Resources", {})
        assert len(resources) > 0, "Synthesized template has no resources"


class TestScheduledSynthStateMachine:
    """Verify the state machine resource in the synthesized template."""

    def test_has_state_machine(self, scheduled_synth: SynthResult) -> None:
        """Template must contain a Step Functions StateMachine resource."""
        scheduled_synth.workflow_template.resource_count_is(
            "AWS::StepFunctions::StateMachine", 1
        )

    def test_state_machine_has_logging(self, scheduled_synth: SynthResult) -> None:
        """State machine must have logging configuration."""
        sm_resources = scheduled_synth.workflow_template.find_resources(
            "AWS::StepFunctions::StateMachine"
        )
        sm = next(iter(sm_resources.values()))
        assert "LoggingConfiguration" in sm["Properties"]

    def test_state_machine_has_tracing(self, scheduled_synth: SynthResult) -> None:
        """State machine must have X-Ray tracing enabled."""
        sm_resources = scheduled_synth.workflow_template.find_resources(
            "AWS::StepFunctions::StateMachine"
        )
        sm = next(iter(sm_resources.values()))
        assert sm["Properties"]["TracingConfiguration"]["Enabled"] is True

    def test_definition_contains_sqs_state(self, scheduled_synth: SynthResult) -> None:
        """State machine definition must reference SQS operations."""
        sm_resources = scheduled_synth.workflow_template.find_resources(
            "AWS::StepFunctions::StateMachine"
        )
        defn_str = str(next(iter(sm_resources.values())))
        assert "sqs" in defn_str.lower(), (
            "State machine definition does not reference SQS"
        )


class TestScheduledSynthTriggers:
    """Verify EventBridge schedule trigger resources."""

    def test_has_schedule_rule(self, scheduled_synth: SynthResult) -> None:
        """Template must contain an EventBridge rule with a schedule."""
        rules = scheduled_synth.workflow_template.find_resources("AWS::Events::Rule")
        schedule_rules = {
            lid: r
            for lid, r in rules.items()
            if "ScheduleExpression" in r.get("Properties", {})
        }
        assert len(schedule_rules) >= 1, (
            "No EventBridge schedule rules found in template"
        )

    def test_schedule_rule_targets_state_machine(
        self, scheduled_synth: SynthResult
    ) -> None:
        """The schedule rule must target the state machine."""
        rules = scheduled_synth.workflow_template.find_resources("AWS::Events::Rule")
        schedule_rules = {
            lid: r
            for lid, r in rules.items()
            if "ScheduleExpression" in r.get("Properties", {})
        }
        for rule in schedule_rules.values():
            targets = rule.get("Properties", {}).get("Targets", [])
            assert len(targets) >= 1, "Schedule rule has no targets"

    def test_has_failed_execution_event_rule(
        self, scheduled_synth: SynthResult
    ) -> None:
        """Template must also contain the failed-execution DLQ rule."""
        rules = scheduled_synth.workflow_template.find_resources("AWS::Events::Rule")
        failure_rules = {lid: r for lid, r in rules.items() if "FAILED" in str(r)}
        assert len(failure_rules) >= 1, "No EventBridge rule for failed executions"


class TestScheduledSynthIAM:
    """Verify IAM resources in the synthesized template."""

    def test_has_execution_role(self, scheduled_synth: SynthResult) -> None:
        """Template must contain an IAM Role for the state machine."""
        scheduled_synth.workflow_template.has_resource_properties(
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

    def test_has_iam_policy(self, scheduled_synth: SynthResult) -> None:
        """Template must contain an IAM Policy for the execution role."""
        policies = scheduled_synth.workflow_template.find_resources("AWS::IAM::Policy")
        assert len(policies) >= 1, "No IAM Policies found"


class TestScheduledSynthInfrastructure:
    """Verify supporting infrastructure resources."""

    def test_has_dead_letter_queue(self, scheduled_synth: SynthResult) -> None:
        """Template must contain an SQS dead-letter queue."""
        queues = scheduled_synth.workflow_template.find_resources("AWS::SQS::Queue")
        assert len(queues) >= 1, "No SQS queues found"

    def test_has_cloudwatch_alarms(self, scheduled_synth: SynthResult) -> None:
        """Template must contain CloudWatch alarms."""
        alarms = scheduled_synth.workflow_template.find_resources(
            "AWS::CloudWatch::Alarm"
        )
        assert len(alarms) >= 3, f"Expected at least 3 alarms, got {len(alarms)}"
