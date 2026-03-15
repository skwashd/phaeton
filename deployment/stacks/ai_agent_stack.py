"""CDK stack for the AI Agent service."""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct


class AiAgentStack(cdk.Stack):
    """Deploy the AI Agent Lambda."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:  # noqa: ANN003
        super().__init__(scope, construct_id, **kwargs)

        self.function = lambda_.Function(
            self,
            "Function",
            function_name="phaeton-ai-agent",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler="phaeton_ai_agent.handler.handler",
            code=lambda_.Code.from_asset("../ai-agent/src"),
            memory_size=1024,
            timeout=cdk.Duration.seconds(120),
        )

        self.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=["arn:aws:bedrock:*::foundation-model/*"],
            )
        )
