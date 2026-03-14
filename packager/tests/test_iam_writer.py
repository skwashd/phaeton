"""Tests for the IAM policy generator."""

from __future__ import annotations

from n8n_to_sfn_packager.models.inputs import (
    LambdaFunctionSpec,
    LambdaFunctionType,
    LambdaRuntime,
)
from n8n_to_sfn_packager.models.ssm import SSMParameterDefinition
from n8n_to_sfn_packager.writers.iam_writer import IAMPolicyGenerator, sdk_action_to_iam


def _make_lambda_spec(name: str = "my_func") -> LambdaFunctionSpec:
    return LambdaFunctionSpec(
        function_name=name,
        runtime=LambdaRuntime.PYTHON,
        handler_code="def handler(event, context): pass",
        function_type=LambdaFunctionType.PICOFUN_API_CLIENT,
    )


def _make_ssm_param(path: str = "/wf/creds/token") -> SSMParameterDefinition:
    return SSMParameterDefinition(parameter_path=path)


class TestSdkActionToIam:
    """Tests for SDK action to IAM mapping."""

    def test_dynamodb(self) -> None:
        """Test DynamoDB action mapping."""
        assert sdk_action_to_iam("DynamoDB", "PutItem") == "dynamodb:PutItem"

    def test_s3(self) -> None:
        """Test S3 action mapping."""
        assert sdk_action_to_iam("S3", "PutObject") == "s3:PutObject"

    def test_sqs(self) -> None:
        """Test SQS action mapping."""
        assert sdk_action_to_iam("SQS", "SendMessage") == "sqs:SendMessage"


class TestLambdaInvoke:
    """Tests for Lambda invoke IAM permissions."""

    def test_single_lambda(self) -> None:
        """Test IAM policy generation for a single Lambda invocation."""
        gen = IAMPolicyGenerator()
        asl = {
            "StartAt": "Invoke",
            "States": {
                "Invoke": {
                    "Type": "Task",
                    "Resource": "arn:aws:states:::lambda:invoke",
                    "End": True,
                },
            },
        }
        policy = gen.generate(
            asl,
            [_make_lambda_spec()],
            [],
            "kms-key",
            "log-group",
            [],
        )
        actions = [s["Action"] for s in policy["Statement"]]
        assert ["lambda:InvokeFunction"] in actions


class TestSdkIntegrations:
    """Tests for AWS SDK integration IAM permissions."""

    def test_s3_and_dynamodb(self) -> None:
        """Test IAM policy includes S3 and DynamoDB actions."""
        gen = IAMPolicyGenerator()
        asl = {
            "StartAt": "PutS3",
            "States": {
                "PutS3": {
                    "Type": "Task",
                    "Resource": "arn:aws:states:::aws-sdk:S3:PutObject",
                    "Next": "PutDDB",
                },
                "PutDDB": {
                    "Type": "Task",
                    "Resource": "arn:aws:states:::aws-sdk:DynamoDB:PutItem",
                    "End": True,
                },
            },
        }
        policy = gen.generate(asl, [], [], "kms-key", "log-group", [])
        all_actions = []
        for stmt in policy["Statement"]:
            all_actions.extend(stmt["Action"])

        assert "s3:PutObject" in all_actions
        assert "dynamodb:PutItem" in all_actions


