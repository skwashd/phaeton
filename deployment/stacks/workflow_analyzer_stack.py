"""CDK stack for the Workflow Analyzer service."""

from __future__ import annotations

from typing import Any

import aws_cdk as cdk
from aws_cdk import aws_lambda as lambda_
from constructs import Construct


class WorkflowAnalyzerStack(cdk.Stack):
    """Deploy the Workflow Analyzer Lambda."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init__(scope, construct_id, **kwargs)

        self.function = lambda_.Function(
            self,
            "Function",
            function_name="phaeton-workflow-analyzer",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler="workflow_analyzer.handler.handler",
            code=lambda_.Code.from_asset("../workflow-analyzer/src"),
            memory_size=512,
            timeout=cdk.Duration.seconds(120),
        )
