"""CDK stack for the Packager service."""

from __future__ import annotations

from typing import Any

import aws_cdk as cdk
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from constructs import Construct


class PackagerStack(cdk.Stack):
    """Deploy the Packager Lambda with S3 output bucket."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init__(scope, construct_id, **kwargs)

        output_bucket = s3.Bucket(
            self,
            "OutputBucket",
            removal_policy=cdk.RemovalPolicy.RETAIN,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )

        self.function = lambda_.Function(
            self,
            "Function",
            function_name="phaeton-packager",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler="n8n_to_sfn_packager.handler.handler",
            code=lambda_.Code.from_asset(
                "../packager/src",
                exclude=["*/cli.py", "*/__main__.py"],
            ),
            memory_size=1024,
            timeout=cdk.Duration.seconds(300),
            ephemeral_storage_size=cdk.Size.gibibytes(1),
            environment={
                "OUTPUT_BUCKET": output_bucket.bucket_name,
            },
        )

        output_bucket.grant_read_write(self.function)
