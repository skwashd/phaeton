"""CDK stack for the Expression Translator service."""

from __future__ import annotations

from typing import Any

import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct


class ExpressionTranslatorStack(cdk.Stack):
    """Deploy the Expression Translator Lambda."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init__(scope, construct_id, **kwargs)

        self.function = lambda_.Function(
            self,
            "Function",
            function_name="phaeton-expression-translator",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler="phaeton_expression_translator.handler.handler",
            code=lambda_.Code.from_asset(
                "../expression-translator/src",
                exclude=["*/cli.py", "*/__main__.py"],
            ),
            memory_size=1024,
            timeout=cdk.Duration.seconds(120),
        )

        self.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=["arn:aws:bedrock:*::foundation-model/*"],
            )
        )
