"""CDK stack for the n8n Release Parser service."""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from constructs import Construct


class ReleaseParserStack(cdk.Stack):
    """Deploy the Release Parser Lambda with S3 catalog bucket and daily schedule."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:  # noqa: ANN003
        super().__init__(scope, construct_id, **kwargs)

        catalog_bucket = s3.Bucket(
            self,
            "CatalogBucket",
            removal_policy=cdk.RemovalPolicy.RETAIN,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )

        self.function = lambda_.Function(
            self,
            "Function",
            function_name="phaeton-release-parser",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler="n8n_release_parser.handler.handler",
            code=lambda_.Code.from_asset("../n8n-release-parser/src"),
            memory_size=512,
            timeout=cdk.Duration.seconds(120),
            environment={
                "CATALOG_BUCKET": catalog_bucket.bucket_name,
            },
        )

        catalog_bucket.grant_read_write(self.function)

        rule = events.Rule(
            self,
            "DailySchedule",
            schedule=events.Schedule.rate(cdk.Duration.days(1)),
        )
        rule.add_target(targets.LambdaFunction(self.function))
