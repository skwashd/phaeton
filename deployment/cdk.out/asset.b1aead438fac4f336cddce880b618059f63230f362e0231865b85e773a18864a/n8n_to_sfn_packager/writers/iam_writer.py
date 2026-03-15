"""
IAM policy generator.

Analyses an ASL definition and Lambda function list to produce a
least-privilege IAM policy for the Step Functions execution role.
"""

from __future__ import annotations

from typing import Any

from n8n_to_sfn_packager.models.inputs import LambdaFunctionSpec
from n8n_to_sfn_packager.models.ssm import SSMParameterDefinition


def sdk_action_to_iam(service: str, action: str) -> str:
    """
    Convert an ASL SDK integration pattern to the IAM action string.

    The ASL resource ``arn:aws:states:::aws-sdk:SERVICE:ACTION`` maps to
    ``service:Action`` in IAM, where the service is lowercased and the
    action is PascalCase.

    Args:
        service: The AWS service name from the ASL resource (e.g. ``DynamoDB``).
        action: The API action from the ASL resource (e.g. ``PutItem``).

    Returns:
        The IAM action string (e.g. ``dynamodb:PutItem``).

    """
    return f"{service.lower()}:{action}"


class IAMPolicyGenerator:
    """Generate least-privilege IAM policies from ASL definitions."""

    def generate(
        self,
        asl_definition: dict[str, Any],
        lambda_specs: list[LambdaFunctionSpec],
        ssm_parameters: list[SSMParameterDefinition],
        kms_key_ref: str,
        log_group_ref: str,
        sub_workflow_arns: list[str],
    ) -> dict[str, Any]:
        """
        Generate an IAM policy document with minimum required permissions.

        Args:
            asl_definition: The ASL state-machine definition dict.
            lambda_specs: Lambda function specifications.
            ssm_parameters: SSM parameter definitions.
            kms_key_ref: CDK reference to the KMS key ARN.
            log_group_ref: CDK reference to the log group ARN.
            sub_workflow_arns: ARNs of sub-workflows.

        Returns:
            An IAM policy document dict.

        """
        statements: list[dict[str, Any]] = []

        # Walk the ASL to discover resources
        resources = self._walk_asl(asl_definition)

        # Lambda invocations
        lambda_arns = self._collect_lambda_arns(resources, lambda_specs)
        if lambda_arns:
            statements.append(
                self._make_statement(
                    actions=["lambda:InvokeFunction"],
                    resources=sorted(lambda_arns),
                ),
            )

        # SDK integrations
        sdk_actions = self._collect_sdk_actions(resources)
        for action, resource_arns in sorted(sdk_actions.items()):
            statements.append(
                self._make_statement(
                    actions=[action],
                    resources=sorted(resource_arns),
                ),
            )

        # Sub-workflow execution
        if sub_workflow_arns:
            statements.append(
                self._make_statement(
                    actions=["states:StartExecution", "states:DescribeExecution"],
                    resources=sorted(sub_workflow_arns),
                ),
            )

        # SSM GetParameter
        if ssm_parameters:
            ssm_arns = [
                f"arn:aws:ssm:*:*:parameter{p.parameter_path}" for p in ssm_parameters
            ]
            statements.append(
                self._make_statement(
                    actions=["ssm:GetParameter", "ssm:GetParametersByPath"],
                    resources=sorted(ssm_arns),
                ),
            )

        # KMS Decrypt
        statements.append(
            self._make_statement(
                actions=["kms:Decrypt"],
                resources=[kms_key_ref],
            ),
        )

        # CloudWatch Logs
        statements.append(
            self._make_statement(
                actions=[
                    "logs:CreateLogDelivery",
                    "logs:GetLogDelivery",
                    "logs:UpdateLogDelivery",
                    "logs:PutLogEvents",
                    "logs:DeleteLogDelivery",
                    "logs:ListLogDeliveries",
                    "logs:PutResourcePolicy",
                    "logs:DescribeResourcePolicies",
                    "logs:DescribeLogGroups",
                ],
                resources=[log_group_ref],
            ),
        )

        # X-Ray tracing
        statements.append(
            self._make_statement(
                actions=["xray:PutTraceSegments", "xray:PutTelemetryRecords"],
                resources=["*"],
            ),
        )

        return {
            "Version": "2012-10-17",
            "Statement": statements,
        }

    def _walk_asl(self, asl: dict[str, Any]) -> list[str]:
        """
        Recursively walk the ASL definition to find all Task Resource values.

        Descends into States, ItemProcessor, Branches, and Iterator.

        Args:
            asl: ASL definition or sub-definition.

        Returns:
            List of Resource ARN strings found in Task states.

        """
        resources: list[str] = []
        states = asl.get("States", {})

        for state in states.values():
            state_type = state.get("Type", "")

            if state_type == "Task":
                resource = state.get("Resource", "")
                if isinstance(resource, str) and resource:
                    resources.append(resource)

            # Recurse into Map's ItemProcessor or Iterator
            if state_type == "Map":
                for key in ("ItemProcessor", "Iterator"):
                    sub = state.get(key)
                    if isinstance(sub, dict):
                        resources.extend(self._walk_asl(sub))

            # Recurse into Parallel's Branches
            if state_type == "Parallel":
                for branch in state.get("Branches", []):
                    if isinstance(branch, dict):
                        resources.extend(self._walk_asl(branch))

        return resources

    @staticmethod
    def _collect_lambda_arns(
        resources: list[str],
        lambda_specs: list[LambdaFunctionSpec],
    ) -> set[str]:
        """Collect Lambda function ARN patterns from discovered resources."""
        arns: set[str] = set()
        for res in resources:
            if "lambda:invoke" in res.lower():
                # Add ARN patterns for all Lambda functions
                for spec in lambda_specs:
                    arns.add(
                        f"arn:aws:lambda:*:*:function:{spec.function_name}",
                    )
        return arns

    @staticmethod
    def _collect_sdk_actions(resources: list[str]) -> dict[str, set[str]]:
        """Collect SDK integration actions and their resource ARNs."""
        actions: dict[str, set[str]] = {}
        for res in resources:
            if "aws-sdk:" in res:
                # Parse: arn:aws:states:::aws-sdk:SERVICE:ACTION
                parts = res.split(":")
                # Find the aws-sdk part
                try:
                    sdk_idx = parts.index("aws-sdk")
                    service = parts[sdk_idx + 1]
                    action = parts[sdk_idx + 2] if len(parts) > sdk_idx + 2 else ""
                except (ValueError, IndexError):
                    continue

                iam_action = sdk_action_to_iam(service, action)
                resource_arn = f"arn:aws:{service.lower()}:::*"
                if iam_action not in actions:
                    actions[iam_action] = set()
                actions[iam_action].add(resource_arn)
        return actions

    @staticmethod
    def _make_statement(
        actions: list[str],
        resources: list[str],
    ) -> dict[str, Any]:
        """Create an IAM policy statement."""
        return {
            "Effect": "Allow",
            "Action": actions,
            "Resource": resources,
        }
