"""CDK stack for the Spec Registry service."""

from __future__ import annotations

from typing import Any

import aws_cdk as cdk
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_notifications as s3n
from constructs import Construct


class SpecRegistryStack(cdk.Stack):
    """Deploy the Spec Registry Lambda with KMS-encrypted S3 bucket and event notifications."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init__(scope, construct_id, **kwargs)

        encryption_key = kms.Key(
            self,
            "SpecBucketKey",
            enable_key_rotation=True,
        )

        self.bucket = s3.Bucket(
            self,
            "SpecBucket",
            bucket_name="phaeton-spec-registry",
            encryption=s3.BucketEncryption.KMS,
            encryption_key=encryption_key,
            versioned=True,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        self.function = lambda_.Function(
            self,
            "Function",
            function_name="phaeton-spec-indexer",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler="spec_registry.handler.handler",
            code=lambda_.Code.from_asset(
                "../spec-registry/src",
                exclude=["*/cli.py", "*/__main__.py"],
            ),
            memory_size=512,
            timeout=cdk.Duration.seconds(120),
            environment={
                "SPEC_BUCKET_NAME": self.bucket.bucket_name,
            },
        )

        self.bucket.grant_read_write(self.function)

        self.bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(self.function),
            s3.NotificationKeyFilter(suffix=".json"),
        )
        self.bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(self.function),
            s3.NotificationKeyFilter(suffix=".yaml"),
        )
