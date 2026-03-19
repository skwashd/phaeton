"""CDK stack for the Translation Engine service."""

from __future__ import annotations

from typing import Any

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
        node_translator_function: lambda_.IFunction | None = None,
        expression_translator_function: lambda_.IFunction | None = None,
        **kwargs: Any,  # noqa: ANN401
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

        if node_translator_function is not None:
            self.function.add_environment(
                "NODE_TRANSLATOR_FUNCTION_NAME",
                node_translator_function.function_name,
            )
            node_translator_function.grant_invoke(self.function)

        if expression_translator_function is not None:
            self.function.add_environment(
                "EXPRESSION_TRANSLATOR_FUNCTION_NAME",
                expression_translator_function.function_name,
            )
            expression_translator_function.grant_invoke(self.function)
