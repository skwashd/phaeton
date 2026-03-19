# Create Spec Registry Stack

**Priority:** P1
**Effort:** M
**Gap Analysis Ref:** Item #16

## Overview

The spec-registry component (TASK-0006) needs a CDK deployment stack. The stack provisions: a KMS-encrypted S3 bucket for API spec files, a Lambda handler for index rebuilding, and an S3 event notification that triggers the Lambda when `.json` or `.yaml` files are uploaded.

## Dependencies

- **Blocked by:** TASK-0006 (spec-registry package must exist for code asset)
- **Blocks:** TASK-0017 (app.py wiring), TASK-0019 (Lambda code asset exclusions)

## Acceptance Criteria

1. `spec_registry_stack.py` exists and defines a `SpecRegistryStack`.
2. S3 bucket is created with KMS encryption and versioning enabled.
3. Lambda function is created with appropriate runtime, memory, and timeout.
4. S3 event notification triggers Lambda on `s3:ObjectCreated` for `.json` and `.yaml` suffixes.
5. Lambda has read/write permissions on the S3 bucket.
6. The stack exposes the bucket and function as properties (for cross-stack references if needed).
7. No CDK alpha constructs are used.
8. `uv run pytest` passes in `deployment/`.
9. `uv run ruff check` passes in `deployment/`.

## Implementation Details

### Files to Modify

- `deployment/stacks/spec_registry_stack.py` (new)

### Technical Approach

1. **Create the stack:**
   ```python
   class SpecRegistryStack(cdk.Stack):
       def __init__(self, scope, construct_id, **kwargs):
           super().__init__(scope, construct_id, **kwargs)

           # KMS key for bucket encryption
           key = kms.Key(self, "SpecBucketKey", ...)

           # S3 bucket for spec files
           self.bucket = s3.Bucket(
               self, "SpecBucket",
               bucket_name="phaeton-spec-registry",
               encryption=s3.BucketEncryption.KMS,
               encryption_key=key,
               versioned=True,
               removal_policy=cdk.RemovalPolicy.RETAIN,
           )

           # Lambda for index rebuilding
           self.function = lambda_.Function(
               self, "IndexerFunction",
               function_name="phaeton-spec-indexer",
               runtime=lambda_.Runtime.PYTHON_3_13,
               architecture=lambda_.Architecture.ARM_64,
               handler="spec_registry.handler.handler",
               code=lambda_.Code.from_asset("../spec-registry/src"),
               environment={
                   "SPEC_BUCKET_NAME": self.bucket.bucket_name,
               },
           )

           # Grant read/write
           self.bucket.grant_read_write(self.function)

           # S3 event notification
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
   ```

2. Follow existing stack patterns for consistent configuration (tags, removal policies, etc.).

### Testing Requirements

- CDK synthesis test should verify the stack produces valid CloudFormation.
- Verify S3 bucket has KMS encryption.
- Verify Lambda has correct permissions.
- Verify S3 event notifications are configured for `.json` and `.yaml` suffixes.
