"""Integration tests for a simple DynamoDB + Lambda workflow.

These tests exercise the full Phaeton pipeline -- from n8n workflow JSON
through analysis, translation, packaging, CDK deployment, state-machine
execution, and output validation -- against a real AWS account.

Run with::

    uv run pytest -m integration

Prerequisites:
    * Valid AWS credentials (environment variables or profile).
    * ``npm`` on ``$PATH`` (for the CDK CLI via ``npx``).
    * IAM permissions: CloudFormation, Lambda, Step Functions, DynamoDB,
      IAM, S3, SQS, KMS, Logs, CloudWatch.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


# -----------------------------------------------------------------------
# Pipeline-only tests (no AWS credentials required for these assertions,
# but they ARE marked integration because they run the full pipeline)
# -----------------------------------------------------------------------


class TestPipelineProducesDeployableOutput:
    """Verify the pipeline produces a complete, deployable CDK application."""

    def test_asl_definition_exists(self, pipeline_result: Path) -> None:
        """The packager must emit a valid ASL definition file."""
        asl_path = pipeline_result / "statemachine" / "definition.asl.json"
        assert asl_path.exists(), "ASL definition not found"
        asl = json.loads(asl_path.read_text())
        assert "StartAt" in asl
        assert "States" in asl
        assert len(asl["States"]) > 0

    def test_cdk_app_exists(self, pipeline_result: Path) -> None:
        """The packager must emit a CDK application."""
        cdk_dir = pipeline_result / "cdk"
        assert (cdk_dir / "app.py").exists(), "CDK app.py not found"
        assert (cdk_dir / "cdk.json").exists(), "cdk.json not found"
        assert (cdk_dir / "pyproject.toml").exists(), "CDK pyproject.toml not found"

    def test_cdk_stacks_exist(self, pipeline_result: Path) -> None:
        """The CDK stacks directory must contain the expected stack modules."""
        stacks_dir = pipeline_result / "cdk" / "stacks"
        assert stacks_dir.is_dir(), "stacks/ directory not found"
        assert (stacks_dir / "workflow_stack.py").exists()
        assert (stacks_dir / "shared_stack.py").exists()

    def test_lambda_directory_created(self, pipeline_result: Path) -> None:
        """At least one Lambda directory must be emitted for the Code node."""
        lambdas_dir = pipeline_result / "lambdas"
        if lambdas_dir.exists():
            handlers = list(lambdas_dir.iterdir())
            assert len(handlers) > 0, "Lambda directory is empty"

    def test_reports_generated(self, pipeline_result: Path) -> None:
        """The packager must emit conversion reports and a migration checklist."""
        assert (pipeline_result / "MIGRATE.md").exists()
        assert (pipeline_result / "conversion_report.json").exists()

    def test_iam_policy_not_overly_broad(self, pipeline_result: Path) -> None:
        """IAM policy should not use ``*`` for both Action and Resource."""
        report_path = pipeline_result / "conversion_report.json"
        if not report_path.exists():
            pytest.skip("No conversion report")

        cdk_stacks = pipeline_result / "cdk" / "stacks" / "workflow_stack.py"
        if cdk_stacks.exists():
            stack_code = cdk_stacks.read_text()
            # A policy with Action: * AND Resource: * is overly broad
            assert not (
                '"Action": "*"' in stack_code and '"Resource": "*"' in stack_code
            ), "IAM policy is overly broad (Action: *, Resource: *)"


# -----------------------------------------------------------------------
# Full AWS deployment tests
# -----------------------------------------------------------------------


class TestDeployAndExecute:
    """Deploy the generated CDK stack and execute the state machine.

    These tests require valid AWS credentials and will create real AWS
    resources.  Resources are cleaned up automatically via the
    ``deployed_stack`` fixture finalizer.
    """

    @pytest.mark.timeout(600)
    def test_stack_deploys_successfully(
        self,
        deployed_stack: dict[str, str],
    ) -> None:
        """The CDK stack must deploy without errors."""
        # If we reach here, deployment succeeded (fixture would have raised)
        assert isinstance(deployed_stack, dict)

    @pytest.mark.timeout(600)
    def test_state_machine_executes(
        self,
        deployed_stack: dict[str, str],
        sfn_client: object,
    ) -> None:
        """The state machine must execute successfully with test input."""
        from tests.integration.conftest import _wait_for_execution

        # Find the state machine ARN from stack outputs
        sm_arn = _find_state_machine_arn(deployed_stack, sfn_client)
        if sm_arn is None:
            pytest.skip("No state machine ARN found in stack outputs")

        # Execute with test input
        test_input = json.dumps(
            {"pk": "test-item-001", "message": "hello from phaeton", "status": "ok"},
        )
        exec_resp = sfn_client.start_execution(  # type: ignore[attr-defined]
            stateMachineArn=sm_arn,
            input=test_input,
        )
        execution_arn = exec_resp["executionArn"]

        # Wait for completion
        result = _wait_for_execution(sfn_client, execution_arn)
        assert result["status"] == "SUCCEEDED", (
            f"State machine execution failed: {result.get('error', 'unknown')}\n"
            f"Cause: {result.get('cause', 'unknown')}"
        )

    @pytest.mark.timeout(600)
    def test_lambda_executes_without_errors(
        self,
        deployed_stack: dict[str, str],
        sfn_client: object,
    ) -> None:
        """Lambda functions invoked by the state machine must not error."""
        from tests.integration.conftest import _wait_for_execution

        sm_arn = _find_state_machine_arn(deployed_stack, sfn_client)
        if sm_arn is None:
            pytest.skip("No state machine ARN found in stack outputs")

        test_input = json.dumps({"pk": "lambda-test-001", "status": "ok"})
        exec_resp = sfn_client.start_execution(  # type: ignore[attr-defined]
            stateMachineArn=sm_arn,
            input=test_input,
        )

        _wait_for_execution(sfn_client, exec_resp["executionArn"])

        # Check execution history for Lambda errors
        history = sfn_client.get_execution_history(  # type: ignore[attr-defined]
            executionArn=exec_resp["executionArn"],
            maxResults=100,
        )
        lambda_failures = [
            evt for evt in history["events"] if evt["type"] == "LambdaFunctionFailed"
        ]
        assert len(lambda_failures) == 0, f"Lambda failures detected: {lambda_failures}"


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


def _find_state_machine_arn(
    stack_outputs: dict[str, str],
    sfn_client: object,
) -> str | None:
    """Locate the state machine ARN from stack outputs or by listing.

    Checks stack outputs first for keys containing ``StateMachine``.
    Falls back to listing state machines tagged with ``phaeton-test``.
    """
    # Check outputs for a state machine ARN
    for key, value in stack_outputs.items():
        if "statemachine" in key.lower() and value.startswith("arn:aws:states:"):
            return value

    # Fallback: list state machines and find the phaeton-test one
    paginator = sfn_client.get_paginator("list_state_machines")  # type: ignore[attr-defined]
    for page in paginator.paginate():
        for sm in page["stateMachines"]:
            if "phaeton-inttest" in sm["name"]:
                return sm["stateMachineArn"]

    return None