class TestSubWorkflows:
    """Tests for sub-workflow IAM permissions."""

    def test_sub_workflow_arns(self) -> None:
        """Test that sub-workflow ARNs generate correct IAM permissions."""
        gen = IAMPolicyGenerator()
        asl = {"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}}
        sub_arns = ["arn:aws:states:us-east-1:123:stateMachine:sub-wf"]
        policy = gen.generate(asl, [], [], "kms-key", "log-group", sub_arns)

        sub_stmt = next(
            s for s in policy["Statement"] if "states:StartExecution" in s["Action"]
        )
        assert "states:DescribeExecution" in sub_stmt["Action"]
        assert sub_arns[0] in sub_stmt["Resource"]


class TestBasePermissions:
    """Tests for base IAM permissions always present."""

    def test_ssm_always_present_when_params_exist(self) -> None:
        """Test that SSM permissions are included when parameters exist."""
        gen = IAMPolicyGenerator()
        asl = {"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}}
        params = [_make_ssm_param()]
        policy = gen.generate(asl, [], params, "kms-key", "log-group", [])

        all_actions = []
        for stmt in policy["Statement"]:
            all_actions.extend(stmt["Action"])

        assert "ssm:GetParameter" in all_actions

    def test_kms_always_present(self) -> None:
        """Test that KMS permissions are always included."""
        gen = IAMPolicyGenerator()
        asl = {"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}}
        policy = gen.generate(asl, [], [], "kms-key", "log-group", [])

        all_actions = []
        for stmt in policy["Statement"]:
            all_actions.extend(stmt["Action"])
        assert "kms:Decrypt" in all_actions

    def test_cloudwatch_always_present(self) -> None:
        """Test that CloudWatch permissions are always included."""
        gen = IAMPolicyGenerator()
        asl = {"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}}
        policy = gen.generate(asl, [], [], "kms-key", "log-group", [])

        all_actions = []
        for stmt in policy["Statement"]:
            all_actions.extend(stmt["Action"])
        assert "logs:PutLogEvents" in all_actions

    def test_xray_always_present(self) -> None:
        """Test that X-Ray permissions are always included."""
        gen = IAMPolicyGenerator()
        asl = {"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}}
        policy = gen.generate(asl, [], [], "kms-key", "log-group", [])

        all_actions = []
        for stmt in policy["Statement"]:
            all_actions.extend(stmt["Action"])
        assert "xray:PutTraceSegments" in all_actions
        assert "xray:PutTelemetryRecords" in all_actions


class TestRecursiveWalking:
    """Tests for recursive ASL walking in IAM policy generation."""

    def test_map_state_item_processor(self) -> None:
        """Test that Map state item processors are walked for permissions."""
        gen = IAMPolicyGenerator()
        asl = {
            "StartAt": "BatchProcess",
            "States": {
                "BatchProcess": {
                    "Type": "Map",
                    "ItemProcessor": {
                        "StartAt": "ProcessItem",
                        "States": {
                            "ProcessItem": {
                                "Type": "Task",
                                "Resource": "arn:aws:states:::lambda:invoke",
                                "End": True,
                            },
                        },
                    },
                    "End": True,
                },
            },
        }
        policy = gen.generate(
            asl,
            [_make_lambda_spec()],
            [],
            "kms-key",
            "log-group",
            [],
        )
        all_actions = []
        for stmt in policy["Statement"]:
            all_actions.extend(stmt["Action"])
        assert "lambda:InvokeFunction" in all_actions

    def test_parallel_branches(self) -> None:
        """Test that Parallel state branches are walked for permissions."""
        gen = IAMPolicyGenerator()
        asl = {
            "StartAt": "ParallelStep",
            "States": {
                "ParallelStep": {
                    "Type": "Parallel",
                    "Branches": [
                        {
                            "StartAt": "BranchTask",
                            "States": {
                                "BranchTask": {
                                    "Type": "Task",
                                    "Resource": "arn:aws:states:::aws-sdk:S3:GetObject",
                                    "End": True,
                                },
                            },
                        },
                    ],
                    "End": True,
                },
            },
        }
        policy = gen.generate(asl, [], [], "kms-key", "log-group", [])
        all_actions = []
        for stmt in policy["Statement"]:
            all_actions.extend(stmt["Action"])
        assert "s3:GetObject" in all_actions


class TestNoDuplicates:
    """Tests for IAM policy deduplication."""

    def test_no_duplicate_statements(self) -> None:
        """Test that duplicate Lambda invocations produce a single IAM statement."""
        gen = IAMPolicyGenerator()
        asl = {
            "StartAt": "Step1",
            "States": {
                "Step1": {
                    "Type": "Task",
                    "Resource": "arn:aws:states:::lambda:invoke",
                    "Next": "Step2",
                },
                "Step2": {
                    "Type": "Task",
                    "Resource": "arn:aws:states:::lambda:invoke",
                    "End": True,
                },
            },
        }
        policy = gen.generate(
            asl,
            [_make_lambda_spec()],
            [],
            "kms-key",
            "log-group",
            [],
        )
        # Should only have one lambda:InvokeFunction statement despite two Task states
        lambda_stmts = [
            s for s in policy["Statement"] if "lambda:InvokeFunction" in s["Action"]
        ]
        assert len(lambda_stmts) == 1
