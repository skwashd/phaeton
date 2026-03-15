"""CDK stack for the Translation Engine service."""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_lambda as lambda_
from constructs import Construct


class TranslationEngineStack(cdk.Stack):
    """Deploy the Translation Engine Lambda."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        ai_agent_function: lambda_.IFunction | None = None,
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.function = lambda_.Function(
            self,
            "Function",
            function_name="phaeton-translation-engine",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler="n8n_to_sfn.handler.handler",
            code=lambda_.Code.from_asset("../n8n-to-sfn/src"),
            memory_size=512,
            timeout=cdk.Duration.seconds(300),
        )

        if ai_agent_function is not None:
            self.function.add_environment(
                "AI_AGENT_FUNCTION_NAME",
                ai_agent_function.function_name,
            )
            ai_agent_function.grant_invoke(self.function)
